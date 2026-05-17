#!/usr/bin/env python3
"""
Phase 6 — RSS/news auto-capture script.

Reads configured RSS feeds and POSTs each new item as a fleeting note via the
Zettelkasten API.  Deduplication is done by searching for the item URL before
writing; existing notes are skipped silently.

Usage:
    python3 capture-rss.py              # capture all feeds
    python3 capture-rss.py --dry-run   # preview without writing
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import feedparser
import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

load_dotenv(Path(__file__).parent / ".env")
API_BASE = os.getenv("ZETTELKASTEN_API_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("ZETTELKASTEN_API_KEY", "")

FEED_URLS = [
    # Linux / sysadmin
    "https://www.redhat.com/en/rss/blog",
    "https://lwn.net/headlines/rss",
    # Cloud / DevOps
    "https://aws.amazon.com/blogs/aws/feed/",
    "https://cloud.google.com/blog/rss/",
    # Security / CMMC
    "https://www.cisa.gov/news.xml",
    # Add more feeds here
]

MAX_ITEMS_PER_FEED = 5   # newest items to process per run

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger("capture-rss")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HEADERS = {"X-API-Key": API_KEY}


def api_get(path: str, params: dict | None = None) -> dict:
    resp = requests.get(f"{API_BASE}{path}", headers=HEADERS, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, payload: dict) -> dict:
    resp = requests.post(f"{API_BASE}{path}", headers=HEADERS, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


def already_captured(url: str) -> bool:
    """Return True if a note containing this URL already exists."""
    try:
        result = api_get("/search", {"q": url})
        return result.get("count", 0) > 0
    except requests.RequestException:
        return False


def capture_item(entry: feedparser.FeedParserDict, feed_title: str, dry_run: bool) -> bool:
    """Capture one feed entry as a fleeting note.  Returns True if written."""
    title = entry.get("title", "(no title)").strip()
    url = entry.get("link", "").strip()
    summary = entry.get("summary", "").strip()[:600]
    published = entry.get("published", datetime.now().isoformat())

    if not url:
        log.debug("Skipping entry with no URL: %s", title)
        return False

    if already_captured(url):
        log.debug("Already captured: %s", url)
        return False

    body = f"Source: {url}\nFeed: {feed_title}\nPublished: {published}\n\n{summary}"
    payload = {
        "title": title[:100],
        "type": "fleeting",
        "tags": ["auto-capture", "rss"],
        "body": body,
    }

    if dry_run:
        log.info("[DRY-RUN] Would capture: %s", title)
        return True

    try:
        result = api_post("/note", payload)
        log.info("Captured: %s -> %s", title, result.get("file", "?"))
        return True
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 409:
            log.debug("Conflict (already exists): %s", title)
        else:
            log.warning("Failed to capture %r: %s", title, exc)
        return False


def process_feed(feed_url: str, dry_run: bool) -> tuple[int, int]:
    """Parse one feed and capture new items.  Returns (captured, skipped)."""
    log.info("Fetching: %s", feed_url)
    try:
        feed = feedparser.parse(feed_url)
    except Exception as exc:
        log.error("Failed to parse feed %s: %s", feed_url, exc)
        return 0, 0

    feed_title = feed.feed.get("title", feed_url)
    entries = feed.entries[:MAX_ITEMS_PER_FEED]

    captured = skipped = 0
    for entry in entries:
        if capture_item(entry, feed_title, dry_run):
            captured += 1
        else:
            skipped += 1

    return captured, skipped


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Capture RSS feeds as fleeting notes")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--feed", metavar="URL", help="Process a single feed URL")
    args = parser.parse_args()

    if not API_KEY:
        log.error("ZETTELKASTEN_API_KEY not set in .env")
        sys.exit(1)

    # Verify API is reachable
    try:
        api_get("/health")
    except requests.RequestException as exc:
        log.error("Cannot reach API at %s: %s", API_BASE, exc)
        sys.exit(1)

    feeds = [args.feed] if args.feed else FEED_URLS
    total_captured = total_skipped = 0

    for feed_url in feeds:
        c, s = process_feed(feed_url, args.dry_run)
        total_captured += c
        total_skipped += s

    mode = "[DRY-RUN] " if args.dry_run else ""
    log.info("%sDone. Captured: %d  Skipped/existing: %d", mode, total_captured, total_skipped)


if __name__ == "__main__":
    main()
