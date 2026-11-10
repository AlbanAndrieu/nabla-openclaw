#!/usr/bin/env python3
"""Offline structural preflight of the coder devbox and its Gateway agent.

Prints ``openclaw_devbox_contract=<status>`` (exit 0), where the status moves
prepared_not_deployed -> ready_to_deploy (base images pinned) -> active, or
``invalid`` (exit 2) and, on stderr, the name of every violated rule.
Reads repository files only: no Docker, SSH, network or secret access.
"""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "deploy/truenas/devbox/contract.json"
SEED = "deploy/truenas/openclaw.json"
GATEWAY_COMPOSE = "deploy/truenas/compose.yml"
REQUIREMENTS = "deploy/truenas/devbox/requirements.txt"
ALLOWLIST = "deploy/truenas/devbox/egress/allowed-domains.txt"
STATUSES = ("prepared_not_deployed", "ready_to_deploy", "active")
DOMAIN = re.compile(r"^\.?(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
# Tools the coder may run inside its sandbox; everything else stays denied.
SANDBOX_TOOLS = {"exec", "process", "read", "ls", "write", "edit", "apply_patch", "view_image", "session_status"}
REQUIRED_DENIES = {"group:automation", "group:nodes", "group:ui", "group:web", "sessions_send", "sessions_spawn"}
SSHD_LINES = ("Port 2222", "UsePAM no", "AllowUsers coder", "PermitRootLogin no", "PasswordAuthentication no",
              "KbdInteractiveAuthentication no", "DisableForwarding yes", "PermitUserEnvironment no",
              "AuthorizedKeysFile /etc/openclaw-devbox/authorized_keys")


def text(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise KeyError(relative)
    return path.read_text(encoding="utf-8")


def service_blocks(compose):
    """Split the `services:` section of a Compose file into per-service text."""
    section = compose.split("\nservices:\n", 1)[1]
    section = re.split(r"\n(?=[a-z])", section, maxsplit=1)[0]
    names = re.findall(r"^  ([a-z0-9-]+):$", section, flags=re.M)
    parts = re.split(r"^  [a-z0-9-]+:$", section, flags=re.M)[1:]
    return dict(zip(names, parts))


def compose_hardened(c, seed, root):
    compose = text(root, c["compose"])
    services = service_blocks(compose)
    if set(services) != {"openclaw-devbox", "openclaw-devbox-egress"}:
        return False
    for block in services.values():
        if any(token in block for token in ("ports:", "privileged", "docker.sock", "network_mode", "cap_add")):
            return False
        if not all(token in block for token in ("cap_drop: [ALL]", "no-new-privileges:true",
                                                 "read_only: true", "restart: unless-stopped", "pids_limit:")):
            return False
    devbox = services["openclaw-devbox"]
    return (f'user: "{c["uid_gid"]}"' in devbox
            and "    networks: [devbox]\n" in devbox
            and "    networks: [devbox, egress]\n" in services["openclaw-devbox-egress"]
            and "docker.sock" not in compose)


def network_internal(c, seed, root):
    compose = text(root, c["compose"])
    return (c["network"]["internal"] is True
            and f'  devbox:\n    name: {c["network"]["name"]}\n    internal: true\n' in compose)


def github_token_off_git(c, seed, root):
    path = c["github_token"]["file"]
    return (path.startswith("/mnt/cpool/secrets/runtime/openclaw-devbox/")
            and f"file: {path}" in text(root, c["compose"])
            and "no_workflows" in c["github_token"]["scope"])


def sshd_locked_down(c, seed, root):
    lines = {line.strip() for line in text(root, c["ssh"]["sshd_config"]).splitlines()}
    proxy = f'HTTPS_PROXY=http://{c["egress"]["proxy"]}'
    set_env = [line for line in lines if line.startswith("SetEnv ")]
    return (all(line in lines for line in SSHD_LINES)
            and len(set_env) == 1 and proxy in set_env[0]
            and not any(line.startswith(("AcceptEnv", "PermitOpen", "AllowTcpForwarding yes")) for line in lines))


def egress_allowlist(c, seed, root):
    """Squid: name-only allowlist file equal to the contract, every refusal before the single allow."""
    conf = [line.strip() for line in text(root, c["egress"]["squid_config"]).splitlines()
            if line.strip() and not line.strip().startswith("#")]
    domains = [line.strip() for line in text(root, ALLOWLIST).splitlines()
               if line.strip() and not line.strip().startswith("#")]
    access = [line for line in conf if line.startswith("http_access ")]
    allow = access.index("http_access allow allowed_domains")
    return ('acl allowed_domains dstdomain -n "/etc/squid/allowed-domains.txt"' in conf
            and domains == c["egress"]["allowed_domains"]
            and all(DOMAIN.fullmatch(domain) for domain in domains)
            and access[-1] == "http_access deny all" and allow == len(access) - 2
            and [line for line in access if line.startswith("http_access allow")] == [access[allow]]
            and all(rule in access[:allow] for rule in (
                "http_access deny !devbox_clients", "http_access deny !CONNECT", "http_access deny !https_port",
                "http_access deny ip_literal", "http_access deny private_destinations")))


def gateway_agent_sandboxed(c, seed, root):
    agent = seed["agents"]["entries"][c["agent"]]
    sandbox, ssh, tools = agent["sandbox"], agent["sandbox"]["ssh"], agent["tools"]
    provider = seed["models"]["providers"][c["model"]["provider"]]
    model_ref = f'{c["model"]["provider"]}/{c["model"]["model"]}'
    allow = set(tools["sandbox"]["tools"]["allow"])
    return (sandbox["mode"] == "all" and sandbox["backend"] == "ssh" and sandbox["scope"] == "session"
            and ssh["target"] == c["ssh"]["target"]
            and ssh["strictHostKeyChecking"] is True and ssh["updateHostKeys"] is False
            and ssh["identityFile"] == c["ssh"]["gateway_identity_file"]
            and ssh["knownHostsFile"] == c["ssh"]["gateway_known_hosts_file"]
            and tools["elevated"]["enabled"] is False and tools["fs"]["workspaceOnly"] is True
            and allow <= SANDBOX_TOOLS and REQUIRED_DENIES <= set(tools["deny"])
            and agent["model"] == model_ref and model_ref in seed["agents"]["defaults"]["modelPolicy"]["allow"]
            and provider["apiKey"] == {"source": "file", "provider": c["model"]["key_secret_provider"], "id": "value"}
            and seed["secrets"]["providers"][c["model"]["key_secret_provider"]] == {
                "source": "file", "path": c["model"]["key_file"], "mode": "singleValue"}
            and c["model"]["key_file"].startswith("/home/node/.openclaw/credentials/")
            and agent["skills"] == [c["workspace"]["skill"]]
            and seed["agents"]["defaults"].get("maxConcurrent", 0) >= 2)


def gateway_joins_network(c, seed, root):
    compose = text(root, GATEWAY_COMPOSE)
    return (c["network"]["gateway_joins"] is True
            and "    networks: [litellm, devbox]\n" in compose
            and f'  devbox:\n    external: true\n    name: {c["network"]["name"]}\n' in compose)


def workspace_sources_exist(c, seed, root):
    base = c["workspace"]["source"]
    skill = text(root, f'{base}/skills/{c["workspace"]["skill"]}/SKILL.md')
    return bool(text(root, f"{base}/AGENTS.md")) and f'\nname: {c["workspace"]["skill"]}\n' in skill


def images_pinned_when_active(c, seed, root):
    compose = text(root, c["compose"])
    pins = re.findall(r"^\s+(?:PYTHON|DEBIAN)_IMAGE: (\S+)$", compose, flags=re.M)
    requirements = text(root, REQUIREMENTS)
    hashed = "uv==" in requirements and "--hash=sha256:" in requirements
    pinned = len(pins) == 2 and all(re.search(r"@sha256:[0-9a-f]{64}$", pin) for pin in pins)
    if c["status"] not in STATUSES or c.get("status_flow") != list(STATUSES):
        return False
    return hashed and len(pins) == 2 and (pinned or c["status"] == "prepared_not_deployed")


RULES = (
    ("compose_hardened", compose_hardened),
    ("network_internal", network_internal),
    ("github_token_off_git", github_token_off_git),
    ("sshd_locked_down", sshd_locked_down),
    ("egress_allowlist_matches_contract", egress_allowlist),
    ("gateway_agent_sandboxed", gateway_agent_sandboxed),
    ("gateway_joins_devbox_network", gateway_joins_network),
    ("workspace_sources_exist", workspace_sources_exist),
    ("images_pinned_when_active", images_pinned_when_active),
)


def violations(root=ROOT):
    try:
        contract = json.loads(text(root, CONTRACT))
        seed = json.loads(text(root, SEED))
    except (KeyError, OSError, UnicodeError, ValueError):
        return ["contract_unreadable"]
    failed = []
    for name, rule in RULES:
        try:
            ok = rule(contract, seed, root)
        except (KeyError, TypeError, AttributeError, IndexError, ValueError):
            ok = False
        if not ok:
            failed.append(name)
    return failed


def main():
    failed = violations()
    status = "" if failed else json.loads(text(ROOT, CONTRACT))["status"]
    print("openclaw_devbox_contract=" + ("invalid" if failed else status))
    for name in failed:
        print("violation=" + name, file=sys.stderr)
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
