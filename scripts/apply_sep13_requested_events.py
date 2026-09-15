#!/usr/bin/env python3
"""September 13 requested verified event import: selected shows, CJ Emulous, and JIMMY ROCK."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = "2026-09-13"
JIMMY_IMAGE = "assets/artists/jimmy-rock-primary.webp"
JIMMY_MIAMI_EVENT_IMAGE = "assets/events/jimmy-rock-worship-wawa-miami-2026.jpg"
JIMMY_DENVER_EVENT_IMAGE = "assets/events/jimmy-rock-rave-worship-denver-2026.jpg"
JIMMY_DALLAS_EVENT_IMAGE = "assets/events/jimmy-rock-rave-worship-dallas-2026.webp"
BOISE_EVENT_IMAGE = "assets/events/boise-invasion-2026.jpg"


def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def save(p, v): Path(p).write_text(json.dumps(v, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
def norm(v): return str(v or "").strip().casefold()
def src(name, url, authority, priority=100):
    return {"name": name, "url": url, "type": "manual_verified", "authority": authority, "priority": priority}


def E(title, date, city, state, artists, official, source_name, *, venue="Venue not provided", address="", event_type="concert",
      headliner=None, ticket="", time="", tz="", end_date="", end_time="", doors="", image="", image_type="fallback",
      image_override=False, price="", authority="artist_calendar", confidence="high", notes="", advertised=None, extra=None, **fields):
    d = {
        "title": title, "startDate": date, "startTime": time, "timezone": tz,
        "venue": venue, "address": address, "city": city, "state": state, "country": "US",
        "artists": artists, "headliner": headliner or artists[0], "eventType": event_type, "status": "scheduled",
        "ticketUrl": ticket, "officialUrl": official, "image": image, "imageType": image_type,
        "imagePosition": fields.pop("imagePosition", "center"), "imageOverride": image_override,
        "price": price, "lineupExplicit": fields.pop("lineupExplicit", True), "authority": authority,
        "confidence": confidence, "sourceName": source_name,
        "sources": [src(source_name, official, authority, 112 if authority.startswith("official") else 100)],
        "auditVerified": AUDIT,
    }
    if ticket and ticket != official:
        d["sources"].append(src("Official ticket / RSVP", ticket, "venue_ticket", 94))
    if extra: d["sources"].extend(extra)
    if end_date: d["endDate"] = end_date
    if end_time: d["endTime"] = end_time
    if doors: d["doorsTime"] = doors
    if notes: d["notes"] = notes
    if advertised: d["advertisedBilling"] = advertised
    d.update(fields)
    return d


UPSERTS = {
    "boise-invasion-2026": E(
        "Grand Opening | The Whosoevers | Boise Invasion", "2026-09-26", "Boise", "ID", ["Kurtis Hoppie", "JIMMY ROCK"],
        "https://www.tickettailor.com/events/thewhosoevers/2302169", "Official Ticket Tailor listing",
        venue="The Whosoevers HQ", address="20 S Auto Dr", time="17:30", doors="17:30", tz="America/Boise",
        ticket="https://www.tickettailor.com/events/thewhosoevers/2302169", price="Outdoor pre-show/overflow free; indoor event sold out",
        authority="venue_ticket", image=BOISE_EVENT_IMAGE, image_type="event_artwork", image_override=True,
        imageSource="The Whosoevers official Ticket Tailor listing",
        imageSourceUrl="https://www.tickettailor.com/events/thewhosoevers/2302169",
        advertised=["P.O.D.", "Lacey Sturm", "Ryan Ries", "Kurtis Hoppie", "JIMMY ROCK"], soldOut=True,
        ticketAvailability="sold_out", preShowTime="17:00",
        notes="Free outdoor pre-show block party and main-event overflow begins at 5:00 PM. Indoor doors open at 5:30 PM and the indoor ticket listing is sold out. JIMMY ROCK is billed for the after party."
    ),
    "oasis-ministry-qbelv-new-york-2026": E(
        "Oasis Ministry — QBELV Tour 2026", "2026-09-26", "New York", "NY", ["Alex Zurdo"],
        "https://unitedpalace.boletosexpress.com/oasis-ministry-s/88341/", "United Palace / Boletos Express official listing",
        venue="United Palace", address="4140 Broadway", time="20:00", doors="18:30", tz="America/New_York",
        ticket="https://unitedpalace.boletosexpress.com/oasis-ministry-s/88341/", authority="venue_ticket",
        advertised=["Oasis Ministry", "Lisney De Font", "Alex Zurdo"]
    ),
    "open-skies-topeka-2026": E(
        "Open Skies — Bethel Music with KB", "2026-09-26", "Topeka", "KS", ["KB"],
        "https://evergyplaza.com/event/open-skies/", "Evergy Plaza official event", venue="Evergy Plaza",
        address="630 S Kansas Ave", time="18:00", end_time="21:00", tz="America/Chicago",
        ticket="https://evergyplaza.com/event/open-skies/", price="Free", authority="official_event",
        image="https://evergyplaza.com/wp-content/uploads/2026/08/open-skies-1.jpg", image_type="event_artwork", image_override=True,
        advertised=["Bethel Music", "KB"]
    ),
    "jay-kalyl-desde-antes-elizabeth-2026": E(
        "Jay Kalyl — Desde Antes Tour", "2026-10-02", "Elizabeth", "NJ", ["Jay Kalyl"],
        "https://boletoslive.com/desde-antes-tour-jay-kalyl/", "BoletosLive official event", venue="Iglesia Torre Fuerte",
        address="30 3rd St", time="19:00", tz="America/New_York", ticket="https://boletoslive.com/desde-antes-tour-jay-kalyl/",
        authority="venue_ticket", image="https://boletoslive.com/wp-content/uploads/2026/08/JAY-K-NJ.png", image_type="event_artwork", image_override=True
    ),
    "one-day-fall-festival-aurora-2026": E(
        "ONE DAY Fall Festival 2026", "2026-10-10", "Aurora", "CO", ["Petrina DeLacey"], "https://onedaydenver.org/",
        "ONE DAY official festival site", venue="Colorado UpLift Community Campus", address="1500 S Dayton St", event_type="festival",
        time="09:00", end_time="20:00", tz="America/Denver", ticket="https://partiful.com/e/SK3SE7vXIs9rYlPcW0hZ", price="Free",
        authority="official_festival", performanceWindow="16:30-20:00",
        notes="Festival runs 9:00 AM–8:00 PM. The sanctuary concert featuring Petrina DeLacey runs 4:30–8:00 PM. Free admission; RSVP requested."
    ),
    "kelo-worship-after-christmas-jacksonville-2026": E(
        "Kelo Cho Presents: The Worship After Christmas", "2026-12-26", "Jacksonville", "FL", ["Kelo"],
        "https://murrayhilltheatre.com/event/kelo-cho-presents-the-worship-after-christmas/", "Murray Hill Theatre official event",
        venue="Murray Hill Theatre", address="932 Edgewood Ave S", time="19:00", doors="18:00", tz="America/New_York", price="$15",
        ticket="https://www.eventbrite.com/e/kelo-cho-presents-the-worship-after-christmas-tickets-1992972194483", authority="official_event",
        advertised=["Kelo Cho"]
    ),
    "cj-emulous-shiloh-church-sierra-vista-2026": E(
        "Shiloh Church with CJ Emulous", "2026-09-20", "Sierra Vista", "AZ", ["CJ Emulous"],
        "https://www.cjemulous.com/event-details/shiloh-church-w-cj-emulous", "CJ Emulous official calendar",
        venue="Shiloh Christian Ministries", address="1519 S Ave Del Sol", event_type="church", tz="America/Phoenix",
        notes="Church appearance. Artist calendar publishes 7:00 PM, but the main time is left blank pending independent local-time confirmation."
    ),
    "cj-emulous-access-granted-retreat-winters-2026": E(
        "Access Granted Marriage Retreat with Psalm Bird & CJ Emulous", "2026-09-25", "Winters", "CA", ["CJ Emulous"],
        "https://www.cjemulous.com/event-details/access-granted-marriage-retreat-w-psalm-bird-cj-emulous", "CJ Emulous official calendar",
        venue="Hotel Winters", address="12 Abbey St", event_type="retreat", tz="America/Los_Angeles", advertised=["Psalm Bird", "CJ Emulous"],
        admissionNotes="Marriage retreat; RSVP/registration applies. The public artist listing does not state broader public-admission eligibility; confirm eligibility with the organizer.",
        notes="Retreat appearance, not categorized as a public concert. Published artist-calendar time is left blank pending independent local-time confirmation."
    ),
    "cj-emulous-sac-town-give-back-west-sacramento-2026": E(
        "The Sac Town Give Back", "2026-10-17", "West Sacramento", "CA", ["CJ Emulous"],
        "https://www.cjemulous.com/event-details/the-sac-town-give-back", "CJ Emulous official calendar",
        venue="985 Riverfront St", address="985 Riverfront St", event_type="appearance", tz="America/Los_Angeles",
        notes="Artist appearance at a community give-back event. The official title does not establish a standalone rap concert; time is left blank pending a local source."
    ),
    "cj-emulous-new-mainstream-miami-2026-11-05": E(
        "New Mainstream Tour — Miles Minnick, Tommy Zuko & CJ Emulous", "2026-11-05", "Miami", "FL",
        ["Miles Minnick", "Tommy Zuko", "CJ Emulous"],
        "https://www.cjemulous.com/event-details/new-mainstream-tour-w-miles-minnick-tommy-zuko-23", "CJ Emulous official New Mainstream Tour calendar",
        headliner="Miles Minnick", tz="America/New_York", ticket="https://milesminnick.com/tour",
        notes="Official artist calendar confirms the date and Miami, but no venue. Time is left blank pending local venue/ticket confirmation."
    ),
    "cj-emulous-new-mainstream-jacksonville-2026-11-08": E(
        "New Mainstream Tour — Miles Minnick, Tommy Zuko & CJ Emulous", "2026-11-08", "Jacksonville", "FL",
        ["Miles Minnick", "Tommy Zuko", "CJ Emulous"],
        "https://www.cjemulous.com/event-details/new-mainstream-tour-w-miles-minnick-tommy-zuko-26", "CJ Emulous official New Mainstream Tour calendar",
        headliner="Miles Minnick", tz="America/New_York", ticket="https://milesminnick.com/tour",
        notes="Official artist calendar confirms the date and Jacksonville, but no venue. Time is left blank pending local venue/ticket confirmation."
    ),
    "cj-emulous-glo-concert-los-angeles-2026": E(
        "GLO Concert", "2026-11-15", "Los Angeles", "CA", ["CJ Emulous"], "https://www.cjemulous.com/event-details/gloconcert",
        "CJ Emulous official calendar", tz="America/Los_Angeles", lineupExplicit=False,
        notes="CJ Emulous is confirmed by his official calendar. Venue and additional artists remain unconfirmed; time is left blank pending a local source."
    ),
    "cj-emulous-state-youth-conference-cocoa-2026": E(
        "State Youth Conference with CJ Emulous", "2026-11-27", "Cocoa", "FL", ["CJ Emulous"],
        "https://www.cjemulous.com/event-details/state-youth-conference-w-cj-emulous", "CJ Emulous official calendar",
        event_type="conference", tz="America/New_York", end_date="2026-11-29", sessionDates=["2026-11-27", "2026-11-28", "2026-11-29"],
        publishedSessionTimes={"2026-11-27": "19:00", "2026-11-28": "10:00", "2026-11-29": "09:00"},
        notes="One conference record covers all three official CJ Emulous appearances. Main time is blank pending independent local-time confirmation.",
        extra=[
            src("CJ Emulous official calendar — Nov 28 session", "https://www.cjemulous.com/event-details/state-youth-conference-w-cj", "artist_calendar", 100),
            src("CJ Emulous official calendar — Nov 29 session", "https://www.cjemulous.com/event-details/state-youth-conference-w-cj-emulous-2", "artist_calendar", 100),
        ]
    ),
    "cj-emulous-christlike-christmas-berkeley-2026": E(
        "Christlike Christmas — CJ Emulous & Miles Minnick", "2026-12-02", "Berkeley", "CA", ["CJ Emulous", "Miles Minnick"],
        "https://www.cjemulous.com/event-details/christlike-christmas-w-cj-emulous-miles-minnick", "CJ Emulous official calendar",
        tz="America/Los_Angeles", notes="Venue and independently confirmed local time are unpublished."
    ),
    "cj-emulous-christlike-christmas-felton-2026": E(
        "Christlike Christmas — CJ Emulous & Miles Minnick", "2026-12-04", "Felton", "CA", ["CJ Emulous", "Miles Minnick"],
        "https://www.cjemulous.com/event-details/christlike-christmas-w-cj-emulous-miles-minnick-2", "CJ Emulous official calendar",
        tz="America/Los_Angeles", notes="Venue and independently confirmed local time are unpublished."
    ),
    "cj-emulous-rize-az-music-festival-2027": E(
        "Rize AZ Music Festival", "2027-04-17", "Sierra Vista", "AZ", ["CJ Emulous"],
        "https://www.cjemulous.com/event-details/rize-az-music-festival", "CJ Emulous official calendar", event_type="festival",
        tz="America/Phoenix", lineupExplicit=False, notes="Venue, additional lineup and independently confirmed local performance time remain unpublished."
    ),
    "jimmy-rock-worship-wawa-miami-2026": E(
        "JIMMY ROCK'S Rave & Worship — The Worship Wawa", "2026-09-18", "Miami", "FL", ["JIMMY ROCK"],
        "https://www.theworshipwawa.com/jimmyrock-rave-worship", "The Worship Wawa official event",
        venue="The Worship Wawa — Margaret Pace Park pickup", address="1745 N Bayshore Dr", event_type="party_bus", time="17:00",
        tz="America/New_York", ticket="https://fareharbor.com/embeds/book/theworshipwawa/?full-items=yes",
        image=JIMMY_MIAMI_EVENT_IMAGE, image_type="event_artwork", image_override=True,
        imageSource="The Worship Wawa official event poster",
        imageSourceUrl="https://www.theworshipwawa.com/jimmyrock-rave-worship",
        rideTimes=["17:00", "18:15", "19:30", "20:45"],
        notes="In-person party-bus event. Four one-hour rides depart at 5:00, 6:15, 7:30 and 8:45 PM. Arrive 15 minutes early; Bandsintown's 4:30 PM header aligns with earliest check-in, not an online event.",
        extra=[src("JIMMY ROCK Bandsintown", "https://www.bandsintown.com/e/108769357", "artist_calendar", 74)]
    ),
    "jimmy-rock-rave-worship-centennial-2026": E(
        "JIMMY ROCK — Rave & Worship Denver 2026", "2026-09-25", "Centennial", "CO", ["JIMMY ROCK"],
        "https://www.eventbrite.com/e/jimmy-rock-rave-worship-denver-2026-tickets-1998020581344", "Official Eventbrite listing",
        venue="Encounter Church Denver", address="6825 S Galena St", time="18:00", end_time="22:00", doors="17:30", tz="America/Denver",
        ticket="https://www.eventbrite.com/e/jimmy-rock-rave-worship-denver-2026-tickets-1998020581344", authority="venue_ticket",
        image=JIMMY_DENVER_EVENT_IMAGE, image_type="event_artwork", image_override=True,
        imageSource="Official Eventbrite event artwork",
        imageSourceUrl="https://www.eventbrite.com/e/jimmy-rock-rave-worship-denver-2026-tickets-1998020581344",
        advertised=["JIMMY ROCK", "Ralov", "trtle", "Transform DJs"],
        notes="Eventbrite lists 6:00–10:00 PM with 5:30 PM doors; Bandsintown's 5:30 PM header corresponds to doors.",
        extra=[src("JIMMY ROCK Bandsintown", "https://www.bandsintown.com/e/108778379", "artist_calendar", 74)]
    ),
    "jimmy-rock-rave-worship-dallas-2026": E(
        "JIMMY ROCK — Rave & Worship Dallas", "2026-10-18", "Dallas", "TX", ["JIMMY ROCK"],
        "https://www.eventim.com/event/jimmy-rock-am-fm-22038857/", "Eventim official ticket listing", venue="AM/FM Dallas — Backyard",
        address="1950 Market Center Blvd", time="19:00", doors="18:00", tz="America/Chicago",
        ticket="https://www.eventim.com/event/jimmy-rock-am-fm-22038857/", authority="venue_ticket",
        image=JIMMY_DALLAS_EVENT_IMAGE, image_type="event_artwork", image_override=True,
        imageSource="Official Dallas ticket artwork",
        imageSourceUrl="https://www.eventim.com/event/jimmy-rock-am-fm-22038857/",
        advertised=["JIMMY ROCK", "J. Horton"], ageRestriction="All ages",
        notes="Doors 6:00 PM; show 7:00 PM; all ages. J. Horton is billed. Artists mentioned only in performer biographies are not associated.",
        extra=[src("JIMMY ROCK Bandsintown", "https://www.bandsintown.com/e/108805378", "artist_calendar", 74)]
    ),
}

EXISTING = {
    "cj-emulous-syatp-sierra-vista-2026": ("https://www.cjemulous.com/event-details/syatp-concert-w-cj-emulous", ["CJ Emulous"]),
    "cj-emulous-live-loud-chico-2026": ("https://www.cjemulous.com/event-details/live-loud-w-cj-emulous", ["CJ Emulous"]),
    "cj-emulous-turlock-back-to-school-2026": ("https://www.cjemulous.com/event-details/back-to-school-concert-w-cj-emulous-1", None),
    "cj-emulous-kickback-grand-prairie-2026": ("https://www.cjemulous.com/event-details/the-kickback-w-cj-emulous", ["CJ Emulous"]),
    "miles-cj-zion-ultra-lounge-chandler-2026": ("https://www.cjemulous.com/event-details/zion-ultra-lounge-w-miles-minnick-cj-emulous", ["Miles Minnick", "CJ Emulous"]),
}
TAMPA_CONFLICTS = {
    "https://www.cjemulous.com/event-details/new-mainstream-tour-w-miles-minnick-tommy-zuko-24",
    "https://www.cjemulous.com/event-details/new-mainstream-tour-w-miles-minnick-tommy-zuko-25",
}


def urls(e):
    out = {str(e.get("officialUrl") or ""), str(e.get("ticketUrl") or "")}
    out |= {str(s.get("url") or "") for s in e.get("sources") or [] if isinstance(s, dict)}
    return {u for u in out if u}


def find(rows, event_id, wanted):
    for r in rows:
        if str(r.get("id") or "").removeprefix("manual:") == event_id: return r
    wu = urls(wanted)
    for r in rows:
        if wu & urls(r): return r
    for r in rows:
        if r.get("startDate") == wanted.get("startDate") and norm(r.get("city")) == norm(wanted.get("city")):
            a, b = norm(r.get("title")), norm(wanted.get("title"))
            if a == b or (a and b and (a in b or b in a)): return r
    return None


def merge(row, wanted):
    keep = {k: row.get(k) for k in ("id", "ticketUrl", "officialUrl") if row.get(k)}
    old_image = row.get("image") if row.get("image") and "event-fallback" not in str(row.get("image")) else ""
    row.update(wanted); row.update(keep)
    if old_image and not wanted.get("imageOverride") and not wanted.get("image"): row["image"] = old_image


def collapse_cocoa(rows):
    session_urls = {
        "https://www.cjemulous.com/event-details/state-youth-conference-w-cj-emulous",
        "https://www.cjemulous.com/event-details/state-youth-conference-w-cj",
        "https://www.cjemulous.com/event-details/state-youth-conference-w-cj-emulous-2",
    }
    rows[:] = [r for r in rows if not (
        r.get("startDate") in {"2026-11-27", "2026-11-28", "2026-11-29"} and norm(r.get("city")) == "cocoa" and
        ("state youth conference" in norm(r.get("title")) or bool(urls(r) & session_urls))
    )]


def patch_rows(path, manual):
    rows = load(path)
    for r in rows:
        base = str(r.get("id") or "").removeprefix("manual:")
        if base in EXISTING:
            url, artists = EXISTING[base]
            if artists:
                r["artists"] = artists
                r["headliner"] = artists[0]
            r["auditVerified"] = AUDIT
            sources = r.setdefault("sources", [])
            if not any(s.get("url") == url for s in sources if isinstance(s, dict)):
                sources.append(src("CJ Emulous official calendar", url, "artist_calendar", 100))
    collapse_cocoa(rows)
    for event_id, wanted in UPSERTS.items():
        row = find(rows, event_id, wanted)
        if row is None:
            value = dict(wanted); value["id"] = event_id if manual else "manual:" + event_id; rows.append(value)
        else:
            merge(row, wanted)
    save(path, rows)


def patch_artist():
    p = ROOT / "config" / "artists.json"; rows = load(p)
    found = [a for a in rows if norm(a.get("name")) == "jimmy rock"]
    if not found:
        a = {"name": "JIMMY ROCK", "aliases": ["JIMMY ROCK", "Jimmy Rock"], "enabled": True, "ticketmasterEnabled": False,
             "category": "core", "monitoringPriority": 2, "topStreamingPriority": False, "socialSearchEnabled": True,
             "activeStatus": "active_or_unknown", "textMatchEnabled": True, "rosterOrder": len(rows) + 1}
        rows.append(a)
    else: a = found[0]
    a.update({"website": "https://www.jimmyrock.com/", "websiteRegistryVerified": True,
              "instagramProfile": "https://www.instagram.com/jimmyrock/",
              "spotifyProfile": "https://open.spotify.com/artist/6YN7TGi4ZlsAy38fZVPvkN",
              "youtubeProfile": "https://www.youtube.com/@JimmyRock",
              "bandsintownProfile": "https://www.bandsintown.com/a/7118692-jimmy-rock",
              "imageUrl": JIMMY_IMAGE, "imagePosition": "center", "preferArtistImage": True,
              "officialImageSource": "https://www.jimmyrock.com/"})
    save(p, rows)


def patch_labels():
    p = ROOT / "app.js"; text = p.read_text(encoding="utf-8")
    if "function eventTypeLabel(event)" not in text:
        anchor = "function eventCard(event) {"
        helper = 'function eventTypeLabel(event) {\n  const v=String(event?.eventType||"concert").toLowerCase();\n  return ({festival:"Festival",retreat:"Retreat",conference:"Conference",church:"Church appearance",party_bus:"Party-bus event",appearance:"Appearance",concert:"Concert"})[v]||"Event";\n}\n'
        if anchor not in text: raise SystemExit("eventCard anchor missing")
        text = text.replace(anchor, helper + anchor, 1)
    text = text.replace('event.eventType === "festival" ? "Festival" : "Concert"', 'eventTypeLabel(event)')
    p.write_text(text, encoding="utf-8")


def verify():
    events = load(ROOT / "events.json"); artists = load(ROOT / "config" / "artists.json")
    for event_id, wanted in UPSERTS.items():
        matches = []
        for r in events:
            same_id = str(r.get("id") or "").removeprefix("manual:") == event_id
            same_url = bool(urls(r) & urls(wanted))
            same_slot = r.get("startDate") == wanted.get("startDate") and norm(r.get("city")) == norm(wanted.get("city")) and norm(r.get("title")) == norm(wanted.get("title"))
            if same_id or same_url or same_slot: matches.append(r)
        if len(matches) != 1: raise SystemExit(f"Expected one {event_id}; found {len(matches)}")
    if len([a for a in artists if norm(a.get("name")) == "jimmy rock"]) != 1: raise SystemExit("JIMMY ROCK profile missing/duplicated")
    if any(TAMPA_CONFLICTS & urls(r) for r in events): raise SystemExit("Unresolved CJ Tampa/Flavor conflict was published")
    cocoa = [r for r in events if r.get("startDate") == "2026-11-27" and r.get("endDate") == "2026-11-29" and norm(r.get("city")) == "cocoa"]
    if len(cocoa) != 1: raise SystemExit("Cocoa conference must be one 11/27–11/29 record")
    if any(norm(a.get("name")) == "madison ryann ward" and a.get("enabled") is not False for a in artists): raise SystemExit("Madison Ryann Ward exclusion regressed")


def apply_requested_repairs():
    patch_artist()
    patch_rows(ROOT / "config" / "manual-events.json", True)
    patch_rows(ROOT / "supplemental-events.json", False)
    patch_rows(ROOT / "events.json", False)
    patch_labels()
    verify()


if __name__ == "__main__": apply_requested_repairs()
