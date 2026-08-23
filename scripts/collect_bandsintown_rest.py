#!/usr/bin/env python3
"""Discover upcoming US shows for the full artist registry via Bandsintown REST.

This collector intentionally uses the structured REST route rather than public
Bandsintown artist pages, which are blocked from GitHub-hosted runners. It is a
conservative discovery source:
- exact canonical/alias artist matches only unless a configured Bandsintown ID exists
- short/ambiguous artist names require a configured Bandsintown ID
- festivals are held for official-lineup confirmation
- events already represented by a multi-day event range are deduped
- only new, non-festival US events are written to supplemental-events.json
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTISTS_FILE = ROOT / "config" / "artists.json"
EVENTS_FILE = ROOT / "events.json"
SUPPLEMENTAL_FILE = ROOT / "supplemental-events.json"
STATUS_FILE = ROOT / "bandsintown-status.json"
CANDIDATES_FILE = ROOT / "bandsintown-candidates.json"
BASE = "https://rest.bandsintown.com"
APP_ID = "js_kingdomcircuit.com"

FESTIVAL_TERMS = re.compile(r"\b(festival|fest|conference|convention|summit)\b", re.I)
RISKY_NAMES = {"116", "350", "kb", "nf", "so", "jr"}


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = text.replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def compact_name(value: str) -> str:
    return norm(value).replace(" ", "")


def risky_identity(name: str) -> bool:
    compact = compact_name(name)
    return len(compact) <= 3 or compact in RISKY_NAMES


def slugify(value: str) -> str:
    value = norm(value).replace(" ", "-")
    return value or "artist"


def get_json(url: str, attempts: int = 3) -> tuple[int | None, Any]:
    last_status: int | None = None
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json,text/plain,*/*",
                "User-Agent": "KingdomCircuitEventDiscovery/1.0 (+https://kingdomcircuit.com)",
                "Referer": "https://kingdomcircuit.com/",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                last_status = response.status
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            last_status = error.code
            if error.code not in {429, 500, 502, 503, 504}:
                return error.code, None
        except Exception:
            pass
        time.sleep(0.35 * attempt)
    return last_status, None


def configured_bit_id(artist: dict[str, Any]) -> str:
    for key in ("bandsintownArtistId", "bandsintownId", "bandsintown_id"):
        value = str(artist.get(key) or "").strip()
        if value:
            return value
    for key in ("bandsintownUrl", "bandsintown", "bandsintownProfile"):
        value = str(artist.get(key) or "")
        match = re.search(r"/a/(\d+)", value)
        if match:
            return match.group(1)
    return ""


def resolve_artist(artist: dict[str, Any]) -> tuple[str, str, str]:
    name = str(artist.get("name") or "").strip()
    configured_id = configured_bit_id(artist)
    if configured_id:
        status, profile = get_json(f"{BASE}/artists/id_{urllib.parse.quote(configured_id)}?app_id={APP_ID}")
        if status == 200 and isinstance(profile, dict):
            return configured_id, str(profile.get("name") or name), "configured_id"
        return "", "", f"configured_id_failed:{status}"

    if risky_identity(name):
        return "", "", "ambiguous_name_requires_configured_id"

    aliases = [name, *[str(v or "").strip() for v in artist.get("aliases", []) if str(v or "").strip()]]
    accepted = {norm(v) for v in aliases if v}
    for candidate in list(dict.fromkeys(aliases))[:4]:
        url = f"{BASE}/artists/{urllib.parse.quote(candidate)}?app_id={APP_ID}"
        status, profile = get_json(url)
        if status != 200 or not isinstance(profile, dict):
            continue
        resolved_name = str(profile.get("name") or "").strip()
        if norm(resolved_name) not in accepted:
            continue
        artist_id = str(profile.get("id") or "").strip()
        if artist_id:
            return artist_id, resolved_name, "exact_name_or_alias"
    return "", "", "not_resolved"


def event_artists(event: dict[str, Any]) -> set[str]:
    return {norm(v) for v in event.get("artists", []) if str(v or "").strip()}


def event_range_contains(event: dict[str, Any], candidate_date: str) -> bool:
    start = str(event.get("startDate") or "")
    end = str(event.get("endDate") or start)
    return bool(start and start <= candidate_date <= end)


def existing_duplicate(candidate: dict[str, Any], published: list[dict[str, Any]]) -> bool:
    artist = norm(candidate["trackedArtist"])
    cdate = candidate["startDate"]
    ccity = norm(candidate.get("city"))
    cvenue = norm(candidate.get("venue"))
    bit_id = str(candidate.get("bandsintownEventId") or "")

    for event in published:
        if artist not in event_artists(event):
            continue
        sources = event.get("sources") or []
        if bit_id and any(bit_id in str(src.get("url") or "") for src in sources if isinstance(src, dict)):
            return True
        if event_range_contains(event, cdate):
            # A candidate within an existing multi-day event is the same appearance,
            # even when Bandsintown represents the artist's performance as a day-specific row.
            if str(event.get("endDate") or "") or norm(event.get("eventType")) == "festival":
                return True
        if str(event.get("startDate") or "") != cdate:
            continue
        ecity = norm(event.get("city"))
        evenue = norm(event.get("venue"))
        if ccity and ecity and ccity == ecity:
            return True
        if cvenue and evenue and cvenue == evenue:
            return True
    return False


def looks_like_festival(event: dict[str, Any]) -> bool:
    blob = " ".join([str(event.get("title") or ""), str(event.get("venue") or "")])
    return bool(FESTIVAL_TERMS.search(blob))


def compact_event(raw: dict[str, Any], artist: dict[str, Any], resolved_name: str, identity: str) -> dict[str, Any]:
    venue = raw.get("venue") if isinstance(raw.get("venue"), dict) else {}
    offers = raw.get("offers") if isinstance(raw.get("offers"), list) else []
    first_offer = next((offer for offer in offers if isinstance(offer, dict) and offer.get("url")), {})
    start = str(raw.get("datetime") or raw.get("starts_at") or "")
    start_date = start[:10]
    title = str(raw.get("title") or "").strip()
    venue_name = str(venue.get("name") or "").strip()
    artist_name = str(artist.get("name") or "").strip()
    source_url = str(raw.get("url") or "").strip()
    event_id = str(raw.get("id") or "").strip()
    image = str(artist.get("imageUrl") or "").strip() or f"assets/artists/{slugify(artist_name)}.webp"
    return {
        "id": f"bandsintown:{event_id}",
        "title": title or (f"{artist_name} Live" if not venue_name else f"{artist_name} at {venue_name}"),
        "startDate": start_date,
        "startTime": start[11:16] if len(start) >= 16 else "",
        "timezone": "",
        "venue": venue_name,
        "address": str(venue.get("street_address") or "").strip(),
        "city": str(venue.get("city") or "").strip(),
        "state": str(venue.get("region") or "").strip(),
        "country": "US",
        "artists": [artist_name],
        "headliner": artist_name,
        "eventType": "concert",
        "status": "scheduled",
        "ticketUrl": str(first_offer.get("url") or source_url),
        "officialUrl": source_url,
        "image": image,
        "price": "Free" if raw.get("free") is True else "",
        "sourceName": "Bandsintown",
        "sources": [{
            "name": "Bandsintown",
            "url": source_url,
            "type": "bandsintown_rest",
            "authority": "artist_calendar",
            "priority": 74,
        }],
        "confidence": "medium",
        "bandsintownEventId": event_id,
        "bandsintownArtistId": str(raw.get("artist_id") or raw.get("artist", {}).get("id") or ""),
        "bandsintownResolvedName": resolved_name,
        "bandsintownIdentity": identity,
        "trackedArtist": artist_name,
    }


def main() -> int:
    artists = load(ARTISTS_FILE, [])
    events = load(EVENTS_FILE, [])
    supplemental = load(SUPPLEMENTAL_FILE, [])
    if not isinstance(artists, list) or not isinstance(events, list) or not isinstance(supplemental, list):
        raise SystemExit("Expected JSON arrays for artists/events/supplemental")

    enabled = [a for a in artists if isinstance(a, dict) and a.get("enabled", True) is not False and a.get("name")]
    today = date.today().isoformat()
    published = [e for e in [*events, *supplemental] if isinstance(e, dict)]
    candidates: list[dict[str, Any]] = []
    holds: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    resolved = 0
    duplicates = 0
    raw_us = 0

    seen_candidate_keys: set[tuple[str, str, str, str]] = set()
    for index, artist in enumerate(enabled, start=1):
        name = str(artist.get("name") or "").strip()
        artist_id, resolved_name, identity = resolve_artist(artist)
        if not artist_id:
            if identity not in {"not_resolved", "ambiguous_name_requires_configured_id"}:
                errors.append({"artist": name, "error": identity})
            continue
        resolved += 1
        status, raw_events = get_json(f"{BASE}/artists/id_{urllib.parse.quote(artist_id)}/events/?app_id={APP_ID}&date=upcoming")
        if status != 200 or not isinstance(raw_events, list):
            errors.append({"artist": name, "error": f"events_request_failed:{status}"})
            continue

        for raw in raw_events:
            if not isinstance(raw, dict):
                continue
            compact = compact_event(raw, artist, resolved_name, identity)
            if not compact["startDate"] or compact["startDate"] < today:
                continue
            country = norm((raw.get("venue") or {}).get("country")) if isinstance(raw.get("venue"), dict) else ""
            if country not in {"united states", "us", "usa"}:
                continue
            raw_us += 1
            key = (norm(name), compact["startDate"], norm(compact["city"]), norm(compact["venue"]))
            if key in seen_candidate_keys:
                continue
            seen_candidate_keys.add(key)

            if existing_duplicate(compact, published):
                duplicates += 1
                continue
            if looks_like_festival(compact):
                compact["holdReason"] = "festival_requires_official_lineup_confirmation"
                holds.append(compact)
                continue
            candidates.append(compact)
            published.append(compact)

        if index % 25 == 0:
            print(f"Bandsintown: checked {index}/{len(enabled)} artists")
        time.sleep(0.06)

    # Replace prior Bandsintown-generated supplemental records with the current
    # verified set so cancellations/changes do not linger forever.
    non_bit = [
        e for e in supplemental
        if not (isinstance(e, dict) and str(e.get("id") or "").startswith("bandsintown:"))
    ]
    merged = [*non_bit, *candidates]
    merged.sort(key=lambda e: (str(e.get("startDate") or "9999-12-31"), str(e.get("title") or "")))
    save(SUPPLEMENTAL_FILE, merged)
    save(CANDIDATES_FILE, holds)
    status = {
        "generatedAt": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "artistsChecked": len(enabled),
        "artistsResolved": resolved,
        "rawUpcomingUSRows": raw_us,
        "duplicatesFiltered": duplicates,
        "festivalCandidatesHeld": len(holds),
        "newNonFestivalShowsPublished": len(candidates),
        "requestErrors": len(errors),
        "errors": errors[:50],
    }
    save(STATUS_FILE, status)
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
