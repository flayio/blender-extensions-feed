#!/usr/bin/env python3
"""Build an RSS feed of Blender Extensions asset libraries.

Scrapes https://extensions.blender.org/asset-libraries/ (newest first), remembers
when each library was first seen in seen.json, and writes feed.xml.
Requires: requests, beautifulsoup4
"""
import json, re, sys
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

import requests
from bs4 import BeautifulSoup

BASE = "https://extensions.blender.org"
URL = f"{BASE}/asset-libraries/?sort_by=-date_approved&page=1"
SEEN = Path("seen.json")
OUT = Path("feed.xml")
SLUG_RE = re.compile(r"^(?:https://extensions\.blender\.org)?/asset-libraries/([^/?#]+)/?$")


def scrape():
    r = requests.get(URL, timeout=30, headers={"User-Agent": "asset-library-rss/1.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    items, seen_slugs = [], set()
    for h3 in soup.find_all("h3"):
        a = h3.find("a", href=SLUG_RE)
        if not a:
            continue
        slug = SLUG_RE.match(a["href"]).group(1)
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        # description = first <p> after the title, if present
        p = h3.find_next("p")
        desc = p.get_text(" ", strip=True) if p else ""
        # author = first author/team link in the same card
        card = h3.find_parent(["li", "div", "article"]) or h3.parent
        auth = card.find("a", href=re.compile(r"/(author|team)/")) if card else None
        items.append({
            "slug": slug,
            "title": a.get_text(strip=True),
            "link": f"{BASE}/asset-libraries/{slug}/",
            "desc": desc,
            "author": auth.get_text(strip=True) if auth else "",
        })
    return items


def main():
    items = scrape()
    if not items:
        sys.exit("No asset libraries found - page layout may have changed.")

    seen = json.loads(SEEN.read_text()) if SEEN.exists() else {}
    now = datetime.now(timezone.utc).isoformat()
    for it in items:
        seen.setdefault(it["slug"], now)
    SEEN.write_text(json.dumps(seen, indent=2, sort_keys=True))

    # newest first-seen at the top
    items.sort(key=lambda i: seen[i["slug"]], reverse=True)

    entries = []
    for it in items:
        pub = format_datetime(datetime.fromisoformat(seen[it["slug"]]))
        body = escape(it["desc"] + (f" (by {it['author']})" if it["author"] else ""))
        entries.append(f"""    <item>
      <title>{escape(it['title'])}</title>
      <link>{it['link']}</link>
      <guid isPermaLink="true">{it['link']}</guid>
      <pubDate>{pub}</pubDate>
      <description>{body}</description>
    </item>""")

    OUT.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Blender Extensions - Asset Libraries</title>
    <link>{BASE}/asset-libraries/</link>
    <description>New asset libraries published on extensions.blender.org</description>
    <lastBuildDate>{format_datetime(datetime.now(timezone.utc))}</lastBuildDate>
{chr(10).join(entries)}
  </channel>
</rss>
""", encoding="utf-8")
    print(f"Wrote {OUT} with {len(items)} items")


if __name__ == "__main__":
    main()
