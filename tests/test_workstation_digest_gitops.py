"""Offline contracts: only the existing digest job is reconciled from this repo."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import contextlib
import io
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "scripts/workstation/reconcile-openclaw-digest-cron.py"
spec = importlib.util.spec_from_file_location("digest_gitops", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def job(message):
    return {
        "id": mod.JOB_ID, "name": mod.JOB_NAME, "enabled": True,
        "agentId": "cron", "sessionTarget": "isolated",
        "schedule": {"kind": "cron", "expr": "0 9 * * *", "tz": "Europe/Paris"},
        "delivery": {"mode": "announce", "channel": "discord", "to": "private"},
        "payload": {"kind": "agentTurn", "message": message, "timeoutSeconds": 300},
    }


class GitOpsDigestTests(unittest.TestCase):
    def test_source_is_this_repository_policy(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(mod.SOURCE, root / "policies/cron/daily-tech-news-digest.message.md")
        policy = __import__("json").loads((root / "policies/cron/daily-tech-news-digest.policy.json").read_text())
        self.assertEqual(policy["runtime_job_id"], mod.JOB_ID)
        self.assertEqual(policy["id"], mod.JOB_NAME)
        self.assertEqual(root / policy["message_source"], mod.SOURCE)

    def test_source_contains_only_integer_five(self):
        src = mod.desired_message()
        self.assertEqual(src.count("- ITEMS_PER_SECTION = 5"), 1)
        self.assertIn("references/digest-prompt.md", src)
        self.assertNotIn("sk-secret", src)

    def test_plan_has_no_mutation_or_private_prompt(self):
        original = "PRIVATE recipient references/digest-prompt.md\n- ITEMS_PER_SECTION = 3-5"
        with patch.object(mod, "host", return_value="workstation"), \
             patch.object(mod, "runtime_job", return_value=("structured", job(original))), \
             patch.object(mod, "cli_edit") as edit, \
             patch.object(mod, "backup") as backup, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(mod.main(["--plan"]), 0)
        self.assertIn("cron_gitops=drift", output.getvalue())
        self.assertNotIn("PRIVATE", output.getvalue())
        edit.assert_not_called()
        backup.assert_not_called()

    def test_unknown_host_blocks_all_gateway_calls(self):
        with patch.object(mod, "host", return_value="truenas"), \
             patch.object(mod, "runtime_job") as load, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(mod.main(["--apply"]), 2)
        load.assert_not_called()

    def test_mismatched_hash_cannot_apply(self):
        old = job("old private prompt")
        with patch.object(mod, "host", return_value="workstation"), \
             patch.object(mod, "runtime_job", return_value=("structured", old)), \
             patch.object(mod, "cli_edit") as edit, \
             patch.object(mod, "backup") as backup, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(mod.main(["--apply","--expected-message-sha","a"*64]),2)
        self.assertIn("blocked_concurrent_drift", output.getvalue())
        edit.assert_not_called()
        backup.assert_not_called()

    def test_apply_updates_existing_job_without_changing_delivery(self):
        initial = job("old private content references/digest-prompt.md\n- ITEMS_PER_SECTION = 3-5")
        final = job(mod.desired_message())
        with patch.object(mod, "host", return_value="workstation"), \
             patch.object(mod, "runtime_job", side_effect=[("structured", initial)] * 2 + [("structured", final)]), \
             patch.object(mod, "backup", return_value=True) as backup, \
             patch.object(mod, "cli_edit", return_value=True) as edit, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            code=mod.main(["--apply", "--expected-message-sha", mod.sha(
                initial["payload"]["message"])])
        self.assertEqual(code,0)
        self.assertIn("apply=verified_existing_job_updated",output.getvalue())
        self.assertNotIn("old private content",output.getvalue())
        edit.assert_called_once_with(mod.desired_message())
        backup.assert_called_once()

    def test_unknown_runtime_prompt_never_overwritten(self):
        old = job("PRIVATE instructions without expected skill contract")
        with patch.object(mod, "host", return_value="workstation"), \
             patch.object(mod, "runtime_job", return_value=("structured", old)), \
             patch.object(mod, "backup") as save, \
             patch.object(mod, "cli_edit") as write, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            rc = mod.main(["--apply", "--expected-message-sha",
                           mod.sha(old["payload"]["message"])])
        self.assertEqual(rc, 2)
        self.assertIn("blocked_unexpected_runtime_template", output.getvalue())
        save.assert_not_called()
        write.assert_not_called()

    def test_unreadable_job_reports_cause_without_mutation(self):
        with patch.object(mod, "host", return_value="workstation"), \
             patch.object(mod, "runtime_job", return_value=("unverified_installation", None)), \
             patch.object(mod, "install_issues", return_value="node:writable_by_group"), \
             patch.object(mod, "cli_edit") as edit, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(mod.main(["--plan"]), 2)
        text = output.getvalue()
        self.assertIn("cron_gitops=runtime_job_unverified", text)
        self.assertIn("cron_job_read=unverified_installation", text)
        self.assertIn("runtime_install=node:writable_by_group", text)
        edit.assert_not_called()

    def test_runtime_job_rejects_other_job_and_payload(self):
        other = job("x")
        other["name"] = "other"
        with patch.object(mod, "read_cron_job", return_value=("structured", other)):
            self.assertEqual(mod.runtime_job(), ("wrong_job", None))
        bad = job("x")
        bad["payload"]["kind"] = "systemEvent"
        with patch.object(mod, "read_cron_job", return_value=("structured", bad)):
            self.assertEqual(mod.runtime_job(), ("unexpected_payload", None))
        with patch.object(mod, "read_cron_job", return_value=("cli_failed", None)):
            self.assertEqual(mod.runtime_job(), ("cli_failed", None))

    def test_already_aligned_is_success_without_backup(self):
        with patch.object(mod, "host", return_value="workstation"), \
             patch.object(mod, "runtime_job", return_value=("structured", job(mod.desired_message()))), \
             patch.object(mod, "backup") as save, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(mod.main(["--check"]), 0)
        self.assertIn("cron_gitops=already_aligned", output.getvalue())
        save.assert_not_called()

    def test_backup_refuses_shared_parent(self):
        with TemporaryDirectory() as temp:
            (Path(temp) / ".local").mkdir(mode=0o777)
            (Path(temp) / ".local").chmod(0o777)
            with patch.object(mod.Path, "home", return_value=Path(temp)):
                with self.assertRaisesRegex(ValueError, "shared_parent_directory"):
                    mod.backup(job("PRIVATE"))
            self.assertFalse((Path(temp) / ".local/state").exists())

    def test_preservation_guard_rejects_delivery_drift(self):
        old=job("before")
        new=job("after")
        new["delivery"]["to"]="different"
        self.assertFalse(mod.preserved(old,new))

    def test_backup_is_private_and_keeps_original_prompt(self):
        with TemporaryDirectory() as temp:
            with patch.object(mod.Path, "home", return_value=Path(temp)):
                self.assertTrue(mod.backup(job("PRIVATE backup")))
            saved=list((Path(temp)/".local/state/nabla-compose/openclaw/digest-gitops").glob("*.json"))
            self.assertEqual(len(saved),1)
            self.assertEqual(saved[0].stat().st_mode & 0o777,0o600)
            self.assertIn("PRIVATE backup",saved[0].read_text())


if __name__ == "__main__":
    unittest.main()
