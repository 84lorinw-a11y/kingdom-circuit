#!/usr/bin/env python3
"""Keep approved artist portraits static, versioned, and independent of the network.

To deliberately replace a portrait, save its original under assets/artists/ and
run: python scripts/artist_portraits.py pin 'Artist' assets/artists/new.jpg
     --source 'https://official-source/' --position '50% 30%'
Routine sync/build commands only read the saved files; they never fetch photos.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from verify_public_performance import ImageParser

ROOT = Path(__file__).resolve().parents[1]
PORTRAITS = Path("config/artist-portraits.json")
OVERRIDES = Path("config/verified-artist-image-overrides.json")
CONTEXTS = {"artist-visual", "seo-profile-image", "profile-visual", "kc-rd-profile-visual"}


def norm(value: object) -> str:
    return str(value or "").strip().casefold()


def local_asset(root: Path, value: str) -> Path:
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError(f"Artist portraits must be saved locally: {value}")
    path = (root / parsed.path.lstrip("/")).resolve()
    if not path.is_relative_to((root / "assets").resolve()):
        raise ValueError(f"Portrait path must stay inside assets/: {value}")
    if not path.is_file():
        raise ValueError(f"Saved artist portrait is missing: {value}")
    return path


def decode_image(path: Path) -> tuple[int, int]:
    from PIL import Image
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        image.load()
        if min(image.size) < 64:
            raise ValueError(f"Artist portrait is too small: {path}")
        return image.size


def load_portraits(root: Path = ROOT, *, decode: bool = False) -> dict[str, dict]:
    records = json.loads((root / PORTRAITS).read_text(encoding="utf-8"))
    overrides = json.loads((root / OVERRIDES).read_text(encoding="utf-8"))
    roster = json.loads((root / "config/artists.json").read_text(encoding="utf-8"))
    names = {norm(a["name"]) for a in roster if a.get("enabled") is not False}
    if not isinstance(records, dict) or not records:
        raise ValueError("Saved artist portrait registry is empty")
    if len({norm(name) for name in records}) != len(records):
        raise ValueError("Duplicate artist portrait names")
    if set(records) != set(overrides):
        raise ValueError("Portrait registry and image overrides disagree; use artist_portraits.py pin")
    for name, record in records.items():
        if norm(name) not in names:
            raise ValueError(f"Saved portrait artist is not in the active roster: {name}")
        if overrides[name] != record["asset"]:
            raise ValueError(f"Unregistered portrait replacement for {name}; use artist_portraits.py pin")
        path = local_asset(root, record["asset"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"Saved portrait changed or is corrupt: {name}; register an intentional replacement")
        if decode and decode_image(path) != (record["width"], record["height"]):
            raise ValueError(f"Saved portrait dimensions changed: {name}")
    return records


def apply_to_records(artists: list[dict], portraits: dict[str, dict]) -> int:
    """A stale Sheet/collector payload cannot overwrite an approved portrait."""
    by_name = {norm(name): item for name, item in portraits.items()}
    changed = 0
    for artist in artists:
        portrait = by_name.get(norm(artist.get("name")))
        if portrait:
            for key, value in (("imageUrl", portrait["asset"]),
                               ("imagePosition", portrait.get("position", "center"))):
                if artist.get(key) != value:
                    artist[key] = value
                    changed += 1
    return changed


def verify_site(site: Path, root: Path = ROOT, *, optimized: bool = True) -> dict[str, int]:
    """Verify every directory/profile portrait, including hidden/inactive cards.

    The source digest ties each responsive variant to the approved original.
    Both src and every srcset candidate must exist, decode, and stay local.
    Artists without an approved photo may retain their existing placeholder.
    """
    records = load_portraits(root, decode=True)
    directory = site / "artists/index.html"
    if not directory.is_file():
        raise ValueError("Artist directory is missing")
    by_name = {norm(name): value for name, value in records.items()}
    seen: dict[Path, set[str]] = {}
    checked: set[Path] = set()
    images = 0
    for page in [directory, *(site / "artists").glob("*/index.html")]:
        parser = ImageParser(page)
        parser.feed(page.read_text(encoding="utf-8"))
        seen[page] = set()
        for image in parser.images:
            if not (set(image.context_classes) & CONTEXTS):
                continue
            name = norm(image.attrs.get("alt"))
            record = by_name.get(name)
            if not record:
                raise ValueError(f"Unregistered portrait in {page}: {name}; save and pin the photo first")
            seen[page].add(name)
            sources = [image.source]
            for entry in str(image.attrs.get("srcset") or "").split(","):
                if entry.strip():
                    sources.append(entry.strip().split()[0])
            fallback = image.attrs.get("data-fallback-src")
            if fallback:
                sources.append(str(fallback))
            for source in sources:
                path = local_asset(site, source)
                relative = path.relative_to(site.resolve()).as_posix()
                expected = record["asset"].lstrip("/")
                variant = re.fullmatch(
                    rf"assets/optimized/{record['sha256'][:24]}-w\d+\.webp", relative
                )
                if relative != expected and not (optimized and variant):
                    raise ValueError(f"Wrong or placeholder portrait for {name}: {source}")
                if path not in checked:
                    decode_image(path)
                    if relative == expected and hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
                        raise ValueError(f"Published portrait differs from saved original: {name}")
                    checked.add(path)
            images += 1
    for name in records:
        key = norm(name)
        slug = re.sub(r"[^a-z0-9]+", "-", key.replace("&", " and ")).strip("-")
        for page in (directory, site / "artists" / slug / "index.html"):
            if key not in seen.get(page, set()):
                raise ValueError(f"Previously approved portrait disappeared: {name} in {page}")
    return {"savedPortraits": len(records), "portraitElements": images, "localFilesDecoded": len(checked)}


def pin(name: str, asset: str, source: str, position: str, root: Path = ROOT) -> None:
    """Explicit editorial action only; never invoked by daily refreshes."""
    from datetime import date
    roster = json.loads((root / "config/artists.json").read_text())
    canonical = next((a['name'] for a in roster if norm(a['name']) == norm(name)), None)
    if not canonical:
        raise ValueError(f"Artist is not in the curated roster: {name}")
    path = local_asset(root, asset)
    width, height = decode_image(path)
    records = json.loads((root / PORTRAITS).read_text())
    records[canonical] = {"asset": path.relative_to(root.resolve()).as_posix(),
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                          "width": width, "height": height, "sourceUrl": source,
                          "position": position, "savedAt": date.today().isoformat()}
    overrides = json.loads((root / OVERRIDES).read_text())
    overrides[canonical] = records[canonical]['asset']
    for relative, data in ((PORTRAITS, records), (OVERRIDES, overrides)):
        (root / relative).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    for relative in ("config/artists.json", "config/verified-artist-registry-updates.json"):
        data = json.loads((root / relative).read_text())
        apply_to_records(data, {canonical: records[canonical]})
        (root / relative).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"Saved static portrait for {canonical}: {asset}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("verify")
    check.add_argument("site", type=Path)
    save = commands.add_parser("pin")
    save.add_argument("artist")
    save.add_argument("asset")
    save.add_argument("--source", required=True)
    save.add_argument("--position", default="center")
    args = parser.parse_args()
    if args.command == "pin":
        pin(args.artist, args.asset, args.source, args.position)
    else:
        print(json.dumps(verify_site(args.site.resolve()), sort_keys=True))


if __name__ == "__main__":
    main()
