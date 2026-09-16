#!/usr/bin/env python3
"""Keep the verified ECHO Nights 26 listing and supplied official ATK artwork durable."""

import argparse
import hashlib
import html
import json
import re
from pathlib import Path

EVENT_ID = "manual:ticketspice:echo-nights-26-brookfield-2026"
TITLE = "ECHO Nights 26"
IMAGE = "assets/events/echo-nights-26.jpg"
PUBLIC_IMAGE = "/" + IMAGE
ABSOLUTE_IMAGE = "https://kingdomcircuit.com/" + IMAGE
IMAGE_SHA256 = "39932408e919ac878f1be5c35205f563302aec26648a9570398d80b3ae66e2ab"
TICKET_URL = "https://atkministry.ticketspice.com/echo-nights-26"
SOURCE_FILES = ("events.json", "supplemental-events.json")
CARD_RE = re.compile(
    r'<article\b(?=[^>]*class=["\'][^"\']*\bevent-card\b[^"\']*["\'])[^>]*>.*?</article>',
    re.I | re.S,
)
IMG_RE = re.compile(r"<img\b[^>]*>", re.I | re.S)


def set_attr(tag: str, name: str, value: str) -> str:
    escaped = html.escape(value, quote=True)
    pattern = re.compile(rf"\b{re.escape(name)}=([\"']).*?\1", re.I | re.S)
    if pattern.search(tag):
        return pattern.sub(f'{name}="{escaped}"', tag, count=1)
    return tag[:-1] + f' {name}="{escaped}">'


def remove_attr(tag: str, name: str) -> str:
    return re.sub(rf"\s+{re.escape(name)}=([\"']).*?\1", "", tag, flags=re.I | re.S)


def pin_img(tag: str) -> str:
    tag = set_attr(tag, "src", PUBLIC_IMAGE)
    tag = remove_attr(tag, "srcset")
    tag = remove_attr(tag, "sizes")
    tag = set_attr(tag, "width", "640")
    tag = set_attr(tag, "height", "906")
    tag = set_attr(tag, "style", "object-position:center top")
    classes = re.search(r'\bclass=(["\'])([^"\']*)\1', tag, re.I)
    if classes:
        values = [part for part in classes.group(2).split() if part != "artist-photo"]
        if "event-artwork" not in values:
            values.append("event-artwork")
        tag = tag[:classes.start()] + f'class="{" ".join(values)}"' + tag[classes.end():]
    else:
        tag = tag[:-1] + ' class="event-artwork">'
    return tag


def patch_html(root: Path) -> int:
    changed_pages = 0
    verified_occurrences = 0
    event_detail_seen = False

    for page in root.rglob("*.html"):
        text = page.read_text(encoding="utf-8", errors="ignore")
        if TITLE not in html.unescape(text):
            continue
        original = text

        def card_repl(match: re.Match[str]) -> str:
            nonlocal verified_occurrences
            block = match.group(0)
            if TITLE not in html.unescape(block):
                return block
            updated, count = IMG_RE.subn(lambda image_match: pin_img(image_match.group(0)), block, count=1)
            verified_occurrences += int(bool(count))
            return updated

        text = CARD_RE.sub(card_repl, text)

        h1 = re.search(r"<h1\b[^>]*>(.*?)</h1>", text, re.I | re.S)
        detail_title = (
            re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(h1.group(1)))).strip()
            if h1 else ""
        )
        if detail_title == TITLE:
            media = re.search(
                r'(<div\b[^>]*class=["\'][^"\']*\bevent-detail-media\b[^"\']*["\'][^>]*>\s*)(<img\b[^>]*>)',
                text,
                re.I | re.S,
            )
            if not media:
                raise SystemExit(f"ECHO Nights event detail image missing: {page}")
            replacement = media.group(1) + pin_img(media.group(2))
            text = text[:media.start()] + replacement + text[media.end():]
            event_detail_seen = True
            verified_occurrences += 1

            # Keep structured event metadata on the same authoritative poster.
            script_re = re.compile(r'(<script[^>]+type=["\']application/ld\+json["\'][^>]*>)(.*?)(</script>)', re.I | re.S)
            def schema_repl(match: re.Match[str]) -> str:
                try:
                    payload = json.loads(match.group(2))
                except json.JSONDecodeError:
                    return match.group(0)
                if isinstance(payload, dict) and payload.get("name") == TITLE and payload.get("@type") in {"Event", "MusicEvent"}:
                    payload["image"] = [ABSOLUTE_IMAGE]
                    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
                    return match.group(1) + encoded + match.group(3)
                return match.group(0)
            text = script_re.sub(schema_repl, text)

        if text != original:
            page.write_text(text, encoding="utf-8")
            changed_pages += 1

    if root.name == "_site" or (root / "seo-build-manifest.json").exists():
        if verified_occurrences == 0:
            raise SystemExit("No ECHO Nights artwork occurrences were found in the deployment HTML")
        if not event_detail_seen:
            raise SystemExit("ECHO Nights event detail page was not found in the deployment artifact")

        stale = []
        for page in root.rglob("*.html"):
            text = page.read_text(encoding="utf-8", errors="ignore")
            if TITLE not in html.unescape(text):
                continue
            for block in CARD_RE.findall(text):
                if TITLE in html.unescape(block) and PUBLIC_IMAGE not in html.unescape(block):
                    stale.append(str(page.relative_to(root)))
            if page.parent.parent == root / "event" and re.search(rf"<h1\b[^>]*>\s*{re.escape(TITLE)}\s*</h1>", html.unescape(text), re.I):
                media = re.search(r'<div\b[^>]*class=["\'][^"\']*\bevent-detail-media\b[^"\']*["\'][^>]*>\s*(<img\b[^>]*>)', text, re.I | re.S)
                if not media or PUBLIC_IMAGE not in html.unescape(media.group(1)):
                    stale.append(str(page.relative_to(root)))
        if stale:
            raise SystemExit("ECHO Nights official artwork did not survive final HTML pin: " + ", ".join(stale[:12]))

    return changed_pages


def enforce_json(root: Path) -> int:
    repaired = 0
    found = 0
    for filename in SOURCE_FILES:
        path = root / filename
        if not path.is_file():
            continue
        events = json.loads(path.read_text(encoding="utf-8"))
        matches = [event for event in events if event.get("id") == EVENT_ID]
        if len(matches) > 1:
            raise SystemExit(f"{filename}: duplicate ECHO Nights 26 events found: {len(matches)}")
        if not matches:
            continue

        found += 1
        event = matches[0]
        event.update({
            "title": TITLE,
            "startDate": "2026-10-02",
            "startTime": "19:00",
            "timezone": "America/Chicago",
            "venue": "Elmbrook Church",
            "address": "777 S Barker Rd",
            "city": "Brookfield",
            "state": "WI",
            "country": "US",
            "artists": ["Kijan Boone", "Austin Joyce", "VVS Big Rock", "Kaymilinn", "DJ Bryce G"],
            "headliner": "Kijan Boone",
            "eventType": "concert",
            "status": "scheduled",
            "ticketUrl": TICKET_URL,
            "officialUrl": TICKET_URL,
            "image": IMAGE,
            "imageType": "event_artwork",
            "imagePosition": "center top",
            "imageOverride": True,
            "imageSource": "Official ATK Ministry ECHO Nights 26 collage artwork",
            "imageSourceUrl": TICKET_URL,
            "sourceName": "Official TicketSpice listing",
            "authority": "venue_ticket",
            "confidence": "high",
            "lineupExplicit": True,
            "notes": "Doors 6 PM; show 7 PM; all ages welcome. Official ATK Ministry collage artwork locked for this listing.",
        })
        path.write_text(json.dumps(events, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        repaired += 1
        print(f"ECHO Nights 26 repaired in {filename} with official artwork: {IMAGE}")

    if found == 0:
        raise SystemExit("ECHO Nights 26 event was not found in any source file")
    return repaired


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default=".", help="Repository/site root to repair")
    args = parser.parse_args()
    root = Path(args.site).resolve()
    image_path = root / IMAGE

    if not image_path.is_file():
        raise SystemExit(f"Verified ECHO Nights artwork is missing: {image_path}")
    digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
    if digest != IMAGE_SHA256:
        raise SystemExit(
            f"Verified ECHO Nights artwork hash mismatch: {image_path} "
            f"expected {IMAGE_SHA256}, got {digest}"
        )

    repaired = enforce_json(root)
    html_pages = patch_html(root)
    print(f"ECHO Nights 26 official guard passed: {repaired} JSON source file(s), {html_pages} HTML page(s) pinned.")


if __name__ == "__main__":
    main()
