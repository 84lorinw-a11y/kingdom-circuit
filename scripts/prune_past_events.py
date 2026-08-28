#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
from datetime import datetime
from zoneinfo import ZoneInfo

# Use Pacific time for the rollover so a show dated "today" is never removed
# while it could still be happening anywhere in the continental U.S.
SITE_ROLLOVER_TZ = ZoneInfo("America/Los_Angeles")
EVENT_JSON_FILES = ("events.json", "supplemental-events.json")


def today_cutoff() -> str:
    return datetime.now(SITE_ROLLOVER_TZ).date().isoformat()


def load_json(path: pathlib.Path) -> list:
    if not path.is_file():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise SystemExit(f"Expected a JSON array: {path}")
    return value


def write_json(path: pathlib.Path, value: list) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def event_last_date(event: dict) -> str:
    return str(event.get("endDate") or event.get("startDate") or "").strip()[:10]


def is_past_event(event: dict, cutoff: str) -> bool:
    last_date = event_last_date(event)
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", last_date)) and last_date < cutoff


def prune_json_file(path: pathlib.Path, cutoff: str) -> tuple[int, int]:
    events = load_json(path)
    kept: list = []
    removed = 0
    for event in events:
        if isinstance(event, dict) and is_past_event(event, cutoff):
            removed += 1
            continue
        kept.append(event)
    if removed:
        write_json(path, kept)
    return removed, len(kept)


def page_last_date(text: str) -> str | None:
    # Prefer endDate for multi-day events. Generated event pages expose these in JSON-LD.
    end_dates = re.findall(r'"endDate"\s*:\s*"(\d{4}-\d{2}-\d{2})', text, flags=re.I)
    if end_dates:
        return max(end_dates)
    start_dates = re.findall(r'"startDate"\s*:\s*"(\d{4}-\d{2}-\d{2})', text, flags=re.I)
    return max(start_dates) if start_dates else None


def remove_past_event_pages(root: pathlib.Path, cutoff: str) -> set[str]:
    removed: set[str] = set()
    event_root = root / "event"
    if not event_root.is_dir():
        return removed
    for page in list(event_root.glob("*/index.html")):
        text = page.read_text(encoding="utf-8", errors="ignore")
        last_date = page_last_date(text)
        if last_date and last_date < cutoff:
            removed.add(page.parent.name.casefold())
            shutil.rmtree(page.parent)
    return removed


CARD_RE = re.compile(
    r'<article\b(?=[^>]*class=["\'][^"\']*\bevent-card\b[^"\']*["\'])[^>]*>.*?</article>',
    flags=re.I | re.S,
)


def event_slug_from_card(block: str) -> str | None:
    match = re.search(r'href=["\']/event/([^/]+)/["\']', block, flags=re.I)
    return match.group(1).casefold() if match else None


def remove_stale_cards(root: pathlib.Path, removed_slugs: set[str]) -> int:
    if not removed_slugs:
        return 0
    removed_cards = 0
    for page in root.rglob("*.html"):
        text = page.read_text(encoding="utf-8", errors="ignore")
        original = text

        def repl(match: re.Match[str]) -> str:
            nonlocal removed_cards
            block = match.group(0)
            slug = event_slug_from_card(block)
            if slug and slug in removed_slugs:
                removed_cards += 1
                return ""
            return block

        text = CARD_RE.sub(repl, text)
        if text != original:
            page.write_text(text, encoding="utf-8")
    return removed_cards


def clean_sitemap(root: pathlib.Path, removed_slugs: set[str]) -> int:
    path = root / "sitemap.xml"
    if not path.is_file() or not removed_slugs:
        return 0
    text = path.read_text(encoding="utf-8")
    original = text
    removed = 0
    for slug in sorted(removed_slugs):
        pattern = re.compile(
            rf'<url>\s*<loc>https://kingdomcircuit\.com/event/{re.escape(slug)}/?</loc>.*?</url>\s*',
            flags=re.I | re.S,
        )
        text, count = pattern.subn("", text)
        removed += count
    if text != original:
        path.write_text(text, encoding="utf-8")
    return removed


def verify_site(root: pathlib.Path, cutoff: str, removed_slugs: set[str]) -> None:
    failures: list[str] = []

    for name in EVENT_JSON_FILES:
        path = root / name
        for event in load_json(path):
            if isinstance(event, dict) and is_past_event(event, cutoff):
                failures.append(f"past JSON event remains in {name}: {event.get('title')} {event_last_date(event)}")

    event_root = root / "event"
    if event_root.is_dir():
        for page in event_root.glob("*/index.html"):
            text = page.read_text(encoding="utf-8", errors="ignore")
            last_date = page_last_date(text)
            if last_date and last_date < cutoff:
                failures.append(f"past event page remains: {page} ({last_date})")

    if removed_slugs:
        for page in root.rglob("*.html"):
            text = page.read_text(encoding="utf-8", errors="ignore").casefold()
            for slug in removed_slugs:
                if f'/event/{slug}/' in text:
                    # A non-card reference to a deleted page is still a broken internal link.
                    failures.append(f"reference to removed event remains: {page} -> {slug}")
                    if len(failures) >= 25:
                        break
            if len(failures) >= 25:
                break

    if failures:
        raise SystemExit("Past-event pruning verification failed:\n" + "\n".join(failures[:25]))


def prune_source(root: pathlib.Path, cutoff: str) -> dict:
    report = {"cutoff": cutoff, "mode": "source", "files": {}}
    total_removed = 0
    for name in EVENT_JSON_FILES:
        removed, kept = prune_json_file(root / name, cutoff)
        report["files"][name] = {"removed": removed, "kept": kept}
        total_removed += removed
    report["removed"] = total_removed
    return report


def prune_site(root: pathlib.Path, cutoff: str) -> dict:
    report = {"cutoff": cutoff, "mode": "site", "files": {}}
    total_json_removed = 0
    for name in EVENT_JSON_FILES:
        removed, kept = prune_json_file(root / name, cutoff)
        report["files"][name] = {"removed": removed, "kept": kept}
        total_json_removed += removed

    removed_slugs = remove_past_event_pages(root, cutoff)
    removed_cards = remove_stale_cards(root, removed_slugs)
    sitemap_entries = clean_sitemap(root, removed_slugs)
    verify_site(root, cutoff, removed_slugs)

    report.update({
        "jsonEventsRemoved": total_json_removed,
        "eventPagesRemoved": len(removed_slugs),
        "eventCardsRemoved": removed_cards,
        "sitemapEntriesRemoved": sitemap_entries,
    })
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove completed Kingdom Circuit events from public data and generated pages.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--source", metavar="DIR", help="Prune source events.json and supplemental-events.json before build")
    mode.add_argument("--site", metavar="DIR", help="Prune the final generated deployment artifact")
    parser.add_argument("--cutoff", help="Override YYYY-MM-DD cutoff for testing")
    args = parser.parse_args()

    cutoff = args.cutoff or today_cutoff()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", cutoff):
        raise SystemExit(f"Invalid cutoff date: {cutoff}")

    root = pathlib.Path(args.source or args.site).resolve()
    report = prune_source(root, cutoff) if args.source else prune_site(root, cutoff)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
