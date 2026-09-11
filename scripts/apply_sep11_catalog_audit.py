#!/usr/bin/env python3
"""Apply the verified September 11, 2026 Kingdom Circuit catalog audit.

This file is intentionally authoritative for the confirmed additions and lineup
repairs in this audit. It is safe to run repeatedly and removes duplicate alias
rows while preserving unrelated events.
"""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS_FILE = ROOT / "events.json"
SUPPLEMENTAL_FILE = ROOT / "supplemental-events.json"
MANUAL_FILE = ROOT / "config" / "manual-events.json"
ARTISTS_FILE = ROOT / "config" / "artists.json"

BLOCKED_ARTISTS = {"madison ryann ward"}
AUDIT_DATE = "2026-09-11"


def norm(value: object) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def load(path: Path, fallback):
    if not path.exists():
        return deepcopy(fallback)
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def source(name: str, url: str, authority: str = "manual_verified", priority: int = 112) -> dict:
    return {
        "name": name,
        "url": url,
        "type": "manual_verified",
        "authority": authority,
        "priority": priority,
    }


def base_event(**kwargs) -> dict:
    item = {
        "title": kwargs["title"],
        "startDate": kwargs["startDate"],
        "startTime": kwargs.get("startTime", ""),
        "timezone": kwargs.get("timezone", ""),
        "venue": kwargs.get("venue", ""),
        "address": kwargs.get("address", ""),
        "city": kwargs.get("city", ""),
        "state": kwargs.get("state", ""),
        "country": "US",
        "artists": kwargs["artists"],
        "headliner": kwargs.get("headliner") or kwargs["artists"][0],
        "eventType": kwargs.get("eventType", "concert"),
        "status": "scheduled",
        "ticketUrl": kwargs.get("ticketUrl", kwargs["officialUrl"]),
        "officialUrl": kwargs["officialUrl"],
        "image": kwargs.get("image", ""),
        "price": kwargs.get("price", ""),
        "sourceName": kwargs["sourceName"],
        "authority": kwargs.get("authority", "official_event"),
        "confidence": "high",
        "lineupExplicit": True,
        "sources": kwargs.get("sources") or [source(kwargs["sourceName"], kwargs["officialUrl"], kwargs.get("authority", "official_event"))],
        "auditVerified": AUDIT_DATE,
    }
    if kwargs.get("endDate"):
        item["endDate"] = kwargs["endDate"]
    if item["image"]:
        item["imageType"] = "event_artwork"
        item["imagePosition"] = "center"
        item["imageOverride"] = True
    if kwargs.get("officialBill"):
        item["officialBill"] = kwargs["officialBill"]
    if kwargs.get("notes"):
        item["notes"] = kwargs["notes"]
    return item


NEW_EVENTS = [
    ("flavor-fest-2026-saturday-concerts", base_event(
        title="Flavor Fest 2026 — Saturday Concerts",
        startDate="2026-11-07", startTime="19:00", timezone="America/New_York",
        venue="Crossover Church", address="1235 Fowler Ave", city="Tampa", state="FL",
        artists=["Lecrae", "Biancallove", "C4 Crotona", "Monster Tarver"], headliner="Lecrae",
        eventType="festival", officialUrl="https://www.flavorfest.org/",
        ticketUrl="https://flavorfest.ticketspice.com/full-conference-",
        image="https://images.squarespace-cdn.com/content/v1/65b435646b1eae535f97c6a3/989d4d2e-f454-4a1b-99df-cc78cf6e6749/FF26-Promo-Saturday-Night.jpg",
        sourceName="Flavor Fest official Saturday poster",
        authority="official_festival",
        officialBill=["Lecrae", "Biancallove", "Gifted Hands", "Monster Tarver", "C4 Crotona"],
        notes="Yung Kriss and Gifted Hands have conflicting poster/schedule day assignments and are not newly associated here pending resolution.",
    )),
    ("future-legacy-hip-hop-showcase-nashville-2026", base_event(
        title="Future Legacy Hip-Hop Showcase",
        startDate="2026-10-04", startTime="18:30", timezone="America/Chicago",
        venue="Cannery Hall — Row One Stage", address="1 Cannery Row", city="Nashville", state="TN",
        artists=["1K Phew", "Don Ready", "LaNell Grant", "Nathan Davis Jr.", "Trendsetter Sense"], headliner="1K Phew",
        officialUrl="https://www.axs.com/events/1580749/future-legacy-hip-hop-showcase-tickets",
        ticketUrl="https://www.axs.com/events/1580749/future-legacy-hip-hop-showcase-tickets",
        image="https://images.discovery-prod.axs.com/2026/08/uploadedimage_6a871ac3abd11.jpg",
        sourceName="AXS / GMA official Future Legacy listing",
        authority="venue_ticket",
        sources=[
            source("AXS official event", "https://www.axs.com/events/1580749/future-legacy-hip-hop-showcase-tickets", "venue_ticket", 94),
            source("GMA Dove Week official schedule", "https://gospelmusic.org/news/dove-week-2026-see-the-schedule", "official_event", 100),
        ],
        officialBill=["ADIA", "Don Ready", "DJ Trendsetter", "LaNell Grant", "Nathan Davis Jr.", "1K Phew"],
        notes="DJ Trendsetter is associated with roster artist Trendsetter Sense based on established professional naming as DJ Trendsetter Sense.",
    )),
    ("miles-cj-zion-ultra-lounge-chandler-2026", base_event(
        title="Miles Minnick & CJ Emulous at Zion Ultra Lounge",
        startDate="2026-12-05", startTime="", timezone="America/Phoenix",
        venue="Zion Ultra Lounge", address="2301 S Stearman Dr", city="Chandler", state="AZ",
        artists=["Miles Minnick", "CJ Emulous"], headliner="Miles Minnick",
        officialUrl="https://www.cjemulous.com/event-details/zion-ultra-lounge-w-miles-minnick-cj-emulous",
        sourceName="CJ Emulous official calendar",
        authority="artist_calendar",
    )),
    ("fountain-fest-wv-2026", base_event(
        title="Fountain Fest WV 2026",
        startDate="2026-09-18", endDate="2026-09-19", startTime="20:00", timezone="America/New_York",
        venue="Orr's Farm Market", address="", city="Martinsburg", state="WV",
        artists=["Rare of Breed"], headliner="Rare of Breed", eventType="festival",
        officialUrl="https://fountainfestwv.com/",
        ticketUrl="https://my.onecause.com/event/organizations/0908e5f7-6980-4a38-8fc5-456d973dcdce/events/vevt:62b43d8b-59e2-479d-a013-fa697f27e51c/home/story",
        sourceName="Fountain Fest WV official lineup",
        authority="official_festival",
        notes="Rare of Breed performs Friday September 18 at 8 PM; festival continues September 19.",
    )),
    ("mission-friends-sacramento-2026", base_event(
        title="Mission and Special Guests",
        startDate="2026-10-17", startTime="18:30", timezone="America/Los_Angeles",
        venue="Victory Outreach South Sacramento", address="6831 Savings Pl", city="Sacramento", state="CA",
        artists=["Mission"], headliner="Mission",
        officialUrl="https://www.bandsintown.com/e/108816740-mission-at-victory-outreach-south-sacramento",
        ticketUrl="https://www.bandsintown.com/e/108816740-mission-at-victory-outreach-south-sacramento",
        sourceName="Mission official Bandsintown event",
        authority="artist_calendar",
    )),
    ("mayia-boxyard-saturdaze-2026", base_event(
        title="Boxyard Saturdaze",
        startDate="2026-10-10", startTime="12:30", timezone="America/New_York",
        venue="Boxyard RTP — BeatBox Stage", address="", city="Durham", state="NC",
        artists=["MAYIA"], headliner="MAYIA",
        officialUrl="https://mayiawarren.org/go/bandsintown/21578/event/108885203",
        sourceName="MAYIA official calendar",
        authority="artist_calendar",
        officialBill=["DJ Watty Tha Shepherd", "MAYIA WARREN"],
    )),
    ("mayia-nc-state-fair-2026", base_event(
        title="MAYIA at the NC State Fair",
        startDate="2026-10-17", startTime="10:00", timezone="America/New_York",
        venue="Heritage Circle Stage — NC State Fairgrounds", address="", city="Raleigh", state="NC",
        artists=["MAYIA"], headliner="MAYIA",
        officialUrl="https://mayiawarren.org/go/bandsintown/21578/event/108885151",
        sourceName="MAYIA official calendar",
        authority="artist_calendar",
        notes="One event with two confirmed acoustic sets: 10–11 AM and 12–1 PM.",
    )),
    ("cj-emulous-syatp-sierra-vista-2026", base_event(
        title="SYATP Concert",
        startDate="2026-09-23", startTime="19:00", timezone="America/Phoenix",
        venue="Shiloh Christian Ministries", address="1519 S Ave Del Sol", city="Sierra Vista", state="AZ",
        artists=["CJ Emulous"], headliner="CJ Emulous",
        officialUrl="https://www.cjemulous.com/event-details/syatp-concert-w-cj-emulous",
        image="https://static.wixstatic.com/media/9c331a_e63115b208054353a76258a4897ad76c~mv2.jpeg/v1/fill/w_980%2Ch_653%2Cal_c%2Cq_85%2Cusm_0.66_1.00_0.01%2Cenc_auto/9c331a_e63115b208054353a76258a4897ad76c~mv2.jpeg",
        sourceName="CJ Emulous official calendar",
        authority="artist_calendar",
    )),
    ("cj-emulous-live-loud-chico-2026", base_event(
        title="Live Loud",
        startDate="2026-10-07", startTime="19:00", timezone="America/Los_Angeles",
        venue="2801 Notre Dame Blvd", address="2801 Notre Dame Blvd", city="Chico", state="CA",
        artists=["CJ Emulous"], headliner="CJ Emulous",
        officialUrl="https://www.cjemulous.com/event-details/live-loud-w-cj-emulous",
        image="https://static.wixstatic.com/media/9c331a_394502e64a45489e872ee2b71bb1a0de~mv2.jpg/v1/fill/w_980%2Ch_543%2Cal_c%2Cq_85%2Cusm_0.66_1.00_0.01%2Cenc_auto/9c331a_394502e64a45489e872ee2b71bb1a0de~mv2.jpg",
        sourceName="CJ Emulous official calendar",
        authority="artist_calendar",
    )),
    ("cj-emulous-turlock-back-to-school-2026", base_event(
        title="Teen Club Kickoff / Back to School Concert",
        startDate="2026-10-12", startTime="18:00", timezone="America/Los_Angeles",
        venue="Westside Ministries", address="950 Columbia Ave", city="Turlock", state="CA",
        artists=["CJ Emulous", "Lul DreDay"], headliner="CJ Emulous",
        officialUrl="https://www.cjemulous.com/event-details/back-to-school-concert-w-cj-emulous-1",
        image="https://static.wixstatic.com/media/9c331a_7832125534df4c06b583f033fe19273e~mv2.png",
        sourceName="CJ Emulous official calendar and event flyer",
        authority="artist_calendar",
        officialBill=["CJ Emulous", "Lul DreDay", "MikeySoChristian"],
    )),
    ("cj-emulous-kickback-grand-prairie-2026", base_event(
        title="The Kickback",
        startDate="2026-11-14", startTime="19:00", timezone="America/Chicago",
        venue="2305 SE 14th St", address="2305 SE 14th St", city="Grand Prairie", state="TX",
        artists=["CJ Emulous"], headliner="CJ Emulous",
        officialUrl="https://www.cjemulous.com/event-details/the-kickback-w-cj-emulous",
        sourceName="CJ Emulous official calendar",
        authority="artist_calendar",
    )),
    ("alex-zurdo-zona-zero-san-juan-2026", base_event(
        title="Alex Zurdo: Zona Zero",
        startDate="2026-10-18", startTime="18:00", timezone="America/Puerto_Rico",
        venue="Coliseo de Puerto Rico", address="500 Arterial B", city="San Juan", state="PR",
        artists=["Alex Zurdo"], headliner="Alex Zurdo",
        officialUrl="https://www.coliseodepuertorico.com/alexzurdozonazero/",
        ticketUrl="https://choli.ticketera.com/event/alex-zurdo-zona-cero-6dn2x2",
        sourceName="Coliseo de Puerto Rico official event",
        authority="venue_ticket",
    )),
    ("jay-kalyl-desde-antes-rockville-centre-2026", base_event(
        title="Jay Kalyl — Desde Antes Tour",
        startDate="2026-10-03", startTime="", timezone="America/New_York",
        venue="Word of Life Ministries", address="430 DeMott Ave", city="Rockville Centre", state="NY",
        artists=["Jay Kalyl"], headliner="Jay Kalyl",
        officialUrl="https://boletoslive.com/jay-kalyl/",
        ticketUrl="https://boletoslive.com/jay-kalyl/",
        sourceName="Boletos Live official event",
        authority="venue_ticket",
        notes="Official page gives conflicting 4:00 PM and 7:30 PM start times; start time intentionally left unspecified.",
    )),
]

EXISTING_PATCHES = {
    "ticketmaster:k7vGF_dl6_HDp": {
        "addArtists": ["Tommy Zuko", "CJ Emulous"],
        "source": source("CJ Emulous official New Mainstream Tour calendar", "https://www.cjemulous.com/event-details/new-mainstream-tour-w-miles-minnick-tommy-zuko-1-21", "artist_calendar", 100),
    },
    "official:64bbcd477c3a36104df3": {
        "title": "Kingdom Choice Awards 2026",
        "replaceArtists": ["Anike", "Don Ready", "Dante' Pride", "Childlike CiCi", "Yung Kriss", "Datin", "BigBreeze", "C4 Crotona", "MAYIA", "Brinson"],
        "image": "https://images.zoogletools.com/s:bzglfiles/u/63036/e9f653372df147d18026413fbf37bc4eed9c7e01/original/2026-kca-flyer-final-master.jpg/!!/b:W1sicmVzaXplIiwxMDAwXSxbIm1heCJdLFsid2UiXV0=/meta:eyJzcmNCdWNrZXQiOiJiemdsZmlsZXMifQ==.jpg",
        "source": source("Kingdom Choice Awards official 2026 poster", "https://kingdomchoiceawards.org/", "official_event", 100),
        "officialBill": ["Anike", "Childlike CiCi", "Yung Kriss", "Don Ready", "Big Breeze", "Datin", "Brinson & Godchaserz", "Dante Pride", "C4 Crotona", "Range The Artist", "Dwayne Fyah", "MAYIA WARREN", "Marcel Patillo", "Craig Watson", "Paito", "MICA"],
        "notes": "MICA remains an unlinked bill name pending confirmation that it is the tracked roster artist mica.",
    },
    "manual:flavor-fest-2026-friday-concerts": {
        "aliases": ["flavor-fest-2026-friday-concerts"],
        "addArtists": ["TRU-SERVA", "VVS Big Rock", "Lyric The Geenyus", "MAYIA"],
        "image": "https://images.squarespace-cdn.com/content/v1/65b435646b1eae535f97c6a3/a2407af7-a012-4df1-8d42-d247ab82cd8b/FF26-Promo-Friday-Night%2B%281%29.jpg",
        "source": source("Flavor Fest official Friday poster", "https://www.flavorfest.org/", "official_festival", 106),
    },
    "official:12ef07b891bbeeefbcb1": {
        "addArtists": ["CJ Emulous"],
        "source": source("CJ Emulous official New Mainstream Tour calendar", "https://www.cjemulous.com/event-details/new-mainstream-tour-w-miles-minnick-tommy-zuko-22", "artist_calendar", 100),
    },
}


def remove_blocked_artists(items: list[dict]) -> tuple[list[dict], int]:
    cleaned: list[dict] = []
    changes = 0
    for original in items:
        if not isinstance(original, dict):
            continue
        event = deepcopy(original)
        before = list(event.get("artists") or [])
        artists = [a for a in before if norm(a) not in BLOCKED_ARTISTS]
        if artists != before:
            changes += 1
            event["artists"] = artists
        if norm(event.get("headliner")) in BLOCKED_ARTISTS:
            if artists:
                event["headliner"] = artists[0]
                changes += 1
            else:
                changes += 1
                continue
        if not artists and before:
            changes += 1
            continue
        cleaned.append(event)
    return cleaned, changes


def loose_match(current: dict, target: dict) -> bool:
    if current.get("startDate") != target.get("startDate"):
        return False
    if norm(current.get("city")) != norm(target.get("city")):
        return False
    current_artists = {norm(a) for a in current.get("artists") or []}
    target_artists = {norm(a) for a in target.get("artists") or []}
    if current_artists & target_artists:
        return True
    current_title = norm(current.get("title"))
    target_title = norm(target.get("title"))
    return bool(current_title and target_title and (current_title in target_title or target_title in current_title))


def upsert_new(items: list[dict], target: dict, canonical_id: str, aliases: set[str]) -> int:
    match_indexes = [
        i for i, current in enumerate(items)
        if str(current.get("id") or "") in aliases or loose_match(current, target)
    ]
    value = deepcopy(target)
    value["id"] = canonical_id
    if not match_indexes:
        items.append(value)
        return 1
    first = match_indexes[0]
    existing = items[first]
    merged = deepcopy(existing)
    for key, val in value.items():
        if val not in (None, "", []):
            merged[key] = deepcopy(val)
        elif key not in merged:
            merged[key] = deepcopy(val)
    merged["id"] = canonical_id
    items[first] = merged
    for index in reversed(match_indexes[1:]):
        del items[index]
    return 1 if merged != existing or len(match_indexes) > 1 else 0


def append_source(event: dict, new_source: dict) -> None:
    sources = event.setdefault("sources", [])
    if not any(str(item.get("url") or "") == new_source["url"] for item in sources if isinstance(item, dict)):
        sources.append(deepcopy(new_source))


def patch_existing(items: list[dict], canonical_id: str, patch: dict) -> int:
    ids = {canonical_id, *patch.get("aliases", [])}
    indexes = [i for i, item in enumerate(items) if str(item.get("id") or "") in ids]
    if not indexes:
        return 0
    changed = 0
    for index in indexes:
        event = items[index]
        original = deepcopy(event)
        if patch.get("title"):
            event["title"] = patch["title"]
        if patch.get("replaceArtists"):
            event["artists"] = list(patch["replaceArtists"])
        for artist in patch.get("addArtists", []):
            if artist not in event.setdefault("artists", []):
                event["artists"].append(artist)
        if patch.get("image"):
            event["image"] = patch["image"]
            event["imageType"] = "event_artwork"
            event["imagePosition"] = "center"
            event["imageOverride"] = True
        if patch.get("officialBill"):
            event["officialBill"] = list(patch["officialBill"])
        if patch.get("notes"):
            event["notes"] = patch["notes"]
        if patch.get("source"):
            append_source(event, patch["source"])
        event["auditVerified"] = AUDIT_DATE
        if event != original:
            changed += 1
    return changed


def apply() -> dict:
    events = load(EVENTS_FILE, [])
    supplemental = load(SUPPLEMENTAL_FILE, [])
    manual = load(MANUAL_FILE, [])
    artists = load(ARTISTS_FILE, [])

    artists_before = len(artists)
    artists = [item for item in artists if norm(item.get("name")) not in BLOCKED_ARTISTS]
    madison_removed = artists_before - len(artists)

    events, removed_events = remove_blocked_artists(events)
    supplemental, removed_supp = remove_blocked_artists(supplemental)
    manual, removed_manual = remove_blocked_artists(manual)

    for raw_id, target in NEW_EVENTS:
        live_id = f"manual:{raw_id}"
        aliases = {raw_id, live_id}
        upsert_new(events, target, live_id, aliases)
        upsert_new(supplemental, target, raw_id, aliases)
        upsert_new(manual, target, raw_id, aliases)

    for event_id, patch in EXISTING_PATCHES.items():
        patch_existing(events, event_id, patch)
        patch_existing(supplemental, event_id, patch)
        patch_existing(manual, event_id, patch)

    # Flavor Fest Friday is stored with a manual: prefix in live data and raw ID in
    # supplemental/manual data. Ensure both forms receive the same lineup repair.
    ff_patch = EXISTING_PATCHES["manual:flavor-fest-2026-friday-concerts"]
    patch_existing(supplemental, "flavor-fest-2026-friday-concerts", ff_patch)
    patch_existing(manual, "flavor-fest-2026-friday-concerts", ff_patch)

    # Keep roster order contiguous after removing Madison.
    for index, artist in enumerate(artists, 1):
        artist["rosterOrder"] = index

    save(EVENTS_FILE, events)
    save(SUPPLEMENTAL_FILE, supplemental)
    save(MANUAL_FILE, manual)
    save(ARTISTS_FILE, artists)

    return {
        "events": len(events),
        "supplemental": len(supplemental),
        "manual": len(manual),
        "artists": len(artists),
        "madisonArtistRowsRemoved": madison_removed,
        "madisonEventRowsChanged": removed_events + removed_supp + removed_manual,
    }


def assert_event(items: list[dict], event_id: str, artists: list[str]) -> dict:
    matches = [item for item in items if item.get("id") == event_id]
    if len(matches) != 1:
        raise SystemExit(f"Expected one {event_id}, found {len(matches)}")
    event = matches[0]
    missing = [artist for artist in artists if artist not in event.get("artists", [])]
    if missing:
        raise SystemExit(f"{event_id} missing artists: {missing}")
    return event


def check() -> None:
    events = load(EVENTS_FILE, [])
    supplemental = load(SUPPLEMENTAL_FILE, [])
    manual = load(MANUAL_FILE, [])
    artists = load(ARTISTS_FILE, [])

    if any(norm(item.get("name")) in BLOCKED_ARTISTS for item in artists):
        raise SystemExit("Madison Ryann Ward remains in artist tracking")
    for collection_name, collection in [("events", events), ("supplemental", supplemental), ("manual", manual)]:
        for event in collection:
            if any(norm(artist) in BLOCKED_ARTISTS for artist in event.get("artists", [])):
                raise SystemExit(f"Madison remains associated in {collection_name}: {event.get('id')}")

    roster = {str(item.get("name") or "") for item in artists}
    for raw_id, target in NEW_EVENTS:
        for artist in target["artists"]:
            if artist not in roster:
                raise SystemExit(f"Audit association references unknown roster artist: {artist}")
        assert_event(events, f"manual:{raw_id}", target["artists"])
        assert_event(supplemental, raw_id, target["artists"])
        assert_event(manual, raw_id, target["artists"])

    assert_event(events, "ticketmaster:k7vGF_dl6_HDp", ["Miles Minnick", "Tommy Zuko", "CJ Emulous"])
    kca = assert_event(events, "official:64bbcd477c3a36104df3", ["Anike", "Don Ready", "Dante' Pride", "Childlike CiCi", "Yung Kriss", "Datin", "BigBreeze", "C4 Crotona", "MAYIA", "Brinson"])
    if kca.get("title") != "Kingdom Choice Awards 2026":
        raise SystemExit("Kingdom Choice Awards title was not repaired")
    assert_event(events, "manual:flavor-fest-2026-friday-concerts", ["TRU-SERVA", "VVS Big Rock", "Lyric The Geenyus", "MAYIA"])
    assert_event(events, "official:12ef07b891bbeeefbcb1", ["CJ Emulous"])

    for name, collection in [("events", events), ("supplemental", supplemental), ("manual", manual)]:
        ids = [str(item.get("id") or "") for item in collection]
        if len(ids) != len(set(ids)):
            raise SystemExit(f"Duplicate IDs remain in {name}")

    print("September 11 catalog audit verification passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check()
    else:
        print(json.dumps(apply(), indent=2))
        check()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
