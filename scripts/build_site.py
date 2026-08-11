#!/usr/bin/env python3
"""Build The Kingdom Circuit's multi-page static site.

The show collector owns events.json. This generator turns the verified event data
and artist registry into crawlable HTML pages for GitHub Pages.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote, urlencode, urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "_site"
BASE_URL = "https://kingdomcircuit.com"
GA_ID = "G-N2KK9XF4TJ"
FORMSPREE_ENDPOINT = "https://formspree.io/f/mljreawj"
NEW_WINDOW_DAYS = 14
NEW_SHOWS_ACTIVATION_DATE = date(2026, 8, 12)

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}

CATEGORY_LABELS = {
    "core": "Christian hip-hop",
    "reach": "Reach Records",
    "rmg": "Reflection Music Group",
    "group": "Group or collective",
    "solo": "Christian hip-hop artist",
    "dj": "DJ or producer",
    "crossover": "Crossover artist",
    "legacy": "Legacy Christian hip-hop",
    "international": "International Christian hip-hop",
    "provisional": "CHH artist — profile under review",
}

NAV_ITEMS = [
    ("home", "/", "Home"),
    ("shows", "/shows/", "All Shows"),
    ("month", "/shows/this-month/", "This Month"),
    ("festivals", "/festivals/", "Festivals"),
    ("new", "/new-shows/", "New Shows"),
    ("artists", "/artists/", "Artists"),
    ("submit", "/submit/", "Submit a Show"),
]


def load_json(path: Path, fallback: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return fallback


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    return cleaned or "item"


def short_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:7]


def safe_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return raw
    except ValueError:
        pass
    return ""


def image_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.startswith("assets/"):
        return "/" + raw
    if raw.startswith("/assets/"):
        return raw
    return safe_url(raw)


def parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError:
        return None


def parse_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def format_date(value: Any, include_year: bool = True) -> str:
    parsed = parse_date(value)
    if not parsed:
        return "Date to be announced"
    fmt = "%B %-d, %Y" if include_year else "%B %-d"
    try:
        return parsed.strftime(fmt)
    except ValueError:  # Windows-compatible fallback; harmless on Linux.
        month = parsed.strftime("%B")
        return f"{month} {parsed.day}, {parsed.year}" if include_year else f"{month} {parsed.day}"


def format_date_range(event: dict[str, Any]) -> str:
    start = parse_date(event.get("startDate"))
    end = parse_date(event.get("endDate"))
    if not start:
        return "Date to be announced"
    if not end or end == start:
        return format_date(start.isoformat())
    if start.year == end.year and start.month == end.month:
        return f"{start.strftime('%B')} {start.day}–{end.day}, {start.year}"
    if start.year == end.year:
        return f"{start.strftime('%B')} {start.day}–{end.strftime('%B')} {end.day}, {start.year}"
    return f"{format_date(start.isoformat())}–{format_date(end.isoformat())}"


def format_time(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = datetime.strptime(raw[:5], "%H:%M")
        return parsed.strftime("%-I:%M %p")
    except ValueError:
        return raw


def human_updated(status: dict[str, Any]) -> str:
    for key in ("finishedAt", "checkedAt", "lastUpdated", "completedAt"):
        parsed = parse_datetime(status.get(key))
        if parsed:
            local = parsed.astimezone(timezone.utc)
            return local.strftime("%B %-d, %Y at %-I:%M %p UTC")
    return "Update time unavailable"


def first_seen_date(event: dict[str, Any]) -> date | None:
    parsed = parse_datetime(event.get("firstSeen") or event.get("firstSeenAt"))
    return parsed.date() if parsed else None


def is_recent(event: dict[str, Any], today: date, days: int = NEW_WINDOW_DAYS) -> bool:
    first_seen = first_seen_date(event)
    if not first_seen or first_seen < NEW_SHOWS_ACTIVATION_DATE:
        return False
    age = (today - first_seen).days
    return 0 <= age < days


def canonical_artist_lookup(artists: list[dict[str, Any]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for artist in artists:
        name = str(artist.get("name") or "").strip()
        if not name:
            continue
        lookup[name.casefold()] = name
        for alias in artist.get("aliases") or []:
            alias_text = str(alias or "").strip()
            if alias_text:
                lookup[alias_text.casefold()] = name
    return lookup


def normalize_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    valid = []
    for item in events:
        if not isinstance(item, dict):
            continue
        if str(item.get("country") or "US").upper() != "US":
            continue
        if str(item.get("status") or "").lower() == "cancelled":
            continue
        if not parse_date(item.get("startDate")):
            continue
        valid.append(item)
    return sorted(valid, key=lambda event: (
        str(event.get("startDate") or "9999-99-99"),
        str(event.get("startTime") or "99:99"),
        str(event.get("city") or ""),
        str(event.get("title") or ""),
    ))


def build_artist_records(
    artist_config: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    lookup = canonical_artist_lookup(artist_config)
    by_name: dict[str, dict[str, Any]] = {}
    for artist in artist_config:
        name = str(artist.get("name") or "").strip()
        if not name or not artist.get("enabled", True):
            continue
        record = dict(artist)
        record["name"] = name
        record["events"] = []
        by_name[name] = record

    # Preserve performers encountered in verified events, even if a roster entry is pending.
    for event in events:
        for raw_name in event.get("artists") or []:
            name = lookup.get(str(raw_name).casefold(), str(raw_name).strip())
            if not name:
                continue
            if name not in by_name:
                by_name[name] = {
                    "name": name,
                    "aliases": [name],
                    "category": "provisional",
                    "enabled": True,
                    "events": [],
                }
            by_name[name]["events"].append(event)

    records = sorted(by_name.values(), key=lambda item: item["name"].casefold())
    return records


def artist_image(artist: dict[str, Any]) -> str:
    configured = image_url(artist.get("imageUrl") or artist.get("image"))
    if configured:
        return configured
    for event in artist.get("events") or []:
        if str(event.get("headliner") or "").casefold() != artist["name"].casefold():
            continue
        if str(event.get("imageType") or "") == "artist":
            resolved = image_url(event.get("image"))
            if resolved:
                return resolved
    return ""


def initials(name: str) -> str:
    tokens = [token for token in re.split(r"\s+", name.strip()) if token]
    if not tokens:
        return "KC"
    if len(tokens) == 1:
        return tokens[0][:2].upper()
    return (tokens[0][0] + tokens[-1][0]).upper()


def event_slug(event: dict[str, Any], seen: set[str]) -> str:
    base = slugify(
        f"{event.get('title') or event.get('headliner') or 'show'} "
        f"{event.get('city') or ''} {event.get('startDate') or ''}"
    )[:110]
    candidate = base
    if candidate in seen:
        candidate = f"{base}-{short_hash(str(event.get('id') or json.dumps(event, sort_keys=True)))}"
    seen.add(candidate)
    return candidate


def build_slug_maps(events: list[dict[str, Any]], artists: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, str]]:
    event_seen: set[str] = set()
    event_map: dict[str, str] = {}
    for event in events:
        event_map[str(event.get("id") or short_hash(json.dumps(event, sort_keys=True)))] = event_slug(event, event_seen)

    artist_seen: set[str] = set()
    artist_map: dict[str, str] = {}
    for artist in artists:
        base = slugify(artist["name"])
        candidate = base
        if candidate in artist_seen:
            candidate = f"{base}-{short_hash(artist['name'])}"
        artist_seen.add(candidate)
        artist_map[artist["name"]] = candidate
    return event_map, artist_map


def event_key(event: dict[str, Any]) -> str:
    return str(event.get("id") or short_hash(json.dumps(event, sort_keys=True)))


def page_head(
    title: str,
    description: str,
    canonical_path: str,
    *,
    image: str = "/assets/logo.png",
    structured_data: list[dict[str, Any]] | None = None,
) -> str:
    canonical = BASE_URL + canonical_path
    resolved_image = image if image.startswith("http") else BASE_URL + image
    json_ld = ""
    if structured_data:
        json_ld = "\n".join(
            f'<script type="application/ld+json">{json.dumps(item, ensure_ascii=False, separators=(",", ":"))}</script>'
            for item in structured_data
        )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', '{GA_ID}');
  </script>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="{escape(description)}">
  <meta name="theme-color" content="#080808">
  <meta property="og:type" content="website">
  <meta property="og:title" content="{escape(title)}">
  <meta property="og:description" content="{escape(description)}">
  <meta property="og:url" content="{escape(canonical)}">
  <meta property="og:image" content="{escape(resolved_image)}">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="canonical" href="{escape(canonical)}">
  <link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/styles.css">
  <script src="/app.js" defer></script>
  <title>{escape(title)}</title>
  {json_ld}
</head>"""


def site_header(active: str) -> str:
    menu_links = []
    for key, href, label in NAV_ITEMS:
        current = ' aria-current="page"' if key == active else ""
        menu_links.append(f'<a href="{href}"{current}>{escape(label)}</a>')
    return f"""
<body data-page="{escape(active)}">
  <header class="site-header">
    <div class="header-inner">
      <a class="brand" href="/" aria-label="The Kingdom Circuit home">
        <img src="/assets/logo.png" alt="The Kingdom Circuit — Christian hip-hop, live and connected">
      </a>
      <button class="menu-toggle" type="button" aria-expanded="false" aria-controls="site-menu" aria-label="Open navigation">
        <span></span><span></span><span></span>
      </button>
    </div>
  </header>
  <div class="menu-backdrop" hidden></div>
  <nav class="menu-drawer" id="site-menu" aria-label="Primary navigation" aria-hidden="true">
    <div class="menu-drawer-head">
      <span>Explore Kingdom Circuit</span>
      <button class="menu-close" type="button" aria-label="Close navigation">×</button>
    </div>
    <div class="menu-links">{''.join(menu_links)}</div>
    <p class="menu-mission">Christian hip-hop, live and connected.</p>
  </nav>"""


def status_warning(status: dict[str, Any]) -> str:
    warnings = status.get("warnings") or []
    errors = status.get("errors") or []
    if errors:
        return "The latest automated update encountered an issue. Existing published listings remain available while the next update retries."
    if warnings:
        return f"Calendar updated. {len(warnings)} source checks were unavailable during the latest run; published listings remain verified."
    return "Calendar updated successfully."


def site_footer(status: dict[str, Any]) -> str:
    return f"""
  <footer class="site-footer">
    <div class="footer-grid">
      <div>
        <strong>The Kingdom Circuit</strong>
        <p>Christian hip-hop, live and connected.</p>
      </div>
      <nav class="footer-links" aria-label="Footer navigation">
        <a href="/shows/">All Shows</a>
        <a href="/artists/">Artists</a>
        <a href="/festivals/">Festivals</a>
        <a href="/submit/">Submit a Show</a>
      </nav>
    </div>
    <p class="disclaimer">Event details may change. Confirm final information with the official organizer or ticket seller before purchasing or traveling.</p>
    <div class="footer-status">
      <span>Last updated: {escape(human_updated(status))}</span>
      <span>{escape(status_warning(status))}</span>
    </div>
  </footer>
</body>
</html>"""


def organization_schema() -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "The Kingdom Circuit",
        "url": BASE_URL,
        "logo": f"{BASE_URL}/assets/logo.png",
        "description": "A Christian hip-hop concert, festival, and artist discovery platform.",
        "sameAs": [],
    }


def breadcrumb_schema(items: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index,
                "name": name,
                "item": BASE_URL + path,
            }
            for index, (name, path) in enumerate(items, 1)
        ],
    }


def render_hero(
    eyebrow: str,
    title: str,
    text: str,
    *,
    mission: str = "",
    actions: list[tuple[str, str, str]] | None = None,
    trust: str = "",
    compact: bool = False,
) -> str:
    action_html = ""
    if actions:
        action_html = '<div class="hero-actions">' + "".join(
            f'<a class="{escape(css)}" href="{escape(href)}">{escape(label)}</a>'
            for label, href, css in actions
        ) + "</div>"
    mission_html = f'<p class="mission-statement">{escape(mission)}</p>' if mission else ""
    trust_html = f'<p class="trust-line">{escape(trust)}</p>' if trust else ""
    compact_class = " hero-compact" if compact else ""
    return f"""
    <section class="page-hero{compact_class}">
      <p class="eyebrow">{escape(eyebrow)}</p>
      <h1>{escape(title)}</h1>
      {mission_html}
      <p class="hero-text">{escape(text)}</p>
      {action_html}
      {trust_html}
    </section>"""


def render_filter_controls(events: list[dict[str, Any]], *, quick: bool = True) -> str:
    artist_names = sorted({str(name) for event in events for name in (event.get("artists") or []) if name}, key=str.casefold)
    states = sorted({str(event.get("state") or "") for event in events if event.get("state")})
    quick_html = ""
    if quick:
        quick_html = """
        <div class="quick-filters" role="group" aria-label="Quick event filters">
          <button class="filter-chip active" type="button" data-date-mode="all">All dates</button>
          <button class="filter-chip" type="button" data-date-mode="weekend">This weekend</button>
          <button class="filter-chip" type="button" data-date-mode="next30">Next 30 days</button>
          <button class="filter-chip" type="button" data-date-mode="month">This month</button>
          <button class="filter-chip" type="button" data-type-mode="festival">Festivals</button>
        </div>"""
    artist_options = "".join(f'<option value="{escape(name.casefold())}">{escape(name)}</option>' for name in artist_names)
    state_options = "".join(f'<option value="{escape(code)}">{escape(STATE_NAMES.get(code, code))}</option>' for code in states)
    return f"""
      <div class="filter-dock" data-filter-dock>
        {quick_html}
        <form class="filters" role="search" data-event-filters>
          <label class="field field-search">
            <span>Search</span>
            <input data-search-filter type="search" placeholder="Artist, city, venue, or event" autocomplete="off">
          </label>
          <label class="field">
            <span>Artist</span>
            <select data-artist-filter><option value="">All artists</option>{artist_options}</select>
          </label>
          <label class="field">
            <span>State</span>
            <select data-state-filter><option value="">All states</option>{state_options}</select>
          </label>
          <label class="field">
            <span>Type</span>
            <select data-type-filter>
              <option value="">All events</option>
              <option value="concert">Concerts</option>
              <option value="festival">Festivals</option>
            </select>
          </label>
          <button class="reset-button" data-reset-filters type="button">Clear filters</button>
        </form>
      </div>"""


def event_card(
    event: dict[str, Any],
    event_map: dict[str, str],
    artist_map: dict[str, str],
    *,
    recent_context: bool = False,
) -> str:
    slug = event_map[event_key(event)]
    title = str(event.get("title") or "Untitled event")
    artists = [str(name) for name in event.get("artists") or [] if name]
    state = str(event.get("state") or "")
    event_type = str(event.get("eventType") or "concert").lower()
    image = image_url(event.get("image")) or "/assets/event-fallback.webp"
    position = str(event.get("imagePosition") or "center")
    official = safe_url(event.get("officialUrl") or event.get("ticketUrl"))
    date_text = format_date_range(event)
    time_text = format_time(event.get("startTime"))
    venue = str(event.get("venue") or "Venue to be announced")
    location = ", ".join(part for part in [str(event.get("city") or ""), state] if part)
    source = str(event.get("sourceName") or "Official event source")
    status = str(event.get("status") or "scheduled").lower()
    lineup_links = []
    for name in artists[:4]:
        artist_slug = artist_map.get(name)
        if artist_slug:
            lineup_links.append(f'<a href="/artists/{artist_slug}/">{escape(name)}</a>')
        else:
            lineup_links.append(escape(name))
    if len(artists) > 4:
        lineup_links.append(f"+{len(artists) - 4} more")
    lineup_html = " · ".join(lineup_links) if lineup_links else "Artist lineup not provided"
    badge_label = "Festival" if event_type == "festival" else "Concert"
    status_badge = ""
    if status not in {"scheduled", "onsale", "on sale"}:
        status_badge = f'<span class="badge badge-status">{escape(status.replace("_", " ").title())}</span>'
    recent_badge = ""
    if recent_context:
        seen = first_seen_date(event)
        if seen:
            recent_badge = f'<span class="badge badge-new">Added {escape(format_date(seen.isoformat(), include_year=False))}</span>'
    official_link = f'<a class="ticket-link ticket-link-small" href="{escape(official)}" target="_blank" rel="noopener noreferrer">Official details</a>' if official else ""
    search_blob = " ".join([title, venue, location, source] + artists).casefold()
    return f"""
      <article class="event-card" data-event-card
        data-search="{escape(search_blob)}"
        data-artists="{escape('|'.join(name.casefold() for name in artists))}"
        data-state="{escape(state)}"
        data-type="{escape(event_type)}"
        data-date="{escape(str(event.get('startDate') or ''))}"
        data-end-date="{escape(str(event.get('endDate') or event.get('startDate') or ''))}">
        <a class="event-media" href="/shows/{slug}/" aria-label="View {escape(title)}">
          <img src="{escape(image)}" alt="{escape(title)} artwork" loading="lazy" style="object-position:{escape(position)}" onerror="this.onerror=null;this.src='/assets/event-fallback.webp';">
        </a>
        <div class="event-content">
          <div class="event-main">
            <div class="event-badges"><span class="badge badge-gold">{badge_label}</span>{recent_badge}{status_badge}</div>
            <h3><a href="/shows/{slug}/">{escape(title)}</a></h3>
            <p class="artist-line">{lineup_html}</p>
            <dl class="event-meta">
              <div><dt>Date</dt><dd>{escape(date_text)}{(' · ' + escape(time_text)) if time_text else ''}</dd></div>
              <div><dt>Venue</dt><dd>{escape(venue)}</dd></div>
              <div><dt>Location</dt><dd>{escape(location or 'Location to be announced')}</dd></div>
            </dl>
          </div>
          <div class="event-footer">
            <p class="source-line">Source: {escape(source)}</p>
            <div class="card-actions">
              <a class="secondary-link" href="/shows/{slug}/">View event</a>
              {official_link}
            </div>
          </div>
        </div>
      </article>"""


def event_grid(
    events: list[dict[str, Any]],
    event_map: dict[str, str],
    artist_map: dict[str, str],
    *,
    recent_context: bool = False,
) -> str:
    if not events:
        return '<div class="empty-state">No verified shows are currently listed in this section. Check back as new dates are added.</div>'
    return '<div class="event-grid" data-event-grid>' + "".join(
        event_card(event, event_map, artist_map, recent_context=recent_context) for event in events
    ) + '</div><div class="empty-state filtered-empty" data-filtered-empty hidden>No shows currently match those filters. Try changing the artist, state, date, or event type.</div>'


def calendar_section(
    events: list[dict[str, Any]],
    event_map: dict[str, str],
    artist_map: dict[str, str],
    *,
    heading: str,
    intro: str,
    quick: bool = True,
    recent_context: bool = False,
    anchor_id: str = "calendar",
) -> str:
    return f"""
    <section class="calendar" id="{escape(anchor_id)}" aria-labelledby="calendar-title">
      <div class="calendar-heading">
        <div>
          <p class="eyebrow">Verified listings</p>
          <h2 id="calendar-title">{escape(heading)}</h2>
          <p class="section-intro">{escape(intro)}</p>
        </div>
        <p class="results-count" data-results-count>{len(events)} shows</p>
      </div>
      {render_filter_controls(events, quick=quick)}
      {event_grid(events, event_map, artist_map, recent_context=recent_context)}
    </section>"""


def page_document(head: str, header: str, main: str, footer: str) -> str:
    return head + header + f"\n<main>{main}</main>\n" + footer


def homepage(events, artists, status, event_map, artist_map) -> str:
    mission = "The Kingdom Circuit exists to connect people with CHH music, concerts, festivals, and community so the music reaches farther and more people have the opportunity to hear the gospel."
    head = page_head(
        "Christian Hip-Hop Shows & Festivals | The Kingdom Circuit",
        "Find verified Christian hip-hop concerts, festivals, tours, and independent events across the United States.",
        "/",
        structured_data=[organization_schema()],
    )
    hero = render_hero(
        "Christian hip-hop, live and connected",
        "Find Christian hip-hop shows across the U.S.",
        "Discover Christian hip-hop concerts, festivals, tours, and independent events across the United States. Search by artist, location, date, or event type, then connect directly to the official event or ticket source.",
        mission=mission,
        actions=[
            ("Find Shows", "#calendar", "primary-button"),
            ("Explore Artists", "/artists/", "secondary-button"),
            ("Submit a Show", "/submit/", "secondary-button"),
        ],
        trust="Updated daily • U.S. music performances only • Official sources prioritized",
    )
    calendar = calendar_section(
        events, event_map, artist_map,
        heading="Find Your Next Show",
        intro="Browse the complete Kingdom Circuit calendar. Use the filters to search by artist, state, date, festival, or event type.",
    )
    return page_document(head, site_header("home"), hero + calendar, site_footer(status))


def list_page(
    active: str,
    title: str,
    description: str,
    path: str,
    eyebrow: str,
    intro: str,
    events: list[dict[str, Any]],
    all_events: list[dict[str, Any]],
    status: dict[str, Any],
    event_map: dict[str, str],
    artist_map: dict[str, str],
    *,
    summary_html: str = "",
    recent_context: bool = False,
    quick: bool = True,
    section_heading: str = "Upcoming Shows",
    section_intro: str = "Use the filters to narrow the list, then open the official event source for final details.",
) -> str:
    head = page_head(title, description, path, structured_data=[breadcrumb_schema([("Home", "/"), (title.split(" | ")[0], path)])])
    hero = render_hero(eyebrow, title.split(" | ")[0], intro, compact=True)
    section = summary_html + calendar_section(
        events, event_map, artist_map,
        heading=section_heading,
        intro=section_intro,
        quick=quick,
        recent_context=recent_context,
    )
    return page_document(head, site_header(active), hero + section, site_footer(status))


def summary_stats(items: list[tuple[str, str]]) -> str:
    cards = "".join(f'<div class="stat-card"><strong>{escape(value)}</strong><span>{escape(label)}</span></div>' for value, label in items)
    return f'<section class="summary-stats" aria-label="Page summary">{cards}</section>'


def artist_directory_page(artists, events, status, artist_map) -> str:
    head = page_head(
        "Christian Hip-Hop Artist Directory | The Kingdom Circuit",
        "Browse Christian hip-hop artists, groups, collectives, DJs, producers, and selected crossover acts, then find their upcoming U.S. shows.",
        "/artists/",
        structured_data=[breadcrumb_schema([("Home", "/"), ("Artists", "/artists/")])],
    )
    hero = render_hero(
        "Discover the artists",
        "Christian Hip-Hop Artist Directory",
        "Discover Christian hip-hop artists, groups, collectives, DJs, producers, and selected crossover acts. Open an artist profile to find official links and upcoming Kingdom Circuit shows.",
        compact=True,
    )
    cards = []
    for artist in artists:
        name = artist["name"]
        slug = artist_map[name]
        upcoming = artist.get("events") or []
        img = artist_image(artist)
        visual = (
            f'<img src="{escape(img)}" alt="{escape(name)}" loading="lazy" onerror="this.closest(\'.artist-visual\').innerHTML=\'<span>{escape(initials(name))}</span>\';">'
            if img else f'<span>{escape(initials(name))}</span>'
        )
        category = CATEGORY_LABELS.get(str(artist.get("category") or ""), "Christian hip-hop")
        label = str(artist.get("label") or artist.get("collective") or "")
        meta = " · ".join(part for part in [category, label] if part)
        cards.append(f"""
        <article class="artist-card" data-artist-card data-search="{escape((name + ' ' + meta).casefold())}" data-has-shows="{'true' if upcoming else 'false'}">
          <a class="artist-visual" href="/artists/{slug}/">{visual}</a>
          <div class="artist-card-body">
            <p class="artist-category">{escape(meta)}</p>
            <h2><a href="/artists/{slug}/">{escape(name)}</a></h2>
            <p>{len(upcoming)} upcoming show{'s' if len(upcoming) != 1 else ''}</p>
            <a class="secondary-link" href="/artists/{slug}/">View artist</a>
          </div>
        </article>""")
    directory = f"""
    <section class="artist-directory">
      <div class="directory-tools">
        <label class="field field-search">
          <span>Search artists</span>
          <input type="search" data-artist-search placeholder="Search artists by name" autocomplete="off">
        </label>
        <label class="check-field"><input type="checkbox" data-has-shows-filter> <span>Artists with upcoming shows</span></label>
        <p class="results-count" data-artist-count>{len(artists)} artists</p>
      </div>
      <div class="artist-grid" data-artist-grid>{''.join(cards)}</div>
      <div class="empty-state" data-artist-empty hidden>No artist profiles match that search.</div>
    </section>"""
    return page_document(head, site_header("artists"), hero + directory, site_footer(status))


def artist_external_links(artist: dict[str, Any]) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(raw: Any, preferred_label: str = "") -> None:
        url = safe_url(raw)
        if not url or url in seen:
            return
        host = urlparse(url).netloc.casefold()
        if preferred_label:
            label = preferred_label
        elif "instagram.com" in host:
            label = "Instagram"
        elif "youtube.com" in host or "youtu.be" in host:
            label = "YouTube"
        elif "spotify.com" in host:
            label = "Spotify"
        elif "music.apple.com" in host:
            label = "Apple Music"
        else:
            label = "Official Website"
        links.append((label, url))
        seen.add(url)

    add(artist.get("officialProfile") or artist.get("officialWebsite") or artist.get("website"))
    add(artist.get("instagramProfile") or artist.get("instagram"), "Instagram")
    add(artist.get("youtubeProfile") or artist.get("youtube"), "YouTube")
    add(artist.get("spotifyProfile") or artist.get("spotify"), "Spotify")

    labels = {label for label, _ in links}
    encoded = quote(str(artist.get("name") or ""))
    if "Spotify" not in labels:
        links.append(("Search Spotify", f"https://open.spotify.com/search/{encoded}"))
    if "YouTube" not in labels:
        links.append(("Search YouTube", f"https://www.youtube.com/results?search_query={encoded}"))
    return links


def artist_page(artist, status, event_map, artist_map) -> str:
    name = artist["name"]
    slug = artist_map[name]
    events = artist.get("events") or []
    category = CATEGORY_LABELS.get(str(artist.get("category") or ""), "Christian hip-hop")
    label = str(artist.get("label") or artist.get("collective") or "")
    description = f"Find upcoming {name} concerts, festivals, official links, and live appearances listed by The Kingdom Circuit."
    image = artist_image(artist)
    head = page_head(
        f"{name} Shows, Music & Official Links | The Kingdom Circuit",
        description,
        f"/artists/{slug}/",
        image=image or "/assets/logo.png",
        structured_data=[
            breadcrumb_schema([("Home", "/"), ("Artists", "/artists/"), (name, f"/artists/{slug}/")]),
            {
                "@context": "https://schema.org",
                "@type": "MusicGroup" if str(artist.get("category")) == "group" else "Person",
                "name": name,
                "url": f"{BASE_URL}/artists/{slug}/",
                **({"image": image if image.startswith("http") else BASE_URL + image} if image else {}),
                "sameAs": [url for label, url in artist_external_links(artist) if not label.startswith("Search ")],
            },
        ],
    )
    if image:
        visual = f'<img src="{escape(image)}" alt="{escape(name)}" onerror="this.closest(\'.profile-visual\').innerHTML=\'<span>{escape(initials(name))}</span>\';">'
    else:
        visual = f'<span>{escape(initials(name))}</span>'
    links = artist_external_links(artist)
    link_html = "".join(f'<a class="secondary-button" href="{escape(url)}" target="_blank" rel="noopener noreferrer">{escape(label_text)}</a>' for label_text, url in links)
    if not link_html:
        link_html = '<p class="muted-copy">Verified official links will appear here as they are added.</p>'
    meta = " · ".join(part for part in [category, label] if part)
    profile = f"""
    <section class="artist-profile">
      <div class="profile-visual">{visual}</div>
      <div class="profile-copy">
        <p class="eyebrow">Artist profile</p>
        <h1>{escape(name)}</h1>
        <p class="profile-meta">{escape(meta)}</p>
        <div class="profile-links">{link_html}</div>
        <a class="text-action" href="/submit/?type=profile-correction&artist={quote(name)}">Report a profile correction</a>
      </div>
    </section>
    <section class="profile-shows">
      <div class="calendar-heading"><div><p class="eyebrow">Verified listings</p><h2>Upcoming {escape(name)} Shows</h2><p class="section-intro">Browse currently verified {escape(name)} concerts, festivals, and live appearances listed by The Kingdom Circuit.</p></div><p class="results-count">{len(events)} shows</p></div>
      {event_grid(events, event_map, artist_map)}
    </section>"""
    return page_document(head, site_header("artists"), profile, site_footer(status))


def event_schema(event: dict[str, Any], page_path: str) -> dict[str, Any]:
    start_date = str(event.get("startDate") or "")
    start_time = str(event.get("startTime") or "")
    start_value = f"{start_date}T{start_time}:00" if start_time else start_date
    end_date = str(event.get("endDate") or start_date)
    image = image_url(event.get("image"))
    official = safe_url(event.get("officialUrl") or event.get("ticketUrl"))
    status_map = {
        "cancelled": "https://schema.org/EventCancelled",
        "postponed": "https://schema.org/EventPostponed",
        "rescheduled": "https://schema.org/EventRescheduled",
    }
    schema: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "MusicEvent",
        "name": str(event.get("title") or "Christian hip-hop event"),
        "startDate": start_value,
        "endDate": end_date,
        "eventStatus": status_map.get(str(event.get("status") or "").lower(), "https://schema.org/EventScheduled"),
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "url": BASE_URL + page_path,
        "location": {
            "@type": "Place",
            "name": str(event.get("venue") or "Venue to be announced"),
            "address": {
                "@type": "PostalAddress",
                "streetAddress": str(event.get("address") or ""),
                "addressLocality": str(event.get("city") or ""),
                "addressRegion": str(event.get("state") or ""),
                "addressCountry": "US",
            },
        },
        "performer": [{"@type": "MusicGroup", "name": str(name)} for name in event.get("artists") or []],
        "organizer": {"@type": "Organization", "name": str(event.get("sourceName") or "Official event organizer"), **({"url": official} if official else {})},
    }
    if image:
        schema["image"] = [image if image.startswith("http") else BASE_URL + image]
    if official:
        schema["offers"] = {
            "@type": "Offer",
            "url": official,
            "availability": "https://schema.org/InStock",
            "validFrom": str(event.get("firstSeen") or event.get("lastVerified") or ""),
        }
    return schema


def event_page(event, all_events, status, event_map, artist_map) -> str:
    slug = event_map[event_key(event)]
    path = f"/shows/{slug}/"
    title = str(event.get("title") or "Christian hip-hop event")
    description = f"{title} in {event.get('city') or 'the U.S.'}, {event.get('state') or ''}. View the verified date, venue, lineup, and official event details."
    image = image_url(event.get("image")) or "/assets/event-fallback.webp"
    head = page_head(
        f"{title} | The Kingdom Circuit",
        description,
        path,
        image=image,
        structured_data=[
            breadcrumb_schema([("Home", "/"), ("Shows", "/shows/"), (title, path)]),
            event_schema(event, path),
        ],
    )
    artists = [str(name) for name in event.get("artists") or [] if name]
    artist_links = []
    for name in artists:
        slug_name = artist_map.get(name)
        artist_links.append(f'<a href="/artists/{slug_name}/">{escape(name)}</a>' if slug_name else escape(name))
    official = safe_url(event.get("officialUrl") or event.get("ticketUrl"))
    city = str(event.get("city") or "")
    state = str(event.get("state") or "")
    state_slug = slugify(STATE_NAMES.get(state, state)) if state else ""
    related = [item for item in all_events if item is not event and set(item.get("artists") or []).intersection(artists)][:3]
    related_html = ""
    if related:
        related_html = f"""
        <section class="related-section">
          <div class="calendar-heading"><div><p class="eyebrow">Keep exploring</p><h2>Related Shows</h2></div></div>
          {event_grid(related, event_map, artist_map)}
        </section>"""
    official_button = f'<a class="primary-button" href="{escape(official)}" target="_blank" rel="noopener noreferrer">Official Details</a>' if official else ""
    detail = f"""
    <article class="event-detail">
      <div class="event-detail-media"><img src="{escape(image)}" alt="{escape(title)} artwork" style="object-position:{escape(str(event.get('imagePosition') or 'center'))}" onerror="this.onerror=null;this.src='/assets/event-fallback.webp';"></div>
      <div class="event-detail-copy">
        <p class="eyebrow">{escape('Festival' if str(event.get('eventType')).lower() == 'festival' else 'Live event')}</p>
        <h1>{escape(title)}</h1>
        <p class="event-detail-lineup">{' · '.join(artist_links) if artist_links else 'Artist lineup not provided'}</p>
        <dl class="detail-list">
          <div><dt>Date</dt><dd>{escape(format_date_range(event))}{(' · ' + escape(format_time(event.get('startTime')))) if format_time(event.get('startTime')) else ''}</dd></div>
          <div><dt>Venue</dt><dd>{escape(str(event.get('venue') or 'Venue to be announced'))}</dd></div>
          <div><dt>Location</dt><dd>{escape(', '.join(part for part in [city, state] if part) or 'Location to be announced')}</dd></div>
          {f'<div><dt>Price</dt><dd>{escape(event.get("price"))}</dd></div>' if event.get('price') else ''}
          <div><dt>Status</dt><dd>{escape(str(event.get('status') or 'scheduled').replace('_',' ').title())}</dd></div>
          <div><dt>Last verified</dt><dd>{escape(format_date(str(event.get('lastVerified') or '')[:10])) if event.get('lastVerified') else 'Verification date unavailable'}</dd></div>
        </dl>
        <div class="detail-actions">{official_button}<a class="secondary-button" href="/submit/?type=correction&event={quote(title)}&url={quote(path)}">Report a Correction</a></div>
        <p class="source-line">Source: {escape(str(event.get('sourceName') or 'Official event source'))}</p>
      </div>
    </article>
    <nav class="context-links" aria-label="Related navigation">
      {''.join(f'<a href="/artists/{artist_map[name]}/">More {escape(name)} shows</a>' for name in artists if name in artist_map)}
      {f'<a href="/states/{state_slug}/">More shows in {escape(STATE_NAMES.get(state, state))}</a>' if state_slug else ''}
      {f'<a href="/festivals/">Related festivals and events</a>' if str(event.get('eventType')).lower() == 'festival' else ''}
    </nav>
    <p class="event-disclaimer">Event details, availability, pricing, and lineups may change. Confirm final information with the official organizer or ticket provider before purchasing or traveling.</p>
    {related_html}"""
    return page_document(head, site_header("shows"), detail, site_footer(status))


def submit_page(status: dict[str, Any]) -> str:
    head = page_head(
        "Submit a Christian Hip-Hop Show | The Kingdom Circuit",
        "Submit a Christian hip-hop concert, festival, tour date, or correction for review by The Kingdom Circuit.",
        "/submit/",
        structured_data=[breadcrumb_schema([("Home", "/"), ("Submit a Show", "/submit/")])],
    )
    hero = render_hero(
        "Help strengthen the calendar",
        "Submit a CHH Show",
        "Know about a Christian hip-hop concert, festival, tour date, church-hosted music event, or campus performance that is missing from the calendar? Send us the official details.",
        compact=True,
    )
    form = f"""
    <section class="submission-page">
      <div class="submission-guidance">
        <h2>What to include</h2>
        <p>Include an official event, ticket, artist, venue, promoter, or social-media source whenever possible. Clear flyers and screenshots are also helpful.</p>
        <p>Every submission is reviewed before publication. Submitting an event does not guarantee that it will be added.</p>
      </div>
      <form class="submission-form" data-submission-form action="{FORMSPREE_ENDPOINT}" method="POST" novalidate>
        <input data-submission-kind name="submission_type" type="hidden" value="New show">
        <label class="field honeypot-field" aria-hidden="true"><span>Leave this field blank</span><input name="_gotcha" tabindex="-1" autocomplete="off"></label>
        <div class="submission-type-switch" role="group" aria-label="Submission type">
          <button class="filter-chip active" type="button" data-submission-mode="New show">Submit a new show</button>
          <button class="filter-chip" type="button" data-submission-mode="Correction">Report a correction</button>
        </div>
        <div class="form-row">
          <label class="field"><span>Your name</span><input name="submitter_name" autocomplete="name" required></label>
          <label class="field"><span>Your email</span><input name="email" type="email" autocomplete="email" required></label>
        </div>
        <label class="field"><span>Event name</span><input name="event_name" data-event-name required></label>
        <div class="form-row">
          <label class="field"><span>Date</span><input name="date" type="date" required></label>
          <label class="field"><span>Local time</span><input name="local_time" type="time"></label>
        </div>
        <label class="field"><span>Venue</span><input name="venue" required></label>
        <div class="form-row">
          <label class="field"><span>City</span><input name="city" required></label>
          <label class="field"><span>State</span><input name="state" maxlength="2" placeholder="TX" required></label>
        </div>
        <label class="field"><span>Confirmed artist lineup</span><textarea name="artist_lineup" rows="3" required></textarea></label>
        <label class="field"><span>Official event, ticket, or social-post URL</span><input name="official_url" type="url" placeholder="https://" required></label>
        <label class="field"><span>Official artwork or flyer URL <em>optional</em></span><input name="artwork_url" type="url" placeholder="https://"></label>
        <label class="field"><span>Your relationship to the event</span><input name="relationship" placeholder="Promoter, artist team, venue, fan..." required></label>
        <label class="field"><span>Additional details <em>optional</em></span><textarea name="details" rows="4" placeholder="Include corrections, screenshot context, or anything that will help verify the event."></textarea></label>
        <input name="page_url" type="hidden" value="{BASE_URL}/submit/">
        <button class="primary-button" type="submit" data-submission-submit>Send for Review</button>
        <p class="form-feedback" data-submission-feedback aria-live="polite"></p>
      </form>
    </section>"""
    return page_document(head, site_header("submit"), hero + form, site_footer(status))


def state_page(code, state_events, status, event_map, artist_map) -> str:
    name = STATE_NAMES.get(code, code)
    slug = slugify(name)
    path = f"/states/{slug}/"
    title = f"Christian Hip-Hop Shows in {name} | The Kingdom Circuit"
    description = f"Find upcoming Christian hip-hop concerts, festivals, and live events in {name}."
    head = page_head(title, description, path, structured_data=[breadcrumb_schema([("Home", "/"), (f"Shows in {name}", path)])])
    hero = render_hero("Shows by location", f"Christian Hip-Hop Shows in {name}", f"Browse verified CHH concerts, festivals, tours, and independent performances currently listed in {name}.", compact=True)
    section = calendar_section(state_events, event_map, artist_map, heading=f"Upcoming Shows in {name}", intro="Open an event to view the verified lineup and official source.", quick=False)
    return page_document(head, site_header("shows"), hero + section, site_footer(status))


def source_fallback_index() -> str:
    """A usable root file if someone briefly switches GitHub Pages to branch deploy."""
    head = page_head(
        "The Kingdom Circuit | Christian Hip-Hop Shows",
        "The Kingdom Circuit is rebuilding the current calendar. Refresh shortly for the latest listings.",
        "/",
        structured_data=[organization_schema()],
    )
    body = render_hero(
        "Christian hip-hop, live and connected",
        "Find Christian hip-hop shows across the U.S.",
        "The live calendar is refreshed by the Kingdom Circuit deployment workflow. If you are seeing this message after an update, refresh the page in a few minutes.",
        mission="The Kingdom Circuit exists to connect people with CHH music, concerts, festivals, and community so the music reaches farther and more people have the opportunity to hear the gospel.",
        actions=[("Refresh Calendar", "/", "primary-button")],
    )
    return page_document(head, site_header("home"), body, site_footer({}))


def generate_site(output_dir: Path, today: date | None = None) -> dict[str, int]:
    today = today or datetime.now(timezone.utc).date()
    events = normalize_events(load_json(ROOT / "events.json", []))
    status = load_json(ROOT / "run-status.json", {})
    artist_config = load_json(ROOT / "config" / "artists.json", [])
    if not isinstance(artist_config, list):
        artist_config = []
    artists = build_artist_records(artist_config, events)
    event_map, artist_map = build_slug_maps(events, artists)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Shared files.
    for filename in ("styles.css", "app.js", "events.json", "run-status.json"):
        source = ROOT / filename
        if source.exists():
            shutil.copy2(source, output_dir / filename)
    assets = ROOT / "assets"
    if assets.exists():
        shutil.copytree(assets, output_dir / "assets", dirs_exist_ok=True)

    write_text(output_dir / "index.html", homepage(events, artists, status, event_map, artist_map))
    write_text(output_dir / "shows" / "index.html", list_page(
        "shows",
        "Christian Hip-Hop Shows | The Kingdom Circuit",
        "Browse verified Christian hip-hop concerts, festivals, tours, and independent performances across the United States.",
        "/shows/",
        "Complete U.S. calendar",
        "Browse upcoming Christian hip-hop concerts, festivals, tours, and independent performances across the United States. Use the filters to find the right event, then visit the official event page for tickets and final details.",
        events, events, status, event_map, artist_map,
        section_heading="Upcoming Shows",
        section_intro="Use the filters to find the right event, then visit the official event page for tickets and final details.",
    ))

    month_events = [event for event in events if (parsed := parse_date(event.get("startDate"))) and parsed.year == today.year and parsed.month == today.month]
    month_label = today.strftime("%B %Y")
    month_summary = summary_stats([
        (str(len(month_events)), "Upcoming shows"),
        (str(len({event.get('state') for event in month_events if event.get('state')})), "States"),
        (str(sum(1 for event in month_events if str(event.get('eventType')).lower() == 'festival')), "Festivals"),
    ])
    write_text(output_dir / "shows" / "this-month" / "index.html", list_page(
        "month",
        f"Christian Hip-Hop Shows in {month_label} | The Kingdom Circuit",
        f"Find every verified Christian hip-hop show currently listed for {month_label}.",
        "/shows/this-month/",
        "Current month",
        f"Find every CHH show currently listed for {month_label}. This page updates automatically as new events are added and past dates are removed.",
        month_events, events, status, event_map, artist_map,
        summary_html=month_summary,
        section_heading="This Month’s Shows",
        section_intro="Browse the complete month chronologically, or use the filters to narrow the list by artist, state, or event type.",
    ))

    festival_events = [event for event in events if str(event.get("eventType") or "").lower() == "festival"]
    festival_summary = summary_stats([
        (str(len(festival_events)), "Upcoming festivals"),
        (str(len({event.get('state') for event in festival_events if event.get('state')})), "States"),
        (str(len({name for event in festival_events for name in event.get('artists') or []})), "Confirmed artists"),
    ])
    write_text(output_dir / "festivals" / "index.html", list_page(
        "festivals",
        "Christian Hip-Hop Festivals | The Kingdom Circuit",
        "Discover upcoming U.S. festivals featuring confirmed Christian hip-hop artists, official artwork, dates, locations, and ticket links.",
        "/festivals/",
        "Festival discovery",
        "Discover upcoming U.S. festivals featuring Christian hip-hop artists. Festival lineups are included only when confirmed by the official festival or event source.",
        festival_events, events, status, event_map, artist_map,
        summary_html=festival_summary,
        quick=False,
        section_heading="Upcoming Festivals",
        section_intro="Explore festival dates, locations, confirmed CHH performers, official artwork, and ticket information.",
    ))

    recent_events = [event for event in events if is_recent(event, today)]
    recent_summary = summary_stats([
        (str(len(recent_events)), "Added in 14 days"),
        (str(len({event.get('state') for event in recent_events if event.get('state')})), "States"),
        (str(len({name for event in recent_events for name in event.get('artists') or []})), "Artists"),
    ])
    write_text(output_dir / "new-shows" / "index.html", list_page(
        "new",
        "New to Kingdom Circuit | Recently Added CHH Shows",
        "Browse Christian hip-hop shows added to The Kingdom Circuit within the last 14 days.",
        "/new-shows/",
        "Recently added",
        "These shows were added to Kingdom Circuit within the last 14 days. A listing may have been announced earlier; new means it was recently added to our calendar.",
        recent_events, events, status, event_map, artist_map,
        summary_html=recent_summary,
        recent_context=True,
        quick=False,
        section_heading="Recently Added Shows",
        section_intro="These listings automatically leave this page after 14 days but remain on the full calendar.",
    ))

    write_text(output_dir / "artists" / "index.html", artist_directory_page(artists, events, status, artist_map))
    for artist in artists:
        write_text(output_dir / "artists" / artist_map[artist["name"]] / "index.html", artist_page(artist, status, event_map, artist_map))

    write_text(output_dir / "submit" / "index.html", submit_page(status))

    for event in events:
        write_text(output_dir / "shows" / event_map[event_key(event)] / "index.html", event_page(event, events, status, event_map, artist_map))

    by_state: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        code = str(event.get("state") or "").upper()
        if code:
            by_state[code].append(event)
    for code, state_events in by_state.items():
        write_text(output_dir / "states" / slugify(STATE_NAMES.get(code, code)) / "index.html", state_page(code, state_events, status, event_map, artist_map))

    # Search-engine support.
    urls = [
        "/", "/shows/", "/shows/this-month/", "/festivals/", "/new-shows/", "/artists/", "/submit/",
    ]
    urls.extend(f"/shows/{slug}/" for slug in event_map.values())
    urls.extend(f"/artists/{slug}/" for slug in artist_map.values())
    urls.extend(f"/states/{slugify(STATE_NAMES.get(code, code))}/" for code in by_state)
    lastmod = today.isoformat()
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(
        f"  <url><loc>{escape(BASE_URL + path)}</loc><lastmod>{lastmod}</lastmod></url>\n" for path in sorted(set(urls))
    ) + "</urlset>\n"
    write_text(output_dir / "sitemap.xml", sitemap)
    write_text(output_dir / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n")
    write_text(output_dir / "404.html", page_document(
        page_head("Page Not Found | The Kingdom Circuit", "The page could not be found.", "/404.html"),
        site_header(""),
        render_hero("404", "That page is not on the circuit.", "Return to the calendar to find current Christian hip-hop shows.", actions=[("View Shows", "/shows/", "primary-button")], compact=True),
        site_footer(status),
    ))

    return {
        "events": len(events),
        "artists": len(artists),
        "festivals": len(festival_events),
        "recent": len(recent_events),
        "states": len(by_state),
        "pages": len(set(urls)) + 1,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Kingdom Circuit static website")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--today", help="Override today's date for testing (YYYY-MM-DD)")
    args = parser.parse_args()
    today = parse_date(args.today) if args.today else None
    stats = generate_site(args.output, today=today)
    print(
        "Built Kingdom Circuit: "
        f"{stats['pages']} pages, {stats['events']} events, {stats['artists']} artists, "
        f"{stats['festivals']} festivals, {stats['states']} states."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
