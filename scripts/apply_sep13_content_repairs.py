#!/usr/bin/env python3
"""Durable verified content and image repairs from September 13, 2026."""
from __future__ import annotations

import json
from pathlib import Path

from apply_sep13_requested_events import apply_requested_repairs

ROOT = Path(__file__).resolve().parents[1]
AUDIT_DATE = "2026-09-13"
KURTIS_IMAGE = "assets/artists/kurtis-hoppie-primary.jpg"
MISSION_IMAGE = "assets/artists/mission-primary.jpg"
UNIVERSAL_IMAGE = "assets/events/rock-the-universe-2027.jpg"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def source(name: str, url: str, authority: str) -> dict:
    return {"name": name, "url": url, "type": "manual_verified", "authority": authority, "priority": 112}


TRIBE_ARTISTS = [
    "Key'ijah", "Tha inspiration", "NISSI SHALOM", "SteveUnordinary",
    "Yasmine Jinelle", "JJ Chosen", "Generation Recovery", "IFearGod", "Hy Chu",
]

NEW_EVENTS = {
    "mike-malagies-florida-takeover-miami-2026": {
        "title": "Mike Malagies Florida Takeover (Miami)", "startDate": "2026-10-16",
        "startTime": "18:30", "doorsTime": "18:00", "timezone": "America/New_York",
        "venue": "Black Box Media Miami", "address": "12355 NE 13th Ave Unit #403-404",
        "city": "North Miami", "state": "FL", "country": "US", "artists": ["Mike Malagies"],
        "headliner": "Mike Malagies", "eventType": "concert", "status": "scheduled",
        "ticketUrl": "https://www.ticketsource.com/the-sound-system/mike-malagies-florida-takeover-miami/e-vgxqxl",
        "officialUrl": "https://www.ticketsource.com/the-sound-system/mike-malagies-florida-takeover-miami/e-vgxqxl",
        "image": "https://static.wixstatic.com/media/61a78b_7545031064f049a6843e4c7d0666886f~mv2.jpg/v1/fill/w_327%2Ch_491%2Cal_c%2Cq_80%2Cusm_0.66_1.00_0.01%2Cenc_avif%2Cquality_auto/61a78b_7545031064f049a6843e4c7d0666886f~mv2.jpg",
        "imageType": "artist", "imagePosition": "50% 25%", "imageOverride": True,
        "lineupExplicit": True, "authority": "venue_ticket", "confidence": "high",
        "sourceName": "TicketSource exact event listing",
        "sources": [
            source("TicketSource exact event listing", "https://www.ticketsource.com/the-sound-system/mike-malagies-florida-takeover-miami/e-vgxqxl", "venue_ticket"),
            source("Black Box Media Miami official venue", "https://www.blackboxstudiosmiami.com/event-list", "venue"),
        ], "auditVerified": AUDIT_DATE,
    },
    "rock-the-universe-orlando-2027": {
        "title": "Rock the Universe 2027", "startDate": "2027-01-22", "endDate": "2027-01-23",
        "startTime": "", "timezone": "America/New_York", "venue": "Universal Studios Florida",
        "address": "", "city": "Orlando", "state": "FL", "country": "US",
        "artists": ["1K Phew", "gio.", "Torey D'Shaun"], "headliner": "1K Phew",
        "eventType": "festival", "status": "scheduled",
        "ticketUrl": "https://www.universalorlando.com/web/en/us/things-to-do/events/rock-the-universe",
        "officialUrl": "https://www.universalorlando.com/web/en/us/things-to-do/events/rock-the-universe",
        "image": UNIVERSAL_IMAGE, "imageType": "event_artwork", "imagePosition": "center",
        "imageOverride": True, "lineupExplicit": True, "authority": "official_festival",
        "confidence": "high", "sourceName": "Universal Orlando official Rock the Universe page",
        "performerDays": {"2027-01-22": ["1K Phew"], "2027-01-23": ["gio.", "Torey D'Shaun"]},
        "fullLineup": ["Elevation Worship", "Jamie MacDonald", "Rave Jesus", "Benjamin William Hastings", "Strings & Heart", "1K Phew", "Joseph O'Brien", "Maddi Jane", "John Allan", "Josiah Queen", "Katy Nichole", "Franni Cash", "CAIN", "Megan Woods", "gio.", "Peter Burton", "Sam Wesley", "Torey D'Shaun"],
        "sources": [
            source("Universal Orlando official Rock the Universe page", "https://www.universalorlando.com/web/en/us/things-to-do/events/rock-the-universe", "official_festival"),
            source("FOX 35 lineup report citing Universal Orlando", "https://www.fox35orlando.com/news/universal-orlando-reveals-rock-universe-2027-concert-lineup", "supporting_press"),
        ], "auditVerified": AUDIT_DATE,
    },
}


def patch_event(item: dict) -> None:
    identity = str(item.get("id") or "").removeprefix("manual:")
    if identity == "tribe-fest-rialto-2026":
        item.update({"artists": TRIBE_ARTISTS, "headliner": "Key'ijah", "headliners": TRIBE_ARTISTS[:5],
                     "officialBill": TRIBE_ARTISTS, "auditVerified": AUDIT_DATE})
    if identity == "mission-friends-sacramento-2026":
        item.update({"image": MISSION_IMAGE, "imageType": "artist", "imagePosition": "center 30%",
                     "imageOverride": True, "imageSource": "Mission official YouTube channel",
                     "imageSourceUrl": "https://www.youtube.com/channel/UCBaU_Xh4fyokc-ckyCeYv3w", "auditVerified": AUDIT_DATE})
    artists = {str(x).casefold() for x in item.get("artists") or []}
    if "kurtis hoppie" in artists:
        item.update({"image": KURTIS_IMAGE, "imageType": "artist", "imagePosition": "50% 22%",
                     "imageOverride": True, "imageSource": "Kurtis Hoppie official website",
                     "imageSourceUrl": "https://www.thekurtishoppie.com/", "auditVerified": AUDIT_DATE})


def patch_event_file(path: Path, manual: bool) -> None:
    rows = load(path)
    for row in rows:
        patch_event(row)
    by_id = {str(row.get("id") or "").removeprefix("manual:"): row for row in rows}
    for event_id, event in NEW_EVENTS.items():
        value = dict(event)
        value["id"] = event_id if manual else f"manual:{event_id}"
        if event_id in by_id:
            by_id[event_id].update(value)
        else:
            rows.append(value)
    save(path, rows)


def patch_artists() -> None:
    path = ROOT / "config" / "artists.json"
    rows = load(path)
    kurtis = next(row for row in rows if str(row.get("name", "")).casefold() == "kurtis hoppie")
    kurtis.update({"imageUrl": KURTIS_IMAGE, "imagePosition": "50% 22%", "preferArtistImage": True})
    known = {str(row.get("name", "")).casefold() for row in rows}
    for name in TRIBE_ARTISTS:
        if name.casefold() in known:
            continue
        rows.append({"name": name, "aliases": [name], "enabled": True, "ticketmasterEnabled": False,
                     "category": "core", "monitoringPriority": 3, "topStreamingPriority": False,
                     "socialSearchEnabled": True, "activeStatus": "active_or_unknown",
                     "textMatchEnabled": False, "rosterOrder": len(rows) + 1})
        known.add(name.casefold())
    save(path, rows)


def main() -> None:
    patch_artists()
    patch_event_file(ROOT / "config" / "manual-events.json", True)
    patch_event_file(ROOT / "supplemental-events.json", False)
    patch_event_file(ROOT / "events.json", False)
    apply_requested_repairs()


if __name__ == "__main__":
    main()
