"""Keep established state URLs alive between shows, without inventing dates."""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from apply_oct3_concert_corrections import rejected
from catalog_removals import removed_event
from add_past_show_archives import is_test, trusted

REGISTRY = "config/permanent-state-pages.json"
CODES = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY PR".split())
ARCHIVE_RE = re.compile(r'<section\b(?=[^>]*\bdata-past-shows-archive\b)[^>]*>.*?</section>', re.S)
NAV_RE = re.compile(r'<section\b[^>]*data-permanent-state-navigation[^>]*>.*?</section>', re.S)
EMPTY_HEADING_STYLE = ('<style id="permanent-state-heading-style">'
                       '@media(max-width:600px){h1[data-permanent-state-heading]'
                       '{font-size:10vw!important;overflow-wrap:anywhere}}'
                       '</style>')


def state_name(code):
    from build_seo_site import STATE_NAMES
    return "Puerto Rico" if code == "PR" else STATE_NAMES[code]


def state_path(code):
    from build_seo_site import state_path as existing_path
    # Preserve the already published territory URL, too.
    return "/shows/pr/" if code == "PR" else existing_path(code)


def eligible(event):
    return (isinstance(event, dict) and event.get("state") in CODES
            and str(event.get("country") or "US").upper() in {"US", "USA", "PR"}
            and not removed_event(event) and not rejected(event) and not is_test(event))


def registry_codes(source):
    path = source / REGISTRY
    if not path.exists():
        return set()
    codes = set(json.loads(path.read_text())["states"])
    if not codes <= CODES:
        raise ValueError(f"Invalid permanent state codes: {codes - CODES}")
    return codes


def discover_codes(source):
    codes = registry_codes(source)
    for name in ("events.json", "supplemental-events.json", "event-history.json"):
        path = source / name
        if not path.exists():
            continue
        payload = json.loads(path.read_text())
        records = payload.get("events", []) if isinstance(payload, dict) else payload
        for record in records:
            event = record.get("event", record)
            if eligible(event) and (name != "event-history.json" or trusted(event)):
                codes.add(event["state"])
    return sorted(codes)


def sync_registry(source):
    codes = discover_codes(source)
    path = source / REGISTRY
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "states": codes}, indent=2) + "\n")
    return codes


def empty_calendar(code):
    from build_seo_site import esc
    name = esc(state_name(code))
    return (f'<section class="calendar" data-state-empty="{code}">'
            '<div class="empty-panel"><h2>Stay tuned for more shows</h2>'
            f'<p>Check back for new {name} dates. In the meantime, explore upcoming '
            'CHH shows across the country.</p><div class="profile-links">'
            '<a class="primary-button" href="/shows/">Explore All Shows</a>'
            '<a class="secondary-button" href="/new-shows/">See Newly Added Shows</a>'
            '</div></div></section>')


def write_empty_page(site, code):
    from build_seo_site import breadcrumbs, breadcrumb_schema, esc, page
    name = state_name(code); url = state_path(code)
    crumbs = [("Shows", "/shows/"), (name, url)]
    body = (f'<section class="page-hero hero-compact">{breadcrumbs(crumbs)}'
            f'<p class="eyebrow">{esc(name)}</p>'
            f'<h1>Christian Hip-Hop &amp; Rap Concerts in {esc(name)}</h1>'
            '<p class="hero-text">Discover Christian hip-hop concerts, Christian rap '
            f'shows and festivals in {esc(name)}. Browse past shows and explore '
            'upcoming dates across the country.</p></section>' + empty_calendar(code))
    target = site / url.strip("/") / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page(f"Christian Hip-Hop & Rap Concerts in {name} | Kingdom Circuit",
                          f"Explore Christian hip-hop concerts in {name}, past shows and upcoming CHH events across the U.S.",
                          url, body, [breadcrumb_schema(crumbs)]))


def approved_history(site, source):
    """Use the exact archive selection/deduplication used by the pinned redesign."""
    module_path = source / "_redesign_source/scripts/apply_test_redesign.py"
    spec = importlib.util.spec_from_file_location("state_archive_redesign", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.configure_environment(True)
    events, _, _ = module.load_source_history(
        [source / "event-history.json"], site, dt.datetime.now(ZoneInfo("America/Los_Angeles")).date())
    return [event for event in events if eligible(event)]


def archive_section(site, events):
    from add_past_show_archives import archive_row, event_path, known_artists
    _, artists = known_artists(site)
    # Never publish a link to a rejected, redirected or unbuilt historical page.
    rows = []
    for event in events:
        path = event_path(event)
        target = site / path.strip("/") / "index.html"
        if not target.is_file():
            raise ValueError(f"State archive event is missing: {path}")
        if f'href="https://kingdomcircuit.com{path}"' not in target.read_text():
            raise ValueError(f"State archive event has a different canonical: {path}")
        rows.append(archive_row(event, set(artists)))
    if not rows:
        return ""
    noun = "show" if len(rows) == 1 else "shows"
    return ('<section class="past-shows-archive" data-past-shows-archive><details>'
            '<summary><span>Past shows</span>'
            f'<span class="past-count">{len(rows)} archived {noun}</span></summary>'
            f'<div class="past-show-list">{"".join(rows)}</div>'
            '<p class="past-archive-note">These events have passed. Check above for upcoming dates.</p>'
            '</details></section>')


def finalize(site, source, history=None, check=False):
    from add_past_show_archives import STYLE
    from build_seo_site import esc
    codes = discover_codes(source)
    events = approved_history(site, source) if history is None else history
    archives = 0
    sitemap = (site / "sitemap.xml").read_text() if check else ""
    for code in codes:
        path = state_path(code); target = site / path.strip("/") / "index.html"
        if not target.is_file():
            raise ValueError(f"Permanent state page missing: {path}")
        original = target.read_text(); text = original
        matches = [e for e in events if e.get("state") == code]
        block = archive_section(site, matches)
        text = ARCHIVE_RE.sub("", text)
        if block:
            text = text.replace("</main>", block + "</main>", 1)
            if 'id="past-show-archive-styles"' not in text:
                text = text.replace("</head>", STYLE + "\n</head>", 1)
            archives += len(matches)
        has_upcoming = bool(re.search(r'<article\b[^>]*\bdata-event-card\b', text))
        if not has_upcoming and f'data-state-empty="{code}"' not in text:
            raise ValueError(f"Permanent state empty message missing: {path}")
        if has_upcoming and 'data-state-empty=' in text:
            raise ValueError(f"Empty state message remained with upcoming shows: {path}")
        if not has_upcoming:
            if '<h1 data-permanent-state-heading' not in text:
                text = text.replace('<h1>', '<h1 data-permanent-state-heading>', 1)
            if 'id="permanent-state-heading-style"' not in text:
                text = text.replace('</head>', EMPTY_HEADING_STYLE + '</head>', 1)
        canonical = f'https://kingdomcircuit.com{path}'
        if f'rel="canonical" href="{canonical}"' not in text:
            raise ValueError(f"State canonical changed: {path}")
        if check:
            if text != original:
                raise ValueError(f"State archive overwritten after finalization: {path}")
            if 'content="index,follow"' not in text or f"<loc>{canonical}</loc>" not in sitemap:
                raise ValueError(f"State page missing indexing metadata: {path}")
        elif text != original:
            target.write_text(text)
    hub = site / "shows/index.html"
    original = hub.read_text()
    links = "".join(f'<a class="seo-chip" href="{state_path(c)}">{esc(state_name(c))}</a>'
                    for c in sorted(codes, key=state_name))
    nav = ('<section class="seo-location-strip" data-permanent-state-navigation>'
           '<details><summary>Browse CHH shows by state</summary>'
           f'<div class="seo-chip-row">{links}</div></details></section>')
    text = NAV_RE.sub("", original).replace("</main>", nav + "</main>", 1)
    if check and text != original:
        raise ValueError("Permanent state navigation is missing or stale")
    if not check and text != original:
        hub.write_text(text)
    return {"statePages": len(codes), "archivedStateRows": archives}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path.cwd())
    parser.add_argument("--site", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.site:
        print(finalize(args.site, args.source, check=args.check))
    else:
        print("Permanent state pages:", sync_registry(args.source))
