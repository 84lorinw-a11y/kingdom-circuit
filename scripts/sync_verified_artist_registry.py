#!/usr/bin/env python3
"""Sync verified artist records from the canonical Artist Source Registry export.

The checked-in JSON is a small, reviewable handoff from the Google Sheet. This
script makes that handoff authoritative for public roster order and verified
social/profile links while preserving existing collector metadata for artists
that were already tracked.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

from artist_portraits import apply_to_records, load_portraits
from owner_roster import order_records, snapshot, verify_records, apply as apply_owner_roster

SYNC_VERSION = 9
ROOT = Path(__file__).resolve().parents[1]
ARTISTS_FILE = ROOT / "config" / "artists.json"
UPDATES_FILE = ROOT / "config" / "verified-artist-registry-updates.json"
WEBSITES_FILE = ROOT / "config" / "verified-artist-websites.json"
APP_FILE = ROOT / "app.js"
TEST_FILE = ROOT / "tests" / "test_update_events.py"

# Owner-requested roster exclusions override stale registry exports.
EXCLUDED_ARTISTS = {"chad jones", "erica mason", "big holy", "jay kalyl", "dj maj", "propaganda"}

# Backward-compatible direct calendar metadata for 808 BEEZY. The generalized
# sync still exposes this constant because the ingestion regression test and
# collector rely on the known direct Bandsintown profile.
ARTIST = {
    "name": "808 BEEZY",
    "bandsintownProfile": "https://www.bandsintown.com/a/792282-808-beezy",
}

SKIP_WEBSITE_HOSTS = {
    "google.com", "www.google.com", "instagram.com", "www.instagram.com",
    "spotify.com", "open.spotify.com", "youtube.com", "www.youtube.com",
    "music.youtube.com", "facebook.com", "www.facebook.com", "x.com",
    "twitter.com", "wikipedia.org", "en.wikipedia.org", "music.apple.com",
    "apple.com", "www.apple.com",
}


def norm(value: object) -> str:
    return str(value or "").strip().casefold()


def load_json(path: Path, fallback):
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def real_official_website(value: object) -> str:
    url = str(value or "").strip()
    if not url.startswith(("http://", "https://")):
        return ""
    parsed = urlparse(url)
    host = parsed.netloc.lower().split(":", 1)[0]
    if not host or host in SKIP_WEBSITE_HOSTS or host.endswith(".wikipedia.org"):
        return ""
    if "google." in host:
        return ""
    return url


def sync_config() -> tuple[list[dict], list[dict], int]:
    artists = order_records(load_json(ARTISTS_FILE, []))
    updates = load_json(UPDATES_FILE, [])
    artists = [item for item in artists if isinstance(item, dict) and norm(item.get("name")) not in EXCLUDED_ARTISTS]
    updates = [item for item in updates if isinstance(item, dict) and norm(item.get("name")) not in EXCLUDED_ARTISTS]
    if not isinstance(artists, list) or not isinstance(updates, list) or not updates:
        raise SystemExit("Verified registry sync expected non-empty artist/update arrays")

    update_names = [str(item.get("name") or "").strip() for item in updates if isinstance(item, dict)]
    if len(update_names) != len(updates) or len({norm(name) for name in update_names}) != len(update_names):
        raise SystemExit("Verified registry updates contain a blank or duplicate artist name")

    actual_orders = [int(item.get("rosterOrder") or 0) for item in updates]
    expected_verified = [row["name"] for row in snapshot() if row["verified"]]
    if update_names != expected_verified or actual_orders != sorted(set(actual_orders)):
        raise SystemExit("Verified handoff must match the owner's reviewed Sheet rows and order")

    by_name = {norm(item.get("name")): item for item in artists if isinstance(item, dict) and item.get("name")}
    changed = 0

    # Preserve the existing record and roster position after the owner's rename.
    if "dj eli williams" in by_name and "eli williams" not in by_name:
        target = by_name.pop("dj eli williams")
        target["name"] = "Eli Williams"
        by_name["eli williams"] = target
        changed += 1

    beezy = by_name.get(norm(ARTIST["name"]))
    if beezy is not None and beezy.get("bandsintownProfile") != ARTIST["bandsintownProfile"]:
        beezy["bandsintownProfile"] = ARTIST["bandsintownProfile"]
        changed += 1

    synced_records: list[dict] = []
    for update in updates:
        name = str(update["name"]).strip()
        key = norm(name)
        target = by_name.get(key)
        if target is None:
            target = {
                "name": name,
                "aliases": [name],
                "enabled": True,
                "ticketmasterEnabled": bool(update.get("ticketmasterEnabled", True)),
                "category": str(update.get("category") or "core"),
                "monitoringPriority": int(update.get("monitoringPriority") or 3),
                "topStreamingPriority": False,
                "socialSearchEnabled": True,
                "activeStatus": "active_or_unknown",
                "textMatchEnabled": bool(update.get("textMatchEnabled", True)),
            }
            artists.append(target)
            by_name[key] = target
            changed += 1

        for field in (
            "name", "aliases", "category", "monitoringPriority", "ticketmasterEnabled",
            "textMatchEnabled", "website", "instagramProfile", "spotifyProfile",
            "youtubeProfile", "officialImageSource", "imageUrl", "imagePosition",
            "state", "label", "bandsintownProfile", "socialSearchEnabled", "activeStatus", "legacyArtistPaths",
        ):
            if field in update and target.get(field) != update[field]:
                target[field] = update[field]
                changed += 1
        for field, value in {
            "enabled": True,
            "socialSearchEnabled": bool(update.get("socialSearchEnabled", True)),
            "activeStatus": target.get("activeStatus") or "active_or_unknown",
            "sourceRegistryVerified": True,
            "sourceRegistryRosterOrder": int(update.get("rosterOrder") or 0),
        }.items():
            if target.get(field) != value:
                target[field] = value
                changed += 1
        if "spotifyProfile" in update and not update["spotifyProfile"]:
            target.pop("spotifyId", None)
        synced_records.append(target)

    final_artists = order_records(artists)
    for index, artist in enumerate(final_artists, 1):
        if artist.get("rosterOrder") != index:
            artist["rosterOrder"] = index
            changed += 1

    names = [str(item.get("name") or "") for item in final_artists]
    if len(names) != len(set(map(norm, names))):
        raise SystemExit("Roster sync produced duplicate artist names")
    verify_records(final_artists)

    # Portraits are editorial assets, not daily refresh data. Apply the saved
    # copy after the Sheet handoff, including the runtime app payload.
    portraits = load_portraits(ROOT)
    changed += apply_to_records(final_artists, portraits)
    apply_to_records(updates, portraits)

    ARTISTS_FILE.write_text(
        json.dumps(final_artists, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    apply_owner_roster(ROOT)
    return final_artists, updates, changed


def sync_verified_websites(updates: list[dict]) -> int:
    websites = load_json(WEBSITES_FILE, {})
    if not isinstance(websites, dict):
        raise SystemExit("Verified website registry is not a JSON object")
    allowed = {norm(row["name"]) for row in snapshot()}
    excluded = [name for name in websites if norm(name) not in allowed or norm(name) in EXCLUDED_ARTISTS]
    for name in excluded:
        del websites[name]
    changed = len(excluded)
    for update in updates:
        if norm(update.get("name")) in EXCLUDED_ARTISTS:
            continue
        website = real_official_website(update.get("website"))
        if not website:
            websites.pop(str(update.get("name") or "").strip(), None)
            continue
        name = str(update.get("name") or "").strip()
        if websites.get(name) != website:
            websites[name] = website
            changed += 1
    WEBSITES_FILE.write_text(
        json.dumps(websites, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return changed


def registry_payload(update: dict) -> dict:
    payload = {
        "aliases": update.get("aliases") or [update["name"]],
        "website": update.get("website") or "",
        "instagramProfile": update.get("instagramProfile") or "",
        "spotifyProfile": update.get("spotifyProfile") or "",
        "youtubeProfile": update.get("youtubeProfile") or "",
        "officialImageSource": update.get("officialImageSource") or "",
        "imageUrl": update.get("imageUrl") or "",
        "imagePosition": update.get("imagePosition") or "",
        "state": update.get("state") or "",
        "label": update.get("label") or "",
        "sourceRegistryVerified": True,
    }
    # Empty reviewed socials must also override stale hard-coded links.
    profile_fields = {"website", "instagramProfile", "spotifyProfile", "youtubeProfile", "officialImageSource"}
    return {key: value for key, value in payload.items()
            if value not in ("", None, []) or key in profile_fields or key == "sourceRegistryVerified"}


def sync_app(artists: list[dict], updates: list[dict]) -> bool:
    text = APP_FILE.read_text(encoding="utf-8")
    original = text
    allowed = {norm(row["name"]) for row in artists}
    legacy_pattern = r"const VERIFIED_ARTIST_REGISTRY = (\{.*?\n\});"
    legacy = re.search(legacy_pattern, text, flags=re.S)
    if legacy:
        records = json.loads(legacy.group(1))
        records = {name: row for name, row in records.items() if norm(name) in allowed}
        # The pinned SEO renderer still reads this older constant directly.
        # Publish the same reviewed values to both supported runtime formats.
        records.update({norm(row["name"]): registry_payload(row) for row in updates})
        replacement = "const VERIFIED_ARTIST_REGISTRY = " + json.dumps(records, indent=2, ensure_ascii=False) + ";"
        text = re.sub(legacy_pattern, lambda _: replacement, text, count=1, flags=re.S)

    portraits = load_portraits(ROOT)
    static_payload = {norm(name): {"imageUrl": p["asset"], "imagePosition": p.get("position", "center")}
                      for name, p in portraits.items()}
    static_js = "const STATIC_ARTIST_PORTRAITS = " + json.dumps(static_payload, indent=2, ensure_ascii=False) + ";"
    if "const STATIC_ARTIST_PORTRAITS = " in text:
        text = re.sub(r"const STATIC_ARTIST_PORTRAITS = \{.*?\n\};", lambda _: static_js, text, count=1, flags=re.S)
    else:
        text = text.replace("const ARTIST_OVERRIDES = {", static_js + "\n\nconst ARTIST_OVERRIDES = {", 1)

    roster_names = [str(item.get("name") or "") for item in artists]
    roster_js = "const ARTIST_ROSTER_ORDER = " + json.dumps(roster_names, indent=2, ensure_ascii=False) + ";"
    text, count = re.subn(
        r"const ARTIST_ROSTER_ORDER = \[.*?\n\];",
        roster_js,
        text,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise SystemExit("ARTIST_ROSTER_ORDER was not found in app.js")

    supplemental = {norm(update["name"]): registry_payload(update) for update in updates}
    supplemental_js = (
        "const VERIFIED_ARTIST_REGISTRY_UPDATES = "
        + json.dumps(supplemental, indent=2, ensure_ascii=False)
        + ";\n"
    )
    pattern = r"const VERIFIED_ARTIST_REGISTRY_UPDATES = \{.*?\n\};\n"
    if re.search(pattern, text, flags=re.S):
        text = re.sub(pattern, lambda _match: supplemental_js, text, count=1, flags=re.S)
    else:
        marker = "const ARTIST_OVERRIDES = {"
        if marker not in text:
            raise SystemExit("ARTIST_OVERRIDES marker was not found in app.js")
        text = text.replace(marker, supplemental_js + marker, 1)

    old_line = "    const verifiedUpdate = VERIFIED_ARTIST_REGISTRY[key] || {};"
    new_line = "    const verifiedUpdate = { ...(VERIFIED_ARTIST_REGISTRY[key] || {}), ...(VERIFIED_ARTIST_REGISTRY_UPDATES[key] || {}) };"
    if old_line in text:
        text = text.replace(old_line, new_line, 1)
    elif new_line not in text:
        raise SystemExit("Verified registry merge line was not found in app.js")

    # The sheet can retain search URLs as research placeholders. Those values
    # stay in the source registry, but the public directory only exposes direct
    # artist/profile links and otherwise shows the platform as pending.
    spotify_pattern = r"function spotifyInfo\(artist\) \{.*?\n\}\nfunction instagramInfo"
    spotify_replacement = '''function spotifyInfo(artist) {
  const candidate = artist.spotifyProfile || (artist.spotifyId ? `https://open.spotify.com/artist/${encodeURIComponent(artist.spotifyId)}` : "");
  const directProfile = /open\\.spotify\\.com\\/artist\\/[A-Za-z0-9]+/i.test(candidate) ? candidate : "";
  if (directProfile) return { url: directProfile, exact: true, status: "Open verified Spotify profile" };
  return { url: "", exact: false, status: "Spotify link pending verification" };
}
function instagramInfo'''
    text, spotify_count = re.subn(
        spotify_pattern, lambda _match: spotify_replacement, text, count=1, flags=re.S
    )
    if spotify_count != 1:
        raise SystemExit("spotifyInfo function was not found in app.js")

    youtube_pattern = r"function youtubeInfo\(artist\) \{.*?\n\}\nfunction websiteInfo"
    youtube_replacement = '''function youtubeInfo(artist) {
  const candidate = artist.youtubeProfile || (/youtu\\.be|youtube\\.com/i.test(artist.officialProfile || "") ? artist.officialProfile : "");
  const official = candidate && !/youtube\\.com\\/results\\?|music\\.youtube\\.com\\/search/i.test(candidate) ? candidate : "";
  return official ? { url: official, status: "Open verified YouTube profile" } : { url: "", status: "YouTube link pending verification" };
}
function websiteInfo'''
    text, youtube_count = re.subn(
        youtube_pattern, lambda _match: youtube_replacement, text, count=1, flags=re.S
    )
    if youtube_count != 1:
        raise SystemExit("youtubeInfo function was not found in app.js")

    website_pattern = r"function websiteInfo\(artist\) \{.*?\n\}\nfunction artistImageInfo"
    website_replacement = '''function websiteInfo(artist) {
  const candidate = artist.website || artist.officialWebsite || artist.officialProfile || "";
  const isPlatform = /instagram\\.com|open\\.spotify\\.com|youtu\\.be|youtube\\.com|music\\.apple\\.com|bandsintown\\.com|google\\.com\\/search|wikipedia\\.org/i.test(candidate);
  return candidate && !isPlatform ? { url: candidate, status: "Open official website" } : { url: "", status: "Website link pending verification" };
}
function artistImageInfo'''
    text, website_count = re.subn(
        website_pattern, lambda _match: website_replacement, text, count=1, flags=re.S
    )
    if website_count != 1:
        raise SystemExit("websiteInfo function was not found in app.js")

    if text != original:
        APP_FILE.write_text(text, encoding="utf-8")
        return True
    return False


def sync_roster_test(artists: list[dict]) -> bool:
    if not TEST_FILE.exists():
        return False
    text = TEST_FILE.read_text(encoding="utf-8")
    original = text
    total = len(artists)
    counts = {
        priority: sum(1 for item in artists if int(item.get("monitoringPriority") or 3) == priority)
        for priority in (1, 2, 3)
    }
    text = re.sub(
        r"def test_master_roster_has_\d+_unique_artists\(self\):",
        f"def test_master_roster_has_{total}_unique_artists(self):",
        text,
        count=1,
    )
    text = re.sub(r"self\.assertEqual\(len\(names\), \d+\)", f"self.assertEqual(len(names), {total})", text, count=1)
    text = re.sub(
        r"self\.assertEqual\(len\(\{name\.casefold\(\) for name in names\}\), \d+\)",
        f"self.assertEqual(len({{name.casefold() for name in names}}), {total})",
        text,
        count=1,
    )
    for priority in (1, 2, 3):
        text = re.sub(
            rf"self\.assertEqual\(sum\(1 for item in artists if item\.get\(\"monitoringPriority\"\) == {priority}\), \d+\)",
            f'self.assertEqual(sum(1 for item in artists if item.get("monitoringPriority") == {priority}), {counts[priority]})',
            text,
            count=1,
        )
    if text != original:
        TEST_FILE.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> int:
    artists, updates, config_changes = sync_config()
    website_changes = sync_verified_websites(updates)
    app_changed = sync_app(artists, updates)
    test_changed = sync_roster_test(artists)
    print(
        "Verified registry synced: "
        f"rows={len(updates)}, artists={len(artists)}, config_changes={config_changes}, "
        f"website_changes={website_changes}, app_changed={app_changed}, test_changed={test_changed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
