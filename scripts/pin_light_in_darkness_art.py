#!/usr/bin/env python3
import json
from pathlib import Path

EVENT_ID = "1997479295343"
EVENT_URL = "https://www.eventbrite.com/e/light-in-the-darkness-tickets-1997479295343"
IMAGE = "assets/events/light-in-the-darkness-2026.webp"

matched = 0
for path in (Path("events.json"), Path("supplemental-events.json"), Path("config/manual-events.json")):
    if not path.exists():
        continue
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        continue
    if not isinstance(rows, list):
        continue
    changed = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        urls = " ".join(str(row.get(key) or "") for key in ("ticketUrl", "officialUrl", "announcementUrl"))
        title = str(row.get("title") or "").strip().casefold()
        target = EVENT_ID in urls or (title == "light in the darkness" and str(row.get("startDate") or "") == "2026-10-31")
        if not target:
            continue
        row["image"] = IMAGE
        row["imageType"] = "event_artwork"
        row["imagePosition"] = "center"
        row["imageOverride"] = True
        row["imageSource"] = "Official Eventbrite event artwork"
        row["imageSourceUrl"] = EVENT_URL
        matched += 1
        changed = True
    if changed:
        path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

if matched == 0:
    raise SystemExit("Light in the Darkness event record was not found")
print(f"Pinned official Eventbrite artwork on {matched} event record(s)")
