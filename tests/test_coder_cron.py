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
SCHEDULE = re.compile(r'\n  ([a-z-]+)\) schedule="(\d+) (\d+) \* \* \*" timeout=(\d+)')


def schedules():
    """Job name -> (start minute of the day, timeout in minutes)."""
    script = (ROOT / "scripts/coder/apply-cron-truenas.sh").read_text(encoding="utf-8")
    return {name: (int(h) * 60 + int(m), int(t) // 60) for name, m, h, t in SCHEDULE.findall(script)}


class CoderCron(unittest.TestCase):
    def test_message_keeps_the_guardrails(self):
        message = (ROOT / f"policies/cron/{NAME}.message.md").read_text(encoding="utf-8")
        # Daily job = accuracy of fastapi-sample probes against the real TrueNAS state.
        for marker in ("openclaw/daily-", "EN ATTENTE", "PR Draft", ".github/workflows/",
                       "uv sync --frozen", "Jamais de merge", "dernière ligne de sa sortie",
                       "`FAUSSE_ALERTE`", "`PANNE_RATÉE`", "Justesse =", "`fastapi-sample-roadmap-pass`",
                       "`RIEN À CORRIGER` n'est permis qu'avec une justesse de 100 %",
                       "http://172.17.0.24:9090/api/v1/query?query=up",
                       # gpt-4.1 is the only model: the prompt forces a tool call (23/11 invented PASS).
                       "Première action, obligatoire : appelle ton outil `exec`"):
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
                       "étapes 0 à 7", "PR Draft", "Jamais de merge"):
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
                       "n'est **pas** un", "`files=0`", "la mettre à jour avec `master`",
                       "gain d'au moins 10 %", "Une passe qui ne fait que consolider la roadmap",
                       "Seulement si les étapes 2 à 4 ont produit au moins un commit de code"):
            with self.subTest(marker=marker):
                self.assertIn(marker, skill)
        # Owner's order (23/11): PRs and CI, then refactor/perf/stability, then roadmap, then consolidation.
        steps = [skill.index(f"\n## {title}") for title in (
            "2. Corriger les PR ouvertes", "3. Refactorer, accélérer, stabiliser", "4. Itérer sur la roadmap",
            "5. Consolider la roadmap", "6. Publier", "7. Compte rendu")]
        self.assertEqual(steps, sorted(steps))

    def test_each_repo_has_its_night_and_a_skill_row(self):
        self.assertIn("`<repo>-roadmap-pass`", (ROOT / "workspaces/coder/AGENTS.md").read_text(encoding="utf-8"))
        script = (ROOT / "scripts/coder/apply-cron-truenas.sh").read_text(encoding="utf-8")
        skill = (ROOT / "workspaces/coder/skills/nabla-roadmap-pass/SKILL.md").read_text(encoding="utf-8")
        repos = json.loads((ROOT / "deploy/truenas/devbox/contract.json").read_text(encoding="utf-8"))["repositories"]
        self.assertEqual(sorted(f"AlbanAndrieu/{repo}" for repo in REPOS), sorted(repos))
        for repo in REPOS:
            with self.subTest(repo=repo):
                self.assertRegex(script, rf'\n  {repo}-{ROADMAP}\) schedule="\d+ \d+ \* \* \*" timeout=3600 ;;')
                self.assertIn(f"{repo}-{ROADMAP}", script.split("  all)", 1)[1].split("exit 0", 1)[0])
                self.assertIn(f"\n| `{repo}` | `", skill)
        self.assertIn('sed "s/<repo>/${name%-roadmap-pass}/g" policies/cron/roadmap-pass.message.md', script)
        # 26/11: gpt-4.1 listed docs/ in the empty sandbox and reported the repository as missing.
        message = (ROOT / "policies/cron/roadmap-pass.message.md").read_text(encoding="utf-8")
        self.assertIn("Deuxième action, obligatoire : appelle ton outil `exec`", message)
        self.assertIn("`test -d <repo>/.git || git clone --filter=blob:none https://github.com/AlbanAndrieu/<repo>.git <repo>`", message)

    def test_waves_start_before_the_night_io_stall(self):
        jobs = schedules()
        self.assertEqual(len(jobs), len(REPOS) + 2)
        # 26/11: the 01:00 night window (Mon-Sat) and the Sunday 00:00 scrub stall
        # TrueNAS IO, so the 60 s cron setup watchdog timed out every job after 01:00.
        for name, (start, _) in jobs.items():
            with self.subTest(job=name):
                self.assertTrue(21 * 60 <= start < 24 * 60)
                # 2-CPU, 3 GB devbox: never more than two sandboxes at once.
                running = [other for other, (s, t) in jobs.items() if s <= start < s + t]
                self.assertLessEqual(len(running), 2)
        daily, roadmap = jobs[NAME], jobs[f"fastapi-sample-{ROADMAP}"]
        self.assertLessEqual(sum(daily), roadmap[0])


class InfraReferee(unittest.TestCase):
    """fastapi-sample and nabla-compose passes talk through one persistent referee session."""

    def test_referee_job_is_persistent_and_primed_before_the_passes(self):
        script = (ROOT / "scripts/coder/apply-cron-truenas.sh").read_text(encoding="utf-8")
        match = re.search(rf'\n  {REFEREE}\) schedule="(\d+) (\d+) \* \* \*" timeout=(\d+) session=session:(\S+) ;;', script)
        self.assertIsNotNone(match)
        minute, hour, timeout, key = match.groups()
        # OpenClaw stores cron target session:<id> as agent:<agentId>:<id>.
        self.assertEqual(f"agent:coder:{key}", REFEREE_SESSION)
        first_pass = min(start for name, (start, _) in schedules().items() if name.endswith(ROADMAP))
        self.assertLessEqual(int(hour) * 60 + int(minute) + int(timeout) // 60, first_pass)
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
        fmt = re.compile(r"\b(QUESTION_SONDES|INFRA_EN_ATTENTE\?|BILAN_INFRA)")
        # Probe questions come from the daily job only; the roadmap passes keep to their roadmap.
        self.assertEqual({"QUESTION_SONDES"}, set(fmt.findall(daily)))
        self.assertEqual({"INFRA_EN_ATTENTE?", "BILAN_INFRA"}, set(fmt.findall(roadmap)))
        for name in ("QUESTION_SONDES", "INFRA_EN_ATTENTE?", "BILAN_INFRA"):
            with self.subTest(fmt=name):
                self.assertIn(f"**`{name}`**", skill)
        self.assertIn("un seul `sessions_send`", daily)
        for text in (roadmap, daily):
            self.assertIn(header, text)
            self.assertIn(f"`{REFEREE_SESSION}`", text)
        self.assertIn("`VERDICT PROBE`", daily)

    def test_referee_is_a_registered_skill(self):
        seed = json.loads((ROOT / "deploy/truenas/openclaw.json").read_text(encoding="utf-8"))
        self.assertIn("nabla-infra-referee", seed["agents"]["entries"]["coder"]["skills"])


if __name__ == "__main__":
    unittest.main()
