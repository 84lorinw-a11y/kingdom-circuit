#!/usr/bin/env python3
"""Best-effort public Instagram announcement discovery.

This module does not bypass Instagram authentication or scrape private content.
It searches a public web index for Instagram posts/Reels that explicitly name a
tracked artist, a future U.S. date/location, and live-music language. Results
that do not meet the strict auto-publish threshold are returned as internal
candidates in run-status.json rather than being published.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from typing import Any, Iterable
from urllib.parse import urlencode, urlparse

BING_SEARCH_URL = "https://www.bing.com/search"
INSTAGRAM_POST_PATTERN = re.compile(
    r"^https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/[A-Za-z0-9_-]+/?",
    re.IGNORECASE,
)
INSTAGRAM_PROFILE_PATTERN = re.compile(
    r"^https?://(?:www\.)?instagram\.com/([A-Za-z0-9._]+)/?$",
    re.IGNORECASE,
)
EVENT_TERMS = re.compile(
    r"\b(concert|show|tour|festival|fest|perform(?:ing|ance)?|live music|"
    r"tickets?|on stage|doors open|coming to|see (?:me|us) live)\b",
    re.IGNORECASE,
)
FESTIVAL_TERMS = re.compile(r"\b(festival|fest)\b", re.IGNORECASE)
NON_EVENT_TERMS = re.compile(
    r"\b(new single|new album|music video|stream now|out now|release date|"
    r"podcast|sermon|bible study|devotional|workshop|conference speaker)\b",
    re.IGNORECASE,
)
MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7,
    "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9,
    "september": 9, "oct": 10, "october": 10, "nov": 11,
    "november": 11, "dec": 12, "december": 12,
}
MONTH_PATTERN = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?"
)
STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC",
}
STATE_CODES = set(STATE_NAMES.values()) | {"DC"}


def normalize(value: str | None) -> str:
    text = str(value or "").lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def clean_markup(value: str | None) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())


def parse_rss_items(xml_text: str) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    items: list[dict[str, str]] = []
    for item in root.findall(".//item"):
        values: dict[str, str] = {}
        for key in ("title", "link", "description", "pubDate"):
            node = item.find(key)
            values[key] = clean_markup(node.text if node is not None else "")
        if values["link"]:
            items.append(values)
    return items


def _chunks(values: list[Any], size: int) -> Iterable[list[Any]]:
    for index in range(0, len(values), size):
        yield values[index:index + size]


def build_search_queries(artists: list[dict[str, Any]], year: int, batch_size: int = 1) -> list[str]:
    names = [str(item.get("name") or "").strip() for item in artists if item.get("enabled", True)]
    names = [name for name in names if name]
    queries: list[str] = []
    for group in _chunks(names, batch_size):
        artist_clause = " OR ".join(f'"{name}"' for name in group)
        queries.append(
            f'site:instagram.com ({artist_clause}) '
            f'("concert" OR "show" OR "tour" OR "festival" OR "tickets" OR "performing") '
            f'({year} OR {year + 1})'
        )
    return queries


def search_url(query: str) -> str:
    return f"{BING_SEARCH_URL}?{urlencode({'format': 'rss', 'q': query})}"


def _artist_records(artists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in artists:
        name = str(item.get("name") or "").strip()
        if not name or not item.get("enabled", True):
            continue
        aliases = [name, *[str(alias) for alias in item.get("aliases", [])]]
        aliases = sorted({normalize(alias) for alias in aliases if normalize(alias)}, key=len, reverse=True)
        profile = str(item.get("instagramProfile") or "").strip()
        handle = ""
        match = INSTAGRAM_PROFILE_PATTERN.match(profile)
        if match:
            handle = normalize(match.group(1))
        records.append({"name": name, "aliases": aliases, "profile": profile, "handle": handle})
    return records


def match_artists(text: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = f" {normalize(text)} "
    matches: list[tuple[int, dict[str, Any]]] = []
    for record in records:
        best_position: int | None = None
        for alias in record["aliases"]:
            if not alias:
                continue
            match = re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized)
            if match and (best_position is None or match.start() < best_position):
                best_position = match.start()
        if best_position is not None:
            matches.append((best_position, record))
    matches.sort(key=lambda pair: pair[0])
    return [record for _, record in matches]


def _month_number(value: str) -> int:
    return MONTHS.get(normalize(value), 0)


def extract_future_date(text: str, today: date, lookahead_days: int) -> str:
    candidates: set[date] = set()
    for match in re.finditer(
        rf"\b({MONTH_PATTERN})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,|\s)+\s*(20\d{{2}})\b",
        text,
        re.IGNORECASE,
    ):
        try:
            candidates.add(date(int(match.group(3)), _month_number(match.group(1)), int(match.group(2))))
        except ValueError:
            pass
    for match in re.finditer(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", text):
        try:
            candidates.add(date(int(match.group(1)), int(match.group(2)), int(match.group(3))))
        except ValueError:
            pass
    for match in re.finditer(r"\b(\d{1,2})/(\d{1,2})/(20\d{2}|\d{2})\b", text):
        year = int(match.group(3))
        if year < 100:
            year += 2000
        try:
            candidates.add(date(year, int(match.group(1)), int(match.group(2))))
        except ValueError:
            pass
    # Instagram captions frequently omit the year. Infer the next occurrence,
    # but only within the configured look-ahead window.
    for match in re.finditer(
        rf"\b({MONTH_PATTERN})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?!\s*,?\s*20\d{{2}})",
        text,
        re.IGNORECASE,
    ):
        month = _month_number(match.group(1))
        day = int(match.group(2))
        for year in (today.year, today.year + 1):
            try:
                candidate = date(year, month, day)
            except ValueError:
                continue
            if candidate >= today:
                candidates.add(candidate)
                break
    upper = today + timedelta(days=lookahead_days)
    future = sorted(item for item in candidates if today <= item <= upper)
    return future[0].isoformat() if future else ""


def extract_time(text: str) -> str:
    match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?\b", text, re.IGNORECASE)
    if not match:
        return ""
    hour = int(match.group(1))
    minute = int(match.group(2) or "00")
    if hour == 12:
        hour = 0
    if match.group(3).lower() == "p":
        hour += 12
    return f"{hour:02d}:{minute:02d}"


def normalize_state(value: str) -> str:
    cleaned = normalize(value)
    if len(cleaned) == 2 and cleaned.upper() in STATE_CODES:
        return cleaned.upper()
    return STATE_NAMES.get(cleaned, "")


def extract_city_state(text: str) -> tuple[str, str]:
    state_terms = sorted([*STATE_NAMES.keys(), *STATE_CODES], key=len, reverse=True)
    state_pattern = "|".join(re.escape(item) for item in state_terms)
    matches = list(re.finditer(
        rf"\b([A-Za-z][A-Za-z .()'&-]{{1,45}}),\s*({state_pattern})\b",
        text,
        re.IGNORECASE,
    ))
    if not matches:
        return "", ""
    match = matches[-1]
    city = " ".join(match.group(1).split())
    # Trim caption fragments before the probable city.
    city = re.sub(r"^.*(?:\b(?:in|to|at|from)\b\s+)", "", city, flags=re.IGNORECASE)
    words = city.split()
    if len(words) > 5:
        city = " ".join(words[-4:])
    return city.strip(" -–—,"), normalize_state(match.group(2))


def extract_venue(text: str, city: str) -> str:
    patterns = [
        r"(?:\bat\b|@)\s+([A-Za-z0-9][A-Za-z0-9 .&'’()+/-]{2,70}?)(?=\s+(?:in|on)\b|[|•;]|$)",
        r"(?:venue|location)\s*[:\-]\s*([A-Za-z0-9][A-Za-z0-9 .&'’()+/-]{2,70}?)(?=[|•;]|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        venue = " ".join(match.group(1).split()).strip(" -–—,.")
        if venue and normalize(venue) != normalize(city) and not re.fullmatch(r"\d{1,2}(?::\d{2})?\s*[ap]m", venue, re.I):
            return venue
    return "Venue not provided"


def _official_for_artist(title: str, description: str, record: dict[str, Any]) -> bool:
    # A display name alone is not enough to prove account ownership because fan
    # accounts can use an artist's name. Auto-publication requires the known
    # official handle to appear in the indexed result. Results without a
    # verified handle remain internal candidates.
    combined_norm = normalize(f"{title} {description}")
    handle = record.get("handle") or ""
    if not handle:
        return False
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(handle)}(?![a-z0-9])", combined_norm))


def _display_title(artist: str, city: str, title: str, description: str) -> str:
    combined = f"{title} {description}"
    quoted = re.search(r'["“]([^"”]{6,90})["”]', combined)
    if quoted and EVENT_TERMS.search(quoted.group(1)):
        return " ".join(quoted.group(1).split())
    return f"{artist} Live in {city}"


def _candidate_reason(
    *, official: bool, event_term: bool, event_date: str, city: str, state: str,
    is_festival: bool, matched: list[dict[str, Any]],
) -> str:
    reasons: list[str] = []
    if not official:
        reasons.append("official artist ownership was not clear")
    if not event_term:
        reasons.append("live-music language was missing")
    if not event_date:
        reasons.append("a future date was not explicit")
    if not city or not state:
        reasons.append("a U.S. city/state was not explicit")
    if not matched:
        reasons.append("no tracked artist was confidently matched")
    if is_festival:
        reasons.append("festival posts require an official festival lineup source")
    return "; ".join(reasons) or "did not meet the strict auto-publish threshold"


def parse_result(
    item: dict[str, str],
    records: list[dict[str, Any]],
    today: date,
    lookahead_days: int,
    known_url: bool = False,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    link = item.get("link", "").strip()
    if not INSTAGRAM_POST_PATTERN.match(link):
        return None, None
    title = clean_markup(item.get("title"))
    description = clean_markup(item.get("description"))
    combined = f"{title} {description}"
    matched = match_artists(combined, records)
    event_term = bool(EVENT_TERMS.search(combined) and not NON_EVENT_TERMS.search(combined))
    event_date = extract_future_date(combined, today, lookahead_days)
    city, state = extract_city_state(combined)
    is_festival = bool(FESTIVAL_TERMS.search(combined))
    official_records = [record for record in matched if _official_for_artist(title, description, record)]
    # A specifically configured post URL is treated as official after its
    # artist name, date, location, and music language are all explicit.
    official = bool(official_records) or (known_url and bool(matched))
    if known_url and matched and not official_records:
        official_records = matched
    chosen_records = official_records or matched
    score = (
        (3 if official else 0)
        + (2 if event_term else 0)
        + (2 if event_date else 0)
        + (2 if city and state else 0)
        + (1 if extract_time(combined) else 0)
        + (2 if known_url else 0)
    )

    candidate = {
        "url": link,
        "title": title,
        "artists": [record["name"] for record in chosen_records],
        "date": event_date,
        "city": city,
        "state": state,
        "score": score,
        "reason": _candidate_reason(
            official=official,
            event_term=event_term,
            event_date=event_date,
            city=city,
            state=state,
            is_festival=is_festival,
            matched=chosen_records,
        ),
    }

    # Festival posts are intentionally discovery-only. An official festival
    # page/lineup must confirm the complete lineup before publication.
    if score < 9 or is_festival or not chosen_records:
        return None, candidate

    artists = [record["name"] for record in chosen_records]
    headliner = artists[0]
    raw_event = {
        "id": f"instagram:{urlparse(link).path.strip('/').replace('/', ':')}",
        "title": _display_title(headliner, city, title, description),
        "startDate": event_date,
        "startTime": extract_time(combined),
        "venue": extract_venue(combined, city),
        "address": "",
        "city": city,
        "state": state,
        "artists": artists,
        "headliner": headliner,
        "eventType": "concert",
        "ticketUrl": link,
        "officialUrl": link,
        "status": "scheduled",
        "lineupExplicit": True,
        "sourceName": "Official Instagram announcement",
        "sourceUrl": link,
        "confidenceScore": score,
    }
    return raw_event, None


def scan_instagram_index(
    *,
    client: Any,
    artists: list[dict[str, Any]],
    known_posts: list[dict[str, Any]],
    today: date,
    checked_at: str,
    lookahead_days: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Check every configured artist through public Instagram search indexing."""

    records = _artist_records(artists)
    queries = build_search_queries(artists, today.year)
    warnings: list[str] = []
    items: list[dict[str, str]] = []
    queries_run = 0
    queries_attempted = 0
    consecutive_failures = 0

    for query in queries:
        queries_attempted += 1
        try:
            items.extend(parse_rss_items(client.get_text(search_url(query))))
            queries_run += 1
            consecutive_failures = 0
        except Exception as exc:  # Network failures are deliberately soft.
            consecutive_failures += 1
            warnings.append(f"Instagram public-index query failed: {exc}")
            if consecutive_failures >= 3:
                warnings.append("Instagram scan stopped after three consecutive search-index failures.")
                break

    known_by_url: dict[str, dict[str, Any]] = {}
    for entry in known_posts if isinstance(known_posts, list) else []:
        if not isinstance(entry, dict) or not entry.get("enabled", True):
            continue
        url = str(entry.get("url") or "").strip()
        if not INSTAGRAM_POST_PATTERN.match(url):
            continue
        known_by_url[url.rstrip("/")] = entry
        shortcode = urlparse(url).path.strip("/").split("/")[-1]
        artist = str(entry.get("artist") or "").strip()
        query = f'"{shortcode}" "{artist}" Instagram'
        try:
            items.extend(parse_rss_items(client.get_text(search_url(query))))
            queries_run += 1
        except Exception as exc:
            warnings.append(f"Known Instagram post lookup failed for {artist or shortcode}: {exc}")

    unique_items: dict[str, dict[str, str]] = {}
    discovered_profiles: dict[str, str] = {}
    for item in items:
        link = item.get("link", "").rstrip("/")
        profile_match = INSTAGRAM_PROFILE_PATTERN.match(link)
        if profile_match:
            discovered_profiles[profile_match.group(1)] = link + "/"
        if INSTAGRAM_POST_PATTERN.match(link):
            unique_items[link] = item

    events: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    resolved_known: set[str] = set()
    for link, item in unique_items.items():
        known_url = link in known_by_url
        event, candidate = parse_result(item, records, today, lookahead_days, known_url=known_url)
        if event:
            events.append(event)
            if known_url:
                resolved_known.add(link)
        elif candidate:
            candidates.append(candidate)
            if known_url:
                resolved_known.add(link)

    for link, entry in known_by_url.items():
        if link in resolved_known:
            continue
        candidates.append({
            "url": link + "/",
            "title": str(entry.get("note") or "Known Instagram announcement"),
            "artists": [str(entry.get("artist") or "").strip()],
            "date": "",
            "city": "",
            "state": "",
            "score": 2,
            "reason": "the known post was not publicly indexed with enough event details",
        })

    # Dedupe output by post URL and keep the highest-scoring candidate summaries.
    event_by_url = {str(event.get("sourceUrl") or event.get("officialUrl")): event for event in events}
    candidate_by_url: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        url = str(candidate.get("url") or "")
        existing = candidate_by_url.get(url)
        if not existing or int(candidate.get("score") or 0) > int(existing.get("score") or 0):
            candidate_by_url[url] = candidate

    report = {
        "artistsConfigured": len(records),
        "queriesRun": queries_run,
        "queriesAttempted": queries_attempted,
        "resultsFound": len(unique_items),
        "eventsFound": len(event_by_url),
        "candidates": sorted(
            candidate_by_url.values(),
            key=lambda item: (-int(item.get("score") or 0), str(item.get("artists") or "")),
        )[:30],
        "profilesDiscovered": list(discovered_profiles.values())[:30],
        "warnings": warnings[:10],
        "checkedAt": checked_at,
        "mode": "free per-artist public-index scan; Stories, private posts, and unindexed posts are not visible",
    }
    return list(event_by_url.values()), report
