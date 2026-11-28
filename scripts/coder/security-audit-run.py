#!/usr/bin/env python3
"""Private, source-only daily audit state. No network, upload or target execution."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
from zoneinfo import ZoneInfo

PIN = "c1c8a8c1471069fb0e188eeaff69b8e8db6564a8"
REPOS = {
    "nabla-compose": ["apps", "scripts", "terraform", "infrastructure"],
    "fastapi-sample": ["nabla", "scripts", "tests"],
    "nabla-site-alban": ["app", "lib", "scripts", "next.config.ts", "vercel.json"],
    "nabla-site-bababou": ["app", "lib", "scripts", "next.config.ts", "vercel.json"],
}
# Reviewed vendored Cloudflare revision. Never execute unpinned validators.
HASHES = {
    "SKILL.md": "5e3e96a1e438d8f35fef0a1e38f02d4f00e2bdf910401b7dfe00e6779c6dac85",
    "RECONNAISSANCE.md": "02ca887aca84de8ae137f1891bd2f0a54f28d3fa6da92a27f54734382b3381a2",
    "HUNTING.md": "71c121decea1322c47c718f6e110f1a892980bb4266bd7ac55ef043a213ade09",
    "ATTACK-CLASSES.md": "3ee4f00c6e8c9dcf6dd02dd5ac2a4ceb322e2085f3e9fbe79cf0c6330bc7ef83",
    "VALIDATION-AND-REPORTING.md": "b892470cb89bb31f33403e050d4bdfbe2cdaef940ade1496fa65e32b2e129449",
    "validate-findings.cjs": "e85f232e36bfac0f866f244da50376692d6b45c690beadcb00608b0e6c8b5283",
    "validate-coverage-ledger.cjs": "2eb280bd2e33c002916f86db9b29f9edfedb6454e5db973c766290465b868ac8",
    "report-schema.json": "6575c9de4a62255699ea052ebf9a49ebfb373a32891bcd89af6f55cc84b35519",
}
FILES = ("architecture.md", "coverage-ledger.json", "findings.json", "REPORT.md",
         "FINDINGS-DETAIL.md", "NEEDS-VALIDATION.md")
MAX = 2 * 1024 * 1024
REASON = "independent verification and OS-enforced target execution unavailable in coder"


def today():
    return dt.datetime.now(ZoneInfo("Europe/Paris")).date()


def selected(day):
    return tuple(REPOS)[day.toordinal() % len(REPOS)]


def private_dir(path, create=False):
    if create:
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            pass
    s = path.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.getuid() or s.st_mode & 0o077:
        raise ValueError("unsafe private directory")
    return path


def read_file(path, private=True):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        s = os.fstat(f.fileno())
        if (not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or s.st_size > MAX
                or (private and (s.st_uid != os.getuid() or s.st_mode & 0o077))):
            raise ValueError("unsafe or oversized file")
        data = f.read(MAX + 1)
        if len(data) != s.st_size or os.fstat(f.fileno()).st_mtime_ns != s.st_mtime_ns:
            raise ValueError("file changed")
        return data


def write_json(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "w") as f:
        json.dump(value, f, indent=2)
        f.write("\n")


def checked_skill(path):
    data = {name: read_file(path / name, private=False) for name in HASHES}
    if any(hashlib.sha256(data[k]).hexdigest() != v for k, v in HASHES.items()):
        raise ValueError("Cloudflare skill pin mismatch")
    return data


def git(target, *args):
    return subprocess.run(["git", "-C", str(target), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          text=True, timeout=30).stdout.strip()


def prepare(root, day, target, skill):
    repo = selected(day)
    checked_skill(skill)
    if git(target, "remote", "get-url", "origin") != f"https://github.com/AlbanAndrieu/{repo}.git":
        raise ValueError("wrong target origin")
    sha = git(target, "rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", sha) or git(target, "status", "--porcelain"):
        raise ValueError("target must be a clean git checkout")
    repo_root = private_dir(private_dir(root, True) / repo, True)
    prior = []
    prior_invalid_count = 0
    for old in sorted(repo_root.glob("run-*")):
        private_dir(old)
        if (old / "summary.json").exists():
            try:
                meta = json.loads(read_file(old / "run-metadata.json"))
                summary = json.loads(read_file(old / "summary.json"))
                expected = json.loads(read_file(old / "manifest.json"))
                actual = {f: hashlib.sha256(read_file(old / f)).hexdigest()
                          for f in (*FILES, "run-metadata.json")}
                if (expected != actual or summary.get("validators") != "PASS"
                        or summary.get("source_ref") != meta.get("source_ref")):
                    raise ValueError("prior receipt mismatch")
                if meta.get("skill_ref") == PIN and meta.get("repo") == f"AlbanAndrieu/{repo}":
                    prior.append(str(old))
            except (OSError, ValueError, TypeError, AttributeError):
                prior_invalid_count += 1
    scopes = [p for p in REPOS[repo] if (target / p).exists()]
    if not scopes:
        raise ValueError("no approved scope present")
    historical = []
    if repo == "nabla-compose":
        for name in ("2026-10-01-cloudflare-security-audit", "2026-10-04-cloudflare-security-audit"):
            old = target.resolve() / "docs/security-audits" / name
            if all((old / f).is_file() for f in ("coverage-ledger.json", "findings.json", "run-metadata.json")):
                historical.append(str(old))
    run = repo_root / f"run-{day.isoformat()}"
    # One claim per repository/date, even if the job times out. No overwrite.
    run.mkdir(mode=0o700)
    write_json(run / "run-metadata.json", {
        "run_id": run.name, "repo": f"AlbanAndrieu/{repo}", "target": str(target.resolve()),
        "source_ref": sha, "source_state": "clean", "skill_ref": PIN,
        "profile": "quick", "scope_paths": scopes, "budget": None,
        "execution_policy": "sandboxed-source-and-local-only",
        "selected_companion_files": [],
        "prior_run_paths": prior, "prior_invalid_count": prior_invalid_count,
        "historical_source_paths": historical, "shared_file_owners": {"parent": "openclaw-coder"},
        "run_status": "incomplete", "incomplete_reason": REASON,
        "mode": "partial_source_review", "target_execution": "NOT_RUN",
        "independent_verification": "NOT_RUN",
    })
    return {"run": str(run), "repo": repo, "source_ref": sha, "scope_paths": scopes,
            "prior_run_paths": prior, "prior_invalid_count": prior_invalid_count,
            "historical_source_paths": historical, "run_status": "incomplete"}


def finish(root, day, skill):
    repo = selected(day)
    run = private_dir(private_dir(private_dir(root) / repo) / f"run-{day.isoformat()}")
    if (run / "summary.json").exists():
        raise ValueError("run already sealed")
    meta = json.loads(read_file(run / "run-metadata.json"))
    if (meta.get("repo") != f"AlbanAndrieu/{repo}" or meta.get("skill_ref") != PIN
            or meta.get("run_status") != "incomplete"
            or not re.fullmatch(r"[0-9a-f]{40}", meta.get("source_ref", ""))):
        raise ValueError("invalid run metadata")
    checkout = Path(meta["target"])
    if (git(checkout, "remote", "get-url", "origin") != f"https://github.com/AlbanAndrieu/{repo}.git"
            or git(checkout, "rev-parse", "HEAD") != meta["source_ref"]
            or git(checkout, "status", "--porcelain")):
        raise ValueError("source changed during review")
    files = {name: read_file(run / name) for name in FILES}
    findings = json.loads(files["findings.json"])
    ledger = json.loads(files["coverage-ledger.json"])
    if findings != [] or not isinstance(ledger, list) or not 1 <= len(ledger) <= 6:
        raise ValueError("independent verifier absent: findings must be empty and coverage recorded")
    for unit in ledger:
        if not isinstance(unit, dict) or unit.get("status") == "planned":
            raise ValueError("unresolved planned coverage must be explicitly deferred")
        if unit.get("status") == "candidate" and not unit.get("unresolved"):
            raise ValueError("candidate must retain its verification blocker")
        for check in unit.get("local_checks", []):
            if check.get("method") != "source" or check.get("artifact") is not None:
                raise ValueError("target execution is forbidden")
    trusted = checked_skill(skill)
    node = shutil.which("node")
    if node is None:
        raise ValueError("trusted Node unavailable")
    # Run only hash-pinned standalone Cloudflare validators on bounded copies.
    # Their stdout/stderr may quote private data, so never relay either.
    with tempfile.TemporaryDirectory(prefix="validation-", dir=run) as tmp:
        tmp = Path(tmp)
        for name in ("validate-findings.cjs", "validate-coverage-ledger.cjs", "report-schema.json"):
            (tmp / name).write_bytes(trusted[name])
        for validator, name in (("validate-findings.cjs", "findings.json"),
                                ("validate-coverage-ledger.cjs", "coverage-ledger.json")):
            (tmp / name).write_bytes(files[name])
            subprocess.run([node, str(tmp / validator), str(tmp / name)], check=True,
                           env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(tmp)},
                           cwd=tmp, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=30)
    summary = {"schema": "nabla-security-audit-summary/v1", "date": day.isoformat(),
               "repo": repo, "source_ref": meta["source_ref"], "skill_ref": PIN,
               "run_status": "incomplete", "independent_verification": "NOT_RUN",
               "validators": "PASS", "coverage_units": len(ledger),
               "candidate_units": sum(u["status"] == "candidate" for u in ledger),
               "deferred_units": sum(u["status"] in ("deferred", "blocked") for u in ledger),
               "reused_units": sum(u.get("prior_status") == "prior_covered_same_source" for u in ledger),
               "confirmed_findings": 0}
    # Receipt permits corruption detection before future reuse; not a signature.
    write_json(run / "manifest.json", {
        f: hashlib.sha256(data).hexdigest()
        for f, data in {**files, "run-metadata.json": read_file(run / "run-metadata.json")}.items()
    })
    write_json(run / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("plan", "prepare", "finish"))
    parser.add_argument("--day", type=dt.date.fromisoformat, default=today())
    parser.add_argument("--target", type=Path)
    parser.add_argument("--skill", type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    root = Path.home() / "security-audit-skill"
    try:
        if args.action == "plan":
            result = {"repo": selected(args.day), "date": args.day.isoformat()}
        elif args.action == "prepare" and args.target and args.skill:
            result = prepare(root, args.day, args.target, args.skill)
        elif args.action == "finish" and args.skill:
            result = finish(root, args.day, args.skill)
        else:
            parser.error("target and/or skill missing")
        print(json.dumps(result))
    except (ValueError, OSError, subprocess.SubprocessError, KeyError, TypeError):
        # Do not relay arbitrary private paths, subprocess output or raw exception data.
        print('{"run_status":"incomplete","error":"AUDIT_STATE_OR_VALIDATION_FAILED"}')
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
