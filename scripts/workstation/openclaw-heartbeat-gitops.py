#!/usr/bin/env python3
"""Explicit and secure GitOps deployment for workstation heartbeat policy.

Exit codes: 0 matching/applied, 2 drift (``--check``) or refused operation.
Outputs only SHA-256 digests and stable reason codes, never file contents.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import errno
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from private_files import (  # noqa: E402
    atomic_replace, create_private_file, ensure_private_dir, read_regular,
)

SOURCE = Path(__file__).resolve().parents[2] / "policies/HEARTBEAT.md"
BRIEFING_SOURCE = SOURCE.with_name("MORNING_BRIEFING.md")
TARGETS = ("HEARTBEAT.md", "MORNING_BRIEFING.md")
BACKUP_DIR = "backups/heartbeat-gitops"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def private_backup(home: Path, target: Path, current: bytes) -> Path:
    backup_dir = ensure_private_dir(home, BACKUP_DIR, strict_parents=False)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_dir / f"{target.stem}.{timestamp}.{digest(current)[:12]}.md"
    try:
        create_private_file(backup, current)
    except FileExistsError:
        # Same-second backup of unchanged bytes: retain existing snapshot.
        if read_regular(backup) != current:
            raise ValueError("backup_collision_different_content") from None
    return backup


def operate(action: str, home: Path, source: Path = SOURCE, *,
            target_name: str = "HEARTBEAT.md", create_missing: bool = False) -> str:
    source_bytes = read_regular(source)
    if target_name not in TARGETS:
        raise ValueError("unsupported_target_name")
    target = home / "workspace" / target_name
    if target.parent.is_symlink():
        raise ValueError("workspace_symlink_refused")
    current = read_regular(target, allow_missing=True)
    if action == "check":
        return ("matching" if current == source_bytes else "different") + (
            f" source_sha256={digest(source_bytes)}"
            + (f" target_sha256={digest(current)}" if current is not None else " target=absent")
        )
    if current is None and (not create_missing or action == "backup"):
        raise ValueError("current_heartbeat_missing_refuse_unsafe_replace")
    if action == "apply" and current == source_bytes:
        # Idempotent apply: no redundant backup or rewrite of identical bytes.
        return f"already_matching sha256={digest(source_bytes)}"
    backup = private_backup(home, target, current) if current is not None else None
    if action == "backup":
        return f"backup={backup} sha256={digest(current)}"
    atomic_replace(target, source_bytes, expected=current, allow_missing=create_missing)
    return (f"applied_sha256={digest(source_bytes)} "
            f"backup={backup if backup is not None else 'none_created_new_file'}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--backup", action="store_true")
    actions.add_argument("--apply", action="store_true")
    actions.add_argument("--briefing-check", action="store_true")
    actions.add_argument("--briefing-apply", action="store_true")
    parser.add_argument("--root", type=Path, default=Path.home() / ".openclaw")
    args = parser.parse_args(argv)
    action = "check" if args.check or args.briefing_check else "backup" if args.backup else "apply"
    briefing = args.briefing_check or args.briefing_apply
    try:
        if briefing:
            result = operate(action, args.root, BRIEFING_SOURCE,
                             target_name="MORNING_BRIEFING.md", create_missing=True)
        else:
            result = operate(action, args.root)
    except ValueError as exc:
        # Reason codes are fixed internal strings, safe to print.
        print(f"ERROR: {exc}; operation not completed", file=sys.stderr)
        return 2
    except OSError as exc:
        reason = errno.errorcode.get(exc.errno, type(exc).__name__)
        print(f"ERROR: {reason}; operation not completed", file=sys.stderr)
        return 2
    print(result)
    return 2 if result.startswith("different") else 0


if __name__ == "__main__":
    raise SystemExit(main())
