from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
from collections import Counter
from xml.sax.saxutils import escape as xml_escape

SITE_ORIGIN = "https://kingdomcircuit.com"

STATE_NAMES = {
    "AL":"Alabama","AK":"Alaska","AZ":"Arizona","AR":"Arkansas","CA":"California","CO":"Colorado","CT":"Connecticut","DE":"Delaware","DC":"District of Columbia","FL":"Florida","GA":"Georgia","HI":"Hawaii","ID":"Idaho","IL":"Illinois","IN":"Indiana","IA":"Iowa","KS":"Kansas","KY":"Kentucky","LA":"Louisiana","ME":"Maine","MD":"Maryland","MA":"Massachusetts","MI":"Michigan","MN":"Minnesota","MS":"Mississippi","MO":"Missouri","MT":"Montana","NE":"Nebraska","NV":"Nevada","NH":"New Hampshire","NJ":"New Jersey","NM":"New Mexico","NY":"New York","NC":"North Carolina","ND":"North Dakota","OH":"Ohio","OK":"Oklahoma","OR":"Oregon","PA":"Pennsylvania","RI":"Rhode Island","SC":"South Carolina","SD":"South Dakota","TN":"Tennessee","TX":"Texas","UT":"Utah","VT":"Vermont","VA":"Virginia","WA":"Washington","WV":"West Virginia","WI":"Wisconsin","WY":"Wyoming"
}

MONTH_RE = re.compile(
    r"^(january|february|march|april|may|june|july|august|september|october|november|december)-\d{4}$"
)
ROBOTS_RE = re.compile(r'<meta\s+name="robots"\s+content="[^"]*"\s*/?>', re.I)
CANONICAL_RE = re.compile(r'<link\s+rel="canonical"\s+href="([^"]+)"\s*/?>', re.I)


def slug(value: str) -> str:
    value = str(value or "").strip().casefold().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-") or "item"


STATE_SLUGS = {slug(name) for name in STATE_NAMES.values()}
CORE_INDEX_URLS = {
    "/",
    "/shows/",
    "/shows/this-month/",
    "/festivals/",
    "/new-shows/",
    "/artists/",
    "/submit/",
}
GENERIC_NOINDEX_URLS = {"/event/", "/artists/profile/"}


def page_url(root: pathlib.Path, page: pathlib.Path) -> str:
    rel = page.relative_to(root)
    if rel == pathlib.Path("index.html"):
        return "/"
    if rel.name != "index.html":
        return "/" + rel.as_posix()
    parent = rel.parent.as_posix().strip(".")
    return "/" + parent.strip("/") + "/"


def set_robots(text: str, directive: str) -> str:
    tag = f'<meta name="robots" content="{directive}">'
    if ROBOTS_RE.search(text):
        return ROBOTS_RE.sub(tag, text, count=1)
    if "</head>" in text:
        return text.replace("</head>", f"  {tag}\n</head>", 1)
    return text


def canonical_from(text: str, url: str) -> str:
    match = CANONICAL_RE.search(text)
    if match:
        return match.group(1)
    return SITE_ORIGIN.rstrip("/") + "/" + url.lstrip("/")


def event_card_count(text: str) -> int:
    return len(re.findall(r"\bdata-event-card\b", text, flags=re.I))


def classify(url: str, text: str) -> tuple[bool, str]:
    if url in CORE_INDEX_URLS:
        return True, "core"
    if url in GENERIC_NOINDEX_URLS:
        return False, "generic-template"

    parts = [part for part in url.strip("/").split("/") if part]

    if parts and parts[0] == "event":
        if "location-tbd" in url:
            return False, "event-location-tbd"
        return True, "event"

    if parts and parts[0] == "artists":
        # Main artist profiles remain strategically indexable even when a show
        # is not currently listed. Artist/state pages need at least two future
        # listings to justify a separate search result.
        if len(parts) == 2:
            return True, "artist"
        if len(parts) == 3:
            count = event_card_count(text)
            if count < 2:
                return False, "thin-artist-state"
            return True, "artist-state"

    if parts and parts[0] == "shows":
        if len(parts) == 1:
            return True, "shows-hub"
        leaf = parts[1]
        if leaf == "this-month" or leaf in STATE_SLUGS or MONTH_RE.match(leaf):
            return True, "show-discovery"
        if leaf.startswith("location-tbd"):
            return False, "location-tbd"
        # City pages with a single event substantially duplicate the event page.
        # Keep them useful for navigation, but keep them out of Google's index
        # until there are at least two upcoming events in that city.
        count = event_card_count(text)
        if count < 2:
            return False, "thin-city"
        return True, "city"

    # Other real public pages remain indexable unless specifically classified.
    return True, "other-public"


def apply(root: pathlib.Path) -> dict:
    if not root.exists():
        raise SystemExit(f"Site root does not exist: {root}")

    indexed: list[tuple[str, str]] = []
    noindexed: list[tuple[str, str]] = []
    reasons = Counter()

    for page in sorted(root.rglob("*.html")):
        rel = page.relative_to(root)
        if rel.name == "404.html" or rel.parts[:1] == ("_seo_source",):
            continue
        text = page.read_text(encoding="utf-8", errors="ignore")
        url = page_url(root, page)
        should_index, reason = classify(url, text)
        reasons[reason] += 1
        directive = "index,follow" if should_index else "noindex,follow"
        patched = set_robots(text, directive)
        if patched != text:
            page.write_text(patched, encoding="utf-8")
            text = patched
        canonical = canonical_from(text, url)
        if should_index:
            if not canonical.startswith(SITE_ORIGIN + "/") and canonical != SITE_ORIGIN:
                raise SystemExit(f"Invalid production canonical on indexable page {url}: {canonical}")
            indexed.append((url, canonical))
        else:
            noindexed.append((url, reason))

    # Rebuild from the final artifact so sitemap coverage cannot be damaged by
    # an earlier cleanup regex or an overlay adding/removing generated pages.
    unique: list[str] = []
    seen: set[str] = set()
    for _, canonical in indexed:
        canonical = canonical.rstrip("/") + "/" if canonical != SITE_ORIGIN + "/" else canonical
        if canonical in seen:
            continue
        seen.add(canonical)
        unique.append(canonical)
    unique.sort()

    today = dt.date.today().isoformat()
    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    xml.extend(
        f"<url><loc>{xml_escape(url)}</loc><lastmod>{today}</lastmod></url>"
        for url in unique
    )
    xml.append("</urlset>")
    (root / "sitemap.xml").write_text("\n".join(xml) + "\n", encoding="utf-8")

    sitemap_text = (root / "sitemap.xml").read_text(encoding="utf-8")
    required = [
        SITE_ORIGIN + "/",
        SITE_ORIGIN + "/shows/",
        SITE_ORIGIN + "/artists/",
        SITE_ORIGIN + "/festivals/",
    ]
    for url in required:
        if f"<loc>{url}</loc>" not in sitemap_text:
            raise SystemExit(f"Required sitemap URL missing: {url}")
    if "location-tbd" in sitemap_text:
        raise SystemExit("Location TBD URL leaked into sitemap")
    if f"<loc>{SITE_ORIGIN}/event/</loc>" in sitemap_text:
        raise SystemExit("Generic event template leaked into sitemap")
    if f"<loc>{SITE_ORIGIN}/artists/profile/</loc>" in sitemap_text:
        raise SystemExit("Generic artist template leaked into sitemap")

    # Verify no noindex page can appear in the sitemap.
    for url, reason in noindexed:
        absolute = SITE_ORIGIN.rstrip("/") + "/" + url.lstrip("/")
        if f"<loc>{absolute}</loc>" in sitemap_text:
            raise SystemExit(f"Noindex page leaked into sitemap: {url} ({reason})")

    if len(unique) < 350:
        raise SystemExit(f"Indexable sitemap unexpectedly small: {len(unique)} URLs")

    report = {
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "indexablePages": len(indexed),
        "noindexPages": len(noindexed),
        "sitemapUrls": len(unique),
        "reasons": dict(sorted(reasons.items())),
        "noindexExamples": [
            {"url": url, "reason": reason}
            for url, reason in noindexed[:30]
        ],
    }
    (root / "seo-indexing-policy.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    args = parser.parse_args()
    apply(pathlib.Path(args.site).resolve())


if __name__ == "__main__":
    main()
