#!/usr/bin/env python3
"""Verify responsive image and loading-policy guarantees in a production artifact."""

from __future__ import annotations

import argparse
import dataclasses
from html.parser import HTMLParser
import html
import json
from pathlib import Path
import re
import sys
from typing import Iterable, Optional
import urllib.parse


DEFAULT_BASE = "/"
DEFAULT_ORIGIN = "https://kingdomcircuit.com"
PUBLIC_JSON_FILES = (
    "events.json",
    "supplemental-events.json",
    "artist-website-events.json",
    "config/artists.json",
    "config/manual-events.json",
)
IMAGE_JSON_KEYS = {
    "image", "imageurl", "image_url", "artwork", "artworkurl", "thumbnail", "thumbnailurl"
}
ELIGIBLE_IMAGE_CLASSES = {"event-artwork", "artist-photo"}
ELIGIBLE_CONTEXT_CLASSES = {
    "event-media", "event-detail-media", "seo-profile-image", "profile-visual", "artist-visual"
}
HERO_CONTEXT_CLASSES = {"event-detail-media", "seo-profile-image", "profile-visual"}
VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}
SAME_SITE_HOSTS = {
    "84lorinw-a11y.github.io", "kingdomcircuit.com", "www.kingdomcircuit.com"
}
OPTIMIZED_NAME = re.compile(r"^[0-9a-f]{24}-w([0-9]+)\.webp$")
SRCSET_ENTRY = re.compile(r"^(?P<url>\S+)\s+(?P<width>[1-9][0-9]*)w$")
OBSOLETE_IMAGE_REPAIR_ASSETS = {
    "verified-event-artwork-guard.js",
    "event-image-repair-kc2100.js",
}


@dataclasses.dataclass
class ImageNode:
    page: Path
    attrs: dict[str, Optional[str]]
    context_classes: frozenset[str]

    @property
    def source(self) -> str:
        return str(self.attrs.get("src") or "").strip()

    @property
    def classes(self) -> set[str]:
        return set(str(self.attrs.get("class") or "").split())

    @property
    def eligible(self) -> bool:
        return bool(
            self.source
            and (self.classes & ELIGIBLE_IMAGE_CLASSES or set(self.context_classes) & ELIGIBLE_CONTEXT_CLASSES)
        )

    @property
    def hero(self) -> bool:
        return bool(set(self.context_classes) & HERO_CONTEXT_CLASSES)


class ImageParser(HTMLParser):
    def __init__(self, page: Path):
        super().__init__(convert_charrefs=True)
        self.page = page
        self.stack: list[tuple[str, frozenset[str]]] = []
        self.images: list[ImageNode] = []
        self.metas: list[dict[str, Optional[str]]] = []
        self.script_sources: list[str] = []

    @staticmethod
    def _classes(attrs: Iterable[tuple[str, Optional[str]]]) -> frozenset[str]:
        for key, value in attrs:
            if key.lower() == "class":
                return frozenset(str(value or "").split())
        return frozenset()

    def _start(self, tag: str, attrs: list[tuple[str, Optional[str]]], push: bool) -> None:
        tag = tag.lower()
        if tag == "img":
            context: set[str] = set()
            for _, classes in self.stack:
                context.update(classes)
            self.images.append(
                ImageNode(
                    self.page,
                    {key.lower(): value for key, value in attrs},
                    frozenset(context),
                )
            )
        else:
            attr_map = {key.lower(): value for key, value in attrs}
            if tag == "meta":
                self.metas.append(attr_map)
            elif tag == "script" and attr_map.get("src"):
                self.script_sources.append(str(attr_map["src"]))
            if push and tag not in VOID_ELEMENTS:
                self.stack.append((tag, self._classes(attrs)))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        self._start(tag, attrs, True)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        self._start(tag, attrs, False)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                return


def normalize_base(value: str) -> str:
    value = "/" + value.strip("/") + "/"
    return "/" if value == "//" else value


def normalize_origin(value: str) -> str:
    parsed = urllib.parse.urlsplit(value.strip())
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError("origin must be an https URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("origin cannot contain credentials, a query, or a fragment")
    if parsed.path not in {"", "/"}:
        raise ValueError("origin cannot contain a path")
    port = f":{parsed.port}" if parsed.port else ""
    return f"https://{parsed.hostname.lower()}{port}"


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def local_path(site: Path, value: str, base: str) -> Optional[Path]:
    value = html.unescape(str(value or "").strip())
    if not value or value.startswith(("data:", "blob:")):
        return None
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme.lower() in {"http", "https"}:
        if (parsed.hostname or "").lower() not in SAME_SITE_HOSTS:
            return None
        raw_path = parsed.path
    elif parsed.scheme:
        return None
    else:
        raw_path = parsed.path
    decoded = urllib.parse.unquote(raw_path)
    if decoded.startswith(base):
        decoded = decoded[len(base):]
    else:
        decoded = decoded.lstrip("/")
    candidate = (site / decoded).resolve()
    return candidate if is_within(candidate, site) else None


def is_external(value: str) -> bool:
    parsed = urllib.parse.urlsplit(html.unescape(str(value or "").strip()))
    return parsed.scheme.lower() in {"http", "https"} and (parsed.hostname or "").lower() not in SAME_SITE_HOSTS


def is_preserved_vector(path: Path) -> bool:
    return path.suffix.casefold() == ".svg"


def webp_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("not a WebP file")
    offset = 12
    while offset + 8 <= len(data):
        fourcc = data[offset:offset + 4]
        size = int.from_bytes(data[offset + 4:offset + 8], "little")
        payload = data[offset + 8:offset + 8 + size]
        if fourcc == b"VP8X" and len(payload) >= 10:
            return (
                1 + int.from_bytes(payload[4:7], "little"),
                1 + int.from_bytes(payload[7:10], "little"),
            )
        if fourcc == b"VP8L" and len(payload) >= 5 and payload[0] == 0x2F:
            b1, b2, b3, b4 = payload[1:5]
            return (
                1 + b1 + ((b2 & 0x3F) << 8),
                1 + (b2 >> 6) + (b3 << 2) + ((b4 & 0x0F) << 10),
            )
        if fourcc == b"VP8 " and len(payload) >= 10:
            marker = payload.find(b"\x9d\x01\x2a")
            if marker >= 0 and marker + 7 <= len(payload):
                return (
                    int.from_bytes(payload[marker + 3:marker + 5], "little") & 0x3FFF,
                    int.from_bytes(payload[marker + 5:marker + 7], "little") & 0x3FFF,
                )
        offset += 8 + size + (size & 1)
    raise ValueError("WebP dimensions not found")


def parse_srcset(value: str) -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []
    for raw in value.split(","):
        match = SRCSET_ENTRY.fullmatch(raw.strip())
        if not match:
            raise ValueError(f"invalid srcset entry: {raw.strip()!r}")
        entries.append((match.group("url"), int(match.group("width"))))
    return entries


def iter_json_image_values(value):  # type: ignore[no-untyped-def]
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in IMAGE_JSON_KEYS and isinstance(child, str):
                yield child
            yield from iter_json_image_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_json_image_values(child)


def short(path: Path, site: Path) -> str:
    try:
        return path.relative_to(site).as_posix()
    except ValueError:
        return str(path)


def verify(
    site: Path,
    base: str,
    origin: str,
    require_remote: bool,
    min_optimized_source_percent: float,
    max_homepage_remotes: Optional[int],
    max_variant_bytes: int,
    max_total_optimized_bytes: int,
) -> tuple[list[str], list[str], dict[str, object]]:
    errors: list[str] = []
    warnings: list[str] = []
    images: list[ImageNode] = []
    page_image_meta: dict[Path, dict[str, str]] = {}
    obsolete_script_references: list[tuple[Path, str]] = []
    for page in sorted(site.rglob("*.html")):
        try:
            text = page.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{short(page, site)}: cannot read HTML ({exc.__class__.__name__})")
            continue
        parser = ImageParser(page)
        parser.feed(text)
        images.extend(parser.images)
        metadata: dict[str, str] = {}
        for attrs in parser.metas:
            identity = str(attrs.get("property") or attrs.get("name") or "").lower()
            if identity in {"og:image", "twitter:image"} and attrs.get("content"):
                metadata[identity] = str(attrs["content"])
        page_image_meta[page] = metadata
        for source in parser.script_sources:
            basename = Path(urllib.parse.urlsplit(source).path).name
            if basename in OBSOLETE_IMAGE_REPAIR_ASSETS:
                obsolete_script_references.append((page, source))

    if obsolete_script_references:
        sample_page, sample_source = obsolete_script_references[0]
        errors.append(
            f"{len(obsolete_script_references)} obsolete image-repair script reference(s) remain; "
            f"first: {short(sample_page, site)} -> {sample_source}"
        )

    optimized_count = 0
    hero_count = 0
    external_eligible = 0
    homepage_remote_sources: set[str] = set()
    preserved_remote_sources: dict[str, str] = {}
    preserved_vector_sources: set[Path] = set()
    optimized_hero_sources: dict[Path, str] = {}
    checked_local: set[Path] = set()
    for node in images:
        label = f"{short(node.page, site)}: {node.source[:100]}"
        source_path = local_path(site, node.source, base)
        if source_path is not None:
            checked_local.add(source_path)
            if not source_path.is_file():
                errors.append(f"{label}: broken local src")

        if not node.eligible:
            continue
        if node.hero:
            hero_count += 1
            if node.attrs.get("loading") != "eager":
                errors.append(f"{label}: hero must use loading=eager")
            if node.attrs.get("fetchpriority") != "high":
                errors.append(f"{label}: hero must use fetchpriority=high")
        elif node.attrs.get("loading") != "lazy":
            errors.append(f"{label}: below-fold image must use loading=lazy")

        if node.attrs.get("decoding") != "async":
            errors.append(f"{label}: eligible image must use decoding=async")
        try:
            width_attr = int(str(node.attrs.get("width") or "0"))
            height_attr = int(str(node.attrs.get("height") or "0"))
        except ValueError:
            width_attr = height_attr = 0
        if width_attr <= 0 or height_attr <= 0:
            errors.append(f"{label}: missing positive width/height")

        optimized = source_path is not None and source_path.parent.name == "optimized"
        if not optimized:
            if is_external(node.source):
                external_eligible += 1
                normalized_remote = html.unescape(node.source)
                preserved_remote_sources.setdefault(normalized_remote, label)
                if node.page == site / "index.html":
                    homepage_remote_sources.add(normalized_remote)
            elif source_path is not None:
                if is_preserved_vector(source_path):
                    preserved_vector_sources.add(source_path)
                else:
                    errors.append(f"{label}: eligible local raster image was not optimized")
            continue

        optimized_count += 1
        if node.hero:
            optimized_hero_sources.setdefault(node.page, node.source)
        match = OPTIMIZED_NAME.fullmatch(source_path.name)
        if not match:
            errors.append(f"{label}: optimized filename is not opaque/deterministic")
        if not node.attrs.get("sizes"):
            errors.append(f"{label}: optimized image is missing sizes")
        try:
            candidates = parse_srcset(str(node.attrs.get("srcset") or ""))
        except ValueError as exc:
            errors.append(f"{label}: {exc}")
            continue
        widths = [candidate_width for _, candidate_width in candidates]
        if len(candidates) < 2 or len(set(widths)) < 2:
            errors.append(f"{label}: srcset must contain at least two genuine widths")
        if widths != sorted(widths) or len(widths) != len(set(widths)):
            errors.append(f"{label}: srcset widths must be unique and ascending")
        dimensions_seen: set[tuple[int, int]] = set()
        for url, descriptor_width in candidates:
            candidate_path = local_path(site, url, base)
            if candidate_path is None or not candidate_path.is_file():
                errors.append(f"{label}: broken local srcset candidate {url}")
                continue
            checked_local.add(candidate_path)
            name_match = OPTIMIZED_NAME.fullmatch(candidate_path.name)
            if not name_match:
                errors.append(f"{label}: srcset candidate filename is not opaque")
            try:
                actual = webp_dimensions(candidate_path)
            except (OSError, ValueError) as exc:
                errors.append(f"{label}: invalid WebP candidate ({exc})")
                continue
            dimensions_seen.add(actual)
            if actual[0] != descriptor_width:
                errors.append(
                    f"{label}: {descriptor_width}w descriptor does not match {actual[0]}px file"
                )
            if name_match and int(name_match.group(1)) != descriptor_width:
                errors.append(f"{label}: filename width does not match its descriptor")
        if len(dimensions_seen) < 2:
            errors.append(f"{label}: srcset files do not have multiple intrinsic sizes")
        if source_path.is_file():
            try:
                source_dimensions = webp_dimensions(source_path)
                if source_dimensions != (width_attr, height_attr):
                    errors.append(
                        f"{label}: width/height attributes do not match the src file dimensions"
                    )
            except (OSError, ValueError) as exc:
                errors.append(f"{label}: invalid optimized src ({exc})")

    for page, source in sorted(optimized_hero_sources.items()):
        parsed_source = urllib.parse.urlsplit(source)
        source_path_value = parsed_source.path if parsed_source.scheme else source
        if not source_path_value.startswith("/"):
            source_path_value = base + source_path_value.lstrip("/")
        expected = origin + source_path_value
        metadata = page_image_meta.get(page, {})
        for identity in ("og:image", "twitter:image"):
            actual = metadata.get(identity)
            if actual != expected:
                errors.append(
                    f"{short(page, site)}: {identity} must match optimized hero URL {expected}"
                )

    for remote, label in sorted(preserved_remote_sources.items()):
        message = f"{label}: remote eligible image was preserved after optimization"
        (errors if require_remote else warnings).append(message)
    if homepage_remote_sources:
        homepage_message = (
            "index.html: preserved "
            f"{len(homepage_remote_sources)} unique remote image source(s)"
        )
        if (
            max_homepage_remotes is not None
            and len(homepage_remote_sources) > max_homepage_remotes
        ):
            errors.append(f"{homepage_message}; limit is {max_homepage_remotes}")
        else:
            warnings.append(homepage_message)

    json_local_refs = 0
    for relative in PUBLIC_JSON_FILES:
        path = site / relative
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{relative}: invalid public JSON ({exc.__class__.__name__})")
            continue
        for image_value in iter_json_image_values(value):
            candidate = local_path(site, image_value, base)
            if candidate is not None:
                json_local_refs += 1
                checked_local.add(candidate)
                if not candidate.is_file():
                    errors.append(f"{relative}: broken local JSON image reference {image_value}")
                elif is_preserved_vector(candidate):
                    preserved_vector_sources.add(candidate)
                elif candidate.parent.name != "optimized":
                    errors.append(
                        f"{relative}: eligible local raster JSON image was not optimized: "
                        f"{image_value}"
                    )

    manifest_path = site / "assets/optimized/manifest.json"
    optimized_source_percent = 0.0
    local_source_count = 0
    optimized_local_source_count = 0
    preserved_vector_source_count = 0
    if not manifest_path.is_file():
        errors.append("assets/optimized/manifest.json: optimizer manifest is missing")
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("scope") != "kingdom-circuit-production":
                errors.append("assets/optimized/manifest.json: unexpected scope")
            if int(manifest.get("uniqueOptimizedImageCount", 0)) < 1:
                errors.append("assets/optimized/manifest.json: no optimized images recorded")
            source_count = int(manifest.get("sourceCount", 0))
            optimized_source_count = int(manifest.get("optimizedSourceCount", 0))
            local_counts_present = {
                "localSourceCount",
                "optimizedLocalSourceCount",
                "preservedVectorSourceCount",
            }.issubset(manifest)
            if not local_counts_present:
                errors.append(
                    "assets/optimized/manifest.json: deterministic local source counts are missing"
                )
            else:
                local_source_count = int(manifest["localSourceCount"])
                optimized_local_source_count = int(manifest["optimizedLocalSourceCount"])
                preserved_vector_source_count = int(manifest["preservedVectorSourceCount"])
                if not (
                    0 <= optimized_local_source_count <= local_source_count <= source_count
                    and 0 <= preserved_vector_source_count <= source_count
                    and local_source_count + preserved_vector_source_count <= source_count
                    and optimized_local_source_count <= optimized_source_count
                    and 0 <= optimized_source_count <= source_count
                ):
                    errors.append(
                        "assets/optimized/manifest.json: local source counts are inconsistent"
                    )
                elif optimized_local_source_count != local_source_count:
                    errors.append(
                        "assets/optimized/manifest.json: optimized "
                        f"{optimized_local_source_count} of {local_source_count} eligible local "
                        "source(s); every local source must be optimized"
                    )
                if preserved_vector_source_count != len(preserved_vector_sources):
                    errors.append(
                        "assets/optimized/manifest.json: recorded "
                        f"{preserved_vector_source_count} preserved vector source(s), but "
                        f"{len(preserved_vector_sources)} remain in public image references"
                    )
            if source_count > 0:
                optimized_source_percent = 100.0 * optimized_source_count / source_count
            if optimized_source_percent < min_optimized_source_percent:
                errors.append(
                    "assets/optimized/manifest.json: optimized source coverage is "
                    f"{optimized_source_percent:.1f}%; required minimum is "
                    f"{min_optimized_source_percent:.1f}%"
                )
            for item in manifest.get("images", []):
                for variant in item.get("variants", []):
                    candidate = (site / str(variant.get("file", ""))).resolve()
                    if not is_within(candidate, site) or not candidate.is_file():
                        errors.append("assets/optimized/manifest.json: broken variant file reference")
                    else:
                        checked_local.add(candidate)
            failed = int(manifest.get("failedSourceCount", 0))
            if failed:
                warnings.append(f"optimizer manifest records {failed} preserved source(s)")
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            errors.append(f"assets/optimized/manifest.json: invalid manifest ({exc.__class__.__name__})")

    optimized_files = sorted((site / "assets/optimized").glob("*.webp"))
    optimized_total_bytes = 0
    for path in optimized_files:
        try:
            size = path.stat().st_size
        except OSError as exc:
            errors.append(f"{short(path, site)}: cannot stat optimized file ({exc.__class__.__name__})")
            continue
        optimized_total_bytes += size
        if size > max_variant_bytes:
            errors.append(
                f"{short(path, site)}: {size} bytes exceeds per-variant limit of {max_variant_bytes}"
            )
    if optimized_total_bytes > max_total_optimized_bytes:
        errors.append(
            "assets/optimized: total WebP bytes "
            f"{optimized_total_bytes} exceed limit of {max_total_optimized_bytes}"
        )

    if optimized_count < 1:
        errors.append("no optimized responsive HTML images were found")
    if hero_count < 1:
        errors.append("no profile/event hero images were found to verify")

    summary = {
        "htmlImages": len(images),
        "optimizedHtmlImages": optimized_count,
        "heroImages": hero_count,
        "preservedRemoteEligibleImages": external_eligible,
        "preservedUniqueRemoteSources": len(preserved_remote_sources),
        "homepagePreservedRemoteSources": len(homepage_remote_sources),
        "localSources": local_source_count,
        "optimizedLocalSources": optimized_local_source_count,
        "preservedVectorSources": preserved_vector_source_count,
        "optimizedSourcePercent": round(optimized_source_percent, 1),
        "optimizedWebPBytes": optimized_total_bytes,
        "socialHeroPagesChecked": len(optimized_hero_sources),
        "obsoleteRepairScriptReferences": len(obsolete_script_references),
        "jsonLocalImageReferences": json_local_refs,
        "uniqueLocalFilesChecked": len(checked_local),
        "errors": len(errors),
        "warnings": len(warnings),
    }
    return errors, warnings, summary


def arguments(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path, help="Optimized production _site artifact")
    parser.add_argument("--base", default=DEFAULT_BASE, help="Published site base path")
    parser.add_argument("--origin", default=DEFAULT_ORIGIN, help="Published site origin")
    parser.add_argument(
        "--require-remote",
        action="store_true",
        help="Fail when any eligible remote image remains (normally a warning for graceful degradation)",
    )
    parser.add_argument(
        "--min-optimized-source-percent",
        type=float,
        default=0.0,
        help=(
            "Optional strict minimum share of all unique manifest sources that must be "
            "optimized (default: 0; every local source is always required)"
        ),
    )
    parser.add_argument(
        "--max-homepage-remotes",
        type=int,
        default=None,
        help=(
            "Optional strict maximum for preserved remote image sources on index.html "
            "(default: warn only)"
        ),
    )
    parser.add_argument("--max-variant-bytes", type=int, default=2 * 1024 * 1024)
    parser.add_argument("--max-total-optimized-bytes", type=int, default=128 * 1024 * 1024)
    args = parser.parse_args(argv)
    if not 0 <= args.min_optimized_source_percent <= 100:
        parser.error("--min-optimized-source-percent must be between 0 and 100")
    if args.max_homepage_remotes is not None and args.max_homepage_remotes < 0:
        parser.error("--max-homepage-remotes must be non-negative")
    if args.max_variant_bytes < 16 * 1024:
        parser.error("--max-variant-bytes must be at least 16 KiB")
    if args.max_total_optimized_bytes < args.max_variant_bytes:
        parser.error("--max-total-optimized-bytes must cover at least one variant")
    try:
        args.origin = normalize_origin(args.origin)
    except ValueError as exc:
        parser.error(str(exc))
    return args


def main(argv: Optional[list[str]] = None) -> int:
    args = arguments(argv)
    site = args.site.expanduser().resolve()
    if not site.is_dir() or not (site / "index.html").is_file():
        print("error: site must be a completed production artifact containing index.html", file=sys.stderr)
        return 2
    base = normalize_base(args.base)
    errors, warnings, summary = verify(
        site,
        base,
        args.origin,
        args.require_remote,
        args.min_optimized_source_percent,
        args.max_homepage_remotes,
        args.max_variant_bytes,
        args.max_total_optimized_bytes,
    )
    for message in warnings[:50]:
        print(f"warning: {message}", file=sys.stderr)
    if len(warnings) > 50:
        print(f"warning: {len(warnings) - 50} additional warnings omitted", file=sys.stderr)
    for message in errors[:100]:
        print(f"error: {message}", file=sys.stderr)
    if len(errors) > 100:
        print(f"error: {len(errors) - 100} additional errors omitted", file=sys.stderr)
    print(json.dumps(summary, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
