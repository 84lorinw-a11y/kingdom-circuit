from __future__ import annotations

import datetime as dt
import html
import json
import pathlib
import re

SITE_ORIGIN = "https://kingdomcircuit.com"
BRAND_LOGO = "/assets/logo-wordmark.svg?v=1"
GA_ID = "G-N2KK9XF4TJ"
ARCHIVE_DAYS = 550
ARCHIVE_LIMIT = 12

STATE_NAMES = {
    "AL":"Alabama","AK":"Alaska","AZ":"Arizona","AR":"Arkansas","CA":"California","CO":"Colorado","CT":"Connecticut","DE":"Delaware","DC":"District of Columbia","FL":"Florida","GA":"Georgia","HI":"Hawaii","ID":"Idaho","IL":"Illinois","IN":"Indiana","IA":"Iowa","KS":"Kansas","KY":"Kentucky","LA":"Louisiana","ME":"Maine","MD":"Maryland","MA":"Massachusetts","MI":"Michigan","MN":"Minnesota","MS":"Mississippi","MO":"Missouri","MT":"Montana","NE":"Nebraska","NV":"Nevada","NH":"New Hampshire","NJ":"New Jersey","NM":"New Mexico","NY":"New York","NC":"North Carolina","ND":"North Dakota","OH":"Ohio","OK":"Oklahoma","OR":"Oregon","PA":"Pennsylvania","RI":"Rhode Island","SC":"South Carolina","SD":"South Dakota","TN":"Tennessee","TX":"Texas","UT":"Utah","VT":"Vermont","VA":"Virginia","WA":"Washington","WV":"West Virginia","WI":"Wisconsin","WY":"Wyoming"
}
MONTH_RE = re.compile(r"^(january|february|march|april|may|june|july|august|september|october|november|december)-\d{4}$")
STATE_BY_SLUG: dict[str, str] = {}

STYLE = """<style id="past-show-archive-styles">
.past-shows-archive{max-width:1180px;margin:38px auto 0;padding:0 20px 34px;color:#d8d8d8}.past-shows-archive details{border-top:1px solid rgba(255,255,255,.12);padding-top:18px}.past-shows-archive summary{display:flex;align-items:center;justify-content:space-between;gap:18px;cursor:pointer;list-style:none;font-weight:700;color:#f1f1f1}.past-shows-archive summary::-webkit-details-marker{display:none}.past-shows-archive summary:after{content:'+';font-size:1.35rem;color:#df725c;font-weight:500}.past-shows-archive details[open] summary:after{content:'−'}.past-shows-archive .past-count{font-size:.78rem;font-weight:600;color:#8f8f8f;text-transform:uppercase;letter-spacing:.08em;margin-left:auto}.past-show-list{margin-top:14px;border-top:1px solid rgba(255,255,255,.07)}.past-show-row{display:grid;grid-template-columns:132px 1fr;gap:18px;padding:15px 0;border-bottom:1px solid rgba(255,255,255,.07)}.past-show-date{font-size:.84rem;color:#9d9d9d;padding-top:2px}.past-show-copy h3{font-size:1rem;line-height:1.35;margin:0 0 5px;font-weight:700}.past-show-copy h3 a{color:#f2f2f2;text-decoration:none}.past-show-copy h3 a:hover{color:#df725c}.past-show-copy p{font-size:.84rem;line-height:1.5;color:#9d9d9d;margin:0}.past-archive-note{font-size:.78rem;line-height:1.5;color:#777;margin:12px 0 0}.past-event-notice{border:1px solid rgba(223,114,92,.28);background:rgba(223,114,92,.06);border-radius:12px;padding:18px;margin:18px 0}@media(max-width:640px){.past-show-row{grid-template-columns:1fr;gap:5px}.past-shows-archive{padding-left:16px;padding-right:16px}.past-shows-archive summary{align-items:flex-start;flex-wrap:wrap}.past-shows-archive .past-count{margin-left:0}}
</style>"""
SECTION_RE = re.compile(r'<section class="past-shows-archive" data-past-shows-archive>.*?</section>', re.I | re.S)


def slug(value: object) -> str:
    text = str(value or "").strip().casefold().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "item"


STATE_BY_SLUG.update({slug(name): code for code, name in STATE_NAMES.items()})


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def fnv(value: object) -> str:
    h = 0x811C9DC5
    for byte in str(value or "").encode():
        h ^= byte
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"[:6]


def event_slug(event: dict) -> str:
    signature = event.get("id") or json.dumps(event, sort_keys=True)
    return f"{slug(event.get('title') or 'event')}-{event.get('startDate','')}-{slug(event.get('city'))}-{fnv(signature)}"


def event_path(event: dict) -> str:
    return f"/event/{event_slug(event)}/"


def artist_path(name: str) -> str:
    return f"/artists/{slug(name)}/"


def state_path(code: str) -> str:
    return f"/shows/{slug(STATE_NAMES.get(code, code))}/"


def city_path(city: str, code: str) -> str:
    return f"/shows/{slug(city)}-{slug(STATE_NAMES.get(code, code))}/"


def page_url(root: pathlib.Path, page: pathlib.Path) -> str:
    rel = page.relative_to(root)
    if rel == pathlib.Path("index.html"):
        return "/"
    if rel.name != "index.html":
        return "/" + rel.as_posix()
    return "/" + rel.parent.as_posix().strip("./") + "/"


def event_date(event: dict) -> dt.date | None:
    raw = str(event.get("endDate") or event.get("startDate") or "")[:10]
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        return None


def date_label(event: dict) -> str:
    raw = str(event.get("startDate") or "")[:10]
    try:
        return dt.date.fromisoformat(raw).strftime("%b %-d, %Y")
    except ValueError:
        return raw or "Past date"


def is_test(event: dict) -> bool:
    text = " ".join([
        str(event.get("title") or ""), str(event.get("venue") or ""),
        str(event.get("city") or ""), str(event.get("headliner") or ""),
        " ".join(str(a) for a in event.get("artists", []) if a),
    ]).casefold()
    urls = " ".join(str(event.get(k) or "") for k in ("ticketUrl", "officialUrl")).casefold()
    return any(x in urls for x in ("example.com", "example.org", "example.net")) or bool(
        re.search(r"\btest\s+(artist|city|venue|event|show|concert)\b", text)
    )


def trusted(event: dict) -> bool:
    if event.get("verifiedVersion") or norm(event.get("confidence")) in {"high", "verified"}:
        return True
    for source in event.get("sources", []) if isinstance(event.get("sources"), list) else []:
        authority = norm(source.get("authority")) if isinstance(source, dict) else ""
        if authority in {"artist_calendar", "official", "official_site", "promoter", "ticketing", "venue", "festival", "primary"}:
            return True
    url = str(event.get("officialUrl") or event.get("ticketUrl") or "").casefold()
    return bool(url and "bandsintown.com" not in url)


def known_artists(root: pathlib.Path) -> tuple[set[str], dict[str, str]]:
    path = root / "config/artists.json"
    if not path.is_file():
        return set(), {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set(), {}
    known: set[str] = set()
    by_slug: dict[str, str] = {}
    for artist in data if isinstance(data, list) else []:
        if not isinstance(artist, dict) or artist.get("enabled") is False:
            continue
        name = str(artist.get("name") or "").strip()
        if not name:
            continue
        known.add(norm(name)); by_slug[slug(name)] = name
        for alias in artist.get("aliases", []) if isinstance(artist.get("aliases"), list) else []:
            known.add(norm(alias))
    return known, by_slug


def load_events(root: pathlib.Path) -> tuple[list[dict], dict[str, str]]:
    path = root / "event-history.json"
    known, by_slug = known_artists(root)
    if not path.is_file():
        return [], by_slug
    try:
        history = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [], by_slug
    today = dt.date.today(); oldest = today - dt.timedelta(days=ARCHIVE_DAYS)
    selected: dict[str, dict] = {}
    for record in history.get("events", []) if isinstance(history, dict) else []:
        if not isinstance(record, dict) or not record.get("observedOnOrAfterEventDate"):
            continue
        event = record.get("event")
        if not isinstance(event, dict) or is_test(event) or not trusted(event):
            continue
        when = event_date(event)
        if when is None or when >= today or when < oldest:
            continue
        if str(event.get("country") or "US").upper() not in {"", "US", "USA"}:
            continue
        if not all(str(event.get(k) or "").strip() for k in ("title", "city", "state", "startDate")):
            continue
        names = [str(a).strip() for a in event.get("artists", []) if str(a).strip()]
        if not names and event.get("headliner"):
            event = dict(event); event["artists"] = [str(event["headliner"]).strip()]; names = event["artists"]
        if not names or (known and not any(norm(name) in known for name in names)):
            continue
        selected[event_slug(event)] = dict(event)
    events = sorted(selected.values(), key=lambda e: (str(e.get("startDate") or ""), str(e.get("startTime") or ""), str(e.get("title") or "")), reverse=True)
    return events, by_slug


def archive_row(event: dict, known_slugs: set[str]) -> str:
    names = [str(a).strip() for a in event.get("artists", []) if str(a).strip()]
    artists = []
    for name in names[:5]:
        artists.append(f'<a href="{artist_path(name)}">{esc(name)}</a>' if slug(name) in known_slugs else esc(name))
    if len(names) > 5:
        artists.append(f"+{len(names)-5} more")
    location = ", ".join(x for x in (str(event.get("city") or "").strip(), str(event.get("state") or "").strip()) if x)
    details = " · ".join(x for x in (" · ".join(artists), esc(event.get("venue")), esc(location)) if x)
    return f'<article class="past-show-row"><div class="past-show-date">{esc(date_label(event))}</div><div class="past-show-copy"><h3><a href="{event_path(event)}">{esc(event.get("title"))}</a></h3><p>{details}</p></div></article>'


def section(events: list[dict], known_slugs: set[str]) -> str:
    shown = events[:ARCHIVE_LIMIT]
    if not shown:
        return ""
    rows = "".join(archive_row(event, known_slugs) for event in shown)
    noun = "show" if len(shown) == 1 else "shows"
    return f'<section class="past-shows-archive" data-past-shows-archive><details><summary><span>Past shows</span><span class="past-count">{len(shown)} archived {noun}</span></summary><div class="past-show-list">{rows}</div><p class="past-archive-note">Past listings are preserved for concert history. Upcoming shows remain at the top of this page.</p></details></section>'


def inject(page: pathlib.Path, events: list[dict], known_slugs: set[str]) -> bool:
    block = section(events, known_slugs)
    if not block:
        return False
    text = page.read_text(encoding="utf-8", errors="ignore"); original = text
    text = SECTION_RE.sub("", text)
    if 'id="past-show-archive-styles"' not in text and "</head>" in text:
        text = text.replace("</head>", STYLE + "\n</head>", 1)
    if "</main>" in text:
        text = text.replace("</main>", block + "\n</main>", 1)
    if text != original:
        page.write_text(text, encoding="utf-8"); return True
    return False


def past_page(root: pathlib.Path, event: dict, known_slugs: set[str]) -> str:
    title = str(event.get("title") or "Past Christian hip-hop show")
    city = str(event.get("city") or "").strip(); state = str(event.get("state") or "").strip(); venue = str(event.get("venue") or "Venue not provided").strip()
    names = [str(a).strip() for a in event.get("artists", []) if str(a).strip()]
    artists = " · ".join(f'<a href="{artist_path(n)}">{esc(n)}</a>' if slug(n) in known_slugs else esc(n) for n in names)
    canonical = SITE_ORIGIN + event_path(event); original = str(event.get("officialUrl") or event.get("ticketUrl") or "").strip()
    nav = ['<a class="secondary-button" href="/shows/">Upcoming shows</a>']
    city_file = root / city_path(city, state).strip("/") / "index.html"; state_file = root / state_path(state).strip("/") / "index.html"
    if city_file.is_file(): nav.append(f'<a class="secondary-button" href="{city_path(city,state)}">Upcoming {esc(city)} shows</a>')
    elif state_file.is_file(): nav.append(f'<a class="secondary-button" href="{state_path(state)}">Upcoming {esc(STATE_NAMES.get(state,state))} shows</a>')
    source = f'<p><a class="text-link" href="{esc(original)}" target="_blank" rel="noopener">Original event source</a></p>' if original and "example." not in original.casefold() else ""
    schema = {"@context":"https://schema.org","@type":"MusicEvent","name":title,"startDate":str(event.get("startDate") or ""),"eventStatus":"https://schema.org/EventCompleted","eventAttendanceMode":"https://schema.org/OfflineEventAttendanceMode","url":canonical,"location":{"@type":"Place","name":venue,"address":{"@type":"PostalAddress","addressLocality":city,"addressRegion":state,"addressCountry":"US"}},"performer":[{"@type":"MusicGroup","name":n} for n in names]}
    schema_json = json.dumps(schema, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    desc = f"Past Christian hip-hop show: {title} in {city}, {state} on {date_label(event)}. Browse current Kingdom Circuit show listings."
    return f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta name="robots" content="index,follow"><meta name="description" content="{esc(desc)}"><link rel="canonical" href="{esc(canonical)}"><link rel="icon" href="/assets/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="/styles.css?v=10.3"><meta property="og:type" content="website"><meta property="og:title" content="{esc(title)} - Past Show | Kingdom Circuit"><meta property="og:description" content="{esc(desc)}"><meta property="og:url" content="{esc(canonical)}"><script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','{GA_ID}');</script><script type="application/ld+json">{schema_json}</script><title>{esc(title)} - Past Show | Kingdom Circuit</title>{STYLE}</head><body><header class="site-header"><div class="header-inner"><a class="brand" href="/" aria-label="The Kingdom Circuit home"><img src="{BRAND_LOGO}" alt="The Kingdom Circuit - Christian hip-hop, live and connected"></a></div></header><main><section class="event-detail-section"><p class="eyebrow"><a class="text-link" href="/shows/">Shows</a> / Past show</p><article class="event-detail"><div class="event-detail-copy"><p class="eyebrow">Past show</p><h1>{esc(title)}</h1><p class="artist-line">{artists}</p><div class="past-event-notice"><strong>This event has passed.</strong><p>Kingdom Circuit keeps verified past listings available as concert history. Use the links below for current shows.</p></div><dl class="detail-list"><div><dt>Date</dt><dd>{esc(date_label(event))}</dd></div><div><dt>Venue</dt><dd>{esc(venue)}</dd></div><div><dt>Location</dt><dd>{esc(city)}, {esc(state)}</dd></div></dl><div class="profile-links">{''.join(nav)}</div>{source}</div></article></section></main><footer class="site-footer"><div><strong>The Kingdom Circuit</strong><p>Christian hip-hop, live and connected.</p></div><div class="footer-links"><a href="/shows/">All Shows</a><a href="/artists/">Artists</a><a href="/festivals/">Festivals</a><a href="/submit/">Submit a Show</a></div><p class="footer-note">Past event details are preserved for historical reference.</p></footer></body></html>'''


def apply_past_show_archives(root: pathlib.Path) -> dict:
    events, artist_by_slug = load_events(root); known_slugs = set(artist_by_slug)
    if not events:
        history = root / "event-history.json"
        if history.is_file(): history.unlink()
        return {"eligiblePastEvents": 0, "archiveSections": 0, "pastEventPages": 0}

    sections = 0
    for page in sorted(root.rglob("*.html")):
        parts = [p for p in page_url(root, page).strip("/").split("/") if p]; matches: list[dict] = []
        if parts and parts[0] == "artists" and len(parts) in {2, 3}:
            artist = artist_by_slug.get(parts[1])
            if artist:
                target = norm(artist); matches = [e for e in events if target in {norm(n) for n in e.get("artists", [])}]
                if len(parts) == 3:
                    code = STATE_BY_SLUG.get(parts[2]); matches = [e for e in matches if e.get("state") == code]
        elif parts and parts[0] == "shows" and len(parts) == 2:
            leaf = parts[1]; code = STATE_BY_SLUG.get(leaf)
            if code:
                matches = [e for e in events if e.get("state") == code]
            elif leaf != "this-month" and not MONTH_RE.match(leaf):
                matches = [e for e in events if slug(e.get("city")) + "-" + slug(STATE_NAMES.get(str(e.get("state") or ""), str(e.get("state") or ""))) == leaf]
        if matches and inject(page, matches, known_slugs): sections += 1

    for event in events:
        target = root / event_path(event).strip("/") / "index.html"; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(past_page(root, event, known_slugs), encoding="utf-8")

    history = root / "event-history.json"
    if history.is_file(): history.unlink()
    return {"eligiblePastEvents": len(events), "archiveSections": sections, "pastEventPages": len(events)}
