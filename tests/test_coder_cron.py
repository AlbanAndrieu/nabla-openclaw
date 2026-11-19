"""Offline guardrails of the daily coder jobs: one Draft PR, never master or workflows."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
NAME = "fastapi-sample-daily-improvement"
ROADMAP = "nabla-compose-roadmap-pass"


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
        self.assertIn(f"name=${{1:-{NAME}}}", script)
        self.assertRegex(script, r"--agent coder --session isolated")
        self.assertTrue(re.search(r"--declaration-key \$name", script))


class RoadmapPassCron(unittest.TestCase):
    def test_message_points_to_the_skill_and_its_branch_only(self):
        message = (ROOT / f"policies/cron/{ROADMAP}.message.md").read_text(encoding="utf-8")
        for marker in ("skills/nabla-roadmap-pass/SKILL.md", "`NO_REPLY` est interdit", "AUTOMATION_FAILED",
                       "openclaw/roadmap-pass-", "PR Draft", "Jamais de merge"):
            with self.subTest(marker=marker):
                self.assertIn(marker, message)
        self.assertNotRegex(message, r"(?i)(?:ghp_|github_pat_|sk-[a-z0-9]{12,}|token\s*=)")

    def test_skill_keeps_the_owner_directive_and_offline_limits(self):
        skill = (ROOT / "workspaces/coder/skills/nabla-roadmap-pass/SKILL.md").read_text(encoding="utf-8")
        for marker in ("consolide la et recommandations la boucle trois fois", "NOT_RUN (vantage devbox)",
                       "jamais `DEPLOYED` ni `ACCEPTED`", ".github/workflows/", "BLOQUÉ: push",
                       "questions restantes, numérotées"):
            with self.subTest(marker=marker):
                self.assertIn(marker, skill)

    def test_job_is_declared_and_allowed(self):
        self.assertIn(f"`{ROADMAP}`", (ROOT / "workspaces/coder/AGENTS.md").read_text(encoding="utf-8"))
        script = (ROOT / "scripts/coder/apply-cron-truenas.sh").read_text(encoding="utf-8")
        self.assertRegex(script, rf"\n  {ROADMAP}\) schedule=")


if __name__ == "__main__":
    unittest.main()
