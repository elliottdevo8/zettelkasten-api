#!/usr/bin/env python3
"""
Phase 6 — Daily journal auto-creation script.

Creates today's Markdown journal in 07-Journals/ using the same template
logic as scripts/daily-journal.py.  Idempotent: skips if today's file
already exists.  Designed to be called by a systemd timer at boot or
a scheduled time.

Usage:
    python3 capture-daily-journal.py
    python3 capture-daily-journal.py --date 2026-05-15
"""

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_DIR = Path(os.getenv("ZETTELKASTEN_BASE_DIR", str(Path.home() / "Documents/SelfDevelopment")))
TEMPLATE_PATH = BASE_DIR / "06-Templates" / "Daily-Journal-Template.md"
JOURNAL_DIR = BASE_DIR / "07-Journals"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def build_journal_content(target_date: date) -> str:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    date_str = target_date.strftime("%Y-%m-%d")
    day_of_week = target_date.strftime("%A")
    content = template.replace("[YYYY-MM-DD]", date_str)
    content = content.replace("[Day of Week]", day_of_week)
    content = content.replace("[YYYY-MM-DD]\n**Created:** [YYYY-MM-DD]", f"{date_str}\n**Created:** {date_str}")
    return content


def get_fleeting_notes(target_date: date) -> list[Path]:
    yesterday = target_date - timedelta(days=1)
    fleeting_dir = BASE_DIR / "05-Zettelkasten" / "Fleeting"
    if not fleeting_dir.exists():
        return []
    prefix = yesterday.strftime("%Y-%m-%d")
    return sorted(fleeting_dir.glob(f"{prefix}*"))


def create_journal(target_date: date) -> tuple[Path, bool]:
    """Create journal file.  Returns (path, created).  created=False if already existed."""
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    date_str = target_date.strftime("%Y-%m-%d")
    journal_path = JOURNAL_DIR / f"{date_str}-Daily-Journal.md"

    if journal_path.exists():
        return journal_path, False

    content = build_journal_content(target_date)
    journal_path.write_text(content, encoding="utf-8")
    return journal_path, True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Auto-create today's daily journal")
    parser.add_argument("--date", metavar="YYYY-MM-DD", help="Target date (default: today)")
    args = parser.parse_args()

    if args.date:
        try:
            target_date = date.fromisoformat(args.date)
        except ValueError:
            print(f"Error: Invalid date '{args.date}'. Use YYYY-MM-DD", file=sys.stderr)
            sys.exit(1)
    else:
        target_date = date.today()

    try:
        journal_path, created = create_journal(target_date)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if created:
        print(f"Created: {journal_path}")
    else:
        print(f"Already exists: {journal_path}")

    fleeting = get_fleeting_notes(target_date)
    if fleeting:
        yesterday = target_date - timedelta(days=1)
        print(f"\nReminder: {len(fleeting)} unprocessed fleeting note(s) from {yesterday}:")
        for note in fleeting[:5]:
            print(f"  - {note.name}")
        if len(fleeting) > 5:
            print(f"  ... and {len(fleeting) - 5} more")


if __name__ == "__main__":
    main()
