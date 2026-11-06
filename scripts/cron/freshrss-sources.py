#!/usr/bin/env python3
"""Sync the digest's RSS sources from the FreshRSS categories on TrueNAS.

Runs in the Gateway workspace before the tech-news-digest pipeline. FreshRSS
holds the feed list; the skill still fetches each feed itself. On any FreshRSS
error the previous overlay is kept, so the digest runs on the last known list.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.request
import xml.etree.ElementTree as ET  # trusted LAN FreshRSS; expat resolves no external entities

FRESHRSS = os.environ.get("FRESHRSS_URL", "http://172.17.0.24:30108")
USER = os.environ.get("FRESHRSS_USER", "nabla")
TOKEN_FILE = Path(os.environ.get("FRESHRSS_TOKEN_FILE", "/home/node/.openclaw/credentials/freshrss-rss-token"))
SKILL = Path("skills/tech-news-digest")
DEFAULTS = SKILL / "config/defaults/sources.json"
OVERLAY = SKILL / "workspace/config/tech-news-digest-sources.json"
CATEGORIES = {"LLM": "llm", "AI Agent": "ai-agent", "Crypto": "crypto", "Frontier Tech": "frontier-tech"}


def feeds_from_opml(opml: bytes) -> list[tuple[str, str, str]]:
    """Return (topic, name, url) for each feed of the mapped categories."""
    feeds = []
    for category in ET.fromstring(opml).iter("outline"):
        topic = CATEGORIES.get(category.get("text", ""))
        if topic:
            feeds += [(topic, f.get("text") or f.get("xmlUrl"), f.get("xmlUrl"))
                      for f in category.findall("outline") if f.get("xmlUrl")]
    return feeds


def merge(defaults: list[dict], overlay: list[dict], feeds: list[tuple[str, str, str]]) -> list[dict]:
    """Disable every non-FreshRSS RSS source and add one source per FreshRSS feed."""
    known = {s["url"]: s for s in defaults + overlay if s.get("type") == "rss" and s.get("url")}
    kept = [s if s.get("type") != "rss" else {**s, "enabled": False}
            for s in overlay if not s.get("id", "").startswith("freshrss-")]
    ids = {s.get("id") for s in kept}
    kept += [{"id": s["id"], "type": "rss", "enabled": False}
             for s in defaults if s.get("type") == "rss" and s.get("id") not in ids]
    added = []
    for topic, name, url in feeds:
        old = known.get(url, {})
        same_topic = (old.get("topics") or [None])[0] == topic
        added.append({
            "id": "freshrss-" + hashlib.sha1(url.encode()).hexdigest()[:10],
            "type": "rss", "name": name, "url": url, "enabled": True,
            "priority": bool(old.get("priority")) if same_topic else False,
            "topics": old["topics"] if same_topic else [topic],
            "note": "FreshRSS",
        })
    return kept + added


def main() -> int:
    token = TOKEN_FILE.read_text().strip()
    url = f"{FRESHRSS}/i/?a=opml&user={USER}&token={token}"
    try:
        feeds = feeds_from_opml(urllib.request.urlopen(url, timeout=30).read())
    except Exception as e:  # keep the last overlay rather than lose the digest
        print(f"freshrss_sources=stale error={type(e).__name__}", file=sys.stderr)
        return 0
    if not feeds:
        print("freshrss_sources=stale error=no_feeds", file=sys.stderr)
        return 0
    data = json.loads(OVERLAY.read_text())
    data["sources"] = merge(json.loads(DEFAULTS.read_text())["sources"], data.get("sources", []), feeds)
    tmp = OVERLAY.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    os.chmod(tmp, OVERLAY.stat().st_mode & 0o777)
    os.replace(tmp, OVERLAY)
    counts = {t: sum(1 for f in feeds if f[0] == t) for t in CATEGORIES.values()}
    print("freshrss_sources=" + str(len(feeds)) + " " + " ".join(f"{t}={n}" for t, n in counts.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
