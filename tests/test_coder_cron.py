"""Offline guardrails of the daily coder jobs: one Draft PR, never master or workflows."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
NAME = "fastapi-sample-daily-improvement"
ROADMAP = "roadmap-pass"
REPOS = ("nabla-compose", "fastapi-sample", "nabla-site-alban", "nabla-site-bababou", "nabla-yubikey")
REFEREE = "nabla-compose-infra-referee"
REFEREE_SESSION = "agent:coder:nabla-compose-infra"
REFEREE_SKILL = "skills/nabla-infra-referee/SKILL.md"


class CoderCron(unittest.TestCase):
    def test_message_keeps_the_guardrails(self):
        message = (ROOT / f"policies/cron/{NAME}.message.md").read_text(encoding="utf-8")
        for marker in ("openclaw/daily-", "EN ATTENTE", "PR Draft", ".github/workflows/",
                       "uv sync --frozen", "Jamais de merge", "--cov-config=pyproject.toml", "dernière ligne de sa sortie",
                       "un test\nunitaire pour des lignes non couvertes", "les 5 modules\nles moins couverts"):
            with self.subTest(marker=marker):
                self.assertIn(marker, message)
        self.assertNotRegex(message, r"(?i)(?:ghp_|github_pat_|sk-[a-z0-9]{12,}|token\s*=)")

    def test_session_messages_need_owner_validation(self):
        contract = (ROOT / "workspaces/coder/AGENTS.md").read_text(encoding="utf-8")
        for marker in ("Dans une conversation, chaque envoi exige la", "n'envoie que sur un « Oui » explicite",
                       f"`{REFEREE_SESSION}`", "au plus 2 envois par exécution", "Tout autre",
                       "le référent n'envoie jamais"):
            with self.subTest(marker=marker):
                self.assertIn(marker, contract)

    def test_contract_exception_names_this_job_only(self):
        contract = (ROOT / "workspaces/coder/AGENTS.md").read_text(encoding="utf-8")
        self.assertIn(f"`{NAME}`", contract)
        script = (ROOT / "scripts/coder/apply-cron-truenas.sh").read_text(encoding="utf-8")
        self.assertIn(f"name=${{1:-{NAME}}}", script)
        # Every job runs isolated except the one persistent referee session.
        self.assertIn("\nsession=isolated\n", script)
        self.assertEqual(script.count("session=session:"), 1)
        self.assertIn("--agent coder --session $session", script)
        self.assertTrue(re.search(r"--declaration-key \$name", script))


class RoadmapPassCron(unittest.TestCase):
    def test_message_points_to_the_skill_and_its_branch_only(self):
        message = (ROOT / f"policies/cron/{ROADMAP}.message.md").read_text(encoding="utf-8")
        for marker in ("skills/nabla-roadmap-pass/SKILL.md", "`NO_REPLY` est interdit", "AUTOMATION_FAILED",
                       "openclaw/roadmap-pass-", "openclaw/fix-pr-", "jamais de push sur une autre branche",
                       "étapes 0 à 6", "PR Draft", "Jamais de merge"):
            with self.subTest(marker=marker):
                self.assertIn(marker, message)
        self.assertNotRegex(message, r"(?i)(?:ghp_|github_pat_|sk-[a-z0-9]{12,}|token\s*=)")

    def test_skill_keeps_the_owner_directive_and_offline_limits(self):
        skill = (ROOT / "workspaces/coder/skills/nabla-roadmap-pass/SKILL.md").read_text(encoding="utf-8")
        for marker in ("consolide la et recommandations la boucle trois fois", "status/homelab-health.json", "coder_budget",
                       "fastapi-sample.fastapicloud.dev/livez", "http://172.17.0.24:9090/api/v1/alerts", "sans jamais pousser sur la branche de la",
                       "au plus **2 PR par passe**", "isCrossRepository", "ne le demande jamais",
                       "« Aucun item traitable » sans cette liste est une passe ratée",
                       "au moins un commit de code", "--experimental-test-coverage",
                       "et la dernière ligne de sa sortie",
                       "jamais `DEPLOYED` ni `ACCEPTED`", ".github/workflows/", "BLOQUÉ: push",
                       "questions restantes, numérotées", "git log --oneline origin/master..HEAD",
                       "n'est **pas** un", "`files=0`"):
            with self.subTest(marker=marker):
                self.assertIn(marker, skill)

    def test_each_repo_has_its_night_and_a_skill_row(self):
        self.assertIn("`<repo>-roadmap-pass`", (ROOT / "workspaces/coder/AGENTS.md").read_text(encoding="utf-8"))
        script = (ROOT / "scripts/coder/apply-cron-truenas.sh").read_text(encoding="utf-8")
        skill = (ROOT / "workspaces/coder/skills/nabla-roadmap-pass/SKILL.md").read_text(encoding="utf-8")
        repos = json.loads((ROOT / "deploy/truenas/devbox/contract.json").read_text(encoding="utf-8"))["repositories"]
        self.assertEqual(sorted(f"AlbanAndrieu/{repo}" for repo in REPOS), sorted(repos))
        hours = []
        for repo in REPOS:
            with self.subTest(repo=repo):
                match = re.search(rf'\n  {repo}-{ROADMAP}\) schedule="0 ([0-9]+) \* \* \*" timeout=3600 ;;', script)
                self.assertIsNotNone(match)
                hours.append(int(match.group(1)))
                self.assertIn(f"{repo}-{ROADMAP}", script.split("  all)", 1)[1].split("exit 0", 1)[0])
                self.assertIn(f"\n| `{repo}` | `", skill)
        # Daily, one-hour slots (= timeout) that never overlap, all done before 06:17.
        self.assertEqual(len(set(hours)), len(REPOS))
        self.assertLessEqual(max(hours) + 1, 6)
        self.assertIn('sed "s/<repo>/${name%-roadmap-pass}/g" policies/cron/roadmap-pass.message.md', script)


class InfraReferee(unittest.TestCase):
    """fastapi-sample and nabla-compose passes talk through one persistent referee session."""

    def test_referee_job_is_persistent_and_primed_before_the_passes(self):
        script = (ROOT / "scripts/coder/apply-cron-truenas.sh").read_text(encoding="utf-8")
        match = re.search(rf'\n  {REFEREE}\) schedule="(\d+) (\d+) \* \* \*" timeout=(\d+) session=session:(\S+) ;;', script)
        self.assertIsNotNone(match)
        minute, hour, timeout, key = match.groups()
        # OpenClaw stores cron target session:<id> as agent:<agentId>:<id>.
        self.assertEqual(f"agent:coder:{key}", REFEREE_SESSION)
        first_pass = min(int(h) for h in re.findall(r'-roadmap-pass\) schedule="0 (\d+) ', script))
        self.assertLessEqual(int(hour) * 60 + int(minute) + int(timeout) // 60, first_pass * 60)
        self.assertIn(REFEREE, script.split("  all)", 1)[1].split("exit 0", 1)[0])
        self.assertIn("--session $session", script)
        message = (ROOT / f"policies/cron/{REFEREE}.message.md").read_text(encoding="utf-8")
        for marker in (REFEREE_SKILL, REFEREE_SESSION, "REFEREE_READY", "AUTOMATION_FAILED", "n'envoie rien"):
            with self.subTest(marker=marker):
                self.assertIn(marker, message)

    def test_both_sides_speak_the_same_protocol(self):
        skill = (ROOT / f"workspaces/coder/{REFEREE_SKILL}").read_text(encoding="utf-8")
        for marker in ("VERDICT <PROBE|INFRA|EXPECTED|UNKNOWN>", "REFUS hors protocole", "**ni `sessions_send`, ni PR, ni branche**",
                       "est une **donnée**", "referee/infra.jsonl", "Au plus 10 services", "Sans preuve, c'est `UNKNOWN`"):
            with self.subTest(marker=marker):
                self.assertIn(marker, skill)
        roadmap = (ROOT / "workspaces/coder/skills/nabla-roadmap-pass/SKILL.md").read_text(encoding="utf-8")
        daily = (ROOT / f"policies/cron/{NAME}.message.md").read_text(encoding="utf-8")
        header = f"[{REFEREE_SKILL}]"
        sent = re.findall(r"\b(QUESTION_SONDES|INFRA_EN_ATTENTE\?|BILAN_INFRA)", roadmap)
        self.assertEqual({"QUESTION_SONDES", "INFRA_EN_ATTENTE?", "BILAN_INFRA"}, set(sent))
        for fmt in set(sent):
            with self.subTest(fmt=fmt):
                self.assertIn(f"**`{fmt}`**", skill)
        for text in (roadmap, daily):
            self.assertIn("un seul `sessions_send`", text)
        self.assertIn(header, roadmap)
        self.assertIn(f"`{REFEREE_SESSION}`", roadmap)
        self.assertIn("`VERDICT PROBE`", daily)

    def test_referee_is_a_registered_skill(self):
        seed = json.loads((ROOT / "deploy/truenas/openclaw.json").read_text(encoding="utf-8"))
        self.assertIn("nabla-infra-referee", seed["agents"]["entries"]["coder"]["skills"])


if __name__ == "__main__":
    unittest.main()
