#!/usr/bin/env python3
from __future__ import annotations

import pathlib

BASE_URL = "https://kingdomcircuit.com"

# Legacy Kingdom Circuit-created flyer assets are not source-authorized event
# artwork. Replace every lingering reference (visible markup, Open Graph,
# Twitter metadata, JSON-LD, etc.) with the verified image/fallback selected by
# the September 12 closeout. The legacy files can remain in the repository for
# history, but must not be referenced by the public artifact.
REPLACEMENTS = {
    "/assets/events/miles-cj-zion-ultra-2026.svg": "https://i.scdn.co/image/ab6761610000e5eb88d578e199bd2ce1021def5b",
    "/assets/events/fountain-fest-wv-2026.svg": "https://i0.wp.com/fountainfestwv.com/wp-content/uploads/2026/07/Rare-of-Breed-Promo-.webp?resize=720%2C900&ssl=1",
    "/assets/events/mission-friends-sacramento-2026.svg": "/assets/event-fallback.webp",
    "/assets/events/mayia-boxyard-saturdaze-2026.svg": "https://ugc.production.linktr.ee/1c7876eb-77d1-4a43-a2db-def6b24563ac_1000010882.jpeg",
    "/assets/events/mayia-nc-state-fair-2026.svg": "https://ugc.production.linktr.ee/1c7876eb-77d1-4a43-a2db-def6b24563ac_1000010882.jpeg",
    "/assets/events/cj-emulous-kickback-2026.svg": "https://ugc.production.linktr.ee/e2e0b25c-780f-4b6f-9a4d-48461885e719_DSC01908.jpeg",
    "/assets/events/alex-zurdo-zona-zero-2026.svg": "https://i.scdn.co/image/ab6761610000e5eb2c81bb40c3b6962eacf9dc9c",
    "/assets/events/jay-kalyl-desde-antes-2026.svg": "https://i.scdn.co/image/ab6761610000e5eb1269b80aed5d08c40aedfdc3",
}


def replace_fabricated_artwork_refs(root: pathlib.Path) -> dict[str, int]:
    root = root.resolve()
    pages_changed = 0
    replacements = 0

    for page in root.rglob("*.html"):
        text = page.read_text(encoding="utf-8", errors="ignore")
        original = text
        for legacy, replacement in REPLACEMENTS.items():
            absolute_legacy = BASE_URL + legacy
            count = text.count(absolute_legacy)
            if count:
                text = text.replace(absolute_legacy, replacement if replacement.startswith("http") else BASE_URL + replacement)
                replacements += count
            count = text.count(legacy)
            if count:
                text = text.replace(legacy, replacement)
                replacements += count
        if text != original:
            page.write_text(text, encoding="utf-8")
            pages_changed += 1

    lingering = []
    for page in root.rglob("*.html"):
        text = page.read_text(encoding="utf-8", errors="ignore")
        for legacy in REPLACEMENTS:
            if legacy in text or (BASE_URL + legacy) in text:
                lingering.append(f"{page.relative_to(root)}:{legacy}")
                if len(lingering) >= 10:
                    break
        if len(lingering) >= 10:
            break
    if lingering:
        raise SystemExit("Fabricated artwork references remain: " + " | ".join(lingering))

    return {"pagesChanged": pages_changed, "referencesReplaced": replacements}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default="_site")
    args = parser.parse_args()
    print(replace_fabricated_artwork_refs(pathlib.Path(args.site)))
