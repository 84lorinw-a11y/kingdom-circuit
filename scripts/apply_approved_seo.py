from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import re
import shutil
import sys

SITE_ORIGIN = "https://kingdomcircuit.com"
BASE = "/"
SEO_SOURCE = pathlib.Path(os.environ.get("KC_SEO_SOURCE", "_seo_source/scripts"))


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def is_build_only_path(page: pathlib.Path, root: pathlib.Path) -> bool:
    try:
        rel = page.relative_to(root)
    except ValueError:
        return False
    return bool(rel.parts and rel.parts[0] == "_seo_source")


def production_overlay_verify(overlay, root: pathlib.Path, generated_state_pages: list[str]) -> None:
    failures: list[str] = []
    kb = root / "artists/kb/index.html"
    if kb.exists():
        text = kb.read_text(encoding="utf-8")
        for required in ["KB Concerts &amp; Tour Dates", "data-artist-state-filter", "seo-social-link", "Upcoming KB Shows"]:
            if required not in text:
                failures.append(f"kb-missing:{required}")
    else:
        failures.append("missing:artists/kb/index.html")

    directory_path = root / "artists/index.html"
    if not directory_path.exists():
        failures.append("missing:artists/index.html")
    else:
        directory = directory_path.read_text(encoding="utf-8")
        for required in ["data-seo-enhanced-directory", "seo-card-socials", "Christian Hip-Hop Artists, Rappers"]:
            if required not in directory:
                failures.append(f"directory-missing:{required}")

    app = (root / "app.js").read_text(encoding="utf-8")
    if overlay.JS_MARKER not in app:
        failures.append("app-directory-guard")
    styles = (root / "styles.css").read_text(encoding="utf-8")
    if ".seo-artist-hero" not in styles or ".seo-artist-grid" not in styles:
        failures.append("css-overlay")
    if not (root / "seo-test-enhancements.js").exists():
        failures.append("enhancement-js")

    for page in root.rglob("*.html"):
        if is_build_only_path(page, root):
            continue
        text = page.read_text(encoding="utf-8", errors="ignore")
        if page.name != "404.html" and 'name="robots" content="index,follow"' not in text:
            failures.append(f"index-follow:{page}")
        if "84lorinw-a11y.github.io/kingdom-circuit-test" in text or "/kingdom-circuit-test/" in text:
            failures.append(f"test-reference:{page}")
        if len(failures) > 60:
            break

    if generated_state_pages:
        if not any((root / str(path).lstrip("/") / "index.html").exists() for path in generated_state_pages):
            failures.append("artist-state-pages")

    if failures:
        raise SystemExit("Production SEO overlay verification failed:\n" + "\n".join(failures[:80]))


def normalize_public_names(root: pathlib.Path) -> None:
    old_js = root / "seo-test-enhancements.js"
    new_js = root / "seo-enhancements.js"
    if old_js.exists():
        old_js.replace(new_js)

    old_manifest = root / "seo-test-overlay-manifest.json"
    new_manifest = root / "seo-overlay-manifest.json"
    if old_manifest.exists():
        data = json.loads(old_manifest.read_text(encoding="utf-8"))
        data["mode"] = "production-seo-overlay-v1"
        new_manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        old_manifest.unlink()

    replacements = {
        "seo-test-enhancements.js": "seo-enhancements.js",
        "KC SEO TEST SCHEMA": "KC SEO SCHEMA",
        "KC SEO TEST DIRECTORY GUARD": "KC SEO DIRECTORY GUARD",
        "KC SEO TEST OVERLAY V1": "KC SEO OVERLAY V1",
    }
    for page in root.rglob("*.html"):
        if is_build_only_path(page, root):
            continue
        text = page.read_text(encoding="utf-8", errors="ignore")
        for old, new in replacements.items():
            text = text.replace(old, new)
        page.write_text(text, encoding="utf-8")

    for rel in ["styles.css", "app.js"]:
        path = root / rel
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="ignore")
            for old, new in replacements.items():
                text = text.replace(old, new)
            path.write_text(text, encoding="utf-8")


def link_next_show_cards(root: pathlib.Path) -> None:
    card_pattern = re.compile(
        r'(<div class="seo-next-show"><span>Next show</span><strong>)(.*?)(</strong></div>)',
        re.S,
    )
    for page in (root / "artists").glob("*/index.html"):
        if page.parent.name == "profile":
            continue
        text = page.read_text(encoding="utf-8", errors="ignore")
        if 'class="seo-next-show"' not in text or 'data-artist-event-grid' not in text:
            continue
        event_match = re.search(
            r'<div class="event-grid" data-artist-event-grid>.*?<a class="event-media" href="([^"]+)"',
            text,
            re.S,
        )
        if not event_match:
            continue
        href = event_match.group(1)
        linked = card_pattern.sub(
            lambda match: (
                match.group(1)
                + f'<a class="seo-next-show-link text-link" href="{href}" aria-label="Open next show">'
                + match.group(2)
                + "</a>"
                + match.group(3)
            ),
            text,
            count=1,
        )
        if linked != text:
            page.write_text(linked, encoding="utf-8")


def apply_artist_fidelity(root: pathlib.Path) -> None:
    finalizer = load_module("kc_approved_finalizer", SEO_SOURCE / "finalize_test_seo.py")
    finalizer.BASE = BASE
    artists = finalizer.resolve_live_artists(root)
    finalizer.patch_directory(root, artists)
    finalizer.patch_artist_profiles(root, artists)

    for page in root.rglob("*.html"):
        if is_build_only_path(page, root):
            continue
        text = page.read_text(encoding="utf-8", errors="ignore")
        branded = finalizer.replace_social_icons(text)
        if branded != text:
            page.write_text(branded, encoding="utf-8")

    finalizer.append_fidelity_css(root)
    failures = finalizer.verify_artist_fidelity(root, artists)
    if failures:
        raise SystemExit("Artist live-fidelity verification failed:\n" + "\n".join(failures))


def align_artist_schema(root: pathlib.Path) -> None:
    aligner = load_module("kc_approved_schema_aligner", SEO_SOURCE / "align_artist_schema.py")
    aligner.TEST_ORIGIN = SITE_ORIGIN
    aligner.align(root)


def final_production_verify(root: pathlib.Path) -> None:
    failures: list[str] = []
    robots = (root / "robots.txt").read_text(encoding="utf-8")
    if "Allow: /" not in robots or "Disallow: /" in robots:
        failures.append("robots")
    if f"{SITE_ORIGIN}/sitemap.xml" not in robots:
        failures.append("robots-sitemap")
    if not (root / "CNAME").exists() or (root / "CNAME").read_text(encoding="utf-8").strip() != "kingdomcircuit.com":
        failures.append("cname")
    if not (root / "seo-enhancements.js").exists():
        failures.append("seo-enhancements-js")
    if not (root / "seo-overlay-manifest.json").exists():
        failures.append("seo-overlay-manifest")

    for page in root.rglob("*.html"):
        if is_build_only_path(page, root):
            continue
        text = page.read_text(encoding="utf-8", errors="ignore")
        if page.name != "404.html" and 'name="robots" content="index,follow"' not in text:
            failures.append(f"index-follow:{page}")
        if "kingdom-circuit-test" in text or "G-TEST-DISABLED" in text:
            failures.append(f"test-leak:{page}")
        canon = re.search(r'<link rel="canonical" href="([^"]+)">', text)
        if canon and not canon.group(1).startswith(SITE_ORIGIN + "/"):
            failures.append(f"canonical:{page}:{canon.group(1)}")
        if len(failures) > 80:
            break

    kb = (root / "artists/kb/index.html").read_text(encoding="utf-8")
    for required in [
        "KB Concerts &amp; Tour Dates",
        "data-artist-state-filter",
        "#1ed760",
        "#ff0033",
        "Upcoming KB Shows",
        f'{SITE_ORIGIN}/artists/kb/',
    ]:
        if required not in kb:
            failures.append(f"kb:{required}")
    if 'class="seo-next-show-link text-link" href="/event/' not in kb:
        failures.append("kb:next-show-link")

    directory = (root / "artists/index.html").read_text(encoding="utf-8")
    if "assets/artists/1k-phew.webp" not in directory:
        failures.append("directory-1k-phew-image")
    if "Christian Hip-Hop Artists" not in directory:
        failures.append("directory-schema")

    if failures:
        raise SystemExit("Final production SEO verification failed:\n" + "\n".join(failures[:100]))


def main(site_root: str) -> None:
    root = pathlib.Path(site_root).resolve()
    overlay_path = SEO_SOURCE / "apply_test_overlay.py"
    if not overlay_path.exists():
        raise SystemExit(f"Approved SEO source is missing: {overlay_path}")

    overlay = load_module("kc_approved_overlay", overlay_path)
    overlay.BASE = BASE
    overlay.TEST_ORIGIN = SITE_ORIGIN
    overlay.JS_MARKER = "/* KC SEO DIRECTORY GUARD */"
    overlay.SCHEMA_MARKER = "<!-- KC SEO SCHEMA -->"
    overlay.verify = lambda site, pages: production_overlay_verify(overlay, pathlib.Path(site), pages)

    saved_argv = sys.argv[:]
    try:
        sys.argv = [str(overlay_path), str(root)]
        overlay.main()
    finally:
        sys.argv = saved_argv

    # The approved source checkout is a build dependency only. If the overlay's
    # broad copier brought it into the artifact, remove it before normalization/deploy.
    shutil.rmtree(root / "_seo_source", ignore_errors=True)

    normalize_public_names(root)
    link_next_show_cards(root)
    apply_artist_fidelity(root)
    align_artist_schema(root)
    final_production_verify(root)
    print("Approved SEO upgrade applied and production safety checks passed")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: apply_approved_seo.py SITE_ROOT")
    main(sys.argv[1])
