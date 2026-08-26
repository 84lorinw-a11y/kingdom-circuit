#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import pathlib
import re
import shutil

FALLBACK = "/assets/event-fallback.webp"
EXCLUDED_ARTISTS = {"chad jones", "erica mason", "big holy"}

# Verified/known-good presentation images used only when an event otherwise has
# generic artwork. Real event artwork is always preserved.
IMAGE_CANDIDATES = {
    "808 beezy": [
        "https://pbs.twimg.com/profile_images/1836827722309312512/e5kgorwv.jpg",
        "https://open.voidware.de/artist/3CltJZLndpJKtpUyRVBB1k",
    ],
    "hulvey": [
        "https://s1.ticketm.net/dam/a/d4e/a49ecab3-089d-46ff-baa5-7942c994ed4e_SOURCE",
        "https://open.voidware.de/artist/3zSrc5vUlUxyDdS0KrxFJO",
    ],
    "yumiya!": [
        "https://i.scdn.co/image/ab6761610000e5ebe8717d1df4abebcd56989c30",
        "https://open.voidware.de/artist/1s4YH0vODE4nW0bREPt4GG",
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
    "mike teezy": [
        "https://real.fm/assets/Uploads/MikeTeezy__FocusFillWyItMC4xMSIsIi0wLjE2IiwxMjAwLDYyN10.jpg",
        "https://open.voidware.de/artist/6tO2zQcTIRfR2Xdsm9XnL7",
    ],
}


def norm(value: object) -> str:
    value = html.unescape(str(value or "")).casefold()
    value = value.replace("’", "'")
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


def excluded_event(event: dict) -> bool:
    names = [event.get("headliner")] + list(event.get("artists") or [])
    return any(norm(name) in EXCLUDED_ARTISTS for name in names if name)


def artist_key_from_names(names: list[str]) -> str | None:
    normalized = [norm(name) for name in names if name]
    for name in normalized:
        if name in IMAGE_CANDIDATES:
            return name
    combined = " | ".join(normalized)
    for key in IMAGE_CANDIDATES:
        if key in combined:
            return key
    return None


def needs_repair(value: object) -> bool:
    image = norm(value)
    return (not image) or ("event-fallback.webp" in image) or ("open.voidware.de/artist/" in image)


def patch_event_json(path: pathlib.Path) -> tuple[int, int]:
    events = load_json(path)
    if not events:
        return 0, 0
    cleaned = []
    removed = repaired = 0
    for event in events:
        if not isinstance(event, dict):
            continue
        if excluded_event(event):
            removed += 1
            continue
        key = artist_key_from_names([event.get("headliner") or ""] + list(event.get("artists") or []))
        if key and needs_repair(event.get("image")):
            event["image"] = IMAGE_CANDIDATES[key][0]
            repaired += 1
        cleaned.append(event)
    write_json(path, cleaned)
    return removed, repaired


def event_page_should_be_removed(text: str) -> bool:
    lowered = norm(strip_tags(text))
    return any(name in lowered for name in EXCLUDED_ARTISTS)


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


def key_from_html(block: str) -> str | None:
    key = artist_key_from_names(names_from_block(block))
    if key:
        return key
    text = norm(strip_tags(block))
    for candidate in IMAGE_CANDIDATES:
        if candidate in text:
            return candidate
    return None


def set_img_src(tag: str, src: str, key: str) -> str:
    escaped = html.escape(src, quote=True)
    if re.search(r'\bsrc=["\'][^"\']*["\']', tag, flags=re.I):
        tag = re.sub(r'\bsrc=(["\'])[^"\']*\1', lambda m: f'src={m.group(1)}{escaped}{m.group(1)}', tag, count=1, flags=re.I)
    else:
        tag = tag[:-1] + f' src="{escaped}">'
    tag = re.sub(r'\s+onerror=(["\']).*?\1', "", tag, flags=re.I | re.S)
    tag = re.sub(r'\s+data-kc-event-artist=(["\']).*?\1', "", tag, flags=re.I | re.S)
    tag = re.sub(r'\s+data-kc-image-index=(["\']).*?\1', "", tag, flags=re.I | re.S)
    return tag[:-1] + (
        f' data-kc-event-artist="{html.escape(key, quote=True)}" data-kc-image-index="0" '
        f'onerror="window.kcEventImageFallback ? window.kcEventImageFallback(this) : '
        f'(this.onerror=null,this.src=\'{FALLBACK}\');">'
    )


def repair_fallbacks_in_block(block: str) -> tuple[str, bool]:
    if "event-fallback.webp" not in norm(block):
        return block, False
    key = key_from_html(block)
    if not key:
        return block, False
    changed = False

    def repl(match: re.Match[str]) -> str:
        nonlocal changed
        tag = match.group(0)
        src_match = re.search(r'\bsrc=["\']([^"\']*)["\']', tag, flags=re.I)
        if not src_match or "event-fallback.webp" not in norm(src_match.group(1)):
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
        if any(name in norm(strip_tags(block)) for name in EXCLUDED_ARTISTS):
            removed_cards += 1
            return ""
        updated, changed = repair_fallbacks_in_block(block)
        repaired += int(changed)
        return updated

    text = CARD_RE.sub(card_repl, text)

    if "/event/" in "/" + str(page).replace("\\", "/") + "/" and "event-fallback.webp" in norm(text):
        key = key_from_html(text)
        if key:
            def detail_repl(match: re.Match[str]) -> str:
                nonlocal repaired
                tag = match.group(0)
                src_match = re.search(r'\bsrc=["\']([^"\']*)["\']', tag, flags=re.I)
                if not src_match or "event-fallback.webp" not in norm(src_match.group(1)):
                    return tag
                repaired += 1
                return set_img_src(tag, IMAGE_CANDIDATES[key][0], key)
            text = re.sub(r'<img\b[^>]*>', detail_repl, text, flags=re.I)

    script_tag = '<script src="/assets/event-image-repair.js"></script>'
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
    fallback_event_pages = 0
    excluded_hits = 0
    for page in root.rglob("*.html"):
        text = page.read_text(encoding="utf-8", errors="ignore")
        for block in CARD_RE.findall(text):
            sources = re.findall(r'<img\b[^>]*?\ssrc=["\']([^"\']+)', block, flags=re.I)
            if any("event-fallback.webp" in norm(src) for src in sources):
                fallback_cards += 1
            if any(name in norm(strip_tags(block)) for name in EXCLUDED_ARTISTS):
                excluded_hits += 1
        if page.parent.parent == root / "event":
            sources = re.findall(r'<img\b[^>]*?\ssrc=["\']([^"\']+)', text, flags=re.I)
            if any("event-fallback.webp" in norm(src) for src in sources):
                fallback_event_pages += 1
            if event_page_should_be_removed(text):
                excluded_hits += 1
    if fallback_cards:
        failures.append(f"generic-event-cards:{fallback_cards}")
    if fallback_event_pages:
        failures.append(f"generic-event-pages:{fallback_event_pages}")
    if excluded_hits:
        failures.append(f"excluded-event-content:{excluded_hits}")
    if failures:
        raise SystemExit("Live event-image audit failed: " + ", ".join(failures))
    return {
        "fallbackEventCards": fallback_cards,
        "fallbackEventPages": fallback_event_pages,
        "excludedEventContent": excluded_hits,
    }


def apply(root: pathlib.Path) -> None:
    if not root.is_dir():
        raise SystemExit(f"Missing site artifact: {root}")
    removed_primary, repaired_primary = patch_event_json(root / "events.json")
    removed_supp, repaired_supp = patch_event_json(root / "supplemental-events.json")
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
