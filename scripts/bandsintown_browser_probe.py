#!/usr/bin/env python3
"""Proof-of-concept Bandsintown browser probe.

Uses a normal Playwright Chromium session from GitHub Actions. This intentionally
uses no proxy rotation, stealth plugins, CAPTCHA bypass, or other anti-bot
circumvention. The goal is to determine whether browser execution alone is
enough to read public Bandsintown pages from a GitHub runner.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "bandsintown-browser-probe.json"

TARGETS = [
    {"artist": "KB", "url": "https://www.bandsintown.com/a/165768-kb"},
    {"artist": "Parris Chariz", "url": "https://www.bandsintown.com/a/14726057-parris-chariz"},
    {"artist": "NF", "url": "https://www.bandsintown.com/a/11969355-nf"},
    {"artist": "1K Phew", "url": f"https://www.bandsintown.com/search?q={quote_plus('1K Phew')}"},
]


def now_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> None:
    report = {
        "checkedAt": now_z(),
        "environment": "github-actions-playwright-chromium-no-proxy",
        "targets": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="en-US",
            viewport={"width": 1365, "height": 900},
        )
        page = context.new_page()

        for target in TARGETS:
            item = {"artist": target["artist"], "url": target["url"]}
            try:
                response = page.goto(target["url"], wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(4000)
                html = page.content()
                title = page.title()
                links = page.locator('a[href*="/e/"]').evaluate_all(
                    "els => Array.from(new Set(els.map(e => e.href))).slice(0, 20)"
                )
                lower = html.lower()
                item.update({
                    "httpStatus": response.status if response else None,
                    "title": title[:200],
                    "htmlBytes": len(html.encode("utf-8")),
                    "eventLinksFound": len(links),
                    "sampleEventLinks": links[:5],
                    "cloudflareChallenge": any(token in lower for token in (
                        "just a moment", "cf-chl-", "verify you are human", "challenge-platform"
                    )),
                    "accessDenied": any(token in lower for token in (
                        "access denied", "error 403", "forbidden"
                    )),
                    "status": "readable" if links or (response and response.status == 200 and len(html) > 20000) else "blocked_or_empty",
                })
            except Exception as exc:
                item.update({"status": "failed", "error": str(exc)[:500]})
            report["targets"].append(item)

        browser.close()

    report["summary"] = {
        "targetsChecked": len(report["targets"]),
        "readable": sum(1 for x in report["targets"] if x.get("status") == "readable"),
        "eventLinksFound": sum(int(x.get("eventLinksFound") or 0) for x in report["targets"]),
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
