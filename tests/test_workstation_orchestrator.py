"""Offline contracts: Workstation GitOps entry point guards and aggregation."""
import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "workstation_gitops", ROOT / "scripts/workstation/openclaw-workstation-gitops.py")
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod  # dataclasses resolve their module through sys.modules
spec.loader.exec_module(mod)


def fake_git(head="abc123def456", status="", reviewed=True):
    def runner(*args):
        if args[0] == "rev-parse":
            return (0, head) if head else (128, "")
        if args[0] == "status":
            return 0, status
        if args[0] == "merge-base":
            return (0 if reviewed else 1), ""
        raise AssertionError(args)
    return runner


class Recorder:
    def __init__(self, codes=None):
        self.steps, self.codes = [], codes or {}

    def __call__(self, step):
        self.steps.append(step)
        return self.codes.get(step, 0)


def run(argv, *, host="workstation", git=None, runner=None):
    runner = runner or Recorder()
    with contextlib.redirect_stdout(io.StringIO()) as out, \
         contextlib.redirect_stderr(io.StringIO()) as err:
        code = mod.main(argv, host=lambda: host, git_runner=git or fake_git(), runner=runner)
    return code, out.getvalue(), err.getvalue(), runner


class Guards(unittest.TestCase):
    def test_wrong_host_runs_nothing(self):
        for argv in (["plan"], ["check"], ["apply-heartbeat"],
                     ["apply-digest", "--expected-message-sha", "a" * 64]):
            code, _, err, runner = run(argv, host="truenas")
            self.assertEqual(code, 2)
            self.assertIn("STOP: not the OpenClaw Workstation", err)
            self.assertEqual(runner.steps, [])

    def test_apply_refuses_uncommitted_unknown_or_unmerged_config(self):
        for git, reason in ((fake_git(status=" M policies/HEARTBEAT.md"), "uncommitted"),
                            (fake_git(head=""), "uncommitted or unknown"),
                            (fake_git(reviewed=False), "not in origin/master")):
            code, _, err, runner = run(["apply-heartbeat"], git=git)
            self.assertEqual(code, 2)
            self.assertIn(reason, err)
            self.assertEqual(runner.steps, [])

    def test_allow_unmerged_is_explicit_and_never_bypasses_uncommitted(self):
        code, _, _, runner = run(["apply-heartbeat", "--allow-unmerged"], git=fake_git(reviewed=False))
        self.assertEqual(code, 0)
        self.assertEqual(len(runner.steps), 2)
        code, _, _, runner = run(["apply-heartbeat", "--allow-unmerged"],
                                 git=fake_git(status="?? policies/x", reviewed=False))
        self.assertEqual((code, runner.steps), (2, []))

    def test_apply_digest_requires_expected_sha(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            mod.main(["apply-digest"], host=lambda: "workstation",
                     git_runner=fake_git(), runner=Recorder())


class Reporting(unittest.TestCase):
    def test_plan_reports_every_component_and_never_fails_on_drift(self):
        drift = Recorder({("openclaw-heartbeat-gitops.py", "--check"): 2})
        code, out, _, runner = run(["plan"], runner=drift)
        self.assertEqual(code, 0)
        self.assertEqual([s[0] for s in runner.steps],
                         [step[0] for _, step in mod.COMPONENTS])
        self.assertIn("config_source=nabla-openclaw@abc123def456 uncommitted_config_paths=0 reviewed=true", out)
        self.assertIn("workstation_heartbeat=not_aligned", out)
        self.assertIn("workstation_runtime_alignment=aligned", out)
        self.assertIn("workstation_gitops=not_aligned", out)
        self.assertFalse(any("--apply" in step for step in runner.steps))

    def test_check_is_strict(self):
        self.assertEqual(run(["check"])[0], 0)
        drift = Recorder({("reconcile-openclaw-digest-cron.py", "--check"): 2})
        self.assertEqual(run(["check"], runner=drift)[0], 2)

    def test_apply_steps_stop_at_first_failure(self):
        failing = Recorder({("openclaw-heartbeat-gitops.py", "--apply"): 2})
        code, _, _, runner = run(["apply-heartbeat"], runner=failing)
        self.assertEqual(code, 2)
        self.assertEqual(runner.steps, [("openclaw-heartbeat-gitops.py", "--apply")])
        code, _, _, runner = run(["apply-digest", "--expected-message-sha", "b" * 64])
        self.assertEqual(runner.steps, [("reconcile-openclaw-digest-cron.py", "--apply",
                                         "--expected-message-sha", "b" * 64)])


class RealGit(unittest.TestCase):
    def test_config_source_against_a_real_repository(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)

            def git(*args):
                result = subprocess.run(["git", "-C", d, *args], capture_output=True, text=True, check=False)
                return result.returncode, result.stdout.strip()

            for args in (("init", "-q"), ("config", "user.email", "t@example.invalid"),
                         ("config", "user.name", "t")):
                git(*args)
            (repo / "policies").mkdir()
            (repo / "policies/HEARTBEAT.md").write_text("# h\n")
            git("add", "-A")
            git("commit", "-qm", "init")
            source = mod.config_source(git)
            self.assertEqual((source.uncommitted, source.reviewed), (0, False))
            git("update-ref", "refs/remotes/origin/master", "HEAD")
            self.assertTrue(mod.config_source(git).reviewed)
            (repo / "policies/HEARTBEAT.md").write_text("# changed\n")
            self.assertEqual(mod.config_source(git).uncommitted, 1)


if __name__ == "__main__":
    unittest.main()
