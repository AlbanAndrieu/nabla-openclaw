#!/usr/bin/env python3
"""Offline structural preflight, not a gateway deployment or readiness test."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def validate():
    target=json.loads((ROOT/"deploy/truenas/target-contract.json").read_text())
    hb=json.loads((ROOT/"policies/heartbeat-restoration.policy.json").read_text())
    cron=json.loads((ROOT/"policies/cron/daily-tech-news-digest.policy.json").read_text())
    if target["target"]["host"]!="truenas" or target["source"]["host"]!="workstation":
        return False
    sub=target["submodule"]
    if (sub.get("proposed_path")!="apps/openclaw"
            or sub.get("current_path_occupied") is not True
            or sub.get("install") is not False):
        return False
    if target["target"]["status"]!="not_deployed" or target["target"]["dataset"]!="unapproved":
        return False
    if target["gates"]["no_auto_heartbeat"] is not True or target["gates"]["no_auto_cron"] is not True:
        return False
    if hb["deployment"]!="candidate_not_applied" or hb["migration_target"]!="truenas_unverified":
        return False
    if not hb.get("recovered_capabilities") or any(p.get("enabled") for p in hb["recovered_capabilities"]):
        return False
    if cron["lifecycle"]!="review_only_no_automatic_reconcile" or cron["parameters"]["ITEMS_PER_SECTION"]!="5":
        return False
    if not (ROOT/cron["message_source"]).is_file() or not (ROOT/hb["source"]).is_file():
        return False
    if "secrets" in json.dumps(target.get("target",{})).lower() and target["target"]["status"]=="deployed":
        return False
    return True

if __name__=="__main__":
    print("openclaw_target_contract=" + ("prepared_not_deployed" if validate() else "invalid"))
    raise SystemExit(0 if validate() else 2)
