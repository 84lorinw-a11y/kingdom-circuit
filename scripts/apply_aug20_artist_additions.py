#!/usr/bin/env python3
"""Add the Aug. 20 approved CHH roster expansion and verified future shows.

This is intentionally idempotent. It runs before collection so the newly approved
artists participate in automated discovery, and again on push builds so their
artist pages and verified supplemental shows are present immediately.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTISTS_FILE = ROOT / "config" / "artists.json"
SUPPLEMENTAL_FILE = ROOT / "supplemental-events.json"

APPROVED_ARTISTS = [
    {"name":"Brenno","aliases":["Brenno"],"enabled":True,"ticketmasterEnabled":True,"category":"core","monitoringPriority":1,"topStreamingPriority":False,"socialSearchEnabled":True,"activeStatus":"active_or_unknown","textMatchEnabled":True,"website":"https://www.brennomusic.live/","instagramProfile":"https://www.instagram.com/brennomusic/"},
    {"name":"Shepherd","aliases":["Shepherd","Shepherd."],"enabled":True,"ticketmasterEnabled":False,"category":"core","label":"Familia Forever","monitoringPriority":2,"topStreamingPriority":False,"socialSearchEnabled":True,"activeStatus":"active_or_unknown","textMatchEnabled":False,"website":"https://www.shepherd.live/"},
    {"name":"Kai Uriah","aliases":["Kai Uriah"],"enabled":True,"ticketmasterEnabled":False,"category":"core","monitoringPriority":2,"topStreamingPriority":False,"socialSearchEnabled":True,"activeStatus":"active_or_unknown","textMatchEnabled":True,"website":"https://linktr.ee/itskaiuriah","instagramProfile":"https://www.instagram.com/itskaiuriah/"},
    {"name":"Hyper Fenton","aliases":["Hyper Fenton","Seth Fenton"],"enabled":True,"ticketmasterEnabled":False,"category":"core","monitoringPriority":2,"topStreamingPriority":False,"socialSearchEnabled":True,"activeStatus":"active_or_unknown","textMatchEnabled":True,"website":"https://hyperfenton.com/"},
    {"name":"Brea Miles","aliases":["Brea Miles"],"enabled":True,"ticketmasterEnabled":False,"category":"core","monitoringPriority":2,"topStreamingPriority":False,"socialSearchEnabled":True,"activeStatus":"active_or_unknown","textMatchEnabled":True,"website":"https://www.alwaysbrea.com/"},
    {"name":"Issac Mansfield","aliases":["Issac Mansfield","Isaac Mansfield"],"enabled":True,"ticketmasterEnabled":False,"category":"core","monitoringPriority":2,"topStreamingPriority":False,"socialSearchEnabled":True,"activeStatus":"active_or_unknown","textMatchEnabled":True,"website":"https://www.issacmansfield.com/"},
    {"name":"Tylan1k","aliases":["Tylan1k","tylan1k"],"enabled":True,"ticketmasterEnabled":False,"category":"core","label":"RMG Amplify","monitoringPriority":2,"topStreamingPriority":False,"socialSearchEnabled":True,"activeStatus":"active_or_unknown","textMatchEnabled":True},
    {"name":"Jabari Heavens","aliases":["Jabari Heavens"],"enabled":True,"ticketmasterEnabled":False,"category":"core","monitoringPriority":2,"topStreamingPriority":False,"socialSearchEnabled":True,"activeStatus":"active_or_unknown","textMatchEnabled":True},
    {"name":"Rhema Soul","aliases":["Rhema Soul"],"enabled":True,"ticketmasterEnabled":False,"category":"legacy","label":"Good City Music","monitoringPriority":3,"topStreamingPriority":False,"socialSearchEnabled":False,"activeStatus":"active_or_unknown","textMatchEnabled":False,"website":"http://rhemasoul.com/"},
    {"name":"Shonlock","aliases":["Shonlock"],"enabled":True,"ticketmasterEnabled":False,"category":"legacy","monitoringPriority":3,"topStreamingPriority":False,"socialSearchEnabled":False,"activeStatus":"active_or_unknown","textMatchEnabled":False,"website":"https://www.shonlock.com/"},
    {"name":"Viktory","aliases":["Viktory"],"enabled":True,"ticketmasterEnabled":False,"category":"legacy","monitoringPriority":3,"topStreamingPriority":False,"socialSearchEnabled":False,"activeStatus":"active_or_unknown","textMatchEnabled":False},
    {"name":"T-Bone","aliases":["T-Bone","T Bone","Rene Sotomayor"],"enabled":True,"ticketmasterEnabled":False,"category":"legacy","monitoringPriority":3,"topStreamingPriority":False,"socialSearchEnabled":False,"activeStatus":"active_or_unknown","textMatchEnabled":False,"website":"https://houseoftbone.com/"},
    {"name":"Bishop Freeze","aliases":["Bishop Freeze"],"enabled":True,"ticketmasterEnabled":False,"category":"legacy","monitoringPriority":3,"topStreamingPriority":False,"socialSearchEnabled":False,"activeStatus":"active_or_unknown","textMatchEnabled":False,"website":"https://www.sozomissions.com/music/bishop-freeze"},
]

VERIFIED_EVENTS = [
    {
        "id":"supplemental:brenno-awake-conference-2026",
        "title":"Awake Conference",
        "startDate":"2026-10-10","startTime":"","venue":"Location TBD","address":"","city":"Centreville","state":"MI","country":"US",
        "artists":["Brenno"],"headliner":"Brenno","eventType":"concert","status":"scheduled",
        "ticketUrl":"https://www.facebook.com/people/AWAKE-Youth-Conference/100084206085878/","officialUrl":"https://www.brennomusic.live/","image":"","price":"",
        "sourceName":"Brenno official upcoming shows","authority":"artist_calendar","confidence":"high","lineupExplicit":True,
        "sources":[{"name":"Brenno official upcoming shows","url":"https://www.brennomusic.live/","type":"manual_verified","authority":"artist_calendar","priority":100}]
    },
    {
        "id":"supplemental:brenno-overflow-conference-2026",
        "title":"Overflow Conference",
        "startDate":"2026-10-17","startTime":"","venue":"Location TBD","address":"","city":"Buffalo","state":"NY","country":"US",
        "artists":["Brenno"],"headliner":"Brenno","eventType":"concert","status":"scheduled",
        "ticketUrl":"https://www.tickettailor.com/events/ablazemovement","officialUrl":"https://www.brennomusic.live/","image":"","price":"",
        "sourceName":"Brenno official upcoming shows","authority":"artist_calendar","confidence":"high","lineupExplicit":True,
        "sources":[{"name":"Brenno official upcoming shows","url":"https://www.brennomusic.live/","type":"manual_verified","authority":"artist_calendar","priority":100}]
    },
    {
        "id":"supplemental:issac-mansfield-saved-by-grace-2026",
        "title":"SAVED BY GRACE",
        "startDate":"2026-10-03","startTime":"18:00","venue":"2842 S Alafaya Trail Ste 150","address":"2842 S Alafaya Trail Ste 150","city":"Orlando","state":"FL","country":"US",
        "artists":["Issac Mansfield"],"headliner":"Issac Mansfield","eventType":"concert","status":"scheduled",
        "ticketUrl":"https://www.bandsintown.com/e/108746397-issac-mansfield-at-2842-s-alafaya-trail-ste-150-orlando-fl-32828?came_from=274","officialUrl":"https://www.bandsintown.com/e/108746397-issac-mansfield-at-2842-s-alafaya-trail-ste-150-orlando-fl-32828?came_from=274","image":"","price":"Free; optional VIP tiers",
        "sourceName":"Issac Mansfield verified Bandsintown event","authority":"artist_calendar","confidence":"high","lineupExplicit":True,
        "sources":[{"name":"Issac Mansfield Bandsintown","url":"https://www.bandsintown.com/e/108746397-issac-mansfield-at-2842-s-alafaya-trail-ste-150-orlando-fl-32828?came_from=274","type":"manual_verified","authority":"artist_calendar","priority":100}]
    },
]


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def norm(value) -> str:
    return str(value or "").strip().casefold()


def main() -> int:
    artists = load(ARTISTS_FILE, [])
    supplemental = load(SUPPLEMENTAL_FILE, [])
    if not isinstance(artists, list) or not isinstance(supplemental, list):
        raise SystemExit("Expected artist and supplemental JSON arrays")

    by_name = {norm(a.get("name")): a for a in artists if isinstance(a, dict)}
    max_order = max([int(a.get("rosterOrder") or 0) for a in artists if isinstance(a, dict)] or [0])
    added = 0
    for record in APPROVED_ARTISTS:
        key = norm(record["name"])
        if key in by_name:
            existing = by_name[key]
            for field, value in record.items():
                if field != "rosterOrder":
                    existing[field] = value
            continue
        max_order += 1
        new_record = dict(record)
        new_record["rosterOrder"] = max_order
        artists.append(new_record)
        by_name[key] = new_record
        added += 1

    # Ensure Brenno is attached to the already-published Beyond The Walls 3 record when present.
    for collection in (supplemental, load(ROOT / "events.json", [])):
        if not isinstance(collection, list):
            continue
        for event in collection:
            if not isinstance(event, dict):
                continue
            if str(event.get("startDate") or "") == "2026-11-07" and norm(event.get("city")) == "cleveland" and "beyond the walls" in norm(event.get("title")):
                names = list(event.get("artists") or [])
                if not any(norm(name) == "brenno" for name in names):
                    names.append("Brenno")
                    event["artists"] = names

    event_ids = {norm(e.get("id")) for e in supplemental if isinstance(e, dict)}
    for event in VERIFIED_EVENTS:
        if norm(event["id"]) not in event_ids:
            supplemental.append(event)
            event_ids.add(norm(event["id"]))

    artists.sort(key=lambda a: int(a.get("rosterOrder") or 999999))
    supplemental.sort(key=lambda e: (str(e.get("startDate") or "9999-12-31"), norm(e.get("title"))))
    write(ARTISTS_FILE, artists)
    write(SUPPLEMENTAL_FILE, supplemental)

    missing = [r["name"] for r in APPROVED_ARTISTS if norm(r["name"]) not in {norm(a.get("name")) for a in artists if isinstance(a, dict)}]
    if missing:
        raise SystemExit(f"Approved artists missing after update: {missing}")
    print(f"Approved artist expansion applied: {added} new artist(s); {len(APPROVED_ARTISTS)} ensured; {len(VERIFIED_EVENTS)} verified supplemental event(s) ensured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
