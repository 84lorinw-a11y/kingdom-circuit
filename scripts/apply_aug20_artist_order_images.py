#!/usr/bin/env python3
"""Place the Aug. 20 artist additions in canonical roster order and enable verified images."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTISTS_FILE = ROOT / "config" / "artists.json"
APP_FILE = ROOT / "app.js"

ADDED = [
    "Brenno",
    "Shepherd",
    "Kai Uriah",
    "Hyper Fenton",
    "Brea Miles",
    "Issac Mansfield",
    "Tylan1k",
    "Jabari Heavens",
    "Rhema Soul",
    "Shonlock",
    "Viktory",
    "T-Bone",
    "Bishop Freeze",
]

IMAGE_SOURCES = {
    "Brenno": "https://www.instagram.com/brenno.music/",
    "Shepherd": "https://www.instagram.com/shepherd_music/",
    "Kai Uriah": "https://www.instagram.com/kaiuriah/?hl=en",
    "Hyper Fenton": "https://www.instagram.com/hyperfenton/?hl=en",
    "Brea Miles": "https://www.instagram.com/alwaysbrea",
    "Issac Mansfield": "https://www.issacmansfield.com/",
    "Tylan1k": "https://www.instagram.com/tylanthechosen1/?hl=en",
    "Jabari Heavens": "https://www.instagram.com/jabariheavens/",
    "Rhema Soul": "https://www.instagram.com/rhemasoul/",
    "Shonlock": "https://www.instagram.com/shonlock/",
    "Viktory": "https://www.instagram.com/viktoryr4/?hl=en",
    "T-Bone": "https://www.instagram.com/tboneoficial/?hl=en",
    "Bishop Freeze": "https://www.instagram.com/bishopfreeze_/",
}


def norm(value: Any) -> str:
    return str(value or "").strip().casefold()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def extract_json_assignment(text: str, marker: str, opener: str, closer: str):
    start = text.find(marker)
    if start < 0:
        raise SystemExit(f"Missing JS marker: {marker}")
    pos = text.find(opener, start + len(marker))
    if pos < 0:
        raise SystemExit(f"Missing JS value after marker: {marker}")
    depth = 0
    in_string = False
    escape = False
    quote = ""
    for idx in range(pos, len(text)):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                in_string = False
            continue
        if ch in ('"', "'"):
            in_string = True
            quote = ch
            continue
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return pos, idx + 1, json.loads(text[pos:idx + 1])
    raise SystemExit(f"Unterminated JS value: {marker}")


def replace_json_assignment(text: str, marker: str, opener: str, closer: str, value) -> str:
    start, end, _ = extract_json_assignment(text, marker, opener, closer)
    rendered = json.dumps(value, indent=2, ensure_ascii=False)
    return text[:start] + rendered + text[end:]


def main() -> int:
    artists = load_json(ARTISTS_FILE)
    if not isinstance(artists, list):
        raise SystemExit("config/artists.json must be a JSON array")
    app = APP_FILE.read_text(encoding="utf-8")

    _, _, old_roster = extract_json_assignment(app, "const ARTIST_ROSTER_ORDER =", "[", "]")
    _, _, verified_registry = extract_json_assignment(app, "const VERIFIED_ARTIST_REGISTRY =", "{", "}")
    if not isinstance(old_roster, list) or not isinstance(verified_registry, dict):
        raise SystemExit("Unexpected app.js artist registry structures")

    added_keys = {norm(name) for name in ADDED}
    base_roster = [name for name in old_roster if norm(name) not in added_keys]
    indie_index = next((i for i, name in enumerate(base_roster) if norm(name) == "indie tribe."), None)
    if indie_index is None:
        raise SystemExit("indie tribe. not found in ARTIST_ROSTER_ORDER")
    canonical = [*base_roster[:indie_index + 1], *ADDED, *base_roster[indie_index + 1:]]

    by_name = {norm(item.get("name")): item for item in artists if isinstance(item, dict)}
    config_names = set(by_name)
    canonical_names = {norm(name) for name in canonical}
    if config_names != canonical_names:
        missing = sorted(config_names - canonical_names)
        extra = sorted(canonical_names - config_names)
        raise SystemExit(f"Canonical roster/config mismatch: missing_from_roster={missing}, extra_in_roster={extra}")
    if len(canonical) != len(canonical_names):
        raise SystemExit("Canonical roster contains duplicate names")

    order = {norm(name): idx + 1 for idx, name in enumerate(canonical)}
    for artist in artists:
        artist["rosterOrder"] = order[norm(artist.get("name"))]

    for name in ADDED:
        artist = by_name[norm(name)]
        if not artist.get("spotifyProfile"):
            raise SystemExit(f"{name} is missing a Spotify profile needed for verified image resolution")
        artist["sourceRegistryVerified"] = True
        artist["officialImageSource"] = IMAGE_SOURCES[name]

        entry: dict[str, Any] = {
            "aliases": list(artist.get("aliases") or [name]),
        }
        for field in ("website", "instagramProfile", "spotifyProfile", "youtubeProfile"):
            value = artist.get(field)
            if value:
                entry[field] = value
        entry["officialImageSource"] = IMAGE_SOURCES[name]
        entry["sourceRegistryVerified"] = True
        verified_registry[norm(name)] = entry

    artists.sort(key=lambda item: (int(item.get("rosterOrder") or 999999), norm(item.get("name"))))
    ARTISTS_FILE.write_text(json.dumps(artists, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    app = replace_json_assignment(app, "const ARTIST_ROSTER_ORDER =", "[", "]", canonical)
    app = replace_json_assignment(app, "const VERIFIED_ARTIST_REGISTRY =", "{", "}", verified_registry)
    APP_FILE.write_text(app, encoding="utf-8")

    # Explicit guardrails for the user-approved order.
    assert canonical[39] == "indie tribe.", canonical[36:56]
    assert canonical[40:53] == ADDED, canonical[36:56]
    assert canonical[53] == "Alex Jean", canonical[36:56]
    for name in ADDED:
        artist = by_name[norm(name)]
        assert artist["sourceRegistryVerified"] is True
        assert verified_registry[norm(name)]["sourceRegistryVerified"] is True
        assert verified_registry[norm(name)].get("spotifyProfile")

    print(
        "Artist registry corrected: indie tribe. #40; "
        "Brenno-Bishop Freeze #41-53; Alex Jean #54; "
        f"{len(ADDED)} verified Spotify image fallbacks enabled."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
