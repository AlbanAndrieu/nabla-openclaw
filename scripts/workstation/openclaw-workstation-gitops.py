#!/usr/bin/env python3
"""Project this repository's configuration onto the Workstation OpenClaw Gateway.

  plan             read-only report of every component (exit 0)
  check            same report, exit 0 only when every component is aligned
  apply-heartbeat  explicit: HEARTBEAT.md and MORNING_BRIEFING.md
  apply-digest     explicit: message of the existing digest job

All commands run on the OpenClaw Workstation only. Applies refuse uncommitted
configuration and, unless --allow-unmerged, a HEAD that is not contained in
the locally fetched origin/master (reviewed configuration). Components run as
their own scripts, so their output and exit codes match a manual run. No
Gateway restart, model request or job creation.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from openclaw_runtime import ROOT, detect_host  # noqa: E402

CONFIG_PATHS = ("policies", "deploy/workstation", "scripts/workstation")
REVIEWED_REF = "origin/master"
COMPONENTS = (
    ("runtime_alignment", ("check-openclaw-runtime-alignment.py",)),
    ("heartbeat", ("openclaw-heartbeat-gitops.py", "--check")),
    ("morning_briefing", ("openclaw-heartbeat-gitops.py", "--briefing-check")),
    ("digest_cron", ("reconcile-openclaw-digest-cron.py", "--check")),
)
APPLY_STEPS = {
    "apply-heartbeat": lambda args: (("openclaw-heartbeat-gitops.py", "--apply"),
                                     ("openclaw-heartbeat-gitops.py", "--briefing-apply")),
    "apply-digest": lambda args: (("reconcile-openclaw-digest-cron.py", "--apply",
                                   "--expected-message-sha", args.expected_message_sha),),
}


def run_script(step: tuple[str, ...]) -> int:
    """Run a sibling script with this interpreter; its output passes through."""
    sys.stdout.flush()
    return subprocess.run([sys.executable, str(HERE / step[0]), *step[1:]],
                          check=False).returncode


def git(*args: str) -> tuple[int, str]:
    try:
        result = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True,
                                text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""
    return result.returncode, result.stdout.strip()


@dataclass(frozen=True)
class ConfigSource:
    head: str          # short SHA, or "unknown"
    uncommitted: int   # changed config paths, -1 when unknown
    reviewed: bool     # HEAD is contained in REVIEWED_REF

    def line(self) -> str:
        return (f"config_source=nabla-openclaw@{self.head} "
                f"uncommitted_config_paths={self.uncommitted} "
                f"reviewed={str(self.reviewed).lower()}")

    def apply_refusal(self, allow_unmerged: bool) -> str | None:
        if self.uncommitted != 0:
            return "uncommitted or unknown config; commit and review before applying"
        if not self.reviewed and not allow_unmerged:
            return (f"HEAD is not in {REVIEWED_REF}; merge then git pull --ff-only, "
                    "or pass --allow-unmerged deliberately")
        return None


def config_source(git_runner=git) -> ConfigSource:
    rc, head = git_runner("rev-parse", "--short=12", "HEAD")
    if rc != 0 or not head:
        return ConfigSource("unknown", -1, False)
    rc, status = git_runner("status", "--porcelain", "--", *CONFIG_PATHS)
    uncommitted = len(status.splitlines()) if rc == 0 else -1
    rc, _ = git_runner("merge-base", "--is-ancestor", "HEAD", REVIEWED_REF)
    return ConfigSource(head, uncommitted, rc == 0)


def report(runner) -> bool:
    results = {name: runner(step) for name, step in COMPONENTS}
    for name, rc in results.items():
        print(f"workstation_{name}=" + ("aligned" if rc == 0 else "not_aligned"))
    aligned = all(rc == 0 for rc in results.values())
    print("workstation_gitops=" + ("aligned" if aligned else "not_aligned"))
    return aligned


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__,
                                   formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("plan")
    commands.add_parser("check")
    for name in APPLY_STEPS:
        command = commands.add_parser(name)
        command.add_argument("--allow-unmerged", action="store_true")
        if name == "apply-digest":
            command.add_argument("--expected-message-sha", required=True)
    return root


def main(argv=None, host=detect_host, git_runner=git, runner=run_script) -> int:
    args = parser().parse_args(argv)
    if host() != "workstation":
        print("STOP: not the OpenClaw Workstation (host_context != workstation)",
              file=sys.stderr)
        return 2
    source = config_source(git_runner)
    print(source.line(), flush=True)
    if args.command in ("plan", "check"):
        aligned = report(runner)
        return 0 if args.command == "plan" or aligned else 2
    refusal = source.apply_refusal(args.allow_unmerged)
    if refusal:
        print("STOP: " + refusal, file=sys.stderr)
        return 2
    for step in APPLY_STEPS[args.command](args):
        if runner(step) != 0:
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
