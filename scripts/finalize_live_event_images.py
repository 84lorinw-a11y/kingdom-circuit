#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import pathlib
import re
import shutil

FALLBACK = "/assets/event-fallback.webp"
PRIMARY_CACHE_TOKEN = "kc-20260829-2050"
RUNTIME_SCRIPT_URL = "/assets/event-image-repair-kc2050.js"
EXCLUDED_ARTISTS = {"chad jones", "erica mason", "big holy"}
EXCLUDED_SLUGS = {"chad-jones", "erica-mason", "big-holy"}
STALE_IMAGE_URLS = {
    "https://s1.ticketm.net/dam/a/295/bf4a2e20-facf-46e6-904e-c19f998cb295_SOURCE",
    "https://fivetwentycollective.com/wp-content/uploads/2021/03/Rare-of-Breed.jpg",
    "https://rareofbreed.com/cdn/shop/files/202511_RareOfBreed_TheWarehouse-32.jpg?v=1784663742&width=3840",
    "https://ugc.production.linktr.ee/0f6ee994-7bd6-4821-bb79-593f035ae2c9_1F523223-FD9A-4E86-88BE-0A34120C8FAD.jpeg?io=true&size=avatar-v3_0",
    "https://i.scdn.co/image/ab6761610000e5ebe8717d1df4abebcd56989c30",
}

# Verified/known-good presentation images used only when an event otherwise has
# generic artwork. Real event artwork is always preserved.
IMAGE_CANDIDATES = {
    "marty": [
        "https://i.scdn.co/image/ab6761610000e5eb3d2d9f74de93906d1f5996f3",
    ],
    "808 beezy": [
        "https://pbs.twimg.com/profile_images/1836827722309312512/e5kgorwv.jpg",
        "https://open.voidware.de/artist/3CltJZLndpJKtpUyRVBB1k",
    ],
    "hulvey": [
        "https://s1.ticketm.net/dam/a/d4e/a49ecab3-089d-46ff-baa5-7942c994ed4e_SOURCE",
        "https://open.voidware.de/artist/3zSrc5vUlUxyDdS0KrxFJO",
    ],
    "yumiya!": [
        "/assets/artists/yumiya-primary.jpg",
        "https://ugc.production.linktr.ee/0f6ee994-7bd6-4821-bb79-593f035ae2c9_1F523223-FD9A-4E86-88BE-0A34120C8FAD.jpeg?io=true&size=avatar-v3_0",
        "https://i.scdn.co/image/ab6761610000e5ebe8717d1df4abebcd56989c30",
    ],
    "rare of breed": [
        "/assets/artists/rare-of-breed-primary.jpg",
        "https://rareofbreed.com/cdn/shop/files/202511_RareOfBreed_TheWarehouse-32.jpg?v=1784663742&width=3840",
    ],
    "indie tribe.": [
        "/assets/artists/indie-tribe.webp",
    ],
    "issac mansfield": [
        "https://i.scdn.co/image/ab6761610000e5eb6d97dd155baa40ea3c14b616",
        "https://open.voidware.de/artist/1QgXbOPk6XpELZrJOzz33w",
    ],
    "zauntee": [
        "/assets/artists/zauntee.webp",
        "https://open.voidware.de/artist/7jyr9Co4MKL1iWML1G7vch",
    ],
    "anike": [
        "https://resources.tidal.com/images/108dfb26/84ff/447e/b0b7/a3e208c409ed/750x750.jpg",
        "https://open.voidware.de/artist/0GdzQJqgRL5SHp7kXOKba0",
    ],
    "brenno": [
        "https://cdn.rapzilla.com/wp-content/uploads/2020/10/23100333/277A3516-e1603484188893.jpg",
        "https://open.voidware.de/artist/7lBcEp7abNiq3WyHT3RRqV",
    ],
    "parris chariz": [
        "https://www.invubu.com/images/artists/1200/parris_chariz.jpg",
        "https://open.voidware.de/artist/2Vt6gyhUH7Vj2cybfQWOqM",
    ],
    "nobigdyl.": [
        "https://resources.tidal.com/images/66d1df15/192b/4a8f/97c3/30a2b85a36f3/750x750.jpg",
        "https://open.voidware.de/artist/2d8NsBa8O4C6bgQatFP5V4",
    ],
    "jet trouble": [
        "https://55promotion.com/kbm24/wp-content/uploads/2025/06/Promo-Headshot-1024x1024.jpg",
        "https://open.voidware.de/artist/6W2lyFO79SNpk3ZpF0A2s9",
    ],
    "don ready": [
        "https://ugc.production.linktr.ee/f87bf85e-d8ca-4d35-92f8-ac16dd0f03f3_Copy-of-Feb-2026---White-Press-Pic--elijah-sten-1.jpeg",
        "https://open.voidware.de/artist/5kQnpfa9Qp5lNSOThWVnFl",
    ],
    "mike teezy": [
        "https://real.fm/assets/Uploads/MikeTeezy__FocusFillWyItMC4xMSIsIi0wLjE2IiwxMjAwLDYyN10.jpg",
        "https://open.voidware.de/artist/6tO2zQcTIRfR2Xdsm9XnL7",
    ],
}


def norm(value: object) -> str:
    value = html.unescape(str(value or "")).casefold().replace("’", "'")
    return re.sub(r"\s+", " ", value).strip()


def strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(value))).strip()


def load_json(path: pathlib.Path) -> list:
    if not path.is_file():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, list) else []


def write_json(path: pathlib.Path, value: list) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def artist_key_from_names(names: list[str]) -> str | None:
    normalized = [norm(name) for name in names if name]
    for name in normalized:
        if name in IMAGE_CANDIDATES:
            return name
    combined = " | ".join(normalized)
    return next((key for key in IMAGE_CANDIDATES if key in combined), None)


def needs_repair(value: object) -> bool:
    raw = str(value or "").strip()
    image = norm(raw)
    return (
        (not image)
        or ("event-fallback.webp" in image)
        or ("open.voidware.de/artist/" in image)
        or raw in STALE_IMAGE_URLS
    )


def patch_event_json(path: pathlib.Path) -> tuple[int, int, int]:
    events = load_json(path)
    if not events:
        return 0, 0, 0
    cleaned: list[dict] = []
    removed = repaired = retired_names_removed = 0
    for event in events:
        if not isinstance(event, dict):
            continue
        original_artists = [str(name) for name in (event.get("artists") or []) if name]
        remaining = [name for name in original_artists if norm(name) not in EXCLUDED_ARTISTS]
        retired_names_removed += len(original_artists) - len(remaining)
        headliner = str(event.get("headliner") or "").strip()
        headliner_excluded = norm(headliner) in EXCLUDED_ARTISTS
        title_excluded = any(name in norm(event.get("title")) for name in EXCLUDED_ARTISTS)

        # Retire an event only when its actual billed identity is retired. Mixed
        # festivals survive; the retired performer is simply removed from lineup.
        if (headliner_excluded or title_excluded) and not remaining:
            removed += 1
            continue
        if original_artists != remaining:
            event["artists"] = remaining
        if headliner_excluded:
            if remaining:
                event["headliner"] = remaining[0]
            else:
                event.pop("headliner", None)

        key = artist_key_from_names([event.get("headliner") or ""] + list(event.get("artists") or []))
        if key and needs_repair(event.get("image")):
            event["image"] = IMAGE_CANDIDATES[key][0]
            repaired += 1
        cleaned.append(event)
    write_json(path, cleaned)
    return removed, repaired, retired_names_removed


def structured_performers(text: str) -> list[str]:
    # Generated event pages encode performers as MusicGroup objects in JSON-LD.
    return [html.unescape(name) for name in re.findall(
        r'"@type"\s*:\s*"MusicGroup"\s*,\s*"name"\s*:\s*"([^"]+)"',
        text,
        flags=re.I,
    )]


def event_page_should_be_removed(text: str) -> bool:
    performers = structured_performers(text)
    if performers:
        normalized = [norm(name) for name in performers]
        return bool(normalized) and all(name in EXCLUDED_ARTISTS for name in normalized)
    # Fallback for older generated pages without performer JSON-LD.
    lowered = norm(text)
    explicit = [name for name in EXCLUDED_ARTISTS if f"content=\"{name} live" in lowered]
    return bool(explicit)


def remove_excluded_event_pages(root: pathlib.Path) -> set[str]:
    removed: set[str] = set()
    event_root = root / "event"
    if not event_root.is_dir():
        return removed
    for page in list(event_root.glob("*/index.html")):
        text = page.read_text(encoding="utf-8", errors="ignore")
        if event_page_should_be_removed(text):
            removed.add(page.parent.name.casefold())
            shutil.rmtree(page.parent)
    return removed


CARD_RE = re.compile(
    r'<article\b(?=[^>]*class="[^"]*\bevent-card\b[^"]*")[^>]*>.*?</article>',
    flags=re.I | re.S,
)


def event_slug_from_block(block: str) -> str | None:
    match = re.search(r'href=["\']/event/([^/]+)/["\']', block, flags=re.I)
    return match.group(1).casefold() if match else None


def names_from_block(block: str) -> list[str]:
    names: list[str] = []
    line = re.search(r'<p\b[^>]*class="[^"]*\bartist-line\b[^"]*"[^>]*>(.*?)</p>', block, flags=re.I | re.S)
    if line:
        anchor_names = re.findall(r'<a\b[^>]*>(.*?)</a>', line.group(1), flags=re.I | re.S)
        names.extend(strip_tags(value) for value in anchor_names)
        if not anchor_names:
            names.append(strip_tags(line.group(1)))
    return [name for name in names if name]


def forced_primary_key(block: str) -> str | None:
    names = [norm(name) for name in names_from_block(block)]
    if names and all(name == "rare of breed" for name in names):
        return "rare of breed"
    if names and all(name == "yumiya!" for name in names):
        return "yumiya!"
    return None


def key_from_html(block: str) -> str | None:
    # Artist-line is the authoritative identity for generated event cards
    # and event detail pages. If it exists but is not one of the special
    # image-repair artists, do not scan unrelated page copy (such as the
    # related-shows section) and accidentally borrow another artist's image.
    names = names_from_block(block)
    key = artist_key_from_names(names)
    if key:
        return key
    if names:
        return None

    # Older generated markup can lack artist-line. Prefer structured
    # performer data before falling back to broad text matching.
    performers = structured_performers(block)
    key = artist_key_from_names(performers)
    if key:
        return key
    if performers:
        return None

    text = norm(strip_tags(block))
    return next((candidate for candidate in IMAGE_CANDIDATES if candidate in text), None)


def set_img_src(tag: str, src: str, key: str) -> str:
    if key in {"rare of breed", "yumiya!"} and src.startswith("/assets/artists/"):
        separator = "&" if "?" in src else "?"
        src = f"{src}{separator}v={PRIMARY_CACHE_TOKEN}"
    escaped = html.escape(src, quote=True)
    if re.search(r'\bsrc=["\'][^"\']*["\']', tag, flags=re.I):
        tag = re.sub(r'\bsrc=(["\'])[^"\']*\1', lambda m: f'src={m.group(1)}{escaped}{m.group(1)}', tag, count=1, flags=re.I)
    else:
        tag = tag[:-1] + f' src="{escaped}">'
    tag = re.sub(r'\s+onerror=(["\']).*?\1', "", tag, flags=re.I | re.S)
    tag = re.sub(r'\s+data-kc-event-artist=(["\']).*?\1', "", tag, flags=re.I | re.S)
    tag = re.sub(r'\s+data-kc-image-index=(["\']).*?\1', "", tag, flags=re.I | re.S)
    tag = re.sub(r'\s+data-kc-lock-primary=(["\']).*?\1', "", tag, flags=re.I | re.S)
    lock_attr = ' data-kc-lock-primary="1"' if key in {"rare of breed", "yumiya!"} else ""
    return tag[:-1] + (
        f' data-kc-event-artist="{html.escape(key, quote=True)}" data-kc-image-index="0"{lock_attr} '
        f'onerror="window.kcEventImageFallback ? window.kcEventImageFallback(this) : '
        f'(this.onerror=null,this.src=\'{FALLBACK}\');">'
    )


def repair_fallbacks_in_block(block: str) -> tuple[str, bool]:
    forced = forced_primary_key(block)
    key = forced or key_from_html(block)
    if not key:
        return block, False
    changed = False

    if forced:
        def force_repl(match: re.Match[str]) -> str:
            nonlocal changed
            changed = True
            return set_img_src(match.group(0), IMAGE_CANDIDATES[forced][0], forced)
        return re.sub(r'<img\b[^>]*>', force_repl, block, count=1, flags=re.I), True

    def repl(match: re.Match[str]) -> str:
        nonlocal changed
        tag = match.group(0)
        src_match = re.search(r'\bsrc=["\']([^"\']*)["\']', tag, flags=re.I)
        if not src_match or not needs_repair(html.unescape(src_match.group(1))):
            return tag
        changed = True
        return set_img_src(tag, IMAGE_CANDIDATES[key][0], key)

    return re.sub(r'<img\b[^>]*>', repl, block, flags=re.I), changed


def patch_html_page(page: pathlib.Path, removed_slugs: set[str]) -> tuple[int, int]:
    text = page.read_text(encoding="utf-8", errors="ignore")
    original = text
    removed_cards = repaired = 0

    def card_repl(match: re.Match[str]) -> str:
        nonlocal removed_cards, repaired
        block = match.group(0)
        slug = event_slug_from_block(block)
        if slug and slug in removed_slugs:
            removed_cards += 1
            return ""
        names = [norm(name) for name in names_from_block(block)]
        if names and all(name in EXCLUDED_ARTISTS for name in names):
            removed_cards += 1
            return ""
        updated, changed = repair_fallbacks_in_block(block)
        repaired += int(changed)
        return updated

    text = CARD_RE.sub(card_repl, text)

    if "/event/" in "/" + str(page).replace("\\", "/") + "/":
        forced = forced_primary_key(text)
        key = forced or key_from_html(text)
        if key:
            def detail_repl(match: re.Match[str]) -> str:
                nonlocal repaired
                tag = match.group(0)
                is_event_media = bool(re.search(r'\bclass=["\'][^"\']*(?:artist-photo|event-artwork)', tag, flags=re.I))
                if forced and is_event_media:
                    repaired += 1
                    return set_img_src(tag, IMAGE_CANDIDATES[forced][0], forced)
                src_match = re.search(r'\bsrc=["\']([^"\']*)["\']', tag, flags=re.I)
                if not src_match or not needs_repair(html.unescape(src_match.group(1))):
                    return tag
                repaired += 1
                return set_img_src(tag, IMAGE_CANDIDATES[key][0], key)
            text = re.sub(r'<img\b[^>]*>', detail_repl, text, flags=re.I)

    script_tag = f'<script src="{RUNTIME_SCRIPT_URL}"></script>'
    text = re.sub(
        r'<script\s+src="/assets/event-image-repair[^"]*\.js[^"]*"\s*></script>',
        script_tag,
        text,
        flags=re.I,
    )
    if script_tag not in text and "</head>" in text.lower():
        text = re.sub(r'</head>', script_tag + '</head>', text, count=1, flags=re.I)

    if text != original:
        page.write_text(text, encoding="utf-8")
    return removed_cards, repaired


def clean_sitemap(root: pathlib.Path, removed_slugs: set[str]) -> None:
    path = root / "sitemap.xml"
    if not path.is_file() or not removed_slugs:
        return
    text = path.read_text(encoding="utf-8")
    for slug in removed_slugs:
        text = re.sub(rf'<url>.*?/event/{re.escape(slug)}/.*?</url>\s*', "", text, flags=re.I | re.S)
    path.write_text(text, encoding="utf-8")


def verify(root: pathlib.Path) -> dict:
    failures: list[str] = []
    fallback_cards = 0
    fallback_card_examples: list[str] = []
    fallback_event_pages = 0
    retired_event_pages = 0
    retired_artist_links = 0
    stale_runtime_script_refs = 0
    unlocked_primary_images = 0
    versioned_script_path = root / RUNTIME_SCRIPT_URL.lstrip("/")
    if not versioned_script_path.is_file():
        failures.append(f"missing-versioned-runtime-script:{RUNTIME_SCRIPT_URL}")
    for page in root.rglob("*.html"):
        text = page.read_text(encoding="utf-8", errors="ignore")
        if '/assets/event-image-repair.js"' in text:
            stale_runtime_script_refs += 1
        for block in CARD_RE.findall(text):
            if "rare-of-breed-primary.jpg" in block or "yumiya-primary.jpg" in block:
                tags = re.findall(r'<img\b[^>]*>', block, flags=re.I)
                for tag in tags:
                    if "rare-of-breed-primary.jpg" in tag or "yumiya-primary.jpg" in tag:
                        if f"?v={PRIMARY_CACHE_TOKEN}" not in html.unescape(tag) or 'data-kc-lock-primary="1"' not in tag:
                            unlocked_primary_images += 1
        for block in CARD_RE.findall(text):
            sources = re.findall(r'<img\b[^>]*?\ssrc=["\']([^"\']+)', block, flags=re.I)
            if any("event-fallback.webp" in norm(src) for src in sources):
                fallback_cards += 1
                if len(fallback_card_examples) < 8:
                    title = strip_tags(re.search(r'<h3\b[^>]*>(.*?)</h3>', block, flags=re.I | re.S).group(1)) if re.search(r'<h3\b[^>]*>(.*?)</h3>', block, flags=re.I | re.S) else "unknown"
                    fallback_card_examples.append(f"{page.relative_to(root)}:{title}")
            for slug in EXCLUDED_SLUGS:
                if f"/artists/{slug}/" in norm(block):
                    retired_artist_links += 1
        if page.parent.parent == root / "event":
            if "rare-of-breed-primary.jpg" in text or "yumiya-primary.jpg" in text:
                media = re.search(r'<div[^>]*class="[^"]*event-detail-media[^"]*"[^>]*>\s*(<img\b[^>]*>)', text, flags=re.I | re.S)
                if not media or f"?v={PRIMARY_CACHE_TOKEN}" not in html.unescape(media.group(1)) or 'data-kc-lock-primary="1"' not in media.group(1):
                    unlocked_primary_images += 1
            sources = re.findall(r'<img\b[^>]*?\ssrc=["\']([^"\']+)', text, flags=re.I)
            if any("event-fallback.webp" in norm(src) for src in sources):
                fallback_event_pages += 1
            if event_page_should_be_removed(text):
                retired_event_pages += 1
    if fallback_cards:
        failures.append(f"generic-event-cards:{fallback_cards}[{' | '.join(fallback_card_examples)}]")
    if fallback_event_pages:
        failures.append(f"generic-event-pages:{fallback_event_pages}")
    if retired_event_pages:
        failures.append(f"retired-event-pages:{retired_event_pages}")
    if retired_artist_links:
        failures.append(f"retired-artist-links:{retired_artist_links}")
    if stale_runtime_script_refs:
        failures.append(f"stale-runtime-script-refs:{stale_runtime_script_refs}")
    if unlocked_primary_images:
        failures.append(f"unlocked-primary-images:{unlocked_primary_images}")
    if failures:
        raise SystemExit("Live event-image audit failed: " + ", ".join(failures))
    return {
        "fallbackEventCards": fallback_cards,
        "fallbackEventPages": fallback_event_pages,
        "retiredEventPages": retired_event_pages,
        "retiredArtistLinks": retired_artist_links,
        "staleRuntimeScriptRefs": stale_runtime_script_refs,
        "unlockedPrimaryImages": unlocked_primary_images,
    }


def apply(root: pathlib.Path) -> None:
    if not root.is_dir():
        raise SystemExit(f"Missing site artifact: {root}")
    removed_primary, repaired_primary, retired_primary = patch_event_json(root / "events.json")
    removed_supp, repaired_supp, retired_supp = patch_event_json(root / "supplemental-events.json")
    removed_slugs = remove_excluded_event_pages(root)
    removed_cards = repaired_html = 0
    for page in root.rglob("*.html"):
        r, p = patch_html_page(page, removed_slugs)
        removed_cards += r
        repaired_html += p
    clean_sitemap(root, removed_slugs)
    audit = verify(root)
    print(
        "Live event image finalizer verified:",
        json.dumps({
            **audit,
            "removedJsonEvents": removed_primary + removed_supp,
            "retiredLineupNamesRemoved": retired_primary + retired_supp,
            "removedEventPages": len(removed_slugs),
            "removedEventCards": removed_cards,
            "repairedJsonImages": repaired_primary + repaired_supp,
            "repairedHtmlImages": repaired_html,
        }, sort_keys=True),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default="_site")
    args = parser.parse_args()
    apply(pathlib.Path(args.site).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
