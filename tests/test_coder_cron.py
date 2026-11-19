"""Offline guardrails of the daily coder job: one Draft PR, never master or workflows."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
NAME = "fastapi-sample-daily-improvement"


class CoderCron(unittest.TestCase):
    def test_message_keeps_the_guardrails(self):
        message = (ROOT / f"policies/cron/{NAME}.message.md").read_text(encoding="utf-8")
        for marker in ("openclaw/daily-", "EN ATTENTE", "PR Draft", ".github/workflows/",
                       "uv sync --frozen", "Jamais de merge"):
            with self.subTest(marker=marker):
                self.assertIn(marker, message)
        self.assertNotRegex(message, r"(?i)(?:ghp_|github_pat_|sk-[a-z0-9]{12,}|token\s*=)")

    def test_contract_exception_names_this_job_only(self):
        contract = (ROOT / "workspaces/coder/AGENTS.md").read_text(encoding="utf-8")
        self.assertIn(f"`{NAME}`", contract)
        script = (ROOT / "scripts/coder/apply-cron-truenas.sh").read_text(encoding="utf-8")
        self.assertIn(f"name={NAME}", script)
        self.assertRegex(script, r"--agent coder --session isolated")
        self.assertTrue(re.search(r"--declaration-key \$name", script))


if __name__ == "__main__":
    unittest.main()
