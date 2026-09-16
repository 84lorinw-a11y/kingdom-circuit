#!/usr/bin/env python3
"""Build responsive, local WebP images inside a production site artifact.

This script operates on a completed ``_site`` directory, never on the live
repository's source files. Images are
deduplicated by content hash and written with opaque, deterministic filenames.

Pillow (with WebP support) is preferred.  ImageMagick is used as a fallback so
the script can also run on a hosted runner without importing Pillow.
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import dataclasses
import hashlib
import html
from html.parser import HTMLParser
import io
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from typing import Iterable, Optional
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


DEFAULT_BASE = "/"
DEFAULT_ORIGIN = "https://kingdomcircuit.com"
DEFAULT_WIDTHS = (320, 640, 960, 1280)
CARD_SIZES = (
    "(max-width: 600px) calc(100vw - 32px), "
    "(max-width: 900px) calc(100vw - 48px), "
    "(max-width: 1180px) 40vw, 453px"
)
HERO_SIZES = (
    "(max-width: 600px) calc(100vw - 32px), "
    "(max-width: 648px) calc(100vw - 48px), "
    "(max-width: 900px) 600px, "
    "(max-width: 1180px) 42vw, 475px"
)
ARTIST_CARD_SIZES = (
    "(max-width: 600px) calc(50vw - 21px), "
    "(max-width: 900px) calc(50vw - 33px), "
    "(max-width: 1180px) calc(25vw - 25.5px), 270px"
)
PUBLIC_JSON_FILES = (
    "events.json",
    "supplemental-events.json",
    "artist-website-events.json",
    "config/artists.json",
    "config/manual-events.json",
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
ELIGIBLE_IMAGE_CLASSES = {"event-artwork", "artist-photo"}
ELIGIBLE_CONTEXT_CLASSES = {
    "event-media",
    "event-detail-media",
    "seo-profile-image",
    "profile-visual",
    "artist-visual",
}
HERO_CONTEXT_CLASSES = {"event-detail-media", "seo-profile-image", "profile-visual"}
VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}
SAME_SITE_HOSTS = {
    "84lorinw-a11y.github.io",
    "kingdomcircuit.com",
    "www.kingdomcircuit.com",
}
OPTIMIZED_NAME = re.compile(r"^[0-9a-f]{24}-w[0-9]+\.webp$")
OBSOLETE_IMAGE_REPAIR_SCRIPT = re.compile(
    r"<script\b(?=[^>]*\bsrc=[\"'][^\"']*(?:"
    r"verified-event-artwork-guard\.js|event-image-repair-kc2100\.js"
    r")[^\"']*[\"'])[^>]*>\s*</script\s*>",
    re.IGNORECASE,
)


class OptimizationFailure(Exception):
    """A deliberately terse failure safe to include in a public manifest."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclasses.dataclass(frozen=True)
class SourceRef:
    key: str
    original: str
    local_path: Optional[Path] = None
    remote_url: Optional[str] = None

    @property
    def source_id(self) -> str:
        return hashlib.sha256(self.key.encode("utf-8")).hexdigest()[:20]


@dataclasses.dataclass
class ImageOccurrence:
    start: int
    end: int
    attrs: list[tuple[str, Optional[str]]]
    context_classes: frozenset[str]

    @property
    def attr_map(self) -> dict[str, Optional[str]]:
        return {key.lower(): value for key, value in self.attrs}

    @property
    def source(self) -> str:
        return str(self.attr_map.get("src") or "").strip()

    @property
    def class_names(self) -> set[str]:
        return set(str(self.attr_map.get("class") or "").split())

    @property
    def eligible(self) -> bool:
        return bool(
            self.source
            and (
                self.class_names & ELIGIBLE_IMAGE_CLASSES
                or set(self.context_classes) & ELIGIBLE_CONTEXT_CLASSES
            )
        )

    @property
    def hero(self) -> bool:
        return bool(set(self.context_classes) & HERO_CONTEXT_CLASSES)


@dataclasses.dataclass
class TagOccurrence:
    start: int
    end: int
    attrs: list[tuple[str, Optional[str]]]

    @property
    def attr_map(self) -> dict[str, Optional[str]]:
        return {key.lower(): value for key, value in self.attrs}


@dataclasses.dataclass(frozen=True)
class Variant:
    width: int
    height: int
    filename: str
    url: str


@dataclasses.dataclass(frozen=True)
class OptimizedImage:
    content_id: str
    source_width: int
    source_height: int
    variants: tuple[Variant, ...]

    @property
    def largest(self) -> Variant:
        return max(self.variants, key=lambda item: item.width)

    @property
    def srcset(self) -> str:
        return ", ".join(f"{item.url} {item.width}w" for item in self.variants)


class SiteImageParser(HTMLParser):
    """Collect image offsets and ancestor classes without reserializing pages."""

    def __init__(self, text: str):
        super().__init__(convert_charrefs=True)
        self.text = text
        self.line_starts: list[int] = [0]
        for match in re.finditer(r"\n", text):
            self.line_starts.append(match.end())
        self.stack: list[tuple[str, frozenset[str]]] = []
        self.images: list[ImageOccurrence] = []
        self.metas: list[TagOccurrence] = []

    @staticmethod
    def _classes(attrs: Iterable[tuple[str, Optional[str]]]) -> frozenset[str]:
        for key, value in attrs:
            if key.lower() == "class":
                return frozenset(str(value or "").split())
        return frozenset()

    def _offset(self) -> int:
        line, column = self.getpos()
        return self.line_starts[line - 1] + column

    def _record(self, tag: str, attrs: list[tuple[str, Optional[str]]], push: bool) -> None:
        tag = tag.lower()
        if tag in {"img", "meta"}:
            raw = self.get_starttag_text() or ""
            start = self._offset()
            if tag == "img":
                context: set[str] = set()
                for _, classes in self.stack:
                    context.update(classes)
                self.images.append(
                    ImageOccurrence(start, start + len(raw), list(attrs), frozenset(context))
                )
            else:
                self.metas.append(TagOccurrence(start, start + len(raw), list(attrs)))
        elif push and tag not in VOID_ELEMENTS:
            self.stack.append((tag, self._classes(attrs)))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        self._record(tag, attrs, True)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        self._record(tag, attrs, False)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                return


class ByteBudget:
    def __init__(self, limit: int):
        self.limit = limit
        self.used = 0
        self.lock = threading.Lock()

    def consume(self, amount: int) -> None:
        with self.lock:
            if self.used + amount > self.limit:
                raise OptimizationFailure("total-byte-limit")
            self.used += amount


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


def local_candidate(site: Path, path_value: str, base: str) -> Optional[Path]:
    decoded = urllib.parse.unquote(path_value or "")
    if not decoded:
        return None
    if decoded.startswith(base):
        decoded = decoded[len(base):]
    else:
        decoded = decoded.lstrip("/")
    candidate = (site / decoded).resolve()
    if not is_within(candidate, site) or not candidate.is_file():
        return None
    return candidate


def source_ref(value: str, site: Path, base: str) -> Optional[SourceRef]:
    value = html.unescape(str(value or "").strip())
    if not value or value.startswith(("data:", "blob:", "javascript:")):
        return None
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme.lower() in {"http", "https"}:
        host = (parsed.hostname or "").lower()
        if host in SAME_SITE_HOSTS:
            local = local_candidate(site, parsed.path, base)
            if local is not None:
                rel = local.relative_to(site).as_posix()
                return SourceRef(f"local:{rel}", value, local_path=local)
        normalized = urllib.parse.urlunsplit(
            (parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, parsed.query, "")
        )
        return SourceRef(f"remote:{normalized}", value, remote_url=normalized)
    if parsed.scheme:
        return None
    local = local_candidate(site, parsed.path, base)
    if local is None:
        return None
    rel = local.relative_to(site).as_posix()
    return SourceRef(f"local:{rel}", value, local_path=local)


def is_preserved_vector(source: SourceRef) -> bool:
    """Return whether a pure local SVG should stay vector-native."""
    path = source.local_path
    if path is None or path.suffix.casefold() != ".svg":
        return False
    try:
        root = ET.fromstring(path.read_bytes())
    except (OSError, ET.ParseError):
        # A malformed SVG is not intentionally exempt: let conversion fail so
        # the deterministic local-raster gate catches it.
        return False
    for element in root.iter():
        if not str(element.tag).casefold().endswith("image"):
            continue
        for key, value in element.attrib.items():
            if not str(key).casefold().endswith("href") or not value.startswith("data:image/"):
                continue
            header = value.split(",", 1)[0].casefold()
            if ";base64" in header and not header.startswith("data:image/svg+xml"):
                return False
    return True


def public_addresses(host: str, port: int) -> None:
    if not host or host.endswith(".local"):
        raise OptimizationFailure("unsafe-address")
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise OptimizationFailure("dns-failure") from exc
    if not addresses:
        raise OptimizationFailure("dns-failure")
    for entry in addresses:
        raw = entry[4][0].split("%", 1)[0]
        try:
            address = ipaddress.ip_address(raw)
        except ValueError as exc:
            raise OptimizationFailure("unsafe-address") from exc
        if not address.is_global:
            raise OptimizationFailure("unsafe-address")


def validate_remote_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise OptimizationFailure("unsupported-url")
    if parsed.username or parsed.password:
        raise OptimizationFailure("unsafe-address")
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    if port not in {80, 443}:
        raise OptimizationFailure("unsafe-port")
    public_addresses(parsed.hostname, port)


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        validate_remote_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def read_source(
    source: SourceRef,
    budget: ByteBudget,
    per_image_limit: int,
    timeout: float,
    deadline: float,
) -> bytes:
    if time.monotonic() >= deadline:
        raise OptimizationFailure("wall-time-limit")
    if source.local_path is not None:
        try:
            size = source.local_path.stat().st_size
            if size > per_image_limit:
                raise OptimizationFailure("image-byte-limit")
            budget.consume(size)
            return source.local_path.read_bytes()
        except OptimizationFailure:
            raise
        except OSError as exc:
            raise OptimizationFailure("local-read-failure") from exc

    if not source.remote_url:
        raise OptimizationFailure("unsupported-url")
    validate_remote_url(source.remote_url)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise OptimizationFailure("wall-time-limit")
    request = urllib.request.Request(
        source.remote_url,
        headers={
            "User-Agent": "KingdomCircuit-PublicImageOptimizer/1.0",
            "Accept": "image/webp,image/jpeg,image/png,image/gif;q=0.9,*/*;q=0.1",
        },
    )
    opener = urllib.request.build_opener(SafeRedirectHandler())
    try:
        with opener.open(request, timeout=max(0.1, min(timeout, remaining))) as response:
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > per_image_limit:
                        raise OptimizationFailure("image-byte-limit")
                except ValueError:
                    pass
            chunks: list[bytes] = []
            received = 0
            while True:
                if time.monotonic() >= deadline:
                    raise OptimizationFailure("wall-time-limit")
                chunk = response.read(min(64 * 1024, per_image_limit - received + 1))
                if not chunk:
                    break
                received += len(chunk)
                if received > per_image_limit:
                    raise OptimizationFailure("image-byte-limit")
                budget.consume(len(chunk))
                chunks.append(chunk)
            if not chunks:
                raise OptimizationFailure("empty-download")
            return b"".join(chunks)
    except OptimizationFailure:
        raise
    except urllib.error.HTTPError as exc:
        raise OptimizationFailure(f"http-{exc.code}") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        code = "download-timeout" if isinstance(reason, (TimeoutError, socket.timeout)) else "download-failure"
        raise OptimizationFailure(code) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise OptimizationFailure("download-timeout") from exc
    except OSError as exc:
        raise OptimizationFailure("download-failure") from exc


def webp_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise OptimizationFailure("invalid-webp-output")
    offset = 12
    while offset + 8 <= len(data):
        fourcc = data[offset:offset + 4]
        size = int.from_bytes(data[offset + 4:offset + 8], "little")
        payload = data[offset + 8:offset + 8 + size]
        if fourcc == b"VP8X" and len(payload) >= 10:
            width = 1 + int.from_bytes(payload[4:7], "little")
            height = 1 + int.from_bytes(payload[7:10], "little")
            return width, height
        if fourcc == b"VP8L" and len(payload) >= 5 and payload[0] == 0x2F:
            b1, b2, b3, b4 = payload[1:5]
            width = 1 + b1 + ((b2 & 0x3F) << 8)
            height = 1 + (b2 >> 6) + (b3 << 2) + ((b4 & 0x0F) << 10)
            return width, height
        if fourcc == b"VP8 " and len(payload) >= 10:
            marker = payload.find(b"\x9d\x01\x2a")
            if marker >= 0 and marker + 7 <= len(payload):
                width = int.from_bytes(payload[marker + 3:marker + 5], "little") & 0x3FFF
                height = int.from_bytes(payload[marker + 5:marker + 7], "little") & 0x3FFF
                return width, height
        offset += 8 + size + (size & 1)
    raise OptimizationFailure("invalid-webp-output")


class PillowBackend:
    name = "pillow"

    def __init__(self) -> None:
        from PIL import Image, ImageOps, features  # type: ignore

        if not features.check("webp"):
            raise RuntimeError("Pillow was built without WebP support")
        Image.MAX_IMAGE_PIXELS = 40_000_000
        self.Image = Image
        self.ImageOps = ImageOps

    @staticmethod
    def _embedded_raster(data: bytes) -> bytes:
        """Unwrap the embedded raster used by the site's lightweight SVG portraits."""
        if not data.lstrip().startswith(b"<svg"):
            return data
        try:
            root = ET.fromstring(data)
            for element in root.iter():
                if not str(element.tag).lower().endswith("image"):
                    continue
                for key, value in element.attrib.items():
                    if not str(key).lower().endswith("href") or not value.startswith("data:image/"):
                        continue
                    header, encoded = value.split(",", 1)
                    if ";base64" not in header.lower():
                        continue
                    return base64.b64decode(encoded, validate=True)
        except (ET.ParseError, ValueError, base64.binascii.Error) as exc:
            raise OptimizationFailure("unsupported-image") from exc
        raise OptimizationFailure("unsupported-image")

    def _open(self, data: bytes):  # type: ignore[no-untyped-def]
        try:
            data = self._embedded_raster(data)
            image = self.Image.open(io.BytesIO(data))
            image.seek(0)
            image.load()
            image = self.ImageOps.exif_transpose(image)
            if "A" in image.getbands() or (image.mode == "P" and "transparency" in image.info):
                return image.convert("RGBA")
            return image.convert("RGB")
        except Exception as exc:
            raise OptimizationFailure("unsupported-image") from exc

    def inspect(self, data: bytes) -> tuple[int, int]:
        image = self._open(data)
        try:
            return int(image.width), int(image.height)
        finally:
            image.close()

    def render(
        self,
        data: bytes,
        targets: list[tuple[int, Path]],
        quality: int,
        deadline: float,
    ) -> list[tuple[int, int]]:
        image = self._open(data)
        results: list[tuple[int, int]] = []
        try:
            for width, destination in targets:
                if time.monotonic() >= deadline:
                    raise OptimizationFailure("wall-time-limit")
                height = max(1, round(image.height * width / image.width))
                resized = image if (width, height) == image.size else image.resize(
                    (width, height), self.Image.Resampling.LANCZOS
                )
                temporary = destination.with_name(destination.name + ".tmp")
                try:
                    resized.save(
                        temporary,
                        "WEBP",
                        quality=quality,
                        method=6,
                        exact=True,
                    )
                    os.replace(temporary, destination)
                finally:
                    temporary.unlink(missing_ok=True)
                    if resized is not image:
                        resized.close()
                actual = webp_dimensions(destination.read_bytes())
                if actual[0] != width:
                    raise OptimizationFailure("variant-width-mismatch")
                results.append(actual)
            return results
        finally:
            image.close()


class ImageMagickBackend:
    name = "imagemagick"

    def __init__(self) -> None:
        magick = shutil.which("magick")
        convert = shutil.which("convert")
        if magick:
            self.prefix = [magick]
        elif convert:
            self.prefix = [convert]
        else:
            raise RuntimeError("ImageMagick not found")

    def _run(self, args: list[str], deadline: float) -> subprocess.CompletedProcess[bytes]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise OptimizationFailure("wall-time-limit")
        try:
            return subprocess.run(
                self.prefix + args,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=max(0.1, min(30.0, remaining)),
            )
        except subprocess.TimeoutExpired as exc:
            raise OptimizationFailure("conversion-timeout") from exc
        except (OSError, subprocess.CalledProcessError) as exc:
            raise OptimizationFailure("unsupported-image") from exc

    def _with_input(self, data: bytes) -> Path:
        handle = tempfile.NamedTemporaryFile(prefix="kc-image-", suffix=".img", delete=False)
        try:
            handle.write(data)
            return Path(handle.name)
        finally:
            handle.close()

    def inspect(self, data: bytes) -> tuple[int, int]:
        source = self._with_input(data)
        try:
            result = self._run(
                [str(source), "-auto-orient", "-format", "%w %h", "info:"],
                time.monotonic() + 30.0,
            )
            width, height = result.stdout.decode("ascii", "strict").strip().split()
            return int(width), int(height)
        except (ValueError, UnicodeError) as exc:
            raise OptimizationFailure("unsupported-image") from exc
        finally:
            source.unlink(missing_ok=True)

    def render(
        self,
        data: bytes,
        targets: list[tuple[int, Path]],
        quality: int,
        deadline: float,
    ) -> list[tuple[int, int]]:
        source = self._with_input(data)
        results: list[tuple[int, int]] = []
        try:
            for width, destination in targets:
                temporary = destination.with_name(destination.name + ".tmp.webp")
                try:
                    self._run(
                        [
                            str(source), "-auto-orient", "-strip", "-resize", f"{width}x>",
                            "-quality", str(quality), "-define", "webp:method=6", str(temporary),
                        ],
                        deadline,
                    )
                    os.replace(temporary, destination)
                finally:
                    temporary.unlink(missing_ok=True)
                actual = webp_dimensions(destination.read_bytes())
                if actual[0] != width:
                    raise OptimizationFailure("variant-width-mismatch")
                results.append(actual)
            return results
        finally:
            source.unlink(missing_ok=True)


def choose_backend():  # type: ignore[no-untyped-def]
    errors: list[str] = []
    try:
        return PillowBackend()
    except (ImportError, RuntimeError) as exc:
        errors.append(str(exc))
    try:
        return ImageMagickBackend()
    except RuntimeError as exc:
        errors.append(str(exc))
    raise RuntimeError(
        "No WebP encoder is available. Install Pillow with WebP support or ImageMagick. "
        + " / ".join(errors)
    )


def planned_widths(source_width: int, requested: tuple[int, ...]) -> list[int]:
    widths = sorted({value for value in requested if 1 <= value <= source_width})
    if source_width not in widths and source_width < max(requested):
        widths.append(source_width)
    if len(widths) < 2 and source_width >= 2:
        widths.extend((max(1, source_width // 2), source_width))
    return sorted(set(widths))


def render_content(
    digest: str,
    data: bytes,
    staging: Path,
    base: str,
    widths: tuple[int, ...],
    quality: int,
    backend,  # type: ignore[no-untyped-def]
    deadline: float,
) -> OptimizedImage:
    source_width, source_height = backend.inspect(data)
    if source_width < 2 or source_height < 1:
        raise OptimizationFailure("image-too-small")
    chosen = planned_widths(source_width, widths)
    if len(chosen) < 2:
        raise OptimizationFailure("insufficient-variant-widths")
    content_id = digest[:24]
    targets = [(width, staging / f"{content_id}-w{width}.webp") for width in chosen]
    actual_dimensions = backend.render(data, targets, quality, deadline)
    variants = tuple(
        Variant(
            width=actual_width,
            height=actual_height,
            filename=path.name,
            url=f"{base}assets/optimized/{path.name}",
        )
        for (_, path), (actual_width, actual_height) in zip(targets, actual_dimensions)
    )
    return OptimizedImage(content_id, source_width, source_height, variants)


def render_tag(
    tag: str,
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
    rendered: list[str] = [f"<{tag}"]
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


def rewrite_html_page(
    text: str,
    site: Path,
    base: str,
    origin: str,
    source_results: dict[str, OptimizedImage],
) -> tuple[str, int, int, int, int]:
    parser = SiteImageParser(text)
    parser.feed(text)
    replacements: list[tuple[int, int, str]] = []
    optimized_count = 0
    priority_count = 0
    meta_count = 0
    optimized_hero: Optional[OptimizedImage] = None
    for occurrence in parser.images:
        if not occurrence.eligible:
            continue
        updates: dict[str, Optional[str]] = {
            "loading": "eager" if occurrence.hero else "lazy",
            "decoding": "async",
            "fetchpriority": "high" if occurrence.hero else None,
        }
        if occurrence.hero:
            priority_count += 1
        ref = source_ref(occurrence.source, site, base)
        result = source_results.get(ref.key) if ref is not None else None
        if result is not None:
            largest = result.largest
            updates.update(
                {
                    "src": largest.url,
                    "srcset": result.srcset,
                    "sizes": (
                        HERO_SIZES
                        if occurrence.hero
                        else CARD_SIZES
                        if "event-media" in occurrence.context_classes
                        else ARTIST_CARD_SIZES
                        if "artist-visual" in occurrence.context_classes
                        else occurrence.attr_map.get("sizes") or "100vw"
                    ),
                    "width": str(largest.width),
                    "height": str(largest.height),
                    "referrerpolicy": None,
                }
            )
            optimized_count += 1
            if occurrence.hero and optimized_hero is None:
                optimized_hero = result
        replacements.append(
            (occurrence.start, occurrence.end, render_tag("img", occurrence.attrs, updates))
        )

    if optimized_hero is not None:
        absolute_hero_url = origin + optimized_hero.largest.url
        for occurrence in parser.metas:
            attributes = occurrence.attr_map
            identity = str(attributes.get("property") or attributes.get("name") or "").lower()
            if identity not in {"og:image", "twitter:image"}:
                continue
            replacements.append(
                (
                    occurrence.start,
                    occurrence.end,
                    render_tag("meta", occurrence.attrs, {"content": absolute_hero_url}),
                )
            )
            meta_count += 1
    # Meta tags occur before body images but are appended after image
    # replacements above.  Always apply by source offset, not append order, so
    # earlier length changes cannot invalidate later offsets.
    for start, end, replacement in sorted(replacements, key=lambda item: item[0], reverse=True):
        text = text[:start] + replacement + text[end:]
    text, obsolete_count = OBSOLETE_IMAGE_REPAIR_SCRIPT.subn("", text)
    return text, optimized_count, priority_count, meta_count, obsolete_count


def iter_json_image_values(value):  # type: ignore[no-untyped-def]
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in IMAGE_JSON_KEYS and isinstance(child, str):
                yield child
            yield from iter_json_image_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_json_image_values(child)


def rewrite_json_images(
    value,
    site: Path,
    base: str,
    source_results: dict[str, OptimizedImage],
) -> int:  # type: ignore[no-untyped-def]
    changed = 0
    if isinstance(value, dict):
        for key, child in list(value.items()):
            if key.lower() in IMAGE_JSON_KEYS and isinstance(child, str):
                ref = source_ref(child, site, base)
                result = source_results.get(ref.key) if ref is not None else None
                if result is not None:
                    # Runtime localAssetUrl() prefixes BASE for non-HTTP values.
                    # Keep JSON paths artifact-relative to avoid doubling the
                    # GitHub Pages project subpath.
                    value[key] = f"assets/optimized/{result.largest.filename}"
                    changed += 1
                    continue
            changed += rewrite_json_images(child, site, base, source_results)
    elif isinstance(value, list):
        for child in value:
            changed += rewrite_json_images(child, site, base, source_results)
    return changed


def atomic_write_text(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp-kc-optimize")
    try:
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def collect_inventory(
    site: Path,
    base: str,
) -> tuple[dict[Path, str], dict[Path, object], dict[str, tuple[int, SourceRef]]]:
    html_pages: dict[Path, str] = {}
    json_files: dict[Path, object] = {}
    inventory: dict[str, tuple[int, SourceRef]] = {}

    def add(value: str, priority: int) -> None:
        ref = source_ref(value, site, base)
        if ref is None:
            return
        current = inventory.get(ref.key)
        if current is None or priority < current[0]:
            inventory[ref.key] = (priority, ref)

    for path in sorted(site.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        html_pages[path] = text
        parser = SiteImageParser(text)
        parser.feed(text)
        relative = path.relative_to(site).as_posix()
        if relative == "index.html":
            page_priority = 0
        elif relative.startswith("event/"):
            page_priority = 1
        elif relative == "artists/index.html":
            page_priority = 2
        elif relative.startswith("artists/"):
            page_priority = 3
        else:
            page_priority = 4
        for occurrence in parser.images:
            if occurrence.eligible:
                add(occurrence.source, page_priority)

    for relative in PUBLIC_JSON_FILES:
        path = site / relative
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        json_files[path] = value
        for image_value in iter_json_image_values(value):
            add(image_value, 5)

    return html_pages, json_files, inventory


def build_manifest(
    base: str,
    widths: tuple[int, ...],
    quality: int,
    backend_name: str,
    source_count: int,
    local_source_count: int,
    preserved_vector_source_count: int,
    selected_count: int,
    source_results: dict[str, OptimizedImage],
    optimized_local_source_count: int,
    failures: dict[str, str],
    html_rewrites: int,
    json_rewrites: int,
) -> dict[str, object]:
    unique: dict[str, OptimizedImage] = {
        result.content_id: result for result in source_results.values()
    }
    return {
        "schemaVersion": 1,
        "scope": "kingdom-circuit-production",
        "base": base,
        "encoder": backend_name,
        "requestedWidths": list(widths),
        "quality": quality,
        "sourceCount": source_count,
        "localSourceCount": local_source_count,
        "preservedVectorSourceCount": preserved_vector_source_count,
        "selectedSourceCount": selected_count,
        "optimizedSourceCount": len(source_results),
        "optimizedLocalSourceCount": optimized_local_source_count,
        "uniqueOptimizedImageCount": len(unique),
        "failedSourceCount": len(failures),
        "rewrittenHtmlImageCount": html_rewrites,
        "rewrittenJsonValueCount": json_rewrites,
        "failures": [
            {
                "sourceId": hashlib.sha256(key.encode("utf-8")).hexdigest()[:20],
                "code": failures[key],
            }
            for key in sorted(failures)
        ],
        "images": [
            {
                "id": item.content_id,
                "sourceWidth": item.source_width,
                "sourceHeight": item.source_height,
                "variants": [
                    {
                        "width": variant.width,
                        "height": variant.height,
                        "file": f"assets/optimized/{variant.filename}",
                        "url": variant.url,
                    }
                    for variant in item.variants
                ],
            }
            for item in sorted(unique.values(), key=lambda candidate: candidate.content_id)
        ],
    }


def parse_widths(value: str) -> tuple[int, ...]:
    try:
        widths = tuple(sorted({int(part.strip()) for part in value.split(",") if part.strip()}))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("widths must be comma-separated integers") from exc
    if len(widths) < 2 or any(width < 16 or width > 4096 for width in widths):
        raise argparse.ArgumentTypeError("provide at least two widths between 16 and 4096")
    return widths


def arguments(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path, help="Production _site artifact to optimize")
    parser.add_argument("--base", default=DEFAULT_BASE, help="Published site base path")
    parser.add_argument("--origin", default=DEFAULT_ORIGIN, help="Published site origin")
    parser.add_argument("--widths", type=parse_widths, default=DEFAULT_WIDTHS)
    parser.add_argument("--quality", type=int, default=82)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--timeout", type=float, default=12.0, help="Per-download timeout in seconds")
    parser.add_argument("--wall-time", type=float, default=180.0, help="Total soft deadline in seconds")
    parser.add_argument("--max-images", type=int, default=256)
    parser.add_argument("--max-image-bytes", type=int, default=12 * 1024 * 1024)
    parser.add_argument("--max-total-bytes", type=int, default=192 * 1024 * 1024)
    parser.add_argument("--offline", action="store_true", help="Skip remote downloads and preserve their URLs")
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 8:
        parser.error("--workers must be between 1 and 8")
    if not 1 <= args.quality <= 100:
        parser.error("--quality must be between 1 and 100")
    if args.timeout <= 0 or args.timeout > 60:
        parser.error("--timeout must be greater than 0 and at most 60 seconds")
    if args.wall_time <= 0 or args.wall_time > 900:
        parser.error("--wall-time must be greater than 0 and at most 900 seconds")
    if args.max_images < 1 or args.max_images > 1000:
        parser.error("--max-images must be between 1 and 1000")
    if args.max_image_bytes < 64 * 1024 or args.max_image_bytes > 64 * 1024 * 1024:
        parser.error("--max-image-bytes must be between 64 KiB and 64 MiB")
    if args.max_total_bytes < args.max_image_bytes or args.max_total_bytes > 1024 * 1024 * 1024:
        parser.error("--max-total-bytes must cover one image and be at most 1 GiB")
    try:
        args.origin = normalize_origin(args.origin)
    except ValueError as exc:
        parser.error(str(exc))
    return args


def main(argv: Optional[list[str]] = None) -> int:
    args = arguments(argv)
    site = args.site.expanduser().resolve()
    base = normalize_base(args.base)
    if not site.is_dir() or not (site / "index.html").is_file():
        print("error: site must be a completed production artifact containing index.html", file=sys.stderr)
        return 2

    try:
        backend = choose_backend()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    html_pages, json_files, inventory = collect_inventory(site, base)
    ranked = sorted(
        inventory.values(),
        # Local assets are the deterministic optimization floor. Keep them
        # ahead of opportunistic third-party downloads even when a remote
        # image appears on a higher-priority page.
        key=lambda item: (item[1].remote_url is not None, item[0], item[1].key),
    )
    preserved_vectors = [
        source for _, source in ranked if is_preserved_vector(source)
    ]
    optimizable_ranked = [
        item for item in ranked if not is_preserved_vector(item[1])
    ]
    local_source_count = sum(
        1 for _, source in optimizable_ranked if source.local_path is not None
    )
    if local_source_count > args.max_images:
        print(
            "error: --max-images is lower than the eligible local source count "
            f"({args.max_images} < {local_source_count})",
            file=sys.stderr,
        )
        return 2
    selected = [source for _, source in optimizable_ranked[: args.max_images]]
    failures: dict[str, str] = {
        source.key: "candidate-limit"
        for _, source in optimizable_ranked[args.max_images :]
    }
    if args.offline:
        for source in selected:
            if source.remote_url:
                failures[source.key] = "offline"
        selected = [source for source in selected if source.local_path is not None]

    assets = site / "assets"
    assets.mkdir(exist_ok=True)
    staging = assets / f".optimized-staging-{os.getpid()}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    by_digest: dict[str, OptimizedImage] = {}
    source_digest: dict[str, str] = {}
    conversion_failures: dict[str, str] = {}
    deadline = time.monotonic() + args.wall_time
    budget = ByteBudget(args.max_total_bytes)
    try:
        # Convert each source as soon as its download finishes.  Waiting for
        # every slow/blocked third-party host before encoding starved the
        # conversion stage and could yield zero optimized images at the soft
        # deadline even when many downloads had succeeded.
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(
                    read_source,
                    source,
                    budget,
                    args.max_image_bytes,
                    args.timeout,
                    deadline,
                ): source
                for source in selected
            }
            for future in concurrent.futures.as_completed(futures):
                source = futures[future]
                try:
                    data = future.result()
                except OptimizationFailure as exc:
                    failures[source.key] = exc.code
                    continue
                except Exception:
                    failures[source.key] = "unexpected-fetch-failure"
                    continue

                digest = hashlib.sha256(data).hexdigest()
                source_digest[source.key] = digest
                if digest in by_digest or digest in conversion_failures:
                    continue
                try:
                    by_digest[digest] = render_content(
                        digest,
                        data,
                        staging,
                        base,
                        args.widths,
                        args.quality,
                        backend,
                        deadline,
                    )
                except OptimizationFailure as exc:
                    conversion_failures[digest] = exc.code
                except Exception:
                    conversion_failures[digest] = "unexpected-conversion-failure"

        source_results: dict[str, OptimizedImage] = {}
        for key, digest in source_digest.items():
            if digest in by_digest:
                source_results[key] = by_digest[digest]
            else:
                failures[key] = conversion_failures.get(digest, "conversion-failure")
        optimized_local_source_count = sum(
            1
            for _, source in optimizable_ranked
            if source.local_path is not None and source.key in source_results
        )

        rewritten_pages: dict[Path, str] = {}
        html_rewrites = 0
        priority_updates = 0
        meta_rewrites = 0
        obsolete_scripts_removed = 0
        for path, text in html_pages.items():
            rewritten, count, priorities, metas, removed = rewrite_html_page(
                text, site, base, args.origin, source_results
            )
            rewritten_pages[path] = rewritten
            html_rewrites += count
            priority_updates += priorities
            meta_rewrites += metas
            obsolete_scripts_removed += removed

        rewritten_json: dict[Path, str] = {}
        json_rewrites = 0
        for path, value in json_files.items():
            json_rewrites += rewrite_json_images(value, site, base, source_results)
            rewritten_json[path] = json.dumps(value, indent=2, ensure_ascii=False) + "\n"

        manifest = build_manifest(
            base=base,
            widths=args.widths,
            quality=args.quality,
            backend_name=backend.name,
            source_count=len(inventory),
            local_source_count=local_source_count,
            preserved_vector_source_count=len(preserved_vectors),
            selected_count=len(selected),
            source_results=source_results,
            optimized_local_source_count=optimized_local_source_count,
            failures=failures,
            html_rewrites=html_rewrites,
            json_rewrites=json_rewrites,
        )
        manifest["priorityImageCount"] = priority_updates
        manifest["socialImageMetaRewriteCount"] = meta_rewrites
        manifest["obsoleteImageRepairScriptCount"] = obsolete_scripts_removed
        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        output = assets / "optimized"
        if output.exists():
            shutil.rmtree(output)
        os.replace(staging, output)
        for path, text in rewritten_pages.items():
            atomic_write_text(path, text)
        for path, text in rewritten_json.items():
            atomic_write_text(path, text)

        summary = {
            "backend": backend.name,
            "sources": len(inventory),
            "localSources": local_source_count,
            "preservedVectorSources": len(preserved_vectors),
            "optimizedSources": len(source_results),
            "optimizedLocalSources": optimized_local_source_count,
            "uniqueImages": len(by_digest),
            "failures": len(failures),
            "htmlImagesRewritten": html_rewrites,
            "jsonValuesRewritten": json_rewrites,
            "socialImageMetaRewritten": meta_rewrites,
            "obsoleteImageRepairScriptsRemoved": obsolete_scripts_removed,
            "bytesRead": budget.used,
        }
        print(json.dumps(summary, sort_keys=True))
        return 0
    finally:
        if staging.exists():
            shutil.rmtree(staging)


if __name__ == "__main__":
    raise SystemExit(main())
