from __future__ import annotations

import pathlib
import re
import sys

from add_past_show_archives import apply_past_show_archives
from finalize_seo_indexing_core import main as finalize_main
from fix_seo_audit import apply_seo_audit_fixes
from pin_verified_event_artwork import pin_site


LISTING_PAGES = (
    "index.html",
    "festivals/index.html",
    "shows/index.html",
    "shows/this-month/index.html",
    "new-shows/index.html",
)


def apply_p0_mobile_listing_safety(root: pathlib.Path) -> dict[str, int]:
    removed_scripts = 0
    inlined_pages = 0
    for relative in LISTING_PAGES:
        page = root / relative
        if not page.exists():
            continue
        html = page.read_text(encoding="utf-8")
        original = html
        html = re.sub(r'\s*<script[^>]+src="/assets/(?:image-fix|home-primary-image-guard|home-kaden-image-fix|event-image-repair-kc2100|verified-event-artwork-guard)[^"]*"[^>]*></script>', "", html)
        html = re.sub(r'\s*<script async src="https://www\.googletagmanager\.com/gtag/js\?id=G-N2KK9XF4TJ"></script>\s*<script>.*?</script>', "", html, flags=re.S)
        if html != original:
            page.write_text(html, encoding="utf-8")
            removed_scripts += 1

    app = root / "app.js"
    patched_runtime = 0
    if app.exists():
        js = app.read_text(encoding="utf-8")
        marker = "async function boot() {\n  try {"
        replacement = """async function boot() {
  const staticCards = [...document.querySelectorAll("[data-event-card]")];
  if (staticCards.length) {
    document.querySelectorAll(".loading-panel").forEach(element => element.remove());
    setupEventFilters(staticCards);
    setupSubmissionForm();
    return;
  }
  try {"""
        if marker in js and "const staticCards =" not in js:
            app.write_text(js.replace(marker, replacement, 1), encoding="utf-8")
            patched_runtime = 1
    return {"pages_cleaned": removed_scripts, "styles_inlined": inlined_pages, "runtime_patched": patched_runtime}


def main() -> None:
    try:
        index = sys.argv.index("--site")
        root = pathlib.Path(sys.argv[index + 1]).resolve()
    except (ValueError, IndexError):
        raise SystemExit("--site is required")

    report = apply_past_show_archives(root)
    print("Past show archive:", report)
    seo_report = apply_seo_audit_fixes(root)
    print("SEO audit fixes:", seo_report)
    finalize_main()
    artwork_report = pin_site(root)
    print("Verified event artwork:", artwork_report)
    safety_report = apply_p0_mobile_listing_safety(root)
    print("P0 mobile listing safety:", safety_report)


if __name__ == "__main__":
    main()
