from __future__ import annotations

import html
import json
import pathlib
import re
import sys


PUBLIC_BASE = "/"
CSS_NAME = "site-ux-repairs.css"
JS_NAME = "site-ux-repairs.js"
CSS_HREF = f"{PUBLIC_BASE}assets/{CSS_NAME}?v=7"
JS_SRC = f"{PUBLIC_BASE}assets/{JS_NAME}?v=6"


def plain_text(fragment: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(fragment))).strip()


def attr_value(tag: str, name: str) -> str:
    match = re.search(rf"\b{re.escape(name)}\s*=\s*([\"'])(.*?)\1", tag, re.I | re.S)
    return html.unescape(match.group(2)).strip() if match else ""


def has_attr(tag: str, name: str) -> bool:
    return bool(re.search(rf"\s{re.escape(name)}(?:\s|=|/?>)", tag, re.I))


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip().casefold()


def opening_anchor(block: str, pattern: str) -> str:
    match = re.search(pattern, block, re.I | re.S)
    return match.group(0) if match else ""


def verify_card_links(path: pathlib.Path, text: str, failures: list[str], totals: dict[str, int]) -> None:
    event_cards = re.findall(
        r'<article\b(?=[^>]*\bdata-event-card\b)[^>]*>.*?</article>', text, re.I | re.S
    )
    artist_cards = re.findall(
        r'<article\b(?=[^>]*\bdata-artist-card\b)[^>]*>.*?</article>', text, re.I | re.S
    )
    totals["eventCards"] += len(event_cards)
    totals["artistCards"] += len(artist_cards)

    for index, card in enumerate(event_cards):
        title_match = re.search(r"<h3\b[^>]*>(.*?)</h3>", card, re.I | re.S)
        title = plain_text(title_match.group(1)) if title_match else ""
        heading = opening_anchor(card, r"<h3\b[^>]*>\s*<a\b[^>]*>")
        media = opening_anchor(
            card,
            r'<a\b(?=[^>]*\bclass\s*=\s*["\'][^"\']*\bevent-media\b)[^>]*>',
        )
        if heading and media and attr_value(heading, "href") == attr_value(media, "href"):
            if attr_value(media, "tabindex") != "-1" or attr_value(media, "aria-hidden") != "true":
                failures.append(f"duplicate-event-link-focusable:{path}:{index}")
        for anchor in re.findall(r"<a\b[^>]*>.*?</a>", card, re.I | re.S):
            opening = anchor.split(">", 1)[0] + ">"
            inner = anchor[len(opening):-4]
            if normalized(plain_text(inner)) != "official details":
                continue
            label = attr_value(opening, "aria-label")
            if not title or normalized(title) not in normalized(label):
                failures.append(f"official-link-not-contextual:{path}:{index}")

    for index, card in enumerate(artist_cards):
        heading_match = re.search(r"<h2\b[^>]*>(.*?)</h2>", card, re.I | re.S)
        artist = plain_text(heading_match.group(1)) if heading_match else ""
        heading = opening_anchor(card, r"<h2\b[^>]*>\s*<a\b[^>]*>")
        media = opening_anchor(
            card,
            r'<a\b(?=[^>]*\bclass\s*=\s*["\'][^"\']*\bartist-visual\b)[^>]*>',
        )
        if heading and media and attr_value(heading, "href") == attr_value(media, "href"):
            if attr_value(media, "tabindex") != "-1" or attr_value(media, "aria-hidden") != "true":
                failures.append(f"duplicate-artist-link-focusable:{path}:{index}")
        social_pattern = re.compile(
            r'<a\b(?=[^>]*(?:class\s*=\s*["\'][^"\']*\bseo-social-link\b|\bdata-artist-social\b))[^>]*>',
            re.I,
        )
        for social in social_pattern.findall(card):
            if not artist or normalized(artist) not in normalized(attr_value(social, "aria-label")):
                failures.append(f"artist-social-not-contextual:{path}:{index}")


def verify_directory(out_dir: pathlib.Path, failures: list[str], totals: dict[str, int]) -> None:
    page = out_dir / "artists" / "index.html"
    if not page.is_file():
        failures.append("missing:artists/index.html")
        return
    text = page.read_text(encoding="utf-8")
    if "artist-filter-fix.js" not in text:
        failures.append("artist-directory-controller-missing")
    for control in (
        "data-directory-artist-filter",
        "data-directory-state-filter",
        "data-directory-month-filter",
        "data-has-shows-filter",
        "data-directory-reset-filters",
    ):
        if control not in text:
            failures.append(f"artist-directory-control-missing:{control}")
    checkbox = re.search(r'<input\b(?=[^>]*\bdata-has-shows-filter\b)[^>]*>', text, re.I)
    if not checkbox or not has_attr(checkbox.group(0), "checked"):
        failures.append("artist-upcoming-filter-not-defaulted")

    cards = re.findall(r'<article\b(?=[^>]*\bdata-artist-card\b)[^>]*>', text, re.I)
    active = sum(attr_value(card, "data-has-shows").casefold() == "true" for card in cards)
    inactive = [card for card in cards if attr_value(card, "data-has-shows").casefold() != "true"]
    totals["directoryArtists"] = len(cards)
    totals["directoryActiveArtists"] = active
    if not cards or not active:
        failures.append("artist-directory-empty")
    if not inactive:
        failures.append("artist-directory-complete-roster-missing")
    if "data-kc-inactive-artists" in text:
        failures.append("artist-directory-cards-still-deferred")


def verify_submission(out_dir: pathlib.Path, failures: list[str]) -> None:
    page = out_dir / "submit" / "index.html"
    if not page.is_file():
        failures.append("missing:submit/index.html")
        return
    text = page.read_text(encoding="utf-8")
    expected = {
        "submitter_name": "name",
        "email": "email",
        "venue": "organization",
        "city": "address-level2",
        "state": "address-level1",
    }
    for name, autocomplete in expected.items():
        tag = re.search(rf'<(?:input|textarea)\b(?=[^>]*\bname=["\']{re.escape(name)}["\'])[^>]*>', text, re.I)
        if not tag or attr_value(tag.group(0), "autocomplete") != autocomplete:
            failures.append(f"submission-autocomplete:{name}")
    if 'name="_gotcha"' not in text or "data-kc-honeypot" not in text:
        failures.append("submission-honeypot-missing")
    if 'id="kc-form-privacy"' not in text or "sensitive personal information" not in text:
        failures.append("submission-privacy-copy-missing")
    form = re.search(r'<form\b(?=[^>]*\bdata-submission-form\b)[^>]*>', text, re.I)
    if not form or "kc-form-privacy" not in attr_value(form.group(0), "aria-describedby"):
        failures.append("submission-privacy-not-associated")
    if form and has_attr(form.group(0), "novalidate"):
        failures.append("submission-native-validation-disabled")


def verify_assets(out_dir: pathlib.Path, failures: list[str]) -> None:
    css_path = out_dir / "assets" / CSS_NAME
    js_path = out_dir / "assets" / JS_NAME
    if not css_path.is_file():
        failures.append(f"missing:assets/{CSS_NAME}")
        return
    if not js_path.is_file():
        failures.append(f"missing:assets/{JS_NAME}")
        return
    css = css_path.read_text(encoding="utf-8")
    js = js_path.read_text(encoding="utf-8")
    css_checks = {
        "hidden-state": "body [hidden] { display: none !important; }",
        "skip-css": ".kc-skip-link",
        "dynamic-viewport": "100dvh",
        "drawer-scroll": "overflow-y: auto",
        "reduced-motion": "prefers-reduced-motion: reduce",
        "contrast": "#b8b4ac",
        "touch-size": "min-height: 44px",
        "two-column-mobile-artists": "grid-template-columns: repeat(2, minmax(0, 1fr)) !important;",
        "uniform-mobile-rows": "grid-auto-rows: 1fr !important;",
        "square-mobile-portraits": "aspect-ratio: 1 / 1 !important;",
        "anchored-mobile-card-footer": "margin-top: auto !important;",
        "wrapped-mobile-card-copy": "overflow-wrap: anywhere !important;",
        "single-row-mobile-socials": "body [data-artist-directory] .artist-card-links,\n  body [data-artist-directory] .seo-card-socials {\n    display: flex !important;\n    flex-wrap: nowrap !important;",
        "even-mobile-socials": "flex: 1 1 36px !important;",
    }
    js_checks = {
        "modal-role": 'setAttribute("role", "dialog")',
        "modal-aria": 'setAttribute("aria-modal", "true")',
        "background-inert": "makeBackgroundInert",
        "focus-containment": 'event.key !== "Tab"',
        "focus-restore": "returnFocus",
        "artist-controller-preserved": 'if (one("[data-directory-artist-filter]", directory)) return;',
        "correction-button": "setupCorrectionMode",
        "correction-hidden-fields-disabled": "field.disabled = correction",
        "correction-link-copy": "Include a supporting link.",
        "dynamic-link-repair": "enhanceCards",
    }
    for name, needle in css_checks.items():
        if needle not in css:
            failures.append(f"overlay-css:{name}")
    for name, needle in js_checks.items():
        if needle not in js:
            failures.append(f"overlay-js:{name}")
    if re.search(r"supporting source|the source", js, re.I):
        failures.append("overlay-js:source-copy-remains")
    if re.search(r"\bfetch\s*\(", js):
        failures.append("overlay-performs-json-fetch")


def verify(out_dir: pathlib.Path) -> tuple[list[str], dict[str, int]]:
    failures: list[str] = []
    totals = {
        "htmlPages": 0,
        "eventCards": 0,
        "artistCards": 0,
        "directoryArtists": 0,
        "directoryActiveArtists": 0,
    }
    pages = list(out_dir.rglob("*.html"))
    totals["htmlPages"] = len(pages)
    if not pages:
        failures.append("no-html-pages")
    for page in pages:
        text = page.read_text(encoding="utf-8")
        if not re.search(r"<main\b", text, re.I):
            continue
        relative = page.relative_to(out_dir).as_posix()
        if not re.search(r'<a\b[^>]*class=["\'][^"\']*\bkc-skip-link\b[^"\']*["\'][^>]*href=["\']#kc-main-content["\']', text, re.I):
            failures.append(f"skip-link:{relative}")
        main = re.search(r"<main\b[^>]*>", text, re.I)
        if not main or attr_value(main.group(0), "id") != "kc-main-content":
            failures.append(f"main-target:{relative}")
        if CSS_HREF not in text or JS_SRC not in text:
            failures.append(f"overlay-production-path:{relative}")
        if "kingdom-circuit-test" in text:
            failures.append(f"test-path-on-production:{relative}")
        verify_card_links(page.relative_to(out_dir), text, failures, totals)
        for anchor in re.findall(r"<a\b[^>]*>.*?</a>", text, re.I | re.S):
            opening = anchor.split(">", 1)[0] + ">"
            inner = anchor[len(opening):-4]
            if normalized(plain_text(inner)) == "official details" and " for " not in attr_value(opening, "aria-label"):
                failures.append(f"official-link-generic:{relative}")
            if re.search(r'\bclass=["\'][^"\']*\bseo-social-link\b', opening, re.I):
                if " for " not in attr_value(opening, "aria-label"):
                    failures.append(f"artist-social-generic:{relative}")

    verify_directory(out_dir, failures, totals)
    verify_submission(out_dir, failures)
    verify_assets(out_dir, failures)
    return failures, totals


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_public_ux.py SITE_OUTPUT")
    out_dir = pathlib.Path(sys.argv[1]).resolve()
    if not out_dir.is_dir():
        raise SystemExit(f"Missing site output: {out_dir}")
    failures, totals = verify(out_dir)
    if failures:
        raise SystemExit(json.dumps({"publicUxVerification": "failed", "failures": failures[:200]}, indent=2))
    print(json.dumps({"publicUxVerification": "passed", **totals}, indent=2))


if __name__ == "__main__":
    main()
