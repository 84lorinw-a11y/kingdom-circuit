#!/usr/bin/env python3
"""Sync verified artist records from the canonical Artist Source Registry."""
from __future__ import annotations

import json
import re
from pathlib import Path

SYNC_VERSION = 1
ROOT = Path(__file__).resolve().parents[1]
ARTISTS_FILE = ROOT / "config" / "artists.json"
APP_FILE = ROOT / "app.js"

ARTIST = {
    "name": "808 BEEZY",
    "aliases": ["808 BEEZY", "808 Beezy"],
    "enabled": True,
    "ticketmasterEnabled": True,
    "category": "core",
    "monitoringPriority": 2,
    "topStreamingPriority": False,
    "socialSearchEnabled": True,
    "activeStatus": "active_or_unknown",
    "textMatchEnabled": True,
    "website": "https://www.808beezy.com/",
    "instagramProfile": "https://www.instagram.com/808beezy/?hl=en",
    "spotifyProfile": "https://open.spotify.com/artist/3CltJZLndpJKtpUyRVBB1k",
    "youtubeProfile": "https://www.youtube.com/@808_BEEZY",
    "sourceRegistryVerified": True,
    "officialImageSource": "https://www.808beezy.com/",
    "rosterOrder": 54,
}


def sync_config() -> bool:
    artists = json.loads(ARTISTS_FILE.read_text(encoding="utf-8"))
    changed = False
    target = next((a for a in artists if str(a.get("name") or "").casefold() == "808 beezy"), None)

    if target is None:
        for artist in artists:
            order = artist.get("rosterOrder")
            if isinstance(order, int) and order >= 54:
                artist["rosterOrder"] = order + 1
        artists.append(dict(ARTIST))
        changed = True
    else:
        for key, value in ARTIST.items():
            if target.get(key) != value:
                target[key] = value
                changed = True

    artists.sort(key=lambda a: (a.get("rosterOrder") if isinstance(a.get("rosterOrder"), int) else 99999, str(a.get("name") or "").casefold()))
    if changed:
        ARTISTS_FILE.write_text(json.dumps(artists, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return changed


def sync_app() -> bool:
    text = APP_FILE.read_text(encoding="utf-8")
    original = text

    roster_match = re.search(r"const ARTIST_ROSTER_ORDER = \[(.*?)\n\];", text, re.S)
    if not roster_match:
        raise SystemExit("ARTIST_ROSTER_ORDER was not found in app.js")
    if '"808 BEEZY"' not in roster_match.group(1):
        updated_roster = roster_match.group(0).replace(
            '  "Bishop Freeze",\n  "Alex Jean",',
            '  "Bishop Freeze",\n  "808 BEEZY",\n  "Alex Jean",',
            1,
        )
        if updated_roster == roster_match.group(0):
            raise SystemExit("Could not place 808 BEEZY after Bishop Freeze in ARTIST_ROSTER_ORDER")
        text = text[:roster_match.start()] + updated_roster + text[roster_match.end():]

    registry_marker = "const VERIFIED_ARTIST_REGISTRY = {\n"
    if registry_marker not in text:
        raise SystemExit("VERIFIED_ARTIST_REGISTRY was not found in app.js")
    if '  "808 beezy": {' not in text:
        registry_entry = '''  "808 beezy": {\n    "aliases": [\n      "808 BEEZY",\n      "808 Beezy"\n    ],\n    "website": "https://www.808beezy.com/",\n    "instagramProfile": "https://www.instagram.com/808beezy/?hl=en",\n    "spotifyProfile": "https://open.spotify.com/artist/3CltJZLndpJKtpUyRVBB1k",\n    "youtubeProfile": "https://www.youtube.com/@808_BEEZY",\n    "officialImageSource": "https://www.808beezy.com/",\n    "sourceRegistryVerified": true\n  },\n'''
        text = text.replace(registry_marker, registry_marker + registry_entry, 1)

    if text != original:
        APP_FILE.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> int:
    config_changed = sync_config()
    app_changed = sync_app()
    print(f"808 BEEZY synced: config_changed={config_changed}, app_changed={app_changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
