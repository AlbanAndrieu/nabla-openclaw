#!/usr/bin/env python3
"""Resolve pinned OpenClaw CLI without falling back to a stale Node install."""
from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = "deploy/workstation/runtime-contract.json"
NODE_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_UNVERIFIED = "__unverified_openclaw_runtime__"


def pinned_cli_paths(repo: Path = ROOT, home: Path | None = None) -> tuple[Path, Path]:
    """Never read secrets; return deliberately unusable paths on drift.

    The runtime contract of this repository is the single Node/OpenClaw pin
    (no duplicated mise.toml). The same policy is consulted by CLI
    diagnostics and by the pre-start alignment gate. No unpinned executable
    search through PATH is allowed.
    """
    target_home = home if home is not None else Path.home()
    version = _UNVERIFIED
    try:
        contract = json.loads((repo / CONTRACT).read_text(encoding="utf-8"))
        pinned = contract.get("node_version") if isinstance(contract, dict) else None
        if (
            isinstance(pinned, str)
            and NODE_VERSION.fullmatch(pinned)
            and contract.get("schema") == "openclaw-workstation-runtime/v1"
            and isinstance(contract.get("openclaw_version"), str)
            and NODE_VERSION.fullmatch(contract["openclaw_version"])
            and contract.get("systemd_unit") == "openclaw-gateway.service"
            and contract.get("port") == 18789
        ):
            version = pinned
    except (OSError, ValueError, KeyError, TypeError, UnicodeError):
        pass
    root = target_home / ".local/share/mise/installs/node" / version
    return root / "bin/node", root / "lib/node_modules/openclaw/openclaw.mjs"
