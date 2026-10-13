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
        "artists": ["Joz", "DJ Mr.E"], "advertisedBilling": ["Southside Joz", "DJ Mr. E"],
        "lineupExplicit": True, "ageRestriction": "18+", "host": "Sean Olivera",
        "officialUrl": "https://www.eventbrite.com/e/good-vibez-jesus-glow-in-the-dark-party-tickets-1997092475354",
        "ticketUrl": "https://www.eventbrite.com/e/good-vibez-jesus-glow-in-the-dark-party-tickets-1997092475354",
        "image": "assets/events/good-vibez-jesus-miami-gardens-2026-10-30-portrait.jpg",
        "imageSource": "Official GOOD VIBEZ & JESUS Instagram portrait flyer, selected by owner October 10",
        "imageSourceUrl": "https://www.instagram.com/goodvibezandjesus/p/Db_ZdIVRocU/",
        "detailImageLayout": "portrait", "organizer": "GOOD VIBEZ & JESUS",
        "notes": "Official Eventbrite and flyer confirm Southside Joz as special guest, DJ Mr. E providing music, Sean Olivera hosting, 8 PM and ages 18+. End time 11:59 PM comes from the Eventbrite structured event data. Southside Joz is the existing curated artist Joz; preserve that profile identity.",
    },
    {'id': 'spin-awards-pre-ceremony-lawrenceville-2026-10-23',
     'title': 'The Spin Awards — 10th Anniversary Weekend',
     'startDate': '2026-10-22',
     'endDate': '2026-10-24',
     'startTime': '',
     'endTime': '',
     'timezone': 'America/New_York',
     'startDateTime': '',
     'endDateTime': '',
     'venue': 'The Lawrence Hotel / Lawrenceville Arts Center',
     'address': '',
     'city': 'Lawrenceville',
     'state': 'GA',
     'postalCode': '',
     'artists': ['Bobby Real Montgomery', 'Shaquille Jones'],
     'advertisedBilling': ['Shaquille Jones',
                           'Bobby Real Montgomery',
                           'Jdot!',
                           'Keylosophy',
                           'Young Men 4 Christ',
                           'Asaun Bynum',
                           'Kiara Hicks',
                           'Talasia',
                           'Darien Brooks',
                           'Antoine Hilton',
                           'Maurice Griffin',
                           'I Am Able',
                           'God’s Horns',
                           'Jai Vaughn',
                           'Kennis Clark',
                           'Denita Gibbs',
                           'Marcus Jordan',
                           'Glory Music',
                           'Dr. Lonnie Hunter',
                           'DJ B4EY'],
     'unconfirmedArtists': [],
     'officialBill': ['Shaquille Jones',
                      'Bobby Real Montgomery',
                      'Jdot!',
                      'Keylosophy',
                      'Young Men 4 Christ',
                      'Asaun Bynum',
                      'Kiara Hicks',
                      'Talasia',
                      'Darien Brooks',
                      'Antoine Hilton',
                      'Maurice Griffin',
                      'I Am Able',
                      'God’s Horns',
                      'Jai Vaughn',
                      'Kennis Clark',
                      'Denita Gibbs',
                      'Marcus Jordan',
                      'Glory Music',
                      'Dr. Lonnie Hunter',
                      'DJ B4EY'],
     'lineupExplicit': True,
     'host': '',
     'confidence': 'high',
     'publicDescription': 'The SPIN Awards 10th Anniversary Weekend Experience runs October 22–24 in '
                          'Lawrenceville, Georgia, with performances across the weekend. Thursday and Friday '
                          'activities take place at The Lawrence Hotel; Friday’s pre-ceremony starts at 7:30 PM. '
                          'Saturday’s main awards ceremony is at Lawrenceville Arts Center at 7:30 PM, with red '
                          'carpet at 5:30 PM. Thursday and Friday registration is free; Saturday requires a '
                          'ticket. The October 21 Chocolate Affair featuring Ahmad Nelson has its own listing.',
     'officialUrl': 'https://www.thespinawards.com/spinitin/',
     'ticketUrl': '',
     'image': 'assets/events/spin-awards-2026-four-day-itinerary.jpg',
     'imageSource': 'The Spin Awards official four-day weekend itinerary portrait',
     'imageSourceUrl': 'https://www.instagram.com/thespinawards/p/Dc_O5zLREnQ/',
     'organizer': 'The Spin Awards',
     'firstSeen': '2026-09-25T21:08:55Z',
     'lastVerified': '2026-10-13T19:52:15Z',
     'notes': 'Owner requested all four days and full announced music billing on October 13. Official updated '
              'four-day itinerary and October 8 Urban Soul Cafe co-announcement confirm October 21 kickoff; '
              'website itinerary covers October 22–24. Official performer announcement series confirms the listed '
              'artists; Jdot! confirmed by management. Bobby Real Montgomery and Shaquille Jones also confirmed '
              'directly to the owner. This replaces the old Friday-only scope while preserving stable ID and '
              'firstSeen. No artist is assigned an unannounced individual day/set. Honorees, nominees, panelists, '
              'sponsor logos, playlist collaborators and tagged accounts are not inferred as performers. Official '
              'artwork is the complete four-day portrait itinerary; its schedule may be revised, so latest '
              'organizer website takes precedence for individual session times. Owner approved splitting October '
              '21 Chocolate Affair from October 22–24 on October 13 after research. Honor direct artist '
              'confirmations from Bobby Real Montgomery and Shaquille Jones as confirmed performances; do not mark '
              'them unconfirmed merely because individual sessions are not announced. Preserve the entire 20-act '
              'bill and original identity/discovery. Ahmad Nelson is directly confirmed for the separate October '
              '21 event. Wednesday hosts belong only on that listing.',
     'country': 'US',
     'eventType': 'event',
     'status': 'scheduled',
     'headliner': '',
     'imageType': 'event_artwork',
     'imageOverride': True,
     'imagePosition': 'center',
     'sourceName': 'Official organizer event listing',
     'authority': 'official_event',
     'sources': [{'name': 'Official Spin Awards current itinerary',
                  'url': 'https://www.thespinawards.com/spinitin/',
                  'type': 'official_event',
                  'authority': 'official_event',
                  'priority': 115},
                 {'name': 'Official four-day itinerary poster',
                  'url': 'https://www.instagram.com/thespinawards/p/Dc_O5zLREnQ/',
                  'type': 'official_event',
                  'authority': 'official_event',
                  'priority': 115},
                 {'name': 'Official October 21 Chocolate Affair kickoff',
                  'url': 'https://www.instagram.com/uscafe/p/DeP0rBlj0Ff/',
                  'type': 'official_event',
                  'authority': 'official_event',
                  'priority': 115},
                 {'name': 'Jdot! management performance announcement',
                  'url': 'https://www.instagram.com/vibe5ent/reel/DeaIDX4gdtd/',
                  'type': 'official_artist',
                  'authority': 'official_artist',
                  'priority': 115},
                 {'name': 'Official Spin Awards performer announcement',
                  'url': 'https://www.instagram.com/thespinawards/reel/Dd_2knxRouc/',
                  'type': 'official_event',
                  'authority': 'official_event',
                  'priority': 115},
                 {'name': 'Official Spin Awards performer announcement',
                  'url': 'https://www.instagram.com/thespinawards/reel/Dd_w1i2xBbo/',
                  'type': 'official_event',
                  'authority': 'official_event',
                  'priority': 115},
                 {'name': 'Official Spin Awards performer announcement',
                  'url': 'https://www.instagram.com/thespinawards/reel/Dd94szyJfyh/',
                  'type': 'official_event',
                  'authority': 'official_event',
                  'priority': 115},
                 {'name': 'Official Spin Awards performer announcement',
                  'url': 'https://www.instagram.com/thespinawards/reel/Dd9VmjXROSJ/',
                  'type': 'official_event',
                  'authority': 'official_event',
                  'priority': 115},
                 {'name': 'Official Spin Awards performer announcement',
                  'url': 'https://www.instagram.com/thespinawards/reel/Ddm-4hxBlvS/',
                  'type': 'official_event',
                  'authority': 'official_event',
                  'priority': 115},
                 {'name': 'Official Spin Awards performer announcement',
                  'url': 'https://www.instagram.com/thespinawards/reel/DdmzYg5hpg5/',
                  'type': 'official_event',
                  'authority': 'official_event',
                  'priority': 115},
                 {'name': 'Official Spin Awards performer announcement',
                  'url': 'https://www.instagram.com/thespinawards/reel/DdmO0-5BCYc/',
                  'type': 'official_event',
                  'authority': 'official_event',
                  'priority': 115},
                 {'name': 'Official Spin Awards performer announcement',
                  'url': 'https://www.instagram.com/thespinawards/reel/DdFagEkJg6q/',
                  'type': 'official_event',
                  'authority': 'official_event',
                  'priority': 115},
                 {'name': 'Official Spin Awards performer announcement',
                  'url': 'https://www.instagram.com/thespinawards/reel/DdFRgwsp3Ay/',
                  'type': 'official_event',
                  'authority': 'official_event',
                  'priority': 115},
                 {'name': 'Official Spin Awards performer announcement',
                  'url': 'https://www.instagram.com/thespinawards/reel/DdFKvDip1W-/',
                  'type': 'official_event',
                  'authority': 'official_event',
                  'priority': 115},
                 {'name': 'Official Spin Awards performer announcement',
                  'url': 'https://www.instagram.com/thespinawards/reel/DdFG0s8pO02/',
                  'type': 'official_event',
                  'authority': 'official_event',
                  'priority': 115},
                 {'name': 'Official Spin Awards performer announcement',
                  'url': 'https://www.instagram.com/thespinawards/reel/DdCNZICBkye/',
                  'type': 'official_event',
                  'authority': 'official_event',
                  'priority': 115},
                 {'name': 'Official Spin Awards performer announcement',
                  'url': 'https://www.instagram.com/thespinawards/reel/DdCF4aEBDOA/',
                  'type': 'official_event',
                  'authority': 'official_event',
                  'priority': 115},
                 {'name': 'Official Spin Awards performer announcement',
                  'url': 'https://www.instagram.com/thespinawards/reel/DdB8XYfxdCI/',
                  'type': 'official_event',
                  'authority': 'official_event',
                  'priority': 115},
                 {'name': 'Official Spin Awards performer announcement',
                  'url': 'https://www.instagram.com/thespinawards/reel/DdB8ME8RQMO/',
                  'type': 'official_event',
                  'authority': 'official_event',
                  'priority': 115},
                 {'name': 'Official Spin Awards performer announcement',
                  'url': 'https://www.instagram.com/thespinawards/reel/DdB74GXxNGV/',
                  'type': 'official_event',
                  'authority': 'official_event',
                  'priority': 115},
                 {'name': 'Shaquille Jones official performer announcement',
                  'url': 'https://www.instagram.com/thespinawards/reel/Dd_2knxRouc/',
                  'type': 'official_event',
                  'authority': 'official_event',
                  'priority': 115}],
     'musicConfirmed': True,
     'hosts': ['Destiny Kingcannon (October 23 pre-ceremony)', 'Tony Gee (main ceremony)'],
     'detailImageLayout': 'portrait',
     'legacyEventPaths': ['/event/the-spin-awards-pre-ceremony-2026-10-23-lawrenceville-3623f3/',
                          '/event/the-spin-awards-10th-anniversary-weekend-2026-10-21-lawrenceville-3623f3/'],
     'legacyEventNotice': 'This listing covers the October 22–24 SPIN Awards Weekend Experience, including the '
                          'October 23 pre-ceremony. The October 21 Chocolate Affair now has a separate listing.',
     'auditVerified': '2026-10-13',
     'billingLabel': 'Artists appearing across the weekend',
     'programSchedule': [{'label': 'Thu, Oct 22',
                          'text': 'The Lawrence Hotel — worship, showcases and DJ programming. Dr. Lonnie Hunter '
                                  'at 2 PM; DJ B4EY at 9:15 PM.'},
                         {'label': 'Fri, Oct 23',
                          'text': 'The Lawrence Hotel — daytime programming and artist spotlight; pre-ceremony '
                                  '7:30–9:30 PM.'},
                         {'label': 'Sat, Oct 24',
                          'text': 'Lawrenceville Arts Center — red carpet 5:30 PM; main ceremony 7:30 PM.'},
                         {'label': 'Admission',
                          'text': 'Thursday and Friday registration is free. Saturday’s main ceremony requires a '
                                  'ticket.'}],
     'programNote': 'All times Eastern. Artists perform across the weekend; individual sets vary by session.',
     'eventLinks': [{'label': 'Free Thursday–Friday registration',
                     'url': 'https://www.thespinawards.com/register/'},
                    {'label': 'Saturday ceremony tickets', 'url': 'https://www.thespinawards.com/tickets/'}],
     'relatedEventId': 'spin-awards-chocolate-affair-lawrenceville-2026-10-21',
     'relatedEventLabel': 'October 21: Chocolate Affair with Ahmad Nelson'},
    {'id': 'spin-awards-chocolate-affair-lawrenceville-2026-10-21',
     'title': 'SPIN Awards — Chocolate Affair',
     'startDate': '2026-10-21',
     'endDate': '2026-10-21',
     'startTime': '19:00',
     'endTime': '',
     'doorsTime': '18:00',
     'timezone': 'America/New_York',
     'startDateTime': '2026-10-21T19:00:00-04:00',
     'endDateTime': '',
     'venue': 'Jewelz Bar & Lounge',
     'address': '1365 Grayson Hwy, Suite 113',
     'city': 'Lawrenceville',
     'state': 'GA',
     'postalCode': '30045',
     'country': 'US',
     'artists': ['Ahmad Nelson'],
     'advertisedBilling': ['Ahmad Nelson'],
     'officialBill': ['Ahmad Nelson'],
     'unconfirmedArtists': [],
     'lineupExplicit': True,
     'headliner': '',
     'hosts': ['Destiny Diggs', 'DJ Tony Tone'],
     'host': '',
     'confidence': 'high',
     'eventType': 'event',
     'status': 'scheduled',
     'musicConfirmed': True,
     'officialUrl': 'https://www.instagram.com/uscafe/p/DeP0rBlj0Ff/',
     'ticketUrl': '',
     'image': 'assets/events/spin-awards-chocolate-affair-2026-10-21-owner.png',
     'imageType': 'event_artwork',
     'imageOverride': True,
     'imagePosition': 'center',
     'imageSource': 'Official Chocolate Affair flyer supplied by Ahmad Nelson through the owner',
     'imageSourceUrl': 'https://www.instagram.com/uscafe/p/DeP0rBlj0Ff/',
     'detailImageLayout': 'portrait',
     'organizer': 'Urban Soul Cafe',
     'firstSeen': '2026-10-13T18:55:00Z',
     'lastVerified': '2026-10-13T19:52:15Z',
     'auditVerified': '2026-10-13',
     'authority': 'official_event',
     'sourceName': 'Official organizer event listing',
     'publicDescription': 'Urban Soul Cafe presents the SPIN Awards 10th Anniversary Chocolate Affair on October '
                          '21 at Jewelz Bar & Lounge in Lawrenceville, Georgia, featuring a live performance by '
                          'Ahmad Nelson. Hosted by Destiny Diggs and DJ Tony Tone. Doors open at 6 PM; '
                          'entertainment starts at 7 PM Eastern. Free admission, with food and drinks available '
                          'for purchase.',
     'programSchedule': [{'label': 'Evening', 'text': 'Doors open at 6 PM Eastern. Live entertainment starts at 7 PM.'},
                         {'label': 'Admission', 'text': 'Free admission. Food and drinks available for purchase.'}],
     'programNote': '',
     'eventLinks': [],
     'relatedEventId': 'spin-awards-pre-ceremony-lawrenceville-2026-10-23',
     'relatedEventLabel': 'October 22–24: SPIN Awards Weekend Experience',
     'notes': 'Ahmad Nelson told the owner he is performing and supplied the exact Chocolate Affair flyer. Owner '
              'explicitly approved trusting direct artist confirmations and this split on October 13. Treat Ahmad '
              'as a confirmed performer even though the generic flyer lists the hosts rather than every performer. '
              'Do not infer that the entire SPIN weekend bill performs October 21. Destiny Diggs and DJ Tony Tone '
              'are hosts, not inferred musical billing. Keep artwork exact and local. End time and individual set '
              'times are not published.',
     'sources': [{'name': 'Urban Soul Cafe official Chocolate Affair announcement',
                  'url': 'https://www.instagram.com/uscafe/p/DeP0rBlj0Ff/',
                  'type': 'official_event',
                  'authority': 'official_event',
                  'priority': 115},
                 {'name': 'Ahmad Nelson direct performance confirmation relayed by site owner October 13, 2026',
                  'type': 'artist_submission',
                  'authority': 'official_artist',
                  'priority': 115}]},
)
for event in EVENTS:
    event.update({
        "country": "US", "eventType": event.get("eventType", "concert"), "status": "scheduled", "headliner": event.get("headliner", ""),
        "officialBill": list(event.get("officialBill", event["advertisedBilling"])),
        "imageType": "event_artwork", "imageOverride": True, "imagePosition": "center",
        "sourceName": "Official organizer event listing", "authority": "official_event", "confidence": event.get("confidence", "high"),
        "firstSeen": event.get("firstSeen", VERIFIED_AT), "lastVerified": event.get("lastVerified", VERIFIED_AT),
        "sources": event.get("sources", []) + [{"name": "Official organizer event listing", "url": url,
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
    "name": "Official Spin Awards four-day itinerary artwork",
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
