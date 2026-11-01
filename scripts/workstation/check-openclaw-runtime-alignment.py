#!/usr/bin/env python3
"""Read-only, fail-closed alignment gate for managed OpenClaw on workstation.

No package installation, service restart, credential access, model request or
configuration mutation. Intended for explicit pre-upgrade/reboot checks and as
the Gateway ``ExecStartPre``. Diagnostics are value-free: versions and reason
codes only, never paths, environment or file contents.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from openclaw_runtime import (  # noqa: E402
    ROOT, UNIT, VERSION, Contract, ContractError, load_contract,
)

OPENCLAW_VERSION = re.compile(r'^OpenClaw\s+(\d+\.\d+\.\d+)(?:\s|$)', re.M)
SYSTEMD_NODE = re.compile(r'/installs/node/(\d+\.\d+\.\d+)/bin/node')
MAX_LISTED_VERSIONS = 20


def invoke(argv: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(argv, capture_output=True, check=False, timeout=8,
                                env={**os.environ, 'NODE_NO_WARNINGS': '1'})
    except (OSError, subprocess.TimeoutExpired):
        return 127, ''
    return result.returncode, result.stdout[:32768].decode('utf-8', 'replace')


def systemd_node_version(unit: str) -> str:
    """Version of the mise Node used by the unit, or why it is unknown."""
    if not unit:
        return 'unavailable'
    versions = set(SYSTEMD_NODE.findall(unit))
    if len(versions) == 1:
        return versions.pop()
    return 'ambiguous' if versions else 'not_mise_managed'


def installed_node_versions(home: Path) -> list[str]:
    try:
        names = [p.name for p in (home / '.local/share/mise/installs/node').iterdir()]
    except OSError:
        return []
    return sorted(n for n in names if VERSION.fullmatch(n))[:MAX_LISTED_VERSIONS]


def hint(files: dict, contract: Contract, systemd: str, installed: list[str]) -> str | None:
    """One stable remediation code; never a command that the gate would run itself."""
    reasons = set(files.values()) - {'ok'}
    if not reasons:
        return None
    if 'absent' in reasons:
        if VERSION.fullmatch(systemd) and systemd != contract.node_version:
            return 'systemd_uses_other_node_update_contract_by_pr'
        if contract.node_version not in installed:
            return 'pinned_node_not_installed'
        return 'openclaw_not_installed_for_pinned_node'
    if reasons & {'writable_by_group', 'writable_by_others'}:
        return 'remove_group_and_other_write_on_install'
    if 'foreign_owner' in reasons:
        return 'install_not_owned_by_gateway_user'
    if reasons & {'symlink', 'hardlinked', 'not_regular'}:
        return 'replace_links_with_regular_files'
    return 'inspect_install'


def classify(contract: Contract, home: Path, runner=invoke) -> dict:
    install = contract.install(home)
    files = install.safety()
    rc, unit = runner(['systemctl', '--user', 'show', UNIT, '-p', 'ExecStart', '--value'])
    unit = unit if rc == 0 else ''
    systemd = systemd_node_version(unit)
    report = {
        'checks': {'node_binary': 'unverified', 'openclaw_package': 'unverified',
                   'systemd_exec': 'unverified'},
        'expected': {'node': contract.node_version, 'openclaw': contract.openclaw_version},
        'files': files,
        'systemd_node_version': systemd,
    }
    checks = report['checks']
    if any(state != 'ok' for state in files.values()):
        checks['node_binary'] = 'unsafe_or_absent'
        installed = installed_node_versions(home)
        report['installed_node_versions'] = installed
        report['hint'] = hint(files, contract, systemd, installed)
        return report
    rc, result = runner([str(install.node), '--version'])
    checks['node_binary'] = 'match' if rc == 0 and result.strip() == 'v' + contract.node_version else 'mismatch'
    try:
        pkg = json.loads(install.manifest.read_text(encoding='utf-8'))
        valid = (pkg.get('name') == 'openclaw' and pkg.get('version') == contract.openclaw_version
                 and pkg.get('bin', {}).get('openclaw') == 'openclaw.mjs')
    except (ValueError, OSError, AttributeError, TypeError):
        valid = False
    if valid:
        rc, actual = runner([str(install.node), str(install.entry), '--version'])
        match = OPENCLAW_VERSION.search(actual)
        valid = rc == 0 and match is not None and match.group(1) == contract.openclaw_version
    checks['openclaw_package'] = 'match' if valid else 'mismatch'
    # The effective service may repeat the same Node path in path= and argv[].
    nodes = re.findall(r'/[^\s;{}"\']+/bin/node', unit)
    entries = re.findall(r'/[^\s;{}"\']+/lib/node_modules/openclaw/openclaw\.mjs', unit)
    checks['systemd_exec'] = ('match' if nodes and set(nodes) == {str(install.node)}
                              and entries == [str(install.entry)]
                              and 'gateway --port 18789' in unit else 'mismatch_or_unavailable')
    return report


def main(argv=None, repo: Path = ROOT, home: Path | None = None, runner=invoke) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    try:
        report = classify(load_contract(repo), home if home is not None else Path.home(), runner)
        state = 'PASS' if all(v == 'match' for v in report['checks'].values()) else 'BLOCKED'
    except ContractError as exc:
        report, state = {'checks': {}, 'contract': str(exc)}, 'UNVERIFIED'
    except (OSError, ValueError, KeyError, TypeError):
        report, state = {'checks': {}}, 'UNVERIFIED'
    print(json.dumps({'alignment': state, **report, 'mutations': 0, 'model_requests': 0},
                     sort_keys=True))
    return 0 if state == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
