#!/usr/bin/env python3
"""Workstation OpenClaw runtime contract, host detection and pinned CLI reads.

``deploy/workstation/runtime-contract.json`` is the single Node/OpenClaw pin.
Never reads secrets, never searches PATH for the CLI and never prints prompts.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess

from private_files import file_safety

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = "deploy/workstation/runtime-contract.json"
SCHEMA = "openclaw-workstation-runtime/v1"
UNIT = "openclaw-gateway.service"
PORT = 18789
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
UNVERIFIED = "__unverified_openclaw_runtime__"
MAX_JSON = 1024 * 1024

DIGEST_JOB_ID = "7ed5dd9a-da30-479f-b0eb-4cc494fb4966"
DIGEST_JOB_NAME = "daily-tech-news-digest"


class ContractError(ValueError):
    """Stable reason code for an unusable runtime contract."""


@dataclass(frozen=True)
class Install:
    """Pinned mise-managed Node and OpenClaw files for one Node version."""
    node: Path
    entry: Path
    manifest: Path

    @classmethod
    def for_version(cls, version: str, home: Path | None = None) -> "Install":
        root = (home if home is not None else Path.home()) / ".local/share/mise/installs/node" / version
        entry = root / "lib/node_modules/openclaw/openclaw.mjs"
        return cls(root / "bin/node", entry, entry.parent / "package.json")

    def safety(self) -> dict[str, str]:
        return {"node": file_safety(self.node), "openclaw_mjs": file_safety(self.entry),
                "package_json": file_safety(self.manifest)}


@dataclass(frozen=True)
class Contract:
    node_version: str
    openclaw_version: str

    def install(self, home: Path | None = None) -> Install:
        return Install.for_version(self.node_version, home)


def load_contract(repo: Path = ROOT) -> Contract:
    try:
        data = json.loads((repo / CONTRACT).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise ContractError("unreadable_contract") from None
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise ContractError("unexpected_contract_schema")
    node = data.get("node_version")
    if not isinstance(node, str) or not VERSION.fullmatch(node):
        raise ContractError("invalid_node_pin")
    release = data.get("openclaw_version")
    if not isinstance(release, str) or not VERSION.fullmatch(release):
        raise ContractError("pin_mismatch")
    if data.get("systemd_unit") != UNIT or data.get("port") != PORT:
        raise ContractError("unexpected_service_contract")
    return Contract(node, release)


def pinned_cli_paths(repo: Path = ROOT, home: Path | None = None) -> tuple[Path, Path]:
    """Fail closed: on any contract problem return deliberately unusable paths."""
    try:
        install = load_contract(repo).install(home)
    except ContractError:
        install = Install.for_version(UNVERIFIED, home)
    return install.node, install.entry


def run_text(argv: list[str], timeout: float = 4) -> str:
    """Stripped stdout of a successful command, or "" (no shell, no raise)."""
    try:
        result = subprocess.run(argv, capture_output=True, text=True,
                                timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def detect_host(home: Path | None = None, runner=run_text) -> str:
    """``truenas``, ``workstation`` or ``unknown``; generic Linux is not a workstation."""
    version = runner(["midclt", "call", "system.version"])
    if version.startswith(("TrueNAS-", '"TrueNAS-')):
        return "truenas"
    config = (home if home is not None else Path.home()) / ".openclaw/openclaw.json"
    load_state = runner(["systemctl", "--user", "show", UNIT, "-p", "LoadState", "--value"])
    if config.is_file() and load_state in ("loaded", "masked"):
        return "workstation"
    return "unknown"


def decode_job(raw: bytes) -> dict | None:
    if not raw or len(raw) > MAX_JSON:
        return None
    try:
        value = json.loads(raw)
    except (UnicodeError, ValueError):
        return None
    if not isinstance(value, dict):
        return None
    job = value.get("job", value)
    return job if isinstance(job, dict) else None


def read_cron_job(job_id: str = DIGEST_JOB_ID, node: Path | None = None,
                  cli: Path | None = None) -> tuple[str, dict | None]:
    """Read one job through the pinned CLI; state names are stable output values."""
    if node is None or cli is None:
        node, cli = pinned_cli_paths()
    if file_safety(node) != "ok" or file_safety(cli) != "ok":
        return "unverified_installation", None
    try:
        result = subprocess.run(
            [str(node), str(cli), "cron", "get", job_id],
            capture_output=True, check=False, timeout=25,
            env={**os.environ, "NODE_NO_WARNINGS": "1"},
        )
    except (OSError, subprocess.TimeoutExpired):
        return "cli_unavailable", None
    if result.returncode:
        return "cli_failed", None
    job = decode_job(result.stdout)
    return ("structured" if job is not None else "invalid_report"), job


def install_issues(repo: Path = ROOT, home: Path | None = None) -> str:
    """Comma-separated non-ok file reasons of the pinned install (value-free)."""
    try:
        install = load_contract(repo).install(home)
    except ContractError as exc:
        return str(exc)
    issues = [f"{name}:{state}" for name, state in install.safety().items() if state != "ok"]
    return ",".join(issues) or "none"
