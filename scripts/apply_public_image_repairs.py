#!/usr/bin/env python3
"""Apply narrowly scoped image-presentation repairs to a production artifact.

The production artifact is already sanitized before this stage.  This module
only adds the truthful responsive-size contract used by event cards and the
two approved focal-point corrections.  It never reads repository source data,
adds provenance fields, or expands the set of JSON files published to Pages.
"""

from __future__ import annotations

import argparse
import dataclasses
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from typing import Iterable, Optional, Sequence
from urllib.parse import urlsplit, urlunsplit


PUBLIC_BASE = "/"
CARD_SIZES = (
    "(max-width: 600px) calc(100vw - 32px), "
    "(max-width: 900px) calc(100vw - 48px), "
    "(max-width: 1180px) 40vw, 453px"
)
CJ_EMULOUS_SOURCE = (
    "https://ugc.production.linktr.ee/"
    "e2e0b25c-780f-4b6f-9a4d-48461885e719_DSC01908.jpeg"
)

# These are the only sanitized JSON files retained in the production artifact.
# Deliberately do not add source-only files such as config/manual-events.json.
PUBLIC_JSON_FILES = (
    "events.json",
    "supplemental-events.json",
    "config/artists.json",
)
IMAGE_JSON_KEYS = {
    "image",
    "imageurl",
    "image_url",
    "artwork",
    "artworkurl",
    "thumbnail",
    "thumbnailurl",
}
VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


@dataclasses.dataclass(frozen=True)
class FocalRule:
    marker: str
    position: str


CJ_RULE = FocalRule("cj-emulous", "center top")
HULVEY_RULE = FocalRule("hulvey", "50% 30%")
FOCAL_RULES = {
    CJ_RULE.marker: CJ_RULE,
    HULVEY_RULE.marker: HULVEY_RULE,
}


@dataclasses.dataclass
class ImageOccurrence:
    start: int
    end: int
    attrs: list[tuple[str, Optional[str]]]
    context_classes: frozenset[str]

    @property
    def attr_map(self) -> dict[str, Optional[str]]:
        return {key.lower(): value for key, value in self.attrs}


class SiteImageParser(HTMLParser):
    """Collect exact image offsets without reserializing complete pages."""

    def __init__(self, text: str):
        super().__init__(convert_charrefs=True)
        self.line_starts = [0]
        self.line_starts.extend(match.end() for match in re.finditer(r"\n", text))
        self.stack: list[tuple[str, frozenset[str]]] = []
        self.images: list[ImageOccurrence] = []

    @staticmethod
    def _classes(attrs: Iterable[tuple[str, Optional[str]]]) -> frozenset[str]:
        for key, value in attrs:
            if key.lower() == "class":
                return frozenset(str(value or "").split())
        return frozenset()

    def _offset(self) -> int:
        line, column = self.getpos()
        return self.line_starts[line - 1] + column

    def _record(
        self,
        tag: str,
        attrs: list[tuple[str, Optional[str]]],
        push: bool,
    ) -> None:
        lowered = tag.lower()
        if lowered == "img":
            raw = self.get_starttag_text() or ""
            context: set[str] = set()
            for _, classes in self.stack:
                context.update(classes)
            start = self._offset()
            self.images.append(
                ImageOccurrence(start, start + len(raw), list(attrs), frozenset(context))
            )
        elif push and lowered not in VOID_ELEMENTS:
            self.stack.append((lowered, self._classes(attrs)))

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, Optional[str]]],
    ) -> None:
        self._record(tag, attrs, True)

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, Optional[str]]],
    ) -> None:
        self._record(tag, attrs, False)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == lowered:
                del self.stack[index:]
                return


def normalized_remote_url(value: str) -> str:
    raw = html.unescape(str(value or "").strip())
    parsed = urlsplit(raw)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return raw
    try:
        port = f":{parsed.port}" if parsed.port else ""
    except ValueError:
        return raw
    return urlunsplit(
        (
            parsed.scheme.lower(),
            (parsed.hostname or "").lower() + port,
            parsed.path,
            parsed.query,
            "",
        )
    )


def focal_rule_for_source(value: str) -> Optional[FocalRule]:
    source = normalized_remote_url(value)
    if source == CJ_EMULOUS_SOURCE:
        return CJ_RULE
    parsed = urlsplit(source)
    lowered_path = parsed.path.casefold()
    if (
        (parsed.hostname or "").casefold() == "s1.ticketm.net"
        and "a49ecab3" in lowered_path
        and "_source" in lowered_path
    ):
        return HULVEY_RULE
    return None


def render_tag(
    attrs: list[tuple[str, Optional[str]]],
    updates: dict[str, Optional[str]],
) -> str:
    order: list[str] = []
    values: dict[str, Optional[str]] = {}
    for key, value in attrs:
        lowered = key.lower()
        if lowered not in values:
            order.append(lowered)
        values[lowered] = value
    for key, value in updates.items():
        lowered = key.lower()
        if value is None:
            values.pop(lowered, None)
            if lowered in order:
                order.remove(lowered)
        else:
            if lowered not in values:
                order.append(lowered)
            values[lowered] = value
    rendered = ["<img"]
    for key in order:
        if key not in values:
            continue
        value = values[key]
        if value is None:
            rendered.append(f" {key}")
        else:
            rendered.append(f' {key}="{html.escape(str(value), quote=True)}"')
    rendered.append(">")
    return "".join(rendered)


def artist_class(value: Optional[str]) -> str:
    classes = [
        item
        for item in str(value or "").split()
        if item not in {"artist-photo", "event-artwork"}
    ]
    classes.append("artist-photo")
    return " ".join(classes)


def style_with_position(value: Optional[str], position: str) -> str:
    declarations = []
    for item in str(value or "").split(";"):
        item = item.strip()
        if not item or item.split(":", 1)[0].strip().casefold() == "object-position":
            continue
        declarations.append(item)
    declarations.append(f"object-position:{position}")
    return ";".join(declarations)


def focal_rule_for_image(attrs: dict[str, Optional[str]]) -> Optional[FocalRule]:
    rule = focal_rule_for_source(str(attrs.get("src") or ""))
    if rule is not None:
        return rule
    return FOCAL_RULES.get(str(attrs.get("data-kc-image-focal") or ""))


def patch_html(text: str, *, focal_only: bool = False) -> tuple[str, int, int]:
    parser = SiteImageParser(text)
    parser.feed(text)
    replacements: list[tuple[int, int, str]] = []
    card_images = 0
    focal_images = 0
    for occurrence in parser.images:
        attrs = occurrence.attr_map
        updates: dict[str, Optional[str]] = {}
        if not focal_only and "event-media" in occurrence.context_classes:
            updates["sizes"] = CARD_SIZES
            card_images += 1
        rule = focal_rule_for_image(attrs)
        if rule is not None:
            updates.update(
                {
                    "class": artist_class(attrs.get("class")),
                    "style": style_with_position(attrs.get("style"), rule.position),
                    "data-kc-image-focal": rule.marker,
                }
            )
            focal_images += 1
        if updates:
            replacements.append(
                (occurrence.start, occurrence.end, render_tag(occurrence.attrs, updates))
            )
    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text, card_images, focal_images


def patch_json(value: object, counts: dict[str, int]) -> None:
    if isinstance(value, dict):
        matched: Optional[FocalRule] = None
        for key, child in value.items():
            if key.casefold() in IMAGE_JSON_KEYS and isinstance(child, str):
                rule = focal_rule_for_source(child)
                if rule is not None:
                    matched = rule
                    break
        if matched is not None:
            value["imageType"] = "artist"
            value["imagePosition"] = matched.position
            counts[matched.marker] = counts.get(matched.marker, 0) + 1
        for child in value.values():
            patch_json(child, counts)
    elif isinstance(value, list):
        for child in value:
            patch_json(child, counts)


def validate_target(site: Path) -> None:
    if not site.is_dir() or not (site / "index.html").is_file():
        raise SystemExit(f"Not a completed production artifact: {site}")
    if (site / ".git").exists():
        raise SystemExit(
            "Refusing to modify a Git worktree. Pass a generated artifact such as _site."
        )
    try:
        Path(__file__).resolve().relative_to(site.resolve())
    except ValueError:
        return
    raise SystemExit("Refusing to modify the directory containing this repair script.")


def apply(site: Path, *, focal_only: bool = False) -> dict[str, object]:
    validate_target(site)

    html_pages = 0
    changed_pages = 0
    card_images = 0
    focal_images = 0
    for path in sorted(site.rglob("*.html")):
        original = path.read_text(encoding="utf-8")
        updated, page_cards, page_focals = patch_html(
            original,
            focal_only=focal_only,
        )
        html_pages += 1
        card_images += page_cards
        focal_images += page_focals
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed_pages += 1

    json_counts: dict[str, int] = {}
    json_files = 0
    changed_json_files = 0
    for relative in PUBLIC_JSON_FILES:
        path = site / relative
        if not path.is_file():
            continue
        try:
            original = path.read_text(encoding="utf-8")
            value = json.loads(original)
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"Invalid public JSON: {relative}: {exc}") from exc
        patch_json(value, json_counts)
        updated = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed_json_files += 1
        json_files += 1

    return {
        "scope": "production-focal-preparation" if focal_only else "production-image-repairs",
        "htmlPages": html_pages,
        "htmlPagesChanged": changed_pages,
        "eventCardImagesSized": card_images,
        "focalHtmlImagesNormalized": focal_images,
        "jsonFilesChecked": json_files,
        "jsonFilesChanged": changed_json_files,
        "focalJsonRecordsNormalized": dict(sorted(json_counts.items())),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path, help="completed production artifact")
    parser.add_argument(
        "--focal-only",
        action="store_true",
        help="prepare focal metadata before optimization without rewriting card sizes",
    )
    args = parser.parse_args(argv)
    report = apply(args.site.expanduser().resolve(), focal_only=args.focal_only)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
