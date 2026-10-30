"""Hermetic target contract: no unintended TrueNAS deployment or active cron."""
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
path=ROOT/"scripts/check-target-contract.py"
spec=importlib.util.spec_from_file_location("target",path)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class Boundary(unittest.TestCase):
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

if __name__=="__main__":unittest.main()
