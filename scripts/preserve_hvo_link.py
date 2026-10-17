#!/usr/bin/env python3
"""Existing reviewed event guard, shared by first attempt and race-safe replay."""
import json
from pathlib import Path

EVENTBRITE = "https://www.eventbrite.com/e/hvo-fest-tickets-1987360837764"
INSTAGRAM = "https://www.instagram.com/reel/DblfWwWu062/"
IDS = {"hvo-fest-2026-los-angeles", "manual:hvo-fest-2026-los-angeles"}

changed_files = []
for relative in ("config/manual-events.json", "events.json", "supplemental-events.json"):
    path = Path(relative)
    if not path.exists():
        continue
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        continue
    changed = False
    for event in data:
        if not isinstance(event, dict):
            continue
        if event.get("id") not in IDS and event.get("title") != "HVO Fest 2026":
            continue
        if event.get("officialUrl") != EVENTBRITE:
            event["officialUrl"] = EVENTBRITE
            changed = True
        if event.get("ticketUrl") != EVENTBRITE:
            event["ticketUrl"] = EVENTBRITE
            changed = True
        if event.get("announcementUrl") != INSTAGRAM:
            event["announcementUrl"] = INSTAGRAM
            changed = True
    if changed:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        changed_files.append(relative)

print("Updated:", ", ".join(changed_files) if changed_files else "nothing")

