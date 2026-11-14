"""Read-only, stdlib contract for cross-agent PR and host boundaries."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RootAgentPolicy(unittest.TestCase):
    def test_scoped_bootstrap_and_owned_runtime(self):
        policy = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        for marker in (
            "nabla-compose", "ansible-workstation",
            "workspaces/coder/AGENTS.md", "CODED", "ACCEPTED",
            "AGENT_EXECUTION_MODE=offline", "AGENT_EXECUTION_MODE=workstation",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, policy)

    def test_pr_reuse_and_publication_threshold(self):
        policy = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        for marker in ("Reuse a compatible", "before editing", "micro-fixes",
                       "completed migration", "no auto-merge", "NOT_RUN"):
            with self.subTest(marker=marker):
                self.assertIn(marker.lower(), policy.lower())

    def test_claude_is_small_adapter(self):
        content = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("@AGENTS.md", content)
        self.assertLessEqual(len(content.splitlines()), 16)
        self.assertTrue((ROOT / "docs/agent-pr-workflow.md").is_file())


if __name__ == "__main__":
    unittest.main()
