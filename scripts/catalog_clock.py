"""One Pacific calendar day for a complete publication attempt.

Only catalog eligibility and display dates use this clock. Collection receipts,
schedule claims, audit timestamps and independent live freshness use real time.
The workflow freezes KC_CATALOG_DAY once before source work, so a build that
crosses midnight cannot mix two calendar days.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
import os
from pathlib import Path
import re
from zoneinfo import ZoneInfo

PACIFIC = ZoneInfo("America/Los_Angeles")


def catalog_date() -> date:
    value = os.environ.get("KC_CATALOG_DAY")
    if value is None:
        return datetime.now(PACIFIC).date()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("KC_CATALOG_DAY must be a valid date in YYYY-MM-DD format")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("KC_CATALOG_DAY must be a valid date in YYYY-MM-DD format") from error


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-env", type=Path, required=True)
    args = parser.parse_args(argv)
    # A new attempt must freeze its actual start day, never inherit a stale
    # override from another build or a local replay.
    day = datetime.now(PACIFIC).date().isoformat()
    with args.github_env.open("a", encoding="utf-8") as stream:
        stream.write(f"KC_CATALOG_DAY={day}\n")


if __name__ == "__main__":
    main()
