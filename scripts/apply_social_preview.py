#!/usr/bin/env python3
"""Install and verify the production site's default social-share card."""

from __future__ import annotations

import hashlib
import html
from pathlib import Path
import re
import shutil
import struct
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOCIAL_PREVIEW_REL = Path("assets/social-preview-wordmark-20260917.png")
SOCIAL_PREVIEW_URL = (
    "https://kingdomcircuit.com/assets/social-preview-wordmark-20260917.png"
)
SOCIAL_PREVIEW_ALT = "The Kingdom Circuit — Find Christian Hip-Hop Shows & Festivals"
SOCIAL_PREVIEW_SIZE = (1200, 630)
SOCIAL_PREVIEW_SHA256 = (
    "af873c5e21288dd2d74cac91fc8a7f52f569e315978de7fb1a64ab11783bc110"
)

GENERIC_SOCIAL_IMAGE_RE = re.compile(
    r"(?:^|/)assets/(?:(?:logo|logo-wordmark)\.(?:png|svg)|social-preview\.png)"
    r"(?:[?#]|$)",
    flags=re.I,
)


def get_attr(tag: str, name: str) -> str:
    match = re.search(
        rf"\b{re.escape(name)}\s*=\s*([\"'])(.*?)\1",
        tag,
        flags=re.I | re.S,
    )
    return html.unescape(match.group(2)) if match else ""


def set_attr(tag: str, name: str, value: str) -> str:
    encoded = html.escape(value, quote=True)
    pattern = re.compile(
        rf"\b{re.escape(name)}\s*=\s*([\"']).*?\1",
        flags=re.I | re.S,
    )
    if pattern.search(tag):
        return pattern.sub(f'{name}="{encoded}"', tag, count=1)
    return tag[:-1] + f' {name}="{encoded}">' if tag.endswith(">") else tag


def meta_content(text: str, key: str) -> str:
    pattern = re.compile(
        rf'<meta\b(?=[^>]*\b(?:name|property)=["\']{re.escape(key)}["\'])[^>]*>',
        flags=re.I,
    )
    match = pattern.search(text)
    return get_attr(match.group(0), "content") if match else ""


def set_meta(text: str, key: str, value: str) -> str:
    attr_name = "property" if key.startswith("og:") else "name"
    pattern = re.compile(
        rf'<meta\b(?=[^>]*\b(?:name|property)=["\']{re.escape(key)}["\'])[^>]*>',
        flags=re.I,
    )
    match = pattern.search(text)
    if match:
        replacement = set_attr(match.group(0), "content", value)
        replacement = re.sub(
            r'\b(?:name|property)\s*=\s*(["\']).*?\1',
            f'{attr_name}="{html.escape(key, quote=True)}"',
            replacement,
            count=1,
            flags=re.I | re.S,
        )
        return text[: match.start()] + replacement + text[match.end() :]

    tag = (
        f'<meta {attr_name}="{html.escape(key, quote=True)}" '
        f'content="{html.escape(value, quote=True)}">'
    )
    return re.sub(r"</head>", tag + "</head>", text, count=1, flags=re.I)


def uses_replaceable_default_social_image(text: str) -> bool:
    values = (meta_content(text, "og:image"), meta_content(text, "twitter:image"))
    replaceable = tuple(
        bool(value == SOCIAL_PREVIEW_URL or GENERIC_SOCIAL_IMAGE_RE.search(value))
        for value in values
    )
    has_specific_art = any(
        value and not is_replaceable
        for value, is_replaceable in zip(values, replaceable)
    )
    return any(replaceable) and not has_specific_art


def apply_to_html(text: str, relative: Path) -> tuple[str, bool]:
    if relative != Path("index.html") and not uses_replaceable_default_social_image(text):
        return text, False

    original = text
    for key, value in (
        ("og:image", SOCIAL_PREVIEW_URL),
        ("og:image:secure_url", SOCIAL_PREVIEW_URL),
        ("og:image:type", "image/png"),
        ("og:image:width", str(SOCIAL_PREVIEW_SIZE[0])),
        ("og:image:height", str(SOCIAL_PREVIEW_SIZE[1])),
        ("og:image:alt", SOCIAL_PREVIEW_ALT),
        ("twitter:card", "summary_large_image"),
        ("twitter:image", SOCIAL_PREVIEW_URL),
        ("twitter:image:alt", SOCIAL_PREVIEW_ALT),
    ):
        text = set_meta(text, key, value)
    return text, text != original


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError(f"Not a valid PNG: {path}")
    return struct.unpack(">II", data[16:24])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install_asset(site: Path) -> None:
    source = ROOT / SOCIAL_PREVIEW_REL
    if not source.is_file():
        raise RuntimeError(f"Missing production social-preview source: {source}")
    if png_dimensions(source) != SOCIAL_PREVIEW_SIZE:
        raise RuntimeError(
            f"Social preview must be {SOCIAL_PREVIEW_SIZE[0]}x{SOCIAL_PREVIEW_SIZE[1]}: {source}"
        )
    if sha256(source) != SOCIAL_PREVIEW_SHA256:
        raise RuntimeError(
            "Production social preview does not match the approved test asset: "
            f"{source}"
        )

    destination = site / SOCIAL_PREVIEW_REL
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)


def verify(site: Path) -> dict[str, int]:
    failures: list[str] = []
    asset = site / SOCIAL_PREVIEW_REL
    if not asset.is_file():
        failures.append("social-preview:missing")
    else:
        try:
            dimensions = png_dimensions(asset)
        except (OSError, ValueError) as exc:
            failures.append(f"social-preview:invalid:{exc}")
        else:
            if dimensions != SOCIAL_PREVIEW_SIZE:
                failures.append(
                    f"social-preview:dimensions:{dimensions[0]}x{dimensions[1]}"
                )
        if sha256(asset) != SOCIAL_PREVIEW_SHA256:
            failures.append("social-preview:not-approved-test-asset")

    html_pages = 0
    default_pages = 0
    for page in sorted(site.rglob("*.html")):
        html_pages += 1
        text = page.read_text(encoding="utf-8")
        relative = page.relative_to(site)
        for key in ("og:image", "twitter:image"):
            value = meta_content(text, key)
            if GENERIC_SOCIAL_IMAGE_RE.search(value):
                failures.append(f"social-preview:legacy-default:{relative}:{key}")

        if meta_content(text, "og:image") == SOCIAL_PREVIEW_URL:
            default_pages += 1
            expected = {
                "og:image:secure_url": SOCIAL_PREVIEW_URL,
                "og:image:type": "image/png",
                "og:image:width": str(SOCIAL_PREVIEW_SIZE[0]),
                "og:image:height": str(SOCIAL_PREVIEW_SIZE[1]),
                "og:image:alt": SOCIAL_PREVIEW_ALT,
                "twitter:card": "summary_large_image",
                "twitter:image": SOCIAL_PREVIEW_URL,
                "twitter:image:alt": SOCIAL_PREVIEW_ALT,
            }
            for key, wanted in expected.items():
                if meta_content(text, key) != wanted:
                    failures.append(f"social-preview:metadata:{relative}:{key}")

    homepage = site / "index.html"
    if not homepage.is_file():
        failures.append("social-preview:homepage-missing")
    else:
        text = homepage.read_text(encoding="utf-8")
        if meta_content(text, "og:image") != SOCIAL_PREVIEW_URL:
            failures.append("social-preview:homepage-og-image")
        if meta_content(text, "twitter:image") != SOCIAL_PREVIEW_URL:
            failures.append("social-preview:homepage-twitter-image")

    if failures:
        raise RuntimeError(
            f"Production social-preview verification failed ({len(failures)} failures): "
            + "; ".join(failures[:100])
        )
    return {"htmlPages": html_pages, "defaultPreviewPages": default_pages}


def apply(site: Path) -> dict[str, Any]:
    site = site.resolve()
    if not site.is_dir():
        raise RuntimeError(f"Missing production site artifact: {site}")
    install_asset(site)

    updated = 0
    for page in sorted(site.rglob("*.html")):
        text = page.read_text(encoding="utf-8")
        output, changed = apply_to_html(text, page.relative_to(site))
        if changed:
            page.write_text(output, encoding="utf-8")
            updated += 1

    totals = verify(site)
    return {
        "asset": SOCIAL_PREVIEW_REL.as_posix(),
        "assetSha256": SOCIAL_PREVIEW_SHA256,
        "pagesUpdated": updated,
        **totals,
    }
