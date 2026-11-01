#!/usr/bin/env python3
"""Offline structural preflight, not a gateway deployment or readiness test.

Prints ``openclaw_target_contract=prepared_not_deployed`` (exit 0) or
``invalid`` (exit 2) and, on stderr, the name of every violated rule.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TARGET = "deploy/truenas/target-contract.json"
HEARTBEAT = "policies/heartbeat-restoration.policy.json"
CRON = "policies/cron/daily-tech-news-digest.policy.json"


def repo_file(root, relative):
    """True only for an existing file that stays inside the repository."""
    path = (root / relative).resolve()
    return path.is_relative_to(root.resolve()) and path.is_file()


def compose_matches(root, t):
    """The TrueNAS Compose pins the contract image, publishes on loopback only
    and keeps cron/heartbeat off while the no_auto_cron gate holds."""
    target = t["target"]
    if not repo_file(root, target["compose"]):
        return False
    text = (root / target["compose"]).read_text(encoding="utf-8")
    ports = [line.strip() for line in text.splitlines() if ":18789" in line and line.strip().startswith("- ")]
    return (f'image: {target["image"]}@{target["image_digest"]}' in text
            and ports == ['- "127.0.0.1:18789:18789"']
            and f'user: "{target["uid_gid"]}"' in text
            and target["secrets_file"] in text
            and (t["gates"]["no_auto_cron"] is not True or 'OPENCLAW_SKIP_CRON: "1"' in text))


RULES = (
    ("target_truenas_source_workstation", lambda t, hb, cron, root:
        t["target"]["host"] == "truenas" and t["source"]["host"] == "workstation"),
    ("submodule_planned_not_installed", lambda t, hb, cron, root:
        t["submodule"].get("proposed_path") == "apps/openclaw"
        and t["submodule"].get("current_path_occupied") is True
        and t["submodule"].get("install") is False),
    ("target_not_deployed_dataset_approved", lambda t, hb, cron, root:
        t["target"]["status"] == "not_deployed" and t["target"]["dataset"] == "cpool/openclaw"
        and t["target"]["image_digest"].startswith("sha256:")),
    ("compose_matches_contract", lambda t, hb, cron, root:
        compose_matches(root, t)),
    ("no_auto_heartbeat_or_cron", lambda t, hb, cron, root:
        t["gates"]["no_auto_heartbeat"] is True and t["gates"]["no_auto_cron"] is True),
    ("heartbeat_candidate_not_applied", lambda t, hb, cron, root:
        hb["deployment"] == "candidate_not_applied"
        and hb["migration_target"] == "truenas_unverified"),
    ("heartbeat_capabilities_all_disabled", lambda t, hb, cron, root:
        bool(hb.get("recovered_capabilities"))
        and not any(p.get("enabled") for p in hb["recovered_capabilities"])),
    ("digest_review_only_integer_top", lambda t, hb, cron, root:
        cron["lifecycle"] == "review_only_no_automatic_reconcile"
        and cron["parameters"]["ITEMS_PER_SECTION"] == "5"),
    ("policy_sources_exist_in_repo", lambda t, hb, cron, root:
        repo_file(root, cron["message_source"]) and repo_file(root, hb["source"])),
    ("no_secrets_in_deployed_target", lambda t, hb, cron, root:
        # secrets_file is the off-Git path of the runtime env file, not a secret.
        not ("secrets" in json.dumps({k: v for k, v in t.get("target", {}).items()
                                      if k != "secrets_file"}).lower()
             and t["target"]["status"] == "deployed")),
)


def violations(root=ROOT):
    try:
        documents = [json.loads((root / name).read_text(encoding="utf-8"))
                     for name in (TARGET, HEARTBEAT, CRON)]
    except (OSError, UnicodeError, ValueError):
        return ["contract_unreadable"]
    failed = []
    for name, rule in RULES:
        try:
            ok = rule(*documents, root)
        except (KeyError, TypeError, AttributeError):
            ok = False
        if not ok:
            failed.append(name)
    return failed


def validate(root=ROOT):
    return not violations(root)


def main():
    failed = violations()
    print("openclaw_target_contract=" + ("invalid" if failed else "prepared_not_deployed"))
    for name in failed:
        print("violation=" + name, file=sys.stderr)
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
