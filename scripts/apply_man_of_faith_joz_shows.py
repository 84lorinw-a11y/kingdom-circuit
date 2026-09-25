#!/usr/bin/env python3
"""Preserve the reviewed September 25 artist-submitted October shows."""
from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
VERIFIED_AT = "2026-09-25T18:55:43Z"
EVENTS = (
    {
        "id": "nu-wave-anointing-sacramento-2026-10-10",
        "title": "A Nu Wave of Anointing — Artist Showcase",
        "startDate": "2026-10-10", "endDate": "2026-10-10",
        "startTime": "17:00", "endTime": "", "timezone": "America/Los_Angeles",
        "startDateTime": "2026-10-10T17:00:00-07:00",
        "venue": "Nu Wave Church", "address": "9529 Folsom Blvd, Suite D",
        "city": "Sacramento", "state": "CA", "postalCode": "95826",
        "artists": ["Man Of FAITH"],
        "headliner": "Man Of FAITH",
        "advertisedBilling": ["Man Of FAITH", "Tiburon Tha Rapper", "K. Murray", "Ya'Sa", "J.P.", "Moe'Style", "Zay Lowly", "Roman6", "Anomilli", "St. Saconni", "King Dorsey"],
        "lineupExplicit": True,
        "officialUrl": "https://www.instagram.com/p/DcJ9-kryraR/",
        "ticketUrl": "https://www.wearenuwaveent.com/",
        "image": "assets/events/nu-wave-anointing-sacramento-2026-10-10.jpg",
        "imageSource": "Nu Wave Entertainment official complete Instagram flyer",
        "imageSourceUrl": "https://www.instagram.com/p/DcJ9-kryraR/",
        "detailImageLayout": "landscape", "organizer": "Nu Wave Entertainment",
        "lastVerified": "2026-09-25T20:24:38Z",
        "notes": "Organizer Instagram caption confirms Nu Wave Church; full flyer confirms October 10 at 5 PM, 9529 Folsom Blvd Suite D, and all eleven billed performers. The September 19 Man Of FAITH/organizer repost corroborates the date, time and bill. Church website confirms the address and ZIP 95826. Homepage confirms free admission. On September 25 the site owner relayed Man Of FAITH's direct confirmation that he is the headliner. End time and individual set times remain unpublished.",
    },
    {
        "id": "ghost-ride-the-gospel-2-berkeley-2026-10-17",
        "title": "Ghost Ride the Gospel 2",
        "startDate": "2026-10-17", "endDate": "2026-10-17",
        "startTime": "17:00", "endTime": "21:00", "timezone": "America/Los_Angeles",
        "startDateTime": "2026-10-17T17:00:00-07:00", "endDateTime": "2026-10-17T21:00:00-07:00",
        "venue": "The Way Christian Center", "address": "1305 University Avenue",
        "city": "Berkeley", "state": "CA", "postalCode": "94702",
        "artists": ["Man Of FAITH"],
        "advertisedBilling": ["Man Of FAITH", "Pastor Chris", "@godsdogvlu", "@jm3fromthep", "@jaysmoov3", "@schwartzen.precil", "@shelbaelatorre", "@zaylowly_music", "@nutce.iv", "@litaniemendiolaofficial"],
        "lineupExplicit": True, "ageRestriction": "All ages",
        "officialUrl": "https://partiful.com/e/bYodVpvtr2jYKyoANwlR",
        "ticketUrl": "https://www.eventbrite.com/e/ghost-ride-the-gospel-2-tickets-2000667257624",
        "image": "assets/events/ghost-ride-the-gospel-2-berkeley-2026-10-17.jpg",
        "imageSource": "Official Ghost Ride the Gospel 2 Partiful flyer",
        "imageSourceUrl": "https://partiful.imgix.net/external/user/42YhAuBM1wVqSbLr6krHWCrxT733/3h6R2W0xMY3ZyRHKMxP3b?w=1000&h=1500&fit=clip",
        "organizer": "Ghost Ride the Gospel",
        "notes": "Partiful UTC start October 18 00:00 is October 17 at 5 PM Pacific; flyer and organizer Eventbrite confirm 5–9 PM. Full flyer billing uses the published handles where stage names are unavailable. Man Of FAITH is @realmanoffaith. No individual set times are inferred.",
    },
    {
        "id": "good-vibez-jesus-miami-gardens-2026-10-30",
        "title": "GOOD VIBEZ & JESUS: Glow in the Dark Party",
        "startDate": "2026-10-30", "endDate": "2026-10-30",
        "startTime": "20:00", "endTime": "23:59", "timezone": "America/New_York",
        "startDateTime": "2026-10-30T20:00:00-04:00", "endDateTime": "2026-10-30T23:59:00-04:00",
        "venue": "3918 NW 167th St", "address": "3918 Northwest 167th Street",
        "city": "Miami Gardens", "state": "FL", "postalCode": "33054",
        "artists": ["Joz"], "advertisedBilling": ["Southside Joz", "DJ Mr. E"],
        "lineupExplicit": True, "ageRestriction": "18+", "host": "Sean Olivera",
        "officialUrl": "https://www.eventbrite.com/e/good-vibez-jesus-glow-in-the-dark-party-tickets-1997092475354",
        "ticketUrl": "https://www.eventbrite.com/e/good-vibez-jesus-glow-in-the-dark-party-tickets-1997092475354",
        "image": "assets/events/good-vibez-jesus-miami-gardens-2026-10-30.png",
        "imageSource": "Official GOOD VIBEZ & JESUS Eventbrite flyer",
        "imageSourceUrl": "https://cdn.evbuc.com/images/1191027196/2999300952530/1/original.20260814-002945",
        "detailImageLayout": "landscape", "organizer": "GOOD VIBEZ & JESUS",
        "notes": "Official Eventbrite and flyer confirm Southside Joz as special guest, DJ Mr. E providing music, Sean Olivera hosting, 8 PM and ages 18+. End time 11:59 PM comes from the Eventbrite structured event data. Southside Joz is the existing curated artist Joz; preserve that profile identity.",
    },
    {
        "id": "spin-awards-pre-ceremony-lawrenceville-2026-10-23",
        "title": "The Spin Awards Pre-Ceremony",
        "startDate": "2026-10-23", "endDate": "2026-10-23",
        "startTime": "19:30", "endTime": "21:30", "timezone": "America/New_York",
        "startDateTime": "2026-10-23T19:30:00-04:00", "endDateTime": "2026-10-23T21:30:00-04:00",
        "venue": "The Lawrence Hotel", "address": "120 E Crogan St",
        "city": "Lawrenceville", "state": "GA", "postalCode": "30046",
        "artists": ["Bobby Real Montgomery"], "advertisedBilling": ["Bobby Real Montgomery"],
        "unconfirmedArtists": ["Bobby Real Montgomery"], "officialBill": [], "lineupExplicit": False,
        "host": "Destiny Kingcannon", "confidence": "medium",
        "publicDescription": "Spin Awards Pre-Ceremony: Oct. 23, 2026, 7:30 PM, The Lawrence Hotel, Lawrenceville, GA.",
        "officialUrl": "https://www.thespinawards.com/spinitin/", "ticketUrl": "",
        "image": "assets/events/spin-awards-pre-ceremony-lawrenceville-2026-10-23.jpg",
        "imageSource": "The Spin Awards official October 23 pre-ceremony host flyer",
        "imageSourceUrl": "https://www.instagram.com/thespinawards/p/DdmNMTtJE5z/",
        "organizer": "The Spin Awards", "firstSeen": "2026-09-25T21:08:55Z",
        "lastVerified": "2026-09-25T21:08:55Z",
        "notes": "Official itinerary confirms Friday October 23, 7:30–9:30 PM Eastern at The Lawrence Hotel, 120 E Crogan St. Official September 22 Instagram flyer confirms the pre-ceremony date/time and host Destiny Kingcannon. Owner relayed Bobby's direct confirmation of performing at the Spin Awards weekend, then requested assuming this Friday session. His exact session remains unconfirmed internally; do not treat Bobby as organizer-confirmed billing or an exact 7:30 PM set. Owner explicitly requested removing the public session-unconfirmed wording and using the short venue name and start time in visible details. Host is not a confirmed musical performer.",
    },
)
for event in EVENTS:
    event.update({
        "country": "US", "eventType": "concert", "status": "scheduled", "headliner": event.get("headliner", ""),
        "officialBill": list(event.get("officialBill", event["advertisedBilling"])),
        "imageType": "event_artwork", "imageOverride": True, "imagePosition": "center",
        "sourceName": "Official organizer event listing", "authority": "official_event", "confidence": event.get("confidence", "high"),
        "firstSeen": event.get("firstSeen", VERIFIED_AT), "lastVerified": event.get("lastVerified", VERIFIED_AT),
        "sources": [{"name": "Official organizer event listing", "url": url,
                     "type": "official_event", "authority": "official_event", "priority": 112}
                    for url in dict.fromkeys((event["officialUrl"], event["ticketUrl"])) if url],
    })

EVENTS[0]["sources"].extend([
    {"name": "Nu Wave Church official address", "url": "https://www.wearenuwave.church/",
     "type": "official_venue", "authority": "official_venue", "priority": 112},
    {"name": "Man Of FAITH and Nu Wave Entertainment September 19 flyer",
     "url": "https://www.instagram.com/realmanoffaith/p/DdeodjYT7Mf/",
     "type": "official_artist", "authority": "official_artist", "priority": 112},
])
EVENTS[3]["sources"].append({
    "name": "Official Spin Awards pre-ceremony host announcement",
    "url": EVENTS[3]["imageSourceUrl"], "type": "official_event", "authority": "official_event", "priority": 112,
})


def source_key(url: str) -> str:
    parts = urlsplit(str(url or ""))
    host = parts.netloc.casefold().removeprefix("www.")
    if host == "eventbrite.com":
        match = re.search(r"-(\d+)$", parts.path.rstrip("/"))
        if match:
            return "eventbrite:" + match[1]
    return host + parts.path.rstrip("/")


def matches(row: dict, event: dict) -> bool:
    if str(row.get("id", "")).removeprefix("manual:") == event["id"]:
        return True
    urls = {source_key(event[field]) for field in ("officialUrl", "ticketUrl") if event.get(field)}
    if not any(source_key(row.get(field, "")) in urls for field in ("officialUrl", "ticketUrl")):
        return False
    # A general organizer homepage is not a unique event identity.
    if event["city"] == "Sacramento":
        return row.get("startDate") == event["startDate"] and str(row.get("city", "")).casefold() == "sacramento"
    if event["id"] == "spin-awards-pre-ceremony-lawrenceville-2026-10-23":
        return row.get("startDate") == event["startDate"] and str(row.get("city", "")).casefold() == "lawrenceville"
    return True


def apply(root: Path = ROOT, today: str | None = None) -> None:
    today = today or dt.datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
    names = ("config/manual-events.json", "events.json", "supplemental-events.json")
    feeds = {name: json.loads((root / name).read_text(encoding="utf-8")) for name in names}
    for event in EVENTS:
        previous = [r for rows in feeds.values() for r in rows if matches(r, event)]
        canonical = {}
        for row in reversed(previous):
            if str(row.get("id", "")).removeprefix("manual:") == event["id"]:
                canonical.update(copy.deepcopy(row))
        canonical.update(copy.deepcopy(event))
        canonical["firstSeen"] = min([event["firstSeen"]] + [r["firstSeen"] for r in previous if r.get("firstSeen")])
        for row in previous:
            for source in row.get("sources", []):
                if source not in canonical["sources"]:
                    canonical["sources"].append(source)
        for name, rows in feeds.items():
            rows[:] = [r for r in rows if not matches(r, event)]
            if name == "config/manual-events.json" or (name == "events.json" and event["endDate"] >= today):
                record = copy.deepcopy(canonical)
                record["id"] = event["id"] if name.startswith("config/") else "manual:" + event["id"]
                rows.append(record)
    for name, rows in feeds.items():
        rows.sort(key=lambda r: (r.get("startDate", ""), r.get("startTime", ""), r.get("title", "")))
        (root / name).write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    apply()
    print("Submitted Man Of FAITH, Southside Joz and Bobby Real Montgomery shows preserved")
