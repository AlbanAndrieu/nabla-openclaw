"""Offline contracts: Workstation HEARTBEAT/MORNING_BRIEFING projected from this repo."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/workstation/openclaw-heartbeat-gitops.py"
spec = importlib.util.spec_from_file_location("heartbeat_gitops", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "state"
        (self.root / "workspace").mkdir(parents=True)
        self.source = Path(self.directory.name) / "source.md"
        self.source.write_text("# comments only\n", encoding="utf-8")


class HeartbeatGitOps(Fixture):
    def test_sources_are_this_repository_policies(self):
        self.assertEqual(mod.SOURCE, ROOT / "policies/HEARTBEAT.md")
        self.assertEqual(mod.BRIEFING_SOURCE, ROOT / "policies/MORNING_BRIEFING.md")
        self.assertTrue(mod.SOURCE.is_file() and mod.BRIEFING_SOURCE.is_file())

    def test_backup_then_apply_and_check(self):
        target = self.root / "workspace/HEARTBEAT.md"
        target.write_text("old private data\n")
        self.assertTrue(mod.operate("check", self.root, self.source).startswith("different"))
        self.assertIn("backup=", mod.operate("backup", self.root, self.source))
        self.assertIn("applied_sha256=", mod.operate("apply", self.root, self.source))
        self.assertTrue(mod.operate("check", self.root, self.source).startswith("matching"))
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        backups = list((self.root / "backups/heartbeat-gitops").glob("HEARTBEAT.*.md"))
        self.assertTrue(backups)
        self.assertEqual(backups[0].read_text(), "old private data\n")

    def test_rejects_symlink(self):
        (self.root / "workspace/HEARTBEAT.md").symlink_to(self.source)
        with self.assertRaisesRegex(ValueError, "symlink_refused"):
            mod.operate("backup", self.root, self.source)

    def test_refuses_missing_heartbeat(self):
        with self.assertRaisesRegex(ValueError, "current_heartbeat_missing_refuse_unsafe_replace"):
            mod.operate("apply", self.root, self.source)

    def test_repeated_backup_does_not_fail_in_same_second(self):
        (self.root / "workspace/HEARTBEAT.md").write_text("previous\n")
        first = mod.operate("backup", self.root, self.source)
        second = mod.operate("backup", self.root, self.source)
        self.assertEqual(first, second)
        self.assertEqual(len(list((self.root / "backups/heartbeat-gitops").glob("HEARTBEAT.*.md"))), 1)


class MorningBriefingGitOps(Fixture):
    def test_creates_template_without_overwriting_existing_heartbeat(self):
        heartbeat = self.root / "workspace/HEARTBEAT.md"
        heartbeat.write_text("owner heartbeat\n")
        result = mod.operate("apply", self.root, self.source,
                             target_name="MORNING_BRIEFING.md", create_missing=True)
        target = self.root / "workspace/MORNING_BRIEFING.md"
        self.assertEqual(target.read_bytes(), self.source.read_bytes())
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(heartbeat.read_text(), "owner heartbeat\n")
        self.assertIn("backup=none_created_new_file", result)

    def test_preserves_previous_briefing_in_private_backup(self):
        (self.root / "workspace/MORNING_BRIEFING.md").write_text("prior private briefing\n")
        mod.operate("apply", self.root, self.source,
                    target_name="MORNING_BRIEFING.md", create_missing=True)
        backups = list((self.root / "backups/heartbeat-gitops").glob("MORNING_BRIEFING.*.md"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), "prior private briefing\n")
        self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)

    def test_refuses_bad_target_name(self):
        with self.assertRaisesRegex(ValueError, "unsupported_target_name"):
            mod.operate("apply", self.root, self.source,
                        target_name="../outside.md", create_missing=True)

    def test_live_heartbeat_is_comment_only_not_routine_reactivation(self):
        text = mod.SOURCE.read_text(encoding="utf-8")
        self.assertIn("reason=empty-heartbeat-file", text)
        self.assertNotIn("tasks:", text)
        body = text.split("<!--", 1)
        self.assertEqual(len(body), 2)
        # Outside the title and the HTML comment, nothing may wake the model.
        self.assertEqual([l for l in body[0].splitlines() if l.strip() and not l.startswith("#")], [])
        self.assertTrue(text.rstrip().endswith("-->"))
        briefing = mod.BRIEFING_SOURCE.read_text(encoding="utf-8")
        for section in ("Météo", "État du système", "Calendriers",
                        "Messagerie", "Alertes", "Tâches"):
            self.assertIn(section, briefing)
        self.assertIn("Non vérifié", briefing)


if __name__ == "__main__":
    unittest.main()
