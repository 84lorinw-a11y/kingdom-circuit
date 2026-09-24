#!/usr/bin/env python3
"""Preserve the organizer's announced 2027 Rock the Pines festival on refresh."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
EVENT = {
    "id": "rock-the-pines-tyler-2027",
    "title": "Rock The Pines 2027",
    "startDate": "2027-04-24",
    "endDate": "2027-04-24",
    "timezone": "America/Chicago",
    "venue": "The Park of East Texas",
    "address": "204 Patton Lane",
    "city": "Tyler", "state": "TX", "country": "US",
    "artists": ["LJ THE MESSENGER", "DEON"],
    "advertisedBilling": ["Skillet", "Stephen Stanley", "Disciple", "LJ THE MESSENGER", "The Protest", "DEON"],
    "officialBill": ["Skillet", "Stephen Stanley", "Disciple", "LJ THE MESSENGER", "The Protest", "DEON"],
    "headliner": "Skillet",
    "eventType": "festival", "status": "scheduled",
    "officialUrl": "https://rockthepines.org/",
    "ticketUrl": "https://rockthepines26.ticketspice.com/rock-the-pines-2027",
    "image": "assets/events/rock-the-pines-logo.png",
    "imageType": "event_artwork", "imageOverride": True,
    "imagePosition": "center", "detailImageLayout": "landscape",
    "imageSource": "Rock the Pines official festival logo",
    "imageSourceUrl": "https://images.squarespace-cdn.com/content/v1/69f817bf0b22fe01858755e4/fcb38e7f-b8b3-4024-aca5-323a760b306a/RTP+transparent2.png?format=1500w",
    "organizer": "Rock The Pines / KVNE",
    "sourceName": "Rock The Pines official 2027 announcement",
    "authority": "official_festival", "confidence": "high", "lineupExplicit": True,
    "firstSeen": "2026-09-24T17:00:00Z", "lastVerified": "2026-09-24T17:00:00Z",
    "notes": "The current homepage announces April 24, 2027 in Tyler and these six performers. More artists are pending. The FAQ and social share banner still describe the old 2026 event; no 2027 time or price is inferred from them.",
    "sources": [{"name": "Rock The Pines official 2027 announcement", "url": "https://rockthepines.org/", "type": "official_festival", "authority": "official_festival", "priority": 112}],
}


def apply(root: Path = ROOT) -> None:
    upcoming = EVENT["endDate"] >= dt.datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
    for relative in ("config/manual-events.json", "events.json", "supplemental-events.json"):
        path = root / relative
        records = json.loads(path.read_text(encoding="utf-8"))
        matches = [r for r in records if str(r.get("id", "")).removeprefix("manual:") == EVENT["id"]]
        records = [r for r in records if r not in matches]
        if relative != "supplemental-events.json" and (upcoming or relative.startswith("config/")):
            event = dict(EVENT)
            if relative == "events.json":
                event["id"] = "manual:" + EVENT["id"]
            event["firstSeen"] = min([EVENT["firstSeen"]] + [r["firstSeen"] for r in matches if r.get("firstSeen")])
            records.append(event)
        records.sort(key=lambda e: (e.get("startDate", ""), e.get("startTime", ""), e.get("title", "")))
        path.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    apply()
    print("Rock the Pines 2027 announcement preserved with both confirmed CHH performers")
