"""Offline contracts for the FreshRSS → digest RSS sources sync."""
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts/cron/freshrss-sources.py"
spec = importlib.util.spec_from_file_location("freshrss_sources", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

OPML = b"""<?xml version="1.0"?><opml version="2.0"><body>
<outline text="LLM"><outline type="rss" text="Simon" xmlUrl="https://simon.example/atom"/></outline>
<outline text="Crypto"><outline type="rss" text="Coin" xmlUrl="https://coin.example/rss"/></outline>
<outline text="Uncategorized"><outline type="rss" text="Other" xmlUrl="https://other.example/rss"/></outline>
</body></opml>"""


class FreshRSSSourcesTests(unittest.TestCase):
    def test_only_mapped_categories_are_read(self):
        self.assertEqual(mod.feeds_from_opml(OPML), [
            ("llm", "Simon", "https://simon.example/atom"),
            ("crypto", "Coin", "https://coin.example/rss"),
        ])

    def test_merge_disables_builtin_rss_and_keeps_other_sources(self):
        defaults = [
            {"id": "simon", "type": "rss", "enabled": True, "url": "https://simon.example/atom",
             "priority": True, "topics": ["llm", "ai-agent"]},
            {"id": "old", "type": "rss", "enabled": True, "url": "https://old.example/rss", "topics": ["crypto"]},
            {"id": "gh", "type": "github", "enabled": True},
        ]
        overlay = [{"id": "gh", "type": "github", "enabled": True},
                   {"id": "freshrss-stale", "type": "rss", "enabled": True, "url": "https://gone.example"}]
        merged = {s["id"]: s for s in mod.merge(defaults, overlay, mod.feeds_from_opml(OPML))}
        self.assertTrue(merged["gh"]["enabled"])
        self.assertFalse(merged["simon"]["enabled"])
        self.assertFalse(merged["old"]["enabled"])
        self.assertNotIn("freshrss-stale", merged)
        added = [s for s in merged.values() if s["id"].startswith("freshrss-")]
        self.assertEqual(len(added), 2)
        simon = next(s for s in added if s["url"] == "https://simon.example/atom")
        self.assertEqual((simon["priority"], simon["topics"]), (True, ["llm", "ai-agent"]))
        coin = next(s for s in added if s["url"] == "https://coin.example/rss")
        self.assertEqual((coin["priority"], coin["topics"]), (False, ["crypto"]))


if __name__ == "__main__":
    unittest.main()
