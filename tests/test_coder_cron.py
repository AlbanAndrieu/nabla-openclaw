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
SCHEDULE = re.compile(r'\n  ([a-z-]+)\) schedule="(\d+) (\d+|\d+-\d+) \* \* \*" timeout=(\d+)')


def hours(field):
    first, _, last = field.partition("-")
    return range(int(first), int(last or first) + 1)


def schedules():
    """Job name -> (start minutes of the day, timeout in minutes)."""
    script = (ROOT / "scripts/coder/apply-cron-truenas.sh").read_text(encoding="utf-8")
    return {name: ([h * 60 + int(m) for h in hours(field)], int(t) // 60)
            for name, m, field, t in SCHEDULE.findall(script)}


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
                       "Seulement si les étapes 2 à 4 ont produit au moins un commit de code",
                       # 27/11, fastapi-sample#460: Ready PR, one-line notes file, roadmap left at 22/11.
                       "**Réconcilier d'abord**", "git grep -n -i 'réconciliation mise à jour' -- tests/",
                       "Jamais de\nfichier de notes", "--body-file ../pr-body.md",
                       "**3 propositions d'amélioration**"):
            with self.subTest(marker=marker):
                self.assertIn(marker, skill)
        # Owner's order (23/11): PRs and CI, then refactor/perf/stability, then roadmap, then consolidation.
        steps = [skill.index(f"\n## {title}") for title in (
            "2. Corriger les PR ouvertes", "3. Refactorer, accélérer, stabiliser", "4. Itérer sur la roadmap",
            "5. Consolider la roadmap", "6. Publier", "7. Compte rendu")]
        self.assertEqual(steps, sorted(steps))

    def test_each_repo_has_its_hourly_pass_and_a_skill_row(self):
        self.assertIn("`<repo>-roadmap-pass`", (ROOT / "workspaces/coder/AGENTS.md").read_text(encoding="utf-8"))
        script = (ROOT / "scripts/coder/apply-cron-truenas.sh").read_text(encoding="utf-8")
        skill = (ROOT / "workspaces/coder/skills/nabla-roadmap-pass/SKILL.md").read_text(encoding="utf-8")
        repos = json.loads((ROOT / "deploy/truenas/devbox/contract.json").read_text(encoding="utf-8"))["repositories"]
        self.assertEqual(sorted(f"AlbanAndrieu/{repo}" for repo in REPOS), sorted(repos))
        for repo in REPOS:
            with self.subTest(repo=repo):
                self.assertRegex(script, rf'\n  {repo}-{ROADMAP}\) schedule="\d+ 8-23 \* \* \*" timeout=1440 ;;')
                self.assertIn(f"{repo}-{ROADMAP}", script.split("  all)", 1)[1].split("exit 0", 1)[0])
                self.assertIn(f"\n| `{repo}` | `", skill)
        self.assertIn('sed "s/<repo>/${name%-roadmap-pass}/g" policies/cron/roadmap-pass.message.md', script)
        # 26/11: gpt-4.1 listed docs/ in the empty sandbox and reported the repository as missing.
        message = (ROOT / "policies/cron/roadmap-pass.message.md").read_text(encoding="utf-8")
        self.assertIn("Deuxième action, obligatoire : appelle ton outil `exec`", message)
        self.assertIn("`test -d <repo>/.git || git clone --filter=blob:none https://github.com/AlbanAndrieu/<repo>.git <repo>`", message)
        # 27/11, first hourly passes: two reports narrated a clone without any tool call,
        # and fastapi-sample ended its turn on "je poursuivrai" while its tests ran.
        for marker in ("ce tour est le seul", "`NOT_RUN`, jamais\n  `PASS`", "l'outil `process`",
                       "jamais sur « je\n  poursuivrai »"):
            with self.subTest(marker=marker):
                self.assertIn(marker, message)

    def test_runs_avoid_the_night_io_stall_two_at_a_time(self):
        jobs = schedules()
        self.assertEqual(len(jobs), len(REPOS) + 2)
        runs = [(name, start, start + t) for name, (starts, t) in jobs.items() for start in starts]
        # A run started late in the evening still holds its sandbox after midnight.
        day = 24 * 60
        spans = runs + [(name, s - day, e - day) for name, s, e in runs]
        for name, start, _ in runs:
            with self.subTest(job=name, start=start):
                # 26/11: the nabla-compose night window stalls TrueNAS IO from 01:15 to
                # 07:30 (Mon-Sat), so the 60 s cron setup watchdog timed out every job.
                self.assertFalse(60 <= start < 8 * 60)
                # 2-CPU, 3 GB devbox: never more than two sandboxes at once.
                self.assertLessEqual(len([other for other, s, e in spans if s <= start < e]), 2)
        roadmap = [(s, e) for name, s, e in spans if name == f"fastapi-sample-{ROADMAP}"]
        for _, start, end in (run for run in spans if run[0] == NAME):
            self.assertFalse(any(s < end and start < e for s, e in roadmap))


class InfraReferee(unittest.TestCase):
    """fastapi-sample and nabla-compose passes talk through one persistent referee session."""

    def test_referee_job_is_persistent_and_primed_before_the_passes(self):
        script = (ROOT / "scripts/coder/apply-cron-truenas.sh").read_text(encoding="utf-8")
        match = re.search(rf'\n  {REFEREE}\) schedule="(\d+) (\d+) \* \* \*" timeout=(\d+) session=session:(\S+) ;;', script)
        self.assertIsNotNone(match)
        minute, hour, timeout, key = match.groups()
        # OpenClaw stores cron target session:<id> as agent:<agentId>:<id>.
        self.assertEqual(f"agent:coder:{key}", REFEREE_SESSION)
        first_pass = min(min(starts) for name, (starts, _) in schedules().items() if name.endswith(ROADMAP))
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
