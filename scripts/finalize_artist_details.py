"""Restore compact artist schedule details after all page-replacing overlays.

Read the final event/state pages, never scrape or mutate source event/artist data.
The independent --check pass runs immediately before the deployment artifact upload.
"""
from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path
import re
import shutil
from urllib.parse import unquote, urlsplit

BASE = "/"
CSS = "assets/artist-schedule-details.css"
ROW = re.compile(r'<a\b(?=[^>]*class="[^"]*\bkc-rd-show-row\b)[^>]*>.*?</a>', re.S)
NEXT = re.compile(r'<a\b(?=[^>]*class="[^"]*\bkc-rd-next-show\b)[^>]*>.*?</a>', re.S)
NAV = re.compile(r'\s*<nav\b[^>]*data-kc-artist-states[^>]*>.*?</nav>', re.S)
EXTRA = re.compile(r'<span class="kc-rd-event-(?:title|status)">.*?</span>', re.S)
FRAMING_STYLE = re.compile(r'\s*<style data-kc-artist-framing>.*?</style>\s*', re.S)
# Owner-approved mobile framing, applied after every imported redesign.
# Inline page-scoped CSS avoids stale shared styles and leaves desktop intact.
MOBILE_FRAMING = {
    'nate-period': '''@media (max-width: 720px) {
  body .kc-rd-profile-visual { aspect-ratio: 1 / 1; }
  body .kc-rd-profile-visual img { object-position: 50% 0% !important; }
  body .kc-rd-profile-name { bottom: 10px; font-size: clamp(1.6rem, 9vw, 3.5rem); }
}''',
    'kevin-kc-campbell': '''@media (max-width: 720px) {
  body .kc-rd-profile-visual { aspect-ratio: 1 / 1; }
  body .kc-rd-profile-visual img { object-position: 50% 0% !important; }
  body .kc-rd-profile-name { bottom: 10px; font-size: clamp(1.4rem, 6.5vw, 3rem); }
}''',
    'marv': '''@media (max-width: 720px) {
  body .kc-rd-profile-visual { aspect-ratio: 1 / 1; }
  body .kc-rd-profile-visual img { object-position: 50% 0% !important; }
  body .kc-rd-profile-name { bottom: 10px; }
}''',
    'rainbow-israel': '''@media (max-width: 720px) {
  body .kc-rd-profile-visual { aspect-ratio: 1 / 1; }
  body .kc-rd-profile-visual img { object-position: 50% 0% !important; }
  body .kc-rd-profile-name {
    bottom: 10px;
    font-size: clamp(1.6rem, 8.2vw, 3.5rem);
    white-space: nowrap;
  }
}''',
    'eli-williams': '''@media (max-width: 720px) {
  body .kc-rd-profile-visual img {
    object-position: 50% 35% !important;
    transform: scale(1.12);
    transform-origin: 50% 0%;
  }
}''',
    'joz': '''@media (max-width: 720px) {
  body .kc-rd-profile-visual img { object-position: 50% 30% !important; }
}''',
    'kurtis-hoppie': '''@media (max-width: 720px) {
  body .kc-rd-profile-visual img { object-position: 50% 0% !important; }
}''',
    'ricko': '''@media (max-width: 720px) {
  body .kc-rd-profile-visual { aspect-ratio: 1 / 1; }
  body .kc-rd-profile-name { bottom: 10px; }
}''',
    '1k-phew': '''@media (max-width: 720px) {
  body .kc-rd-profile-visual { aspect-ratio: 1 / 1; }
  body .kc-rd-profile-visual img { object-position: 50% 15% !important; }
  body .kc-rd-profile-visual::after {
    height: 30%;
    background: linear-gradient(to bottom, transparent, rgba(5,5,5,.5));
  }
  body .kc-rd-profile-name { bottom: 10px; }
}''',
}

# Page-scoped presentation only: the approved photo, optimized variants, and
# directory thumbnails stay untouched. Coordinates describe a viewport in
# fractions of the original image; out-of-bounds space provides headroom.
FRAMING_PATH = Path(__file__).resolve().parents[1] / 'config/artist-profile-framing.json'
PROFILE_FRAMING = json.loads(FRAMING_PATH.read_text())


def framing_css(slug: str) -> str:
    parts = [MOBILE_FRAMING[slug]] if slug in MOBILE_FRAMING else []
    entry = PROFILE_FRAMING.get(slug, {})
    for view, query in [('desktop', 'min-width: 721px'), ('mobile', 'max-width: 720px')]:
        frame = entry.get(view)
        if not frame:
            continue
        inset, largest = (20, 60) if view == 'desktop' else (12, 36)
        name_size = frame['nameSize']
        if not math.isfinite(name_size) or not 1 <= name_size <= 12:
            raise ValueError(f'Invalid artist name size: {slug}/{view}')
        name_css = f'''
  body .kc-rd-profile-hero {{ container-type: inline-size; }}
  body .kc-rd-profile-name {{
    left: {inset}px; right: {inset}px; bottom: {inset}px; max-width: calc(100% - {2 * inset}px);
    font-size: clamp(18px, {name_size}cqw, {largest}px); line-height: 1.08;
    letter-spacing: -.035em; overflow-wrap: normal; word-break: normal; white-space: normal;
    margin: 0; text-shadow: 0 2px 10px rgba(0,0,0,.8);
  }}'''
        if frame.get('nameOnly'):
            parts.append(f'@media ({query}) {{' + name_css + '\n}')
            continue
        x, y, width, height = frame['window']
        ratio = frame['ratio']
        brightness = frame.get('brightness', 1)
        if not all(math.isfinite(v) for v in [x, y, width, height, ratio, name_size, brightness]):
            raise ValueError(f'Non-finite artist framing: {slug}/{view}')
        if not (0 < width <= 5 and 0 < height <= 5 and .5 <= ratio <= 2 and 1 <= brightness <= 1.2):
            raise ValueError(f'Invalid artist framing: {slug}/{view}')
        parts.append(f'''@media ({query}) {{
  body .kc-rd-profile-visual {{ aspect-ratio: {ratio:.8f}; background: #160c09; }}
  body .kc-rd-profile-visual img {{
    position: absolute; width: {100 / width:.6f}% !important; height: {100 / height:.6f}% !important;
    left: {-100 * x / width:.6f}%; top: {-100 * y / height:.6f}%;
    object-fit: fill !important; max-width: none !important; transform: none !important;
    filter: brightness({brightness});
  }}
  body .kc-rd-profile-visual::after {{
    height: 24%; background: linear-gradient(to bottom, transparent, rgba(5,5,5,.65));
  }}
{name_css}
}}''')
    return '\n'.join(parts)


def text(value: str) -> str:
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', value))).strip()


def attr(tag: str, name: str) -> str:
    found = re.search(r'\b' + re.escape(name) + r'="([^"]*)"', tag)
    return html.unescape(found.group(1)) if found else ''


def local_page(site: Path, href: str, base: str) -> Path:
    url = urlsplit(href)
    path = unquote(url.path)
    if url.scheme or url.netloc or not path.startswith(base + 'event/'):
        raise ValueError(f'Expected a local event URL: {href}')
    target = (site / path[len(base):].strip('/') / 'index.html').resolve()
    if not target.is_relative_to(site.resolve()) or not target.is_file():
        raise ValueError(f'Missing or unsafe event URL: {href}')
    return target


def schema_objects(value):
    if isinstance(value, list):
        for item in value:
            yield from schema_objects(item)
    elif isinstance(value, dict):
        yield value
        if '@graph' in value:
            yield from schema_objects(value['@graph'])


def event_details(site: Path, href: str, base: str) -> tuple[str, str]:
    source = local_page(site, href, base).read_text()
    heading = re.search(r'<h1\b[^>]*>(.*?)</h1>', source, re.S)
    if not heading or not text(heading.group(1)):
        raise ValueError(f'Event title missing: {href}')
    status = re.search(r'<dt>\s*Status\s*</dt>\s*<dd>(.*?)</dd>', source, re.S | re.I)
    if status:
        label = text(status.group(1))
        # Routine "Scheduled" is not an alert; only carry meaningful exceptions.
        return text(heading.group(1)), '' if label.casefold() == 'scheduled' else label
    labels = []
    for block in re.findall(r'<script\b[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', source, re.S):
        for item in schema_objects(json.loads(block)):
            types = item.get('@type', [])
            types = [types] if isinstance(types, str) else types
            if not set(types) & {'Event', 'MusicEvent', 'Festival'}:
                continue
            label = {'EventCancelled': 'Cancelled', 'EventPostponed': 'Postponed',
                     'EventRescheduled': 'Rescheduled'}.get(str(item.get('eventStatus', '')).rsplit('/', 1)[-1])
            if label:
                labels.append(label)
            offers = item.get('offers', [])
            offers = [offers] if isinstance(offers, dict) else offers
            # A single sold-out ticket tier must not mark the entire event sold out.
            if offers and all(isinstance(o, dict) and str(o.get('availability', '')).rsplit('/', 1)[-1] == 'SoldOut' for o in offers):
                labels.append('Sold Out')
    return text(heading.group(1)), ' · '.join(dict.fromkeys(labels))


def state_links(profile: Path, name: str, base: str) -> list[tuple[str, str]]:
    result = []
    for page in sorted(profile.parent.glob('*/index.html')):
        source = page.read_text()
        heading = re.search(r'<h1\b[^>]*>(.*?)</h1>', source, re.S)
        canonical = re.search(r'<link\b[^>]*rel="canonical"[^>]*>', source)
        href = f'{base}artists/{profile.parent.name}/{page.parent.name}/'
        # Never link to empty, redirect, or noncanonical state placeholders.
        if not heading or not canonical or urlsplit(attr(canonical.group(0), 'href')).path != href:
            continue
        if re.search(r'http-equiv=["\']refresh', source, re.I):
            continue
        if not re.search(r'class="[^"]*\b(?:event-card|past-show-row)\b', source):
            continue
        label = text(heading.group(1))
        prefix = name + ' Concerts in '
        if not label.startswith(prefix):
            raise ValueError(f'Unexpected artist-state heading: {page}')
        result.append((label[len(prefix):], href))
    return sorted(result, key=lambda item: item[0].casefold())


def profile_name(source: str) -> str:
    heading = re.search(r'<h1\b[^>]*id="kc-rd-artist-name"[^>]*>(.*?)</h1>', source, re.S)
    if not heading:
        raise ValueError('Redesigned artist identity heading is missing')
    return text(heading.group(1))


def enrich_row(row: str, site: Path, base: str, *, next_show=False) -> str:
    row = EXTRA.sub('', row)
    title, status = event_details(site, attr(row.split('>', 1)[0], 'href'), base)
    extra = f'<span class="kc-rd-event-title">{html.escape(title)}</span>'
    if status:
        extra += f'<span class="kc-rd-event-status">{html.escape(status)}</span>'
    venue_class = 'kc-rd-next-venue' if next_show else 'kc-rd-show-venue'
    pattern = r'(<span class="' + venue_class + r'">.*?</span>)'
    row, count = re.subn(pattern, lambda m: m.group(1) + extra, row, count=1, flags=re.S)
    if count != 1:
        raise ValueError('Schedule row venue marker is missing')
    # Keep the old date/location/venue accessible label and append the new facts.
    opening, rest = row.split('>', 1)
    old_label = attr(opening, 'aria-label')
    if old_label:
        old_label = old_label.split(' | ', 1)[0]
        label = ' | '.join(p for p in (old_label, title, status) if p)
        opening = re.sub(r'\baria-label="[^"]*"', lambda _: 'aria-label="' + html.escape(label, quote=True) + '"', opening)
    return opening + '>' + rest


def render_profile(site: Path, profile: Path, source: str, base: str) -> str:
    name = profile_name(source)
    source = ROW.sub(lambda m: enrich_row(m.group(0), site, base), source)
    source = NEXT.sub(lambda m: enrich_row(m.group(0), site, base, next_show=True), source)
    source, count = re.subn(r'(<h2\b[^>]*id="kc-rd-shows-title"[^>]*>).*?(</h2>)',
                          lambda m: m.group(1) + html.escape(name + ' concerts & tour dates') + m.group(2), source, count=1, flags=re.S)
    if count != 1:
        raise ValueError(f'Schedule heading missing: {profile}')
    source = NAV.sub('', source)
    links = state_links(profile, name, base)
    if links:
        anchors = ''.join(f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>' for label, href in links)
        nav = ('\n    <nav class="kc-rd-artist-states" data-kc-artist-states '
               f'aria-label="{html.escape(name, quote=True)} shows by state">'
               '<span>Shows by state</span>' + anchors + '</nav>')
        source, count = re.subn(r'(<section class="kc-rd-profile-shows"[^>]*>)', lambda m: m.group(1) + nav, source, count=1)
        if count != 1:
            raise ValueError(f'Schedule section missing: {profile}')
    link = f'<link rel="stylesheet" href="{base}{CSS}?v=1" data-kc-artist-details>'
    source = re.sub(r'\s*<link\b[^>]*data-kc-artist-details[^>]*>\s*', '', source)
    source = FRAMING_STYLE.sub('', source)
    framing = framing_css(profile.parent.name)
    if framing:
        link += '\n<style data-kc-artist-framing>' + framing + '</style>'
    # The existing year finalizer owns the last style in <head>. Preserve its
    # position so its independent repeat-safety check still passes unchanged.
    if '<style data-kc-artist-schedule-years>' in source:
        return re.sub(r'\s*<style data-kc-artist-schedule-years>',
                      lambda _: '\n' + link + '\n<style data-kc-artist-schedule-years>', source, count=1)
    return re.sub(r'\s*</head>', lambda _: '\n' + link + '\n</head>', source, count=1)


def profiles(site: Path):
    for profile in sorted((site / 'artists').glob('*/index.html')):
        source = profile.read_text()
        if 'data-kc-rd-artist-profile' in source:
            yield profile, source


def check(site: Path, base: str = BASE) -> dict:
    """Check final rendered facts independently; do not repair failed checks."""
    failures = []
    counts = dict(profiles=0, showRows=0, statusRows=0, stateLinks=0)
    for profile, source in profiles(site):
        counts['profiles'] += 1
        name = profile_name(source)
        heading = re.search(r'<h2\b[^>]*id="kc-rd-shows-title"[^>]*>(.*?)</h2>', source, re.S)
        if not heading or text(heading.group(1)) != name + ' concerts & tour dates':
            failures.append(f'{profile}: schedule heading')
        expected = state_links(profile, name, base)
        navs = NAV.findall(source)
        actual = [(text(label), html.unescape(href)) for nav in navs for href, label in re.findall(r'<a href="([^"]+)">(.*?)</a>', nav, re.S)]
        if actual != expected or len(navs) != bool(expected):
            failures.append(f'{profile}: missing/duplicate/incorrect state links')
        counts['stateLinks'] += len(expected)
        for row in ROW.findall(source) + NEXT.findall(source):
            title, status = event_details(site, attr(row.split('>', 1)[0], 'href'), base)
            titles = re.findall(r'<span class="kc-rd-event-title">(.*?)</span>', row, re.S)
            statuses = re.findall(r'<span class="kc-rd-event-status">(.*?)</span>', row, re.S)
            if list(map(text, titles)) != [title] or list(map(text, statuses)) != ([status] if status else []):
                failures.append(f'{profile}: event name/status mismatch for {title}')
            if 'kc-rd-show-row' in row.split('>', 1)[0]:
                counts['showRows'] += 1
                counts['statusRows'] += bool(status)
        if f'href="{base}{CSS}?v=1"' not in source:
            failures.append(f'{profile}: details stylesheet missing')
        framing = framing_css(profile.parent.name)
        actual_framing = re.findall(r'<style data-kc-artist-framing>(.*?)</style>', source, re.S)
        if actual_framing != ([framing] if framing else []):
            failures.append(f'{profile}: approved artist framing missing or changed')
    if not counts['profiles']:
        failures.append('No artist profiles found')
    manifest = site / 'assets/live-redesign-manifest.json'
    if manifest.is_file():
        baseline = json.loads(manifest.read_text())
        for key, recorded in [('profiles', 'profilePageCount'), ('showRows', 'profileShowRowCount')]:
            if counts[key] != baseline[recorded]:
                failures.append(f'Final {key} count changed: {counts[key]} != {baseline[recorded]}')
    if not (site / CSS).is_file():
        failures.append('Details stylesheet asset missing')
    if failures:
        raise ValueError('\n'.join(failures))
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('site', type=Path)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--base', default=BASE)
    args = parser.parse_args()
    site = args.site.resolve()
    if not args.check:
        for profile, source in profiles(site):
            profile.write_text(render_profile(site, profile, source, args.base))
        shutil.copyfile(Path(__file__).resolve().parents[1] / 'assets/artist-schedule-details.css', site / CSS)
    print(json.dumps(check(site, args.base), indent=2))


if __name__ == '__main__':
    main()
