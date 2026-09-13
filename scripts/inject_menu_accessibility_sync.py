#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import re

SCRIPT = "/assets/menu-accessibility-sync.js?v=20260912-1"


def inject_menu_accessibility_sync(root: pathlib.Path) -> dict[str, int]:
    root = root.resolve()
    asset = root / "assets" / "menu-accessibility-sync.js"
    if not asset.is_file():
        raise SystemExit("menu-accessibility-sync.js missing from deployment artifact")

    tag = f'<script src="{SCRIPT}" defer></script>'
    pages = 0
    for page in root.rglob("*.html"):
        text = page.read_text(encoding="utf-8", errors="ignore")
        if "menu-accessibility-sync.js" in text:
            continue
        if "menu-drawer" not in text or "</head>" not in text.lower():
            continue
        updated = re.sub(r"</head>", tag + "</head>", text, count=1, flags=re.I)
        if updated != text:
            page.write_text(updated, encoding="utf-8")
            pages += 1
    return {"pagesEnhanced": pages}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default="_site")
    args = parser.parse_args()
    print(inject_menu_accessibility_sync(pathlib.Path(args.site)))
