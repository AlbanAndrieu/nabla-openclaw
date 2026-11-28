"""Offline daily audit persistence, no networks and no target execution."""
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import shlex
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("audit", ROOT / "scripts/coder/security-audit-run.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AuditRun(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name) / "archive"
        self.day = dt.date(2026, 11, 28)
        self.repo = audit.selected(self.day)
        self.target = Path(self.dir.name) / "checkout"
        self.target.mkdir()
        scope = audit.REPOS[self.repo][0]
        (self.target / scope).mkdir()
        self.sha = "a" * 40
        self.skill = Path(self.dir.name) / "skill"
        self.skill.mkdir()
        self.trusted = patch.object(audit, "checked_skill", return_value={
            "validate-findings.cjs": b"", "validate-coverage-ledger.cjs": b"",
            "report-schema.json": b"{}",
        })
        self.trusted.start()
        self.addCleanup(self.trusted.stop)
        self.git = patch.object(audit, "git", side_effect=lambda _, *a: {
            ("remote", "get-url", "origin"): f"https://github.com/AlbanAndrieu/{self.repo}.git",
            ("rev-parse", "HEAD"): self.sha, ("status", "--porcelain"): "",
        }[a])
        self.git.start()
        self.addCleanup(self.git.stop)

    def prepare(self, day=None):
        return audit.prepare(self.root, day or self.day, self.target, self.skill)

    def fill(self, run, ledger=None, findings=None):
        ledger = ledger if ledger is not None else [{"status": "covered", "local_checks": [
            {"method": "source", "artifact": None}]}]
        for name in audit.FILES:
            p = run / name
            if name == "coverage-ledger.json":
                audit.write_json(p, ledger)
            elif name == "findings.json":
                audit.write_json(p, [] if findings is None else findings)
            else:
                p.write_text("INCOMPLETE", encoding="utf-8")
                p.chmod(0o600)

    def test_rotation_and_one_claim(self):
        self.assertEqual(set(audit.REPOS), {audit.selected(self.day + dt.timedelta(days=i)) for i in range(4)})
        run = Path(self.prepare()["run"])
        self.assertEqual(run.stat().st_mode & 0o777, 0o700)
        self.assertEqual((run / "run-metadata.json").stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertFalse((run / "summary.json").exists())

    def test_seal_and_reuse_only_sealed(self):
        run = Path(self.prepare()["run"])
        self.fill(run)
        with patch.object(audit.subprocess, "run") as verify:
            summary = audit.finish(self.root, self.day, self.skill)
        self.assertEqual(verify.call_count, 2)
        self.assertEqual(summary["run_status"], "incomplete")
        self.assertEqual(summary["validators"], "PASS")
        self.assertEqual(summary["confirmed_findings"], 0)
        self.assertNotIn("target", summary)
        with self.assertRaises(ValueError):
            audit.finish(self.root, self.day, self.skill)
        next_day = self.day + dt.timedelta(days=4)
        next_run = self.prepare(next_day)
        self.assertEqual(next_run["prior_run_paths"], [str(run)])
        self.assertEqual(self.prepare(next_day + dt.timedelta(days=4))["prior_run_paths"], [str(run)])

    def test_corrupt_prior_is_not_reused(self):
        run = Path(self.prepare()["run"])
        self.fill(run)
        with patch.object(audit.subprocess, "run"):
            audit.finish(self.root, self.day, self.skill)
        (run / "REPORT.md").write_text("changed")
        nxt = self.prepare(self.day + dt.timedelta(days=4))
        self.assertEqual(nxt["prior_run_paths"], [])
        self.assertEqual(nxt["prior_invalid_count"], 1)

    def test_no_unverified_findings_or_target_execution(self):
        run = Path(self.prepare()["run"])
        self.fill(run, findings=[{"verdict": "confirmed"}])
        with self.assertRaises(ValueError):
            audit.finish(self.root, self.day, self.skill)
        self.assertFalse((run / "summary.json").exists())
        (run / "findings.json").unlink()
        audit.write_json(run / "findings.json", [])
        (run / "coverage-ledger.json").unlink()
        audit.write_json(run / "coverage-ledger.json", [{"status": "covered",
                         "local_checks": [{"method": "local", "artifact": "raw"}]}])
        with self.assertRaises(ValueError):
            audit.finish(self.root, self.day, self.skill)

    def test_failed_validator_and_symlink_never_seal(self):
        run = Path(self.prepare()["run"])
        self.fill(run)
        with patch.object(audit.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "node")):
            with self.assertRaises(subprocess.CalledProcessError):
                audit.finish(self.root, self.day, self.skill)
        self.assertFalse((run / "summary.json").exists())
        (run / "REPORT.md").unlink()
        (run / "REPORT.md").symlink_to(run / "architecture.md")
        with self.assertRaises(OSError):
            audit.finish(self.root, self.day, self.skill)

    def test_root_mode_and_symlink_rejected(self):
        self.root.mkdir(mode=0o755)
        with self.assertRaises(ValueError):
            self.prepare()
        self.root.rmdir()
        self.root.symlink_to(self.target, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.prepare()

    def test_declaration_installs_runner_before_cron(self):
        # Fake SSH records calls and stdin. No LAN contact.
        base = Path(self.dir.name)
        ssh = base / "ssh"
        ssh.write_text("#!/usr/bin/env python3\nimport json, os, sys\n"
                       "with open(os.environ['CALLS'], 'a') as f:\n"
                       "    f.write(json.dumps([sys.argv[1:], sys.stdin.read()]) + '\\n')\n")
        ssh.chmod(0o700)
        calls = base / "calls"
        env = {**os.environ, "PATH": f"{base}:{os.environ['PATH']}",
               "CALLS": str(calls), "CODER_TELEGRAM_GROUP_ID": "-100123456"}
        result = subprocess.run(["bash", str(ROOT / "scripts/coder/apply-cron-truenas.sh"),
                                 "security-audit-daily"], env=env, text=True,
                                capture_output=True, timeout=10, check=True)
        records = [json.loads(line) for line in calls.read_text().splitlines()]
        self.assertEqual(len(records), 2)
        cmd = records[0][0][-1]
        args = shlex.split(cmd)
        self.assertEqual(args[-2], "-c")
        compile(args[-1], "<installer>", "exec")
        self.assertEqual(records[0][1], (ROOT / "scripts/coder/security-audit-run.py").read_text())
        self.assertIn("--declaration-key security-audit-daily", records[1][0][-1])
        self.assertIn("Première action obligatoire", records[1][1])
        self.assertIn("declared", result.stdout)

    def test_cron_is_private_and_registered(self):
        script = (ROOT / "scripts/coder/apply-cron-truenas.sh").read_text()
        self.assertIn('security-audit-daily) schedule="0 0 * * *" timeout=1500', script)
        self.assertIn("for job in security-audit-daily", script)
        self.assertIn("docker exec -i -u 1001:1001 openclaw-devbox", script)
        message = (ROOT / "policies/cron/security-audit-daily.message.md").read_text()
        for marker in ("Aucune autorisation de commit, push", "sessions_spawn", "prepare --day",
                       "finish --day", "findings.json doit être", "aucun verdict indépendant"):
            self.assertIn(marker, message)


if __name__ == "__main__":
    unittest.main()
