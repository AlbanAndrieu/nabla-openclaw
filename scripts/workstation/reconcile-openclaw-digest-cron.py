#!/usr/bin/env python3
"""Declarative digest cron reconciliation; no new jobs, secrets or inference."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from openclaw_runtime import (  # noqa: E402
    DIGEST_JOB_ID as JOB_ID, DIGEST_JOB_NAME as JOB_NAME, ROOT,
    detect_host, install_issues, pinned_cli_paths, read_cron_job,
)
from private_files import create_private_file, ensure_private_dir, file_safety  # noqa: E402

SOURCE = ROOT / "policies/cron/daily-tech-news-digest.message.md"
# Kept at the historical nabla-compose location so all digest snapshots stay together.
BACKUP_DIR = ".local/state/nabla-compose/openclaw/digest-gitops"
MAX_BYTES = 1024 * 1024
PRESERVED_FIELDS = ("schedule", "delivery", "agentId", "sessionTarget", "enabled")


def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def desired_message(path=SOURCE):
    meta = path.lstat()
    if (not stat.S_ISREG(meta.st_mode) or path.is_symlink()
            or meta.st_size > 16 * 1024 or meta.st_size == 0):
        raise ValueError("unsafe_source")
    message = path.read_text(encoding="utf-8").strip()
    if (message.count("- ITEMS_PER_SECTION = 5") != 1
            or "references/digest-prompt.md" not in message
            or re.search(r"(?i)(?:sk-[a-z0-9]{12,}|api[_-]?key\s*=|token\s*=)", message)):
        raise ValueError("invalid_versioned_message")
    return message


def runtime_job():
    """Return ``(read_state, job)``; ``job`` is None unless it is the expected digest."""
    state, job = read_cron_job(JOB_ID)
    if state != "structured" or not isinstance(job, dict):
        return state, None
    if job.get("id") != JOB_ID or job.get("name") != JOB_NAME:
        return "wrong_job", None
    payload = job.get("payload")
    if (not isinstance(payload, dict) or not isinstance(payload.get("message"), str)
            or payload.get("kind") not in ("agentTurn", None)):
        return "unexpected_payload", None
    return state, job


def host():
    return detect_host()


def cli_edit(message):
    node, entry = pinned_cli_paths()
    if file_safety(node) != "ok" or file_safety(entry) != "ok":
        return False
    # Only a versioned, public, secret-free message goes into process argv.
    # Never put an existing private job prompt on a command line.
    try:
        result = subprocess.run(
            [str(node), str(entry), "automations", "edit", JOB_ID, "--message", message],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=35, check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def backup(job):
    # Existing unsafe parents are refused, not re-permissioned.
    target = ensure_private_dir(Path.home(), BACKUP_DIR, strict_parents=True)
    raw = json.dumps(job, ensure_ascii=False, sort_keys=True).encode("utf-8")
    if len(raw) > MAX_BYTES:
        raise ValueError("snapshot_too_large")
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    create_private_file(target / f"digest-before-{now}.json", raw)
    return True


def preserved(old, new):
    def payload_without_message(job):
        return {k: v for k, v in job["payload"].items() if k != "message"}
    return (all(old.get(field) == new.get(field) for field in PRESERVED_FIELDS)
            and payload_without_message(old) == payload_without_message(new))


def apply(job, desired, expected_sha):
    """Guarded edit of the existing job; returns the final ``apply=`` status."""
    before = job["payload"]["message"]
    if not re.fullmatch("[0-9a-f]{64}", expected_sha):
        return "blocked_missing_expected_digest"
    if sha(before) != expected_sha:
        return "blocked_concurrent_drift"
    # Only migrate the known affected skill contract. A different private
    # message may contain custom instructions; do not overwrite it blindly.
    if (before.count("ITEMS_PER_SECTION = 3-5") != 1
            or "references/digest-prompt.md" not in before):
        return "blocked_unexpected_runtime_template_review_in_ui"
    state = job.get("state")
    if isinstance(state, dict) and state.get("runningAtMs"):
        return "blocked_running_job"
    _, current = runtime_job()
    if current is None or sha(current["payload"]["message"]) != expected_sha:
        return "blocked_concurrent_drift"
    try:
        backup(job)
    except (OSError, ValueError):
        return "blocked_private_backup"
    print("private_backup=created_0600")
    if not cli_edit(desired):
        return "cli_failed_no_runtime_proof"
    _, after = runtime_job()
    if after is None or after["payload"]["message"] != desired or not preserved(job, after):
        return "unverified_after_edit_review_snapshot_privately"
    return "verified_existing_job_updated"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    options = parser.add_mutually_exclusive_group()
    options.add_argument("--plan", action="store_true")
    options.add_argument("--check", action="store_true")
    options.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-message-sha", default="")
    args = parser.parse_args(argv)

    if host() != "workstation":
        print("⚠️  WRONG_HOST: cron GitOps applies only to OpenClaw Workstation")
        print("cron_gitops=not_applicable_or_unverified")
        return 2
    try:
        desired = desired_message()
    except (OSError, ValueError, UnicodeError):
        print("cron_gitops=invalid_source")
        return 2
    state, job = runtime_job()
    if job is None:
        print("cron_gitops=runtime_job_unverified")
        print("cron_job_read=" + state)
        if state == "unverified_installation":
            print("runtime_install=" + install_issues())
        return 2
    before = job["payload"]["message"]
    print("cron_gitops=existing_job_only")
    print("job_identity=verified")
    print("runtime_message_sha256=" + sha(before))
    print("desired_message_sha256=" + sha(desired))
    print("job_schedule_and_delivery=preserved_by_design")
    print("model_requests=0")
    if before == desired:
        print("cron_gitops=already_aligned")
        return 0
    print("cron_gitops=drift")
    if not args.apply:
        return 2 if args.check else 0
    status = apply(job, desired, args.expected_message_sha)
    print("apply=" + status)
    return 0 if status == "verified_existing_job_updated" else 2


if __name__ == "__main__":
    raise SystemExit(main())
