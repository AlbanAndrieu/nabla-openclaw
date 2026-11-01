"""Hermetic target contract: no unintended TrueNAS deployment or active cron."""
import importlib.util
import json
import shutil
import tempfile
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
path=ROOT/"scripts/check-target-contract.py"
spec=importlib.util.spec_from_file_location("target",path)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class Boundary(unittest.TestCase):
    def test_heartbeat_candidate_is_bounded_and_inactive(self):
        candidate = (ROOT / "policies/HEARTBEAT-RESTORED.candidate.md").read_text()
        self.assertIn("3 anomalies prioritaires", candidate)
        self.assertIn("UNKNOWN / NOT_VERIFIED", candidate)
        self.assertIn("HEARTBEAT_OK", candidate)
        self.assertNotIn("\ntasks:\n", candidate)
        self.assertIn("CANDIDAT INACTIF", candidate)

    def test_target_is_not_source(self):
        self.assertTrue(mod.validate())
    def test_truenas_seed_config_has_only_env_secret_refs(self):
        seed = json.loads((ROOT/"deploy/truenas/openclaw.json").read_text())
        self.assertEqual(seed["gateway"]["auth"]["token"],
                         {"source": "env", "provider": "default", "id": "OPENCLAW_GATEWAY_TOKEN"})
        keys = {p["apiKey"]["id"] for p in seed["models"]["providers"].values()}
        self.assertEqual(keys, {"LITELLM_OPENCLAW_MAIN_API_KEY", "LITELLM_OPENCLAW_CRON_API_KEY"})
        self.assertEqual(seed["agents"]["defaults"]["heartbeat"], {"agentId": "main"})
        # Channel allowlists hold personal identifiers: applied by CLI, never in Git.
        self.assertNotIn("channels", seed)
        self.assertNotIn("bindings", seed)
    def test_target_models_and_rollback_unverified(self):
        t=__import__("json").loads((ROOT/"deploy/truenas/target-contract.json").read_text())
        self.assertFalse(t["rollback"]["tested"])
        self.assertTrue(t["target"]["image_digest"].startswith("sha256:"))
        self.assertTrue(t["gates"]["manual_cutover_required"])
        self.assertEqual(t["submodule"]["path"],"apps/openclaw")
        self.assertTrue(t["submodule"]["installed"])

class Violations(unittest.TestCase):
    def copy(self, directory):
        for name in (mod.TARGET, mod.HEARTBEAT, mod.CRON, "deploy/truenas/compose.yml",
                     "policies/cron/daily-tech-news-digest.message.md",
                     "policies/LEGACY_HEARTBEAT_RECOVERY.md"):
            (Path(directory) / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / name, Path(directory) / name)
        return Path(directory)

    def test_compose_exposed_on_lan_is_a_violation(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.copy(d)
            compose = root / "deploy/truenas/compose.yml"
            compose.write_text(compose.read_text().replace('"127.0.0.1:18789:18789"', '"18789:18789"'))
            self.assertEqual(mod.violations(root), ["compose_matches_contract"])

    def test_active_target_requires_stopped_workstation(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.copy(d)
            target = json.loads((root / mod.TARGET).read_text())
            target["source"]["state"] = "active_keep_running_until_cutover"
            (root / mod.TARGET).write_text(json.dumps(target))
            self.assertEqual(mod.violations(root), ["single_gateway_owner"])

    def test_repository_has_no_violation(self):
        self.assertEqual(mod.violations(), [])

    def test_named_violations(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.copy(d)
            self.assertEqual(mod.violations(root), [])
            target = json.loads((root / mod.TARGET).read_text())
            target["target"]["status"] = "deployed"
            del target["gates"]["no_auto_cron"]
            (root / mod.TARGET).write_text(json.dumps(target))
            self.assertEqual(mod.violations(root), ["target_status_dataset_approved",
                                                    "compose_matches_contract",
                                                    "single_gateway_owner"])
            cron = json.loads((root / mod.CRON).read_text())
            cron["message_source"] = "../outside.md"
            (root / mod.CRON).write_text(json.dumps(cron))
            self.assertIn("policy_sources_exist_in_repo", mod.violations(root))
            (root / mod.HEARTBEAT).write_text("{not json")
            self.assertEqual(mod.violations(root), ["contract_unreadable"])
            self.assertFalse(mod.validate(root))

if __name__=="__main__":unittest.main()
