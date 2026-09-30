"""Owner-approved corrections from the first fifty September 26 audit entries.

Run after older refresh repairs. Billing may include unprofiled performers;
the curated artist roster and each event's discovery age remain unchanged.
"""
import copy
import json
import re


def artwork(filename, source_url, description):
    return {
        "image": "assets/events/" + filename, "imageType": "event_artwork",
        "imagePosition": "center", "imageOverride": True,
        "imageSourceUrl": source_url, "imageSource": description,
    }


ARK_BILL = [
    "Jekalyn Carr", "Kierra Sheard", "Travis Greene", "Charles Weems",
    "Kijan Boone", "Zauntee", "Scootie Wop", "Dante' Pride", "Anike", "Ahjah",
    "Y Shadey", "Kefia Rollerson", "DJ PARTYwithParks", "180MINDSET",
]
REIGN_BILL = ["Aasha Marie", "Justin Martyr", "Conquest", "Crystal B."]
ONE_DAY_BILL = ["Petrina DeLacey", "JBthaPreacher", "Cyfë II", "Grace Runkle", "Serin Oh"]
ANIKE_URL = "https://www.eventbrite.com/e/anike-live-the-all-star-concert-tickets-1997805844059"
OVERFLOW_URL = "https://www.overflowconf.com/schedule"
MIAMI_URL = "https://www.ticketsource.com/the-sound-system/mike-malagies-it-s-a-god-night-miami/e-vgxqxl"

PATCHES = {
    "bandsintown:1040305060": {
        "title": "57th Annual GMA Dove Awards — featuring Hulvey",
        "legacyEventPaths": ["/event/hulvey-at-bridgestone-arena-2026-10-06-nashville-090597/"],
    },
    "let-the-church-sing-tour-dunedin-2026": artwork(
        "let-the-church-sing-dunedin-2026-10-02.jpg",
        "https://brushfire.com/jakeragermusic/letthechurchsingtour/629466/details",
        "Official Brushfire Dunedin concert flyer"),
    "ark-of-worship-2026": {
        "artists": ["Zauntee", "Scootie Wop", "Dante' Pride", "Anike", "Y Shadey", "180MINDSET", "Kijan Boone"],
        "advertisedBilling": ARK_BILL, "officialBill": ARK_BILL,
        "performerDays": {
            "2026-10-09": ["Kijan Boone", "Ahjah", "Anike", "Y Shadey", "180MINDSET", "DJ PARTYwithParks"],
            "2026-10-10": ["Jekalyn Carr", "Kierra Sheard", "Travis Greene", "Charles Weems", "Zauntee", "Scootie Wop", "Dante' Pride", "Kefia Rollerson", "DJ PARTYwithParks"],
        },
    },
    "tru-serva-cupojoy-green-bay-2026": artwork(
        "tru-serva-cupojoy-2026-10-09.jpg", "https://www.itickets.com/events/487141",
        "Official iTickets TRU-SERVA event graphic"),
    "one-day-fall-festival-aurora-2026": {
        **artwork("one-day-festival-2026-10-10-lineup-crop.png", "https://www.instagram.com/runwchristden/p/Dd4WmfHEdta/?img_index=2",
                  "Owner-approved upper-section edit of RWC Denver official ONE DAY lineup flyer"),
        "startTime": "16:30", "startDateTime": "2026-10-10T16:30:00-06:00",
        "timezone": "America/Denver", "endTime": "20:00",
        "artists": ["Petrina DeLacey", "JBthaPreacher"], "advertisedBilling": ONE_DAY_BILL, "officialBill": ONE_DAY_BILL,
        "notes": "The full festival runs 9 AM–8 PM; Kingdom Circuit lists the evening concert start, 4:30 PM. The official RWC Denver lineup flyer confirms Petrina DeLacey, JBthaPreacher, Cyfë II, Grace Runkle and Serin Oh. Billing follows the owner's requested order, with Petrina and JB first, then Cyfë II.",
    },
    "mayia-boxyard-saturdaze-2026": {
        **artwork("mayia-boxyard-2026-10-10.png",
                  "https://boxyard.rtp.org/events/saturdaze-wattyandmayia-102026-295-435-108/",
                  "Boxyard RTP official DJ Watty and MAYIA event poster"),
        "startTime": "11:30", "startDateTime": "2026-10-10T11:30:00-04:00",
        "timezone": "America/New_York", "endTime": "14:30",
    },
    "eventbrite:reign-volume-one-aasha-marie-brooklyn-2026": {
        "advertisedBilling": REIGN_BILL, "officialBill": REIGN_BILL,
    },
    "official:7c07397fa047689b0215": {
        "startTime": "19:30", "startDateTime": "2026-10-11T19:30:00-05:00",
        "timezone": "America/Chicago", "venue": "RCCG Cornerstone Church Austin",
        "address": "9309 Cameron Road", "officialUrl": ANIKE_URL, "ticketUrl": ANIKE_URL,
    },
    "mike-malagies-florida-takeover-miami-2026": {
        **artwork("mike-malagies-miami-2026-10-16.png", MIAMI_URL,
                  "Official TicketSource It's A God Night Miami flyer"),
        "soldOut": True, "ticketAvailability": "sold_out", "status": "scheduled",
    },
    "supplemental:brenno-overflow-conference-2026": {
        "startTime": "15:30", "startDateTime": "2026-10-17T15:30:00-04:00",
        "timezone": "America/New_York", "venue": "Sword of The Spirit Ministries",
        "address": "300 Kensington Ave", "officialUrl": OVERFLOW_URL,
        "ticketUrl": "https://www.tickettailor.com/events/ablazemovement/2047830",
        "notes": "The Ticket Tailor listing covers the entire October 16–17 conference, opening Friday at 7 PM. The organizer's Saturday schedule explicitly lists Concert featuring Brenno at 3:30 PM on October 17. Kingdom Circuit lists that music performance, not the Friday conference opening.",
    },
    "bandsintown:108902772": {
        **artwork("issac-mansfield-sazon-2026-10-17.jpg", "https://www.bandsintown.com/e/108902772",
                  "Issac Mansfield official Bandsintown Sazon Experience event poster"),
        "city": "Lakeland",
        "legacyEventPaths": ["/event/the-sazon-experience-2026-10-17-lakeland-estates-mobile-home-community-e9a5d0/"],
    },
    "alex-zurdo-zona-zero-san-juan-2026": artwork(
        "alex-zurdo-zona-zero-2026-10-18.jpg", "https://choli.ticketera.com/event/alex-zurdo-zona-cero-6dn2x2",
        "Official Ticketera Zona Zero concert artwork"),
}


def patch_event(row):
    event_id = str(row.get("id") or "").removeprefix("manual:")
    wanted = PATCHES.get(event_id)
    if wanted is None:
        return
    legacy = row.get("legacyEventPaths", [])
    row.update(copy.deepcopy(wanted))
    if "legacyEventPaths" in wanted:
        row["legacyEventPaths"] = list(dict.fromkeys(wanted["legacyEventPaths"] + legacy))
    row["auditVerified"] = "2026-09-26"
    if event_id in {"official:7c07397fa047689b0215", "supplemental:brenno-overflow-conference-2026"}:
        source = {"name": "Official organizer event details", "url": wanted["officialUrl"],
                  "type": "manual_verified", "authority": "venue_ticket", "priority": 115}
        row["sources"] = [source] + [s for s in row.get("sources", []) if s.get("url") != source["url"]]


def sold_out_badge(card):
    if re.search(r'>Sold Out</span>', card):
        return card
    return card.replace('<div class="event-badges">',
                        '<div class="event-badges"><span class="badge">Sold Out</span>', 1)


def finalize_availability(site):
    """Keep the approved Miami availability visible on every discovery card."""
    from build_seo_site import event_path
    paths = set()
    for name in ("events.json", "supplemental-events.json"):
        if not (site / name).exists():
            continue
        for event in json.loads((site / name).read_text()):
            event_id = str(event.get("id", "")).removeprefix("manual:")
            if PATCHES.get(event_id, {}).get("soldOut") and event.get("soldOut"):
                paths.add(event_path(event))
    if not paths:
        return
    for page in site.rglob("*.html"):
        original = page.read_text()
        text = re.sub(r'<article\b[^>]*data-event-card[^>]*>.*?</article>',
                      lambda m: sold_out_badge(m[0]) if any(f'href="{path}"' in m[0] for path in paths) else m[0],
                      original, flags=re.S)
        if text != original:
            page.write_text(text)
