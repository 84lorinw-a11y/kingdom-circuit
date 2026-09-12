#!/usr/bin/env python3
"""Pin verified event artwork across every generated Kingdom Circuit page.

This runs after the general image finalizer so purpose-built event artwork wins
over artist-photo fallbacks everywhere the event is rendered.
"""
from __future__ import annotations

import html
import json
import pathlib
import re

FALLBACK = "/assets/event-fallback.webp"
GUARD_SCRIPT = "/assets/verified-event-artwork-guard.js?v=20260911-1"

# title -> (date, image)
VERIFIED_ARTWORK: dict[str, tuple[str, str]] = {
    "The Genesis Show – All Women's CHH Event": (
        "2026-09-19",
        "assets/events/genesis-show-2026-all-women-v3.jpg",
    ),
    "Flavor Fest 2026 — Saturday Concerts": (
        "2026-11-07",
        "https://images.squarespace-cdn.com/content/v1/65b435646b1eae535f97c6a3/989d4d2e-f454-4a1b-99df-cc78cf6e6749/FF26-Promo-Saturday-Night.jpg",
    ),
    "Future Legacy Hip-Hop Showcase": (
        "2026-10-04",
        "https://images.discovery-prod.axs.com/2026/08/uploadedimage_6a871ac3abd11.jpg",
    ),
    "Miles Minnick & CJ Emulous at Zion Ultra Lounge": (
        "2026-12-05",
        "assets/events/miles-cj-zion-ultra-2026.svg",
    ),
    "Fountain Fest WV 2026": (
        "2026-09-18",
        "assets/events/fountain-fest-wv-2026.svg",
    ),
    "Mission and Special Guests": (
        "2026-10-17",
        "assets/events/mission-friends-sacramento-2026.svg",
    ),
    "Boxyard Saturdaze": (
        "2026-10-10",
        "assets/events/mayia-boxyard-saturdaze-2026.svg",
    ),
    "MAYIA at the NC State Fair": (
        "2026-10-17",
        "assets/events/mayia-nc-state-fair-2026.svg",
    ),
    "SYATP Concert": (
        "2026-09-23",
        "https://static.wixstatic.com/media/9c331a_e63115b208054353a76258a4897ad76c~mv2.jpeg/v1/fill/w_980%2Ch_653%2Cal_c%2Cq_85%2Cusm_0.66_1.00_0.01%2Cenc_auto/9c331a_e63115b208054353a76258a4897ad76c~mv2.jpeg",
    ),
    "Live Loud": (
        "2026-10-07",
        "https://static.wixstatic.com/media/9c331a_394502e64a45489e872ee2b71bb1a0de~mv2.jpg/v1/fill/w_980%2Ch_543%2Cal_c%2Cq_85%2Cusm_0.66_1.00_0.01%2Cenc_auto/9c331a_394502e64a45489e872ee2b71bb1a0de~mv2.jpg",
    ),
    "Teen Club Kickoff / Back to School Concert": (
        "2026-10-12",
        "https://static.wixstatic.com/media/9c331a_7832125534df4c06b583f033fe19273e~mv2.png",
    ),
    "The Kickback": (
        "2026-11-14",
        "assets/events/cj-emulous-kickback-2026.svg",
    ),
    "Alex Zurdo: Zona Zero": (
        "2026-10-18",
        "assets/events/alex-zurdo-zona-zero-2026.svg",
    ),
    "Jay Kalyl — Desde Antes Tour": (
        "2026-10-03",
        "assets/events/jay-kalyl-desde-antes-2026.svg",
    ),
}

CARD_RE = re.compile(
    r'<article\b(?=[^>]*class="[^"]*\bevent-card\b[^"]*")[^>]*>.*?</article>',
    flags=re.I | re.S,
)


def norm(value: object) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or "")).replace("’", "'")).strip().casefold()


def public_src(image: str) -> str:
    if image.startswith(("http://", "https://", "/")):
        return image
    return "/" + image.lstrip("/")


def title_from_block(block: str) -> str:
    match = re.search(r"<h3\b[^>]*>(.*?)</h3>", block, flags=re.I | re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(match.group(1)))).strip() if match else ""


def date_from_block(block: str) -> str:
    match = re.search(r'\bdata-date=["\']([^"\']+)["\']', block, flags=re.I)
    return match.group(1)[:10] if match else ""


def artwork_for(title: str, date: str = "") -> str | None:
    wanted = VERIFIED_ARTWORK.get(title)
    if not wanted:
        title_key = norm(title)
        wanted = next((value for name, value in VERIFIED_ARTWORK.items() if norm(name) == title_key), None)
    if not wanted:
        return None
    expected_date, image = wanted
    if date and date[:10] != expected_date:
        return None
    return image


def replace_img(tag: str, image: str) -> str:
    src = html.escape(public_src(image), quote=True)
    if re.search(r'\bsrc=["\'][^"\']*["\']', tag, flags=re.I):
        tag = re.sub(
            r'\bsrc=(["\'])[^"\']*\1',
            lambda m: f"src={m.group(1)}{src}{m.group(1)}",
            tag,
            count=1,
            flags=re.I,
        )
    else:
        tag = tag[:-1] + f' src="{src}">'

    class_match = re.search(r'\bclass=(["\'])([^"\']*)\1', tag, flags=re.I)
    if class_match:
        classes = [value for value in class_match.group(2).split() if value != "artist-photo"]
        if "event-artwork" not in classes:
            classes.append("event-artwork")
        class_value = " ".join(classes)
        tag = tag[:class_match.start()] + f'class="{class_value}"' + tag[class_match.end():]
    else:
        tag = tag[:-1] + ' class="event-artwork">'

    for attr in ("data-kc-event-artist", "data-kc-image-index", "data-kc-lock-primary", "data-kc-primary-locked"):
        tag = re.sub(rf'\s+{re.escape(attr)}=(["\']).*?\1', "", tag, flags=re.I | re.S)
    tag = re.sub(r'\s+onerror=(["\']).*?\1', "", tag, flags=re.I | re.S)
    return tag[:-1] + f' onerror="this.onerror=null;this.src=\'{FALLBACK}\';">'


def patch_card(block: str) -> tuple[str, bool]:
    title = title_from_block(block)
    image = artwork_for(title, date_from_block(block))
    if not image:
        return block, False
    updated, count = re.subn(
        r"<img\b[^>]*>",
        lambda match: replace_img(match.group(0), image),
        block,
        count=1,
        flags=re.I,
    )
    return updated, bool(count)


def patch_event_detail(text: str) -> tuple[str, bool]:
    h1 = re.search(r"<h1\b[^>]*>(.*?)</h1>", text, flags=re.I | re.S)
    if not h1:
        return text, False
    title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(h1.group(1)))).strip()
    image = artwork_for(title)
    if not image:
        return text, False

    media = re.search(
        r'(<div\b[^>]*class="[^"]*\bevent-detail-media\b[^"]*"[^>]*>\s*)(<img\b[^>]*>)',
        text,
        flags=re.I | re.S,
    )
    if not media:
        return text, False
    replacement = media.group(1) + replace_img(media.group(2), image)
    return text[: media.start()] + replacement + text[media.end() :], True


def inject_guard(text: str) -> str:
    if "verified-event-artwork-guard.js" in text:
        return text
    tag = f'<script src="{GUARD_SCRIPT}" defer></script>'
    return re.sub(r"</head>", tag + "</head>", text, count=1, flags=re.I)


def patch_json(path: pathlib.Path) -> int:
    if not path.is_file():
        return 0
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0
    if not isinstance(rows, list):
        return 0

    changed = 0
    for event in rows:
        if not isinstance(event, dict):
            continue
        title = str(event.get("title") or "")
        date = str(event.get("startDate") or "")[:10]
        image = artwork_for(title, date)
        if not image:
            continue
        desired = {
            "image": image,
            "imageType": "event_artwork",
            "imagePosition": "center",
            "imageOverride": True,
        }
        if any(event.get(key) != value for key, value in desired.items()):
            event.update(desired)
            changed += 1
    if changed:
        path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return changed


def verify_local_assets(root: pathlib.Path) -> None:
    missing = []
    for _title, (_date, image) in VERIFIED_ARTWORK.items():
        if image.startswith(("http://", "https://")):
            continue
        if not (root / image).is_file():
            missing.append(image)
    if missing:
        raise SystemExit(f"Missing verified event artwork assets: {sorted(set(missing))}")


def pin_site(root: pathlib.Path) -> dict[str, int]:
    root = root.resolve()
    verify_local_assets(root)

    json_updates = sum(
        patch_json(root / relative)
        for relative in ("events.json", "supplemental-events.json")
    )

    cards = details = pages = 0
    for page in root.rglob("*.html"):
        text = page.read_text(encoding="utf-8", errors="ignore")
        original = text

        def card_repl(match: re.Match[str]) -> str:
            nonlocal cards
            updated, changed = patch_card(match.group(0))
            cards += int(changed)
            return updated

        text = CARD_RE.sub(card_repl, text)
        if page.parent.parent == root / "event":
            text, changed = patch_event_detail(text)
            details += int(changed)

        text = inject_guard(text)
        if text != original:
            page.write_text(text, encoding="utf-8")
            pages += 1

    guard = root / "assets" / "verified-event-artwork-guard.js"
    if not guard.is_file():
        raise SystemExit("Verified event artwork guard is missing from deployment artifact")

    genesis_expected = public_src(VERIFIED_ARTWORK["The Genesis Show – All Women's CHH Event"][1])
    genesis_pages = 0
    genesis_wrong = []
    for page in root.rglob("*.html"):
        text = page.read_text(encoding="utf-8", errors="ignore")
        if "The Genesis Show" not in text:
            continue
        for block in CARD_RE.findall(text):
            if "The Genesis Show" not in block:
                continue
            genesis_pages += 1
            if genesis_expected not in html.unescape(block) or "event-artwork" not in block:
                genesis_wrong.append(str(page.relative_to(root)))
        if page.parent.parent == root / "event":
            h1 = re.search(r"<h1\b[^>]*>(.*?)</h1>", text, flags=re.I | re.S)
            detail_title = (
                re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(h1.group(1)))).strip()
                if h1
                else ""
            )
            if norm(detail_title) == norm("The Genesis Show – All Women's CHH Event"):
                genesis_pages += 1
                media = re.search(
                    r'<div\b[^>]*class="[^"]*\bevent-detail-media\b[^"]*"[^>]*>\s*(<img\b[^>]*>)',
                    text,
                    flags=re.I | re.S,
                )
                if not media or genesis_expected not in html.unescape(media.group(1)) or "event-artwork" not in media.group(1):
                    genesis_wrong.append(str(page.relative_to(root)))

    if genesis_pages == 0 or genesis_wrong:
        raise SystemExit(f"Genesis event artwork verification failed: pages={genesis_pages}, wrong={genesis_wrong[:8]}")

    return {
        "jsonRecordsPinned": json_updates,
        "eventCardsPinned": cards,
        "eventDetailsPinned": details,
        "htmlPagesTouched": pages,
        "genesisOccurrencesVerified": genesis_pages,
    }
