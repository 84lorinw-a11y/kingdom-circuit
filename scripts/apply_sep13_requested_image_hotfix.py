#!/usr/bin/env python3
"""Verified image hotfix for the Sep. 13 requested event batch."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PINS = {
    "one-day-fall-festival-aurora-2026": {
        "image": "https://onedaydenver.org/assets/img/artist-petrina.jpg?v=9dd8a283",
        "imageType": "artist",
        "imagePosition": "50% 28%",
        "imageOverride": True,
        "imageSource": "ONE DAY official festival site — Petrina DeLacey lineup image",
        "imageSourceUrl": "https://onedaydenver.org/",
    },
    "kelo-worship-after-christmas-jacksonville-2026": {
        "image": "https://murrayhilltheatre.com/wp-content/uploads/2026/07/https-cdn.evbuc_.com-images-1188053564-306363782001-1-original.20260702-021736-1130x650.jpeg",
        "imageType": "event_artwork",
        "imagePosition": "center",
        "imageOverride": True,
        "imageSource": "Murray Hill Theatre official event page",
        "imageSourceUrl": "https://murrayhilltheatre.com/event/kelo-cho-presents-the-worship-after-christmas/",
    },
}


def apply_requested_image_hotfix() -> None:
    for rel in ("config/manual-events.json", "supplemental-events.json", "events.json"):
        path = ROOT / rel
        rows = json.loads(path.read_text(encoding="utf-8"))
        changed = 0
        for row in rows:
            key = str(row.get("id") or "").removeprefix("manual:")
            pin = PINS.get(key)
            if not pin:
                continue
            row.update(pin)
            changed += 1
        path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if changed != len(PINS):
            raise SystemExit(f"{rel}: expected {len(PINS)} requested image pins, found {changed}")


if __name__ == "__main__":
    apply_requested_image_hotfix()
