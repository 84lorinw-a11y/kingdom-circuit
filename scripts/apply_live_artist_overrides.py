#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import pathlib
import re
import shutil

EXCLUDED_ARTISTS = {"chad jones", "erica mason", "big holy"}
EXCLUDED_SLUGS = {"chad-jones", "erica-mason", "big-holy"}
FALLBACK_IMAGE = "/assets/event-fallback.webp"

REGISTRY_UPDATES = {
    "caleb gordon": {
        "name": "Caleb Gordon",
        "aliases": ["Caleb Gordon"],
        "category": "core",
        "monitoringPriority": 1,
        "ticketmasterEnabled": True,
        "textMatchEnabled": True,
        "website": "https://tprlive.co/collections/caleb-gordon-the-eden-experience",
        "instagramProfile": "https://www.instagram.com/calebfromeden/",
        "spotifyProfile": "https://open.spotify.com/artist/6s3XaJkcT7464G4oII9V41",
        "youtubeProfile": "https://www.youtube.com/@CalebGordon",
        "officialImageSource": "https://tprlive.co/collections/caleb-gordon-the-eden-experience",
        "imageUrl": "https://tprlive.co/cdn/shop/files/ARTIST_HEADSHOT_36.jpg?v=1776887171&width=1797",
        "imagePosition": "center",
        "preferArtistImage": True,
        "sourceRegistryVerified": True,
        "sourceRegistryRosterOrder": 4,
    },
    "kelo": {
        "name": "Kelo",
        "aliases": ["Kelo"],
        "category": "core",
        "monitoringPriority": 2,
        "ticketmasterEnabled": False,
        "textMatchEnabled": False,
        "website": "https://www.instagram.com/cutthecho/",
        "instagramProfile": "https://www.instagram.com/cutthecho/",
        "spotifyProfile": "https://open.spotify.com/artist/6j8t8rQzrAtRx5tYImodgd",
        "youtubeProfile": "https://www.youtube.com/channel/UCAvlfmD2aiqXxxknr-9VSVg",
        "officialImageSource": "https://www.instagram.com/cutthecho/",
        "sourceRegistryVerified": True,
        "sourceRegistryRosterOrder": 79,
    },
    "dkg kie": {
        "name": "DKG Kie",
        "aliases": ["DKG Kie"],
        "category": "core",
        "monitoringPriority": 1,
        "ticketmasterEnabled": False,
        "textMatchEnabled": True,
        "website": "https://www.dkgkiemerch.com/",
        "instagramProfile": "https://www.instagram.com/dkg.kie",
        "spotifyProfile": "https://open.spotify.com/artist/1eeYg6dFkaRT5GA0lsCVHA",
        "youtubeProfile": "https://www.youtube.com/@dkgkie",
        "officialImageSource": "https://www.instagram.com/dkg.kie",
        "sourceRegistryVerified": True,
        "sourceRegistryRosterOrder": 80,
    },
    "braille": {
        "name": "Braille",
        "aliases": ["Braille"],
        "category": "legacy",
        "monitoringPriority": 3,
        "ticketmasterEnabled": False,
        "textMatchEnabled": True,
        "website": "https://www.humblebeast.com/music/braille",
        "instagramProfile": "https://www.instagram.com/bryanbraille/",
        "spotifyProfile": "https://open.spotify.com/artist/6RYTz1tFNDF2qP0mwqEwDO",
        "youtubeProfile": "https://www.youtube.com/@bryanbraille",
        "officialImageSource": "https://www.humblebeast.com/music/braille",
        "sourceRegistryVerified": True,
        "sourceRegistryRosterOrder": 81,
    },
    "canton jones": {
        "name": "Canton Jones",
        "aliases": ["Canton Jones"],
        "category": "legacy",
        "monitoringPriority": 3,
        "ticketmasterEnabled": True,
        "textMatchEnabled": True,
        "website": "https://www.instagram.com/thecantonjones/?hl=en",
        "instagramProfile": "https://www.instagram.com/thecantonjones/?hl=en",
        "spotifyProfile": "https://open.spotify.com/artist/3nzEXHMRFWTw4zt3pVRv6V",
        "youtubeProfile": "https://www.youtube.com/@CantonJones1",
        "officialImageSource": "https://www.instagram.com/thecantonjones/?hl=en",
        "sourceRegistryVerified": True,
        "sourceRegistryRosterOrder": 82,
    },
    "jay-way": {
        "name": "Jay-Way",
        "aliases": ["Jay-Way", "Jay Way"],
        "category": "core",
        "monitoringPriority": 1,
        "ticketmasterEnabled": False,
        "textMatchEnabled": True,
        "website": "https://www.jaywaythealien.com/",
        "instagramProfile": "https://www.instagram.com/JayWayTheAlien",
        "spotifyProfile": "https://open.spotify.com/artist/1RDbE3dM2bNNSTh88R4MQ7",
        "youtubeProfile": "https://www.youtube.com/@JayWayTheAlien",
        "officialImageSource": "https://www.jaywaythealien.com/",
        "sourceRegistryVerified": True,
        "sourceRegistryRosterOrder": 83,
    },
    "stixx aka conejo": {
        "name": "Stixx aka Conejo",
        "aliases": ["Stixx aka Conejo", "Stixx"],
        "category": "core",
        "monitoringPriority": 2,
        "ticketmasterEnabled": True,
        "textMatchEnabled": True,
        "website": "https://linktr.ee/stixxwym",
        "instagramProfile": "https://www.instagram.com/stixxwym",
        "spotifyProfile": "https://open.spotify.com/artist/3khYLvZ6GmLlPMPlTfMTBr",
        "youtubeProfile": "https://www.youtube.com/@stixxwym/videos",
        "officialImageSource": "https://linktr.ee/stixxwym",
        "sourceRegistryVerified": True,
        "sourceRegistryRosterOrder": 84,
    },
    "ruslan": {
        "name": "Ruslan",
        "aliases": ["Ruslan", "Ruslan KD"],
        "category": "core",
        "monitoringPriority": 1,
        "ticketmasterEnabled": False,
        "textMatchEnabled": False,
        "website": "https://www.instagram.com/ruslankd/?hl=en",
        "instagramProfile": "https://www.instagram.com/ruslankd/?hl=en",
        "spotifyProfile": "https://open.spotify.com/artist/2GEXrCflKZ5S5ZHBM4LNcV",
        "youtubeProfile": "https://www.youtube.com/@RuslanKD/featured",
        "officialImageSource": "https://www.instagram.com/ruslankd/?hl=en",
        "sourceRegistryVerified": True,
        "sourceRegistryRosterOrder": 85,
    },
}

CANONICAL_KEYS = ["kelo", "dkg kie", "braille", "canton jones", "jay-way", "stixx aka conejo", "ruslan"]


def norm(value: object) -> str:
    return str(value or "").strip().casefold()


def slugify(value: str) -> str:
    value = value.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def load_json(path: pathlib.Path, fallback):
    if not path.is_file():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: pathlib.Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def canonical_record(update: dict) -> dict:
    keys = (
        "name", "aliases", "category", "monitoringPriority", "ticketmasterEnabled",
        "textMatchEnabled", "website", "instagramProfile", "spotifyProfile",
        "youtubeProfile", "officialImageSource",
    )
    record = {"rosterOrder": int(update["sourceRegistryRosterOrder"])}
    record.update({key: update[key] for key in keys if key in update})
    return record


def patch_canonical_updates(root: pathlib.Path) -> None:
    path = root / "config" / "verified-artist-registry-updates.json"
    updates = load_json(path, [])
    if not isinstance(updates, list):
        raise SystemExit("Verified registry updates must be a JSON array")
    replacements = {key: canonical_record(REGISTRY_UPDATES[key]) for key in CANONICAL_KEYS}
    cleaned = []
    used = set()
    for item in updates:
        if not isinstance(item, dict):
            continue
        key = norm(item.get("name"))
        if key in EXCLUDED_ARTISTS:
            continue
        if key in replacements:
            if key not in used:
                cleaned.append(replacements[key])
                used.add(key)
            continue
        cleaned.append(item)
    for key in CANONICAL_KEYS:
        if key not in used:
            cleaned.append(replacements[key])
    cleaned.sort(key=lambda item: (int(item.get("rosterOrder") or 99999), norm(item.get("name"))))
    write_json(path, cleaned)


def patch_sync_script(root: pathlib.Path) -> None:
    path = root / "scripts" / "sync_verified_artist_registry.py"
    text = path.read_text(encoding="utf-8")
    original = text
    text = text.replace("SYNC_VERSION = 4", "SYNC_VERSION = 5")

    filter_marker = "    updates = load_json(UPDATES_FILE, [])\n"
    filter_block = (
        filter_marker
        + "    artists = [item for item in artists if isinstance(item, dict) and norm(item.get(\"name\")) not in {\"chad jones\", \"erica mason\", \"big holy\"}]\n"
        + "    updates = [item for item in updates if isinstance(item, dict) and norm(item.get(\"name\")) not in {\"chad jones\", \"erica mason\", \"big holy\"}]\n"
    )
    if filter_block not in text:
        if filter_marker not in text:
            raise SystemExit("Could not locate verified registry load marker")
        text = text.replace(filter_marker, filter_block, 1)

    old_orders = '''    expected_orders = list(range(55, 55 + len(updates)))
    actual_orders = [int(item.get("rosterOrder") or 0) for item in updates]
    if actual_orders != expected_orders:
        raise SystemExit(f"Verified registry block must be contiguous 55-{54 + len(updates)}: {actual_orders}")
'''
    new_orders = '''    actual_orders = [int(item.get("rosterOrder") or 0) for item in updates]
    if not actual_orders or actual_orders[0] != 55 or actual_orders != sorted(set(actual_orders)):
        raise SystemExit(f"Verified registry source orders must be unique, increasing, and begin at 55: {actual_orders}")
'''
    if old_orders in text:
        text = text.replace(old_orders, new_orders, 1)
    elif new_orders not in text:
        raise SystemExit("Could not update verified registry source-order validation")

    source_marker = '            "sourceRegistryVerified": True,\n'
    source_line = '            "sourceRegistryRosterOrder": int(update.get("rosterOrder") or 0),\n'
    if source_line not in text:
        if source_marker not in text:
            raise SystemExit("Could not locate sourceRegistryVerified field")
        text = text.replace(source_marker, source_marker + source_line, 1)

    text = text.replace(
        "    if names[54:78] != update_names:\n        raise SystemExit(\"Verified registry block did not land exactly at roster positions 55-78\")",
        "    if names[54:54 + len(update_names)] != update_names:\n        raise SystemExit(f\"Verified registry block did not land exactly after roster position 54: {update_names}\")",
    )

    if text != original:
        path.write_text(text, encoding="utf-8")


def patch_sync_workflow(root: pathlib.Path) -> None:
    path = root / ".github" / "workflows" / "sync-verified-artist-registry.yml"
    text = path.read_text(encoding="utf-8")
    original = text
    text = text.replace("assert len(artists) == 321, len(artists)", "assert len(artists) >= 250, len(artists)")
    text = text.replace("assert len({artist['name'].casefold() for artist in artists}) == 321", "assert len({artist['name'].casefold() for artist in artists}) == len(artists)")
    text = text.replace("assert [artist['rosterOrder'] for artist in artists] == list(range(1, 322))", "assert [artist['rosterOrder'] for artist in artists] == list(range(1, len(artists) + 1))")
    text = text.replace("assert [artist['name'] for artist in artists[54:78]] == [item['name'] for item in updates]", "assert [artist['name'] for artist in artists[54:54 + len(updates)]] == [item['name'] for item in updates]")
    text = text.replace("assert artists[78]['name'] == 'Alex Jean'", "assert artists[54 + len(updates)]['name'] == 'Alex Jean'")
    text = text.replace("print('Verified artist rows 55-78 validated:', len(updates), 'rows; roster=', len(artists))", "print('Verified artist registry block validated:', len(updates), 'rows; roster=', len(artists))")
    if text != original:
        path.write_text(text, encoding="utf-8")


def patch_deploy_workflow(root: pathlib.Path) -> None:
    path = root / ".github" / "workflows" / "update-and-deploy.yml"
    text = path.read_text(encoding="utf-8")
    original = text

    source_step = '''      - name: Apply verified live artist overrides
        run: python scripts/apply_live_artist_overrides.py --source .

'''
    source_marker = "      - name: Restore runtime-only source configuration\n"
    if source_step not in text:
        if source_marker not in text:
            raise SystemExit("Could not locate live source override insertion point")
        text = text.replace(source_marker, source_step + source_marker, 1)

    artifact_step = '''      - name: Apply verified live artist artifact cleanup
        run: python scripts/apply_live_artist_overrides.py --site _site

'''
    artifact_marker = "      - name: Verify production SEO architecture\n"
    if artifact_step not in text:
        if artifact_marker not in text:
            raise SystemExit("Could not locate live artifact override insertion point")
        text = text.replace(artifact_marker, artifact_step + artifact_marker, 1)

    if text != original:
        path.write_text(text, encoding="utf-8")


def patch_artists(path: pathlib.Path) -> list[dict]:
    artists = load_json(path, [])
    if not isinstance(artists, list):
        raise SystemExit(f"Artist registry is not an array: {path}")
    artists = [a for a in artists if isinstance(a, dict) and norm(a.get("name")) not in EXCLUDED_ARTISTS]
    by_name = {norm(a.get("name")): a for a in artists}

    for key, update in REGISTRY_UPDATES.items():
        artist = by_name.get(key)
        if artist is None:
            artist = {
                "name": update["name"],
                "aliases": update.get("aliases") or [update["name"]],
                "enabled": True,
                "ticketmasterEnabled": bool(update.get("ticketmasterEnabled", True)),
                "category": update.get("category") or "core",
                "monitoringPriority": int(update.get("monitoringPriority") or 3),
                "topStreamingPriority": False,
                "socialSearchEnabled": int(update.get("monitoringPriority") or 3) <= 2,
                "activeStatus": "active_or_unknown",
                "textMatchEnabled": bool(update.get("textMatchEnabled", True)),
                "rosterOrder": len(artists) + 1,
            }
            artists.append(artist)
            by_name[key] = artist
        artist.update(update)
        artist["enabled"] = True

    artists.sort(key=lambda item: (int(item.get("rosterOrder") or 99999), norm(item.get("name"))))
    for index, artist in enumerate(artists, 1):
        artist["rosterOrder"] = index
    write_json(path, artists)
    return artists


def patch_events(path: pathlib.Path) -> int:
    if not path.is_file():
        return 0
    events = load_json(path, [])
    if not isinstance(events, list):
        return 0
    cleaned = []
    removed_count = 0
    for event in events:
        if not isinstance(event, dict):
            continue
        original_artists = list(event.get("artists") or [])
        remaining = [name for name in original_artists if norm(name) not in EXCLUDED_ARTISTS]
        removed_artist = len(remaining) != len(original_artists)
        title = norm(event.get("title"))
        title_excluded = any(name in title for name in EXCLUDED_ARTISTS)
        if title_excluded or (removed_artist and not remaining):
            removed_count += 1
            continue
        if removed_artist:
            event["artists"] = remaining
            if norm(event.get("headliner")) in EXCLUDED_ARTISTS:
                if remaining:
                    event["headliner"] = remaining[0]
                else:
                    event.pop("headliner", None)
        cleaned.append(event)
    write_json(path, cleaned)
    return removed_count


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
        "preferArtistImage": bool(update.get("preferArtistImage", False)),
        "sourceRegistryVerified": True,
        "sourceRegistryRosterOrder": int(update.get("sourceRegistryRosterOrder") or 0),
    }
    return {key: value for key, value in payload.items() if value not in ("", None, False, 0, []) or key == "sourceRegistryVerified"}


def patch_app(path: pathlib.Path, artists: list[dict]) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    original = text

    roster_names = [str(item.get("name") or "") for item in artists]
    roster_js = "const ARTIST_ROSTER_ORDER = " + json.dumps(roster_names, indent=2, ensure_ascii=False) + ";"
    text, count = re.subn(r"const ARTIST_ROSTER_ORDER = \[.*?\n\];", roster_js, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"ARTIST_ROSTER_ORDER not found in {path}")

    registry_pattern = r"const VERIFIED_ARTIST_REGISTRY_UPDATES = (\{.*?\n\});\n"
    match = re.search(registry_pattern, text, flags=re.S)
    registry = {}
    if match:
        try:
            registry = json.loads(match.group(1))
        except json.JSONDecodeError:
            registry = {}
    for key in list(registry):
        if norm(key) in EXCLUDED_ARTISTS:
            registry.pop(key, None)
    for key, update in REGISTRY_UPDATES.items():
        registry[key] = registry_payload(update)
    registry_js = "const VERIFIED_ARTIST_REGISTRY_UPDATES = " + json.dumps(registry, indent=2, ensure_ascii=False) + ";\n"
    if match:
        text = re.sub(registry_pattern, lambda _m: registry_js, text, count=1, flags=re.S)

    if "function enhanceVerifiedArtistImages()" not in text:
        marker = "function renderEventDetail()"
        enhancement = r'''
function enhanceVerifiedArtistImages() {
  document.querySelectorAll("[data-artist-card]").forEach(card => {
    const name = card.querySelector("h2 a")?.textContent || "";
    const artist = artistConfig(name);
    const visual = card.querySelector(".artist-visual");
    if (!visual || !artist?.imageUrl) return;
    visual.classList.remove("artist-visual-empty");
    visual.innerHTML = `<img src="${esc(localAssetUrl(artist.imageUrl))}" alt="${esc(artist.name)}" loading="lazy" onerror="this.onerror=null;this.src='${FALLBACK_EVENT_IMAGE}';">`;
  });

  const root = document.querySelector("[data-artist-profile]");
  if (!root) return;
  const name = new URLSearchParams(location.search).get("name") || "";
  const artist = artistConfig(name);
  const hero = root.querySelector(".profile-hero");
  if (!hero || !artist?.imageUrl || hero.querySelector(".profile-visual")) return;
  hero.classList.remove("profile-hero-no-image");
  hero.insertAdjacentHTML("afterbegin", `<div class="profile-visual"><img src="${esc(localAssetUrl(artist.imageUrl))}" alt="${esc(artist.name)}" onerror="this.onerror=null;this.src='${FALLBACK_EVENT_IMAGE}';"></div>`);
  hero.querySelector(".profile-image-note")?.remove();
}
'''
        if marker in text:
            text = text.replace(marker, enhancement + "\n" + marker, 1)
        call_marker = "  renderArtistProfile();"
        if call_marker in text:
            text = text.replace(call_marker, call_marker + "\n  enhanceVerifiedArtistImages();", 1)

    if text != original:
        path.write_text(text, encoding="utf-8")


def verify_source(root: pathlib.Path, artists: list[dict]) -> None:
    by_name = {norm(a.get("name")): a for a in artists}
    failures = []
    for excluded in EXCLUDED_ARTISTS:
        if excluded in by_name:
            failures.append(f"excluded-artist:{excluded}")
    for key, update in REGISTRY_UPDATES.items():
        artist = by_name.get(key)
        if not artist:
            failures.append(f"missing-update:{key}")
            continue
        for field in ("website", "instagramProfile", "spotifyProfile", "youtubeProfile", "officialImageSource"):
            if update.get(field) and artist.get(field) != update[field]:
                failures.append(f"update-mismatch:{key}:{field}")
        if update.get("imageUrl") and artist.get("imageUrl") != update["imageUrl"]:
            failures.append(f"update-mismatch:{key}:imageUrl")
    orders = [int(a.get("rosterOrder") or 0) for a in artists]
    if orders != list(range(1, len(artists) + 1)):
        failures.append("roster-order-not-contiguous")
    if failures:
        raise SystemExit("Live artist source verification failed:\n" + "\n".join(failures))


def apply_source(root: pathlib.Path) -> None:
    artists = patch_artists(root / "config" / "artists.json")
    removed_events = patch_events(root / "events.json")
    patch_app(root / "app.js", artists)
    verify_source(root, artists)
    print(f"Live source artist overrides verified: artists={len(artists)}, removed_events={removed_events}")


def normalize_html(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip().casefold()


def contains_excluded_name(value: str) -> bool:
    text = normalize_html(value)
    return any(name in text for name in EXCLUDED_ARTISTS)


def artist_slugs(value: str) -> list[str]:
    return [match.casefold() for match in re.findall(r'/artists/([^/]+)/', value, flags=re.I)]


def remove_excluded_event_pages(out_dir: pathlib.Path) -> set[str]:
    removed = set()
    event_root = out_dir / "event"
    if not event_root.is_dir():
        return removed
    for page in event_root.glob("*/index.html"):
        text = page.read_text(encoding="utf-8")
        h1_match = re.search(r"<h1\b[^>]*>(.*?)</h1>", text, flags=re.I | re.S)
        h1 = h1_match.group(1) if h1_match else ""
        linked = artist_slugs(text)
        only_excluded = bool(linked) and all(slug in EXCLUDED_SLUGS for slug in linked)
        if contains_excluded_name(h1) or only_excluded:
            removed.add(page.parent.name)
            shutil.rmtree(page.parent)
    return removed


def remove_cards_for_slugs(text: str, card_class: str, path_prefix: str, slugs: set[str]) -> str:
    pattern = re.compile(
        rf'<article\b(?=[^>]*class="[^"]*\b{re.escape(card_class)}\b[^"]*")[^>]*>.*?</article>',
        flags=re.I | re.S,
    )
    def repl(match: re.Match[str]) -> str:
        block = match.group(0)
        lowered = block.casefold()
        return "" if any(f"/{path_prefix}/{slug}/" in lowered for slug in slugs) else block
    return pattern.sub(repl, text)


def clean_artist_lines(text: str) -> str:
    pattern = re.compile(r'(<p\b[^>]*class="[^"]*\bartist-line\b[^"]*"[^>]*>)(.*?)(</p>)', flags=re.I | re.S)
    anchor_pattern = re.compile(r'<a\b[^>]*href="[^"]*/artists/([^/]+)/[^"]*"[^>]*>.*?</a>', flags=re.I | re.S)
    def repl(match: re.Match[str]) -> str:
        inner = match.group(2)
        anchors = [anchor.group(0) for anchor in anchor_pattern.finditer(inner) if anchor.group(1).casefold() not in EXCLUDED_SLUGS]
        if anchors:
            return match.group(1) + " - ".join(anchors) + match.group(3)
        if any(f"/artists/{slug}/" in inner.casefold() for slug in EXCLUDED_SLUGS):
            return ""
        return match.group(0)
    return pattern.sub(repl, text)


def add_event_image_fallbacks(text: str) -> str:
    pattern = re.compile(r'<img\b(?=[^>]*class="[^"]*(?:event-artwork|artist-photo)[^"]*")[^>]*>', flags=re.I)
    def repl(match: re.Match[str]) -> str:
        tag = match.group(0)
        if "onerror=" in tag.lower():
            return tag
        return tag[:-1] + f' onerror="this.onerror=null;this.src=\'{FALLBACK_IMAGE}\';">'
    return pattern.sub(repl, text)


def clean_static_html(out_dir: pathlib.Path, removed_event_slugs: set[str]) -> None:
    for page in out_dir.rglob("*.html"):
        text = page.read_text(encoding="utf-8")
        original = text
        text = remove_cards_for_slugs(text, "artist-card", "artists", EXCLUDED_SLUGS)
        if removed_event_slugs:
            text = remove_cards_for_slugs(text, "event-card", "event", removed_event_slugs)
        text = clean_artist_lines(text)
        text = add_event_image_fallbacks(text)
        if page == out_dir / "artists" / "index.html":
            count = len(re.findall(r'<article\b[^>]*\bdata-artist-card\b', text, flags=re.I))
            text = re.sub(
                r'(<p\b[^>]*data-artist-count[^>]*>)\s*\d+\s+artists\s*(</p>)',
                rf'\g<1>{count} artists\g<2>', text, count=1, flags=re.I,
            )
        if text != original:
            page.write_text(text, encoding="utf-8")


def artist_link_html(artist: dict) -> str:
    fields = [
        ("Instagram", artist.get("instagramProfile")),
        ("Spotify", artist.get("spotifyProfile")),
        ("YouTube", artist.get("youtubeProfile")),
        ("Website", artist.get("website") or artist.get("officialWebsite") or artist.get("officialProfile")),
    ]
    links = []
    seen = set()
    for label, url in fields:
        if not url or url in seen:
            continue
        seen.add(url)
        links.append(f'<a class="secondary-button" href="{html.escape(str(url), quote=True)}" target="_blank" rel="noopener">{html.escape(label)}</a>')
    return "".join(links)


def patch_static_artist_pages(out_dir: pathlib.Path, artists: list[dict]) -> None:
    by_name = {norm(a.get("name")): a for a in artists}
    for key in REGISTRY_UPDATES:
        artist = by_name.get(key)
        if not artist:
            continue
        page = out_dir / "artists" / slugify(artist["name"]) / "index.html"
        if not page.is_file():
            continue
        text = page.read_text(encoding="utf-8")
        original = text
        links = artist_link_html(artist)
        text = re.sub(r'<div class="profile-links">.*?</div>', f'<div class="profile-links">{links}</div>', text, count=1, flags=re.S)
        image_url = artist.get("imageUrl")
        if image_url and "profile-visual" not in text:
            hero_pattern = r'(<section\b[^>]*class="[^"]*\bprofile-hero\b[^"]*"[^>]*>)'
            image_markup = f'<div class="profile-visual"><img src="{html.escape(str(image_url), quote=True)}" alt="{html.escape(artist["name"], quote=True)}" onerror="this.onerror=null;this.src=\'{FALLBACK_IMAGE}\';"></div>'
            text = re.sub(hero_pattern, lambda m: m.group(1).replace(" profile-hero-no-image", "") + image_markup, text, count=1, flags=re.I)
        if text != original:
            page.write_text(text, encoding="utf-8")


def clean_sitemap(out_dir: pathlib.Path, removed_event_slugs: set[str]) -> None:
    sitemap = out_dir / "sitemap.xml"
    if not sitemap.is_file():
        return
    text = sitemap.read_text(encoding="utf-8")
    targets = [f"/artists/{slug}/" for slug in EXCLUDED_SLUGS]
    targets.extend(f"/event/{slug}/" for slug in removed_event_slugs)
    for target in targets:
        text = re.sub(rf"<url>.*?{re.escape(target)}.*?</url>\s*", "", text, flags=re.I | re.S)
    sitemap.write_text(text, encoding="utf-8")


def verify_site(out_dir: pathlib.Path) -> None:
    failures = []
    for slug in EXCLUDED_SLUGS:
        if (out_dir / "artists" / slug).exists():
            failures.append(f"excluded-artist-page:{slug}")
    for page in out_dir.rglob("*.html"):
        lowered = page.read_text(encoding="utf-8", errors="ignore").casefold()
        for slug in EXCLUDED_SLUGS:
            if f"/artists/{slug}/" in lowered:
                failures.append(f"excluded-artist-link:{page.relative_to(out_dir)}:{slug}")
    caleb = out_dir / "artists" / "caleb-gordon" / "index.html"
    if not caleb.is_file() or "ARTIST_HEADSHOT_36.jpg" not in caleb.read_text(encoding="utf-8", errors="ignore"):
        failures.append("caleb-profile-image-missing")
    if failures:
        raise SystemExit("Live artifact artist verification failed:\n" + "\n".join(failures[:100]))


def apply_site(out_dir: pathlib.Path) -> None:
    if not out_dir.is_dir():
        raise SystemExit(f"Missing site artifact: {out_dir}")
    artists = patch_artists(out_dir / "config" / "artists.json")
    patch_events(out_dir / "events.json")
    patch_app(out_dir / "app.js", artists)
    for slug in EXCLUDED_SLUGS:
        target = out_dir / "artists" / slug
        if target.exists():
            shutil.rmtree(target)
    removed_event_slugs = remove_excluded_event_pages(out_dir)
    clean_static_html(out_dir, removed_event_slugs)
    patch_static_artist_pages(out_dir, artists)
    clean_sitemap(out_dir, removed_event_slugs)
    __import__("subprocess").run([__import__("sys").executable, str(pathlib.Path(__file__).with_name("finalize_live_event_images.py")), "--site", str(out_dir)], check=True)
    verify_site(out_dir)
    print(f"Live artifact artist cleanup verified: artists={len(artists)}, removed_event_pages={len(removed_event_slugs)}")


def install(root: pathlib.Path) -> None:
    patch_sync_script(root)
    patch_sync_workflow(root)
    patch_deploy_workflow(root)
    patch_canonical_updates(root)
    print("Live artist promotion pipeline installed.")


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--install", action="store_true")
    group.add_argument("--source", metavar="ROOT")
    group.add_argument("--site", metavar="OUT_DIR")
    args = parser.parse_args()
    if args.install:
        install(pathlib.Path.cwd())
    elif args.source:
        apply_source(pathlib.Path(args.source).resolve())
    else:
        apply_site(pathlib.Path(args.site).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
