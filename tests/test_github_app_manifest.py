"""The devbox GitHub App manifest stays minimal: no webhook, no workflows, no admin."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "deploy/truenas/devbox/github-app-manifest.json"


class GitHubAppManifest(unittest.TestCase):
    def setUp(self):
        self.m = json.loads(MANIFEST.read_text())

    def test_private_without_webhook(self):
        self.assertIs(self.m["public"], False)
        self.assertNotIn("hook_attributes", self.m)
        self.assertEqual(self.m["default_events"], [])

    def test_permissions_are_the_devbox_needs_only(self):
        self.assertEqual(self.m["default_permissions"], {
            "metadata": "read", "contents": "write", "pull_requests": "write", "actions": "read"})


if __name__ == "__main__":
    unittest.main()
