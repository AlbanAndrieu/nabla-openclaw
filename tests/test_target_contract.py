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
    def test_no_executable_true_nas_compose_yet(self):
        self.assertFalse((ROOT/"deploy/truenas/compose.yml").exists())
    def test_target_models_and_rollback_unverified(self):
        t=__import__("json").loads((ROOT/"deploy/truenas/target-contract.json").read_text())
        self.assertFalse(t["rollback"]["tested"])
        self.assertEqual(t["target"]["image_digest"],"unverified")
        self.assertTrue(t["gates"]["manual_cutover_required"])
        self.assertEqual(t["submodule"]["proposed_path"],"apps/openclaw")
        self.assertTrue(t["submodule"]["current_path_occupied"])
        self.assertFalse(t["submodule"]["install"])

class Violations(unittest.TestCase):
    def copy(self, directory):
        for name in (mod.TARGET, mod.HEARTBEAT, mod.CRON,
                     "policies/cron/daily-tech-news-digest.message.md",
                     "policies/LEGACY_HEARTBEAT_RECOVERY.md"):
            (Path(directory) / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / name, Path(directory) / name)
        return Path(directory)

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
            self.assertEqual(mod.violations(root), ["target_not_deployed_dataset_unapproved",
                                                    "no_auto_heartbeat_or_cron"])
            cron = json.loads((root / mod.CRON).read_text())
            cron["message_source"] = "../outside.md"
            (root / mod.CRON).write_text(json.dumps(cron))
            self.assertIn("policy_sources_exist_in_repo", mod.violations(root))
            (root / mod.HEARTBEAT).write_text("{not json")
            self.assertEqual(mod.violations(root), ["contract_unreadable"])
            self.assertFalse(mod.validate(root))

if __name__=="__main__":unittest.main()
