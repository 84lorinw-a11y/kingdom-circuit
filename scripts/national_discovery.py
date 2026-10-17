"""Production national discovery, promoted from reviewed test 36be2c60.

The homepage becomes a selection, never the authority for the full catalog.
Existing event/artist/location pages, data, assets and SEO identities are retained.
The new destinations are an evergreen weekend calendar and the owner's About Us page.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timedelta
from html import escape
import json
from math import ceil
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit
from zoneinfo import ZoneInfo

import mobile_discovery as mobile
from mobile_discovery import Document, replace_spans, source_html
SITE_BASE = "/"
SITE_ORIGIN = "https://kingdomcircuit.com"

ROOT = Path(__file__).resolve().parents[1]
VERSION = '20261017-live-1'
ASSETS = ('national-discovery.css', 'national-discovery.js', 'fan-discovery.css', 'fan-discovery.js')
WEEKEND_PATH = 'shows/this-weekend/index.html'
WEEKEND_HREF = SITE_BASE + 'shows/this-weekend/'
ABOUT_PATH = 'about-us/index.html'
ABOUT_HREF = SITE_BASE + 'about-us/'
HOME_HEADING = 'Find CHH Shows Near You!'
HOME_SUBTITLE = 'CHH concerts, christian rap shows and festivals!'
# Owner-selected homepage order; only promote artists already eligible below.
# Canonical profile slugs keep this independent of roster order and aliases.
HOME_ARTIST_PRIORITY = ('whatuprg', 'brenno', '1k-phew', 'joz', 'tru-serva', 'cj-emulous')
# Circle-only crops, visually reviewed on the exact current photos. Never apply
# an old crop to a replacement photo or change directory/profile image framing.
# asset, intrinsic width/height, object-position, scale, transform-origin
HOME_ARTIST_CIRCLE_CROPS = {
    '1k-phew': ('6df7b566d71761e10c8e1cb9-w639.webp', 639, 960, '50% 12%', 1.05, '50% 0%'),
    'cj-emulous': ('4c8ff9f99d115317dfbf4ebc-w1280.webp', 1280, 1920, '50% 15%', 1.55, '0% 0%'),
    'zay-lowly': ('1ef856d020303e85e2b334b5-w562.webp', 562, 1000, '50% 0%', 1.5, '100% 0%'),
    'shaquille-jones': ('b4cdb3853ce544c6c633adc6-w640.webp', 640, 427, '78% 35%', 1, '50% 50%'),
    'scarlito-jr': ('296279fcb910860da24b7c07-w529.webp', 529, 640, '50% 0%', 1.5, '95% 0%'),
}
FACEBOOK_HREF = 'https://www.facebook.com/profile.php?id=61593510924754'
FACEBOOK_BUTTON = (f'<a class="kc-facebook-button" href="{FACEBOOK_HREF}" target="_blank" rel="noopener noreferrer" '
                   'aria-label="Kingdom Circuit on Facebook (opens in new tab)" title="Follow Kingdom Circuit on Facebook">'
                   '<svg class="kc-facebook-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
                   '<circle cx="12" cy="12" r="11" fill="#0866ff"/>'
                   '<path fill="#fff" d="M13.5 22v-8h2.7l.4-3h-3.1V9c0-.9.3-1.5 1.6-1.5H17V4.8c-.3 0-1.4-.1-2.6-.1-2.6 0-4.4 1.6-4.4 4.5V11H7.2v3H10v8Z"/>'
                   '</svg></a>')
CARD_IMAGE_RATIO = '1092 / 1440'  # Approved Brenno poster frame for every shape.
# Visually reviewed empty/decorative margins only. Match the exact asset and
# dimensions, not an event/artist name, so replacement flyers default to contain.
# Bounds are left, top, right, bottom as fractions of the original image.
ARTWORK_SAFE_BOUNDS = {
    '1914811f461045f3cde8d98a-w720.webp': (720, 1010, (0, .018, 1, .982)),  # CJ: blank top/bottom paper
    'fb18ec129d915d345e02bd1d-w608.webp': (608, 1080, (0, .10, 1, .87)),  # Faith Fest: yellow top/bottom space
    '3a35b500fb25a34f0df71c80-w720.webp': (720, 720, (.045, 0, .955, 1)),  # Mission: side margins, keep date/tickets
    'bc7652d5faeb8580c20b76c8-w1280.webp': (1280, 1600, (.026, 0, .974, 1)),  # CENDIA: decorative sides
    '9aaded4384127f8719630099-w1280.webp': (1280, 1280, (.12, 0, .88, 1)),  # Sazon: empty orange sides
    'cde71a5a77b9203a03388413-w720.webp': (720, 1280, (0, .145, 1, .855)),  # Family Day: embedded black bars
}
SEARCH_ICON = '<svg class="kc-search-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="m16 16 5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'

# Land-border neighbors only. Islands do not get invented "nearby" states.
STATE_NEIGHBORS = {
    'Alabama': 'Florida|Georgia|Mississippi|Tennessee',
    'Alaska': '', 'Arizona': 'California|Nevada|Utah|New Mexico',
    'Arkansas': 'Louisiana|Mississippi|Missouri|Oklahoma|Tennessee|Texas',
    'California': 'Arizona|Nevada|Oregon', 'Colorado': 'Kansas|Nebraska|New Mexico|Oklahoma|Utah|Wyoming',
    'Connecticut': 'Massachusetts|New York|Rhode Island', 'Delaware': 'Maryland|New Jersey|Pennsylvania',
    'District of Columbia': 'Maryland|Virginia', 'Florida': 'Alabama|Georgia',
    'Georgia': 'Alabama|Florida|North Carolina|South Carolina|Tennessee', 'Hawaii': '',
    'Idaho': 'Montana|Nevada|Oregon|Utah|Washington|Wyoming',
    'Illinois': 'Indiana|Iowa|Kentucky|Missouri|Wisconsin', 'Indiana': 'Illinois|Kentucky|Michigan|Ohio',
    'Iowa': 'Illinois|Minnesota|Missouri|Nebraska|South Dakota|Wisconsin',
    'Kansas': 'Colorado|Missouri|Nebraska|Oklahoma', 'Kentucky': 'Illinois|Indiana|Missouri|Ohio|Tennessee|Virginia|West Virginia',
    'Louisiana': 'Arkansas|Mississippi|Texas', 'Maine': 'New Hampshire',
    'Maryland': 'Delaware|District of Columbia|Pennsylvania|Virginia|West Virginia',
    'Massachusetts': 'Connecticut|New Hampshire|New York|Rhode Island|Vermont',
    'Michigan': 'Indiana|Ohio|Wisconsin', 'Minnesota': 'Iowa|North Dakota|South Dakota|Wisconsin',
    'Mississippi': 'Alabama|Arkansas|Louisiana|Tennessee',
    'Missouri': 'Arkansas|Illinois|Iowa|Kansas|Kentucky|Nebraska|Oklahoma|Tennessee',
    'Montana': 'Idaho|North Dakota|South Dakota|Wyoming',
    'Nebraska': 'Colorado|Iowa|Kansas|Missouri|South Dakota|Wyoming', 'Nevada': 'Arizona|California|Idaho|Oregon|Utah',
    'New Hampshire': 'Maine|Massachusetts|Vermont', 'New Jersey': 'Delaware|New York|Pennsylvania',
    'New Mexico': 'Arizona|Colorado|Oklahoma|Texas', 'New York': 'Connecticut|Massachusetts|New Jersey|Pennsylvania|Vermont',
    'North Carolina': 'Georgia|South Carolina|Tennessee|Virginia', 'North Dakota': 'Minnesota|Montana|South Dakota',
    'Ohio': 'Indiana|Kentucky|Michigan|Pennsylvania|West Virginia',
    'Oklahoma': 'Arkansas|Colorado|Kansas|Missouri|New Mexico|Texas', 'Oregon': 'California|Idaho|Nevada|Washington',
    'Pennsylvania': 'Delaware|Maryland|New Jersey|New York|Ohio|West Virginia', 'Puerto Rico': '',
    'Rhode Island': 'Connecticut|Massachusetts', 'South Carolina': 'Georgia|North Carolina',
    'South Dakota': 'Iowa|Minnesota|Montana|Nebraska|North Dakota|Wyoming',
    'Tennessee': 'Alabama|Arkansas|Georgia|Kentucky|Mississippi|Missouri|North Carolina|Virginia',
    'Texas': 'Arkansas|Louisiana|New Mexico|Oklahoma', 'Utah': 'Arizona|Colorado|Idaho|Nevada|Wyoming',
    'Vermont': 'Massachusetts|New Hampshire|New York', 'Virginia': 'District of Columbia|Kentucky|Maryland|North Carolina|Tennessee|West Virginia',
    'Washington': 'Idaho|Oregon', 'West Virginia': 'Kentucky|Maryland|Ohio|Pennsylvania|Virginia',
    'Wisconsin': 'Illinois|Iowa|Michigan|Minnesota', 'Wyoming': 'Colorado|Idaho|Montana|Nebraska|South Dakota|Utah',
}


def neighbor_states(state, states):
    names = STATE_NEIGHBORS.get(state['name'], '').split('|')
    return sorted((s for s in states if s['name'] in names and s['count'] > 0),
                  key=lambda s: (-s['count'], s['name']))


def today():
    # Match the published catalog's existing expiration boundary.
    return datetime.now(ZoneInfo('America/Los_Angeles')).date()


def weekend_window(day):
    offset = 4 - day.weekday() if day.weekday() >= 4 else (4 - day.weekday()) % 7
    friday = day + timedelta(days=offset)
    return friday, friday + timedelta(days=2)


def date_label(first, last):
    if first.year != last.year:
        return f'{first:%b} {first.day}, {first.year} – {last:%b} {last.day}, {last.year}'
    if first.month != last.month:
        return f'{first:%b} {first.day} – {last:%b} {last.day}, {last.year}'
    return f'{first:%B} {first.day}–{last.day}, {last.year}'


def weekend_matches(start, end, day):
    first, last = weekend_window(day)
    start, end = date.fromisoformat(start), date.fromisoformat(end or start)
    return start <= last and end >= max(first, day)


def week_end(day):
    return day + timedelta(days=6 - day.weekday())


def home_selection(context):
    """Two nonoverlapping, date-driven shelves; never invent popularity."""
    day = context['as_of']
    end = week_end(day)
    eligible = sorted((r for r in context['active'] if feature_eligible(r)),
                      key=lambda r: r['attrs']['data-date'])
    week = [r for r in eligible if r['attrs']['data-date'] <= end.isoformat()]
    following_end = end + timedelta(days=7)
    following = [r for r in eligible if end.isoformat() < r['attrs']['data-date'] <= following_end.isoformat()]
    return week, following


def card_records(text):
    doc = Document(text)
    records = []
    for node in doc.nodes:
        if 'data-event-card' not in node.attrs:
            continue
        fragment = Document(doc.raw(node))
        title = fragment.one(lambda n: n.tag == 'h3')
        link = next(n for n in title.children if n.tag == 'a')
        image = fragment.one(lambda n: n.tag == 'img')
        artists = fragment.one(lambda n: n.has('artist-line'))
        badges = fragment.one(lambda n: n.has('event-badges'))
        meta = {}
        for dt in (n for n in fragment.nodes if n.tag == 'dt'):
            dd = next(n for n in fragment.nodes if n.tag == 'dd' and n.start >= dt.end)
            meta[fragment.text(dt)] = fragment.text(dd)
        records.append({'html': doc.raw(node), 'attrs': node.attrs, 'href': link.attrs['href'],
                        'name': fragment.text(title), 'image': fragment.raw(image),
                        'artists': fragment.raw(artists), 'badges': fragment.raw(badges), 'meta': meta})
    hrefs = [r['href'] for r in records]
    assert len(set(hrefs)) == len(hrefs), 'Duplicate event destinations in catalog'
    return records


def feature_eligible(record):
    # Respect existing owner guidance: keep school/private/TBA/cancelled listings
    # available, but do not automatically promote them as public shows on home.
    text = (record['name'] + ' ' + ' '.join(record['meta'].values()) + ' ' + record['badges']).lower()
    return not any(x in text for x in ('cancelled', 'canceled', 'sold out', 'details pending',
                                     'postponed', 'invite only', 'school', 'venue to be announced', 'venue not provided'))


def search_portrait(image):
    """Use an existing small directory-photo variant, not a show flyer or new asset."""
    attrs = Document(image).one(lambda n: n.tag == 'img').attrs
    candidates = []
    for item in attrs.get('srcset', '').split(','):
        match = re.fullmatch(r'\s*(\S+)\s+(\d+)w\s*', item)
        if match and match[1].startswith(SITE_BASE + 'assets/'):
            candidates.append((int(match[2]), match[1]))
    candidates.sort()
    src = next((src for width, src in candidates if width >= 216),
               candidates[-1][1] if candidates else attrs.get('src', ''))
    if not src.startswith(SITE_BASE + 'assets/'):
        return {}
    position = 'center'
    for declaration in attrs.get('style', '').split(';'):
        key, _, value = declaration.partition(':')
        if key.strip() == 'object-position' and re.fullmatch(r'[\w.%+\-\s]+', value.strip()):
            position = value.strip()
    return {'src': src, 'position': position}


def featured_artist_hrefs(upcoming):
    """Prioritize eligible owner picks, then preserve next-show discovery order."""
    priority = [SITE_BASE + 'artists/' + slug + '/' for slug in HOME_ARTIST_PRIORITY]
    ordered = list(dict.fromkeys(upcoming))
    return ([href for href in priority if href in ordered]
            + [href for href in ordered if href not in priority])[:40]


def load_context(live, as_of):
    states = mobile.catalog(live)
    baseline_states = states
    records = card_records(source_html(live, 'shows/index.html'))
    active = [r for r in records if (r['attrs'].get('data-end-date') or r['attrs']['data-date']) >= as_of.isoformat()]
    weekend = [r for r in active if weekend_matches(r['attrs']['data-date'], r['attrs'].get('data-end-date'), as_of)]
    directory = Document(source_html(live, 'artists/index.html'))
    portraits = {}
    for node in directory.nodes:
        if 'data-artist-card' not in node.attrs:
            continue
        part = Document(directory.raw(node))
        heading = part.one(lambda n: n.tag == 'h2')
        link = next(n for n in heading.children if n.tag == 'a')
        portraits[link.attrs['href']] = {'name': part.text(heading),
                                        'image': part.raw(part.one(lambda n: n.tag == 'img'))}
    counts = Counter()
    upcoming = []
    for record in active:
        fragment = Document(record['artists'])
        for link in (n for n in fragment.nodes if n.tag == 'a'):
            href = link.attrs['href']
            counts[href] += 1
            if feature_eligible(record) and href in portraits and href not in upcoming:
                upcoming.append(href)
    # Counts cover every show. Owner picks lead only while eligible; the rest
    # retain next-show order. Apply priority before the 40-artist shelf limit.
    artists = [{**portraits[href], 'href': href, 'count': counts[href]}
               for href in featured_artist_hrefs(upcoming)]
    # Recalculate recommendation counts from the current, unexpired calendar.
    state_counts = Counter(r['attrs'].get('data-state', '') for r in active)
    states = [{**s, 'count': state_counts[s['code']] if s['code'] else 0} for s in states]
    active_by_href = {r['href']: r for r in active}
    recent = [active_by_href[r['href']] for r in card_records(source_html(live, 'new-shows/index.html'))
              if r['href'] in active_by_href]
    search_artists = [{'name': p['name'], 'href': href, 'count': counts[href],
                       'portrait': search_portrait(p['image'])} for href, p in portraits.items()]
    return {'states': states, 'baseline_states': baseline_states, 'records': records, 'active': active, 'weekend': weekend,
            'artists': artists, 'artist_total': len(portraits), 'search_artists': search_artists,
            'recent': recent, 'as_of': as_of}


def section_heading(eyebrow, title, href, action, ident):
    return (f'<header class="kc-discovery-heading"><div><p class="eyebrow">{escape(eyebrow)}</p>'
            f'<h2 id="{ident}">{escape(title)}</h2></div><a href="{href}">{escape(action)} <span aria-hidden="true">↗</span></a></header>')


def artwork_layout(image_html):
    """Classify source artwork but use the same approved Brenno frame for all."""
    image = Document(image_html).one(lambda n: n.tag == 'img')
    try:
        width, height = int(image.attrs.get('width', '')), int(image.attrs.get('height', ''))
    except ValueError:
        return 'unknown', CARD_IMAGE_RATIO
    if width <= 0 or height <= 0:
        return 'unknown', CARD_IMAGE_RATIO
    ratio = width / height
    if ratio < .65:
        return 'tall', CARD_IMAGE_RATIO
    shape = 'portrait' if ratio < .9 else 'square' if ratio <= 1.1 else 'landscape'
    return shape, CARD_IMAGE_RATIO


def artwork_presentation(image_html):
    """CSS-only framing: keep original files and full event-page posters intact."""
    image = Document(image_html).one(lambda n: n.tag == 'img')
    try:
        width, height = int(image.attrs.get('width', '')), int(image.attrs.get('height', ''))
    except ValueError:
        return 'contain', '', 178
    if width <= 0 or height <= 0:
        return 'contain', '', 178
    frame_ratio = 1092 / 1440
    if image.has('artist-photo'):
        return 'photo-fill', '', ceil(max(178, 178 / frame_ratio * width / height))
    reviewed = ARTWORK_SAFE_BOUNDS.get(Path(urlsplit(image.attrs.get('src', '')).path).name)
    if not reviewed or (width, height) != reviewed[:2]:
        return 'contain', '', 178
    left, top, right, bottom = reviewed[2]
    assert 0 <= left < right <= 1 and 0 <= top < bottom <= 1
    # Fit the reviewed content rectangle, never distort it. Any remaining
    # margins are intentional: content touching an edge must not be cut off.
    frame_height = 1 / frame_ratio
    scale = min(1 / (width * (right - left)), frame_height / (height * (bottom - top)))
    rendered_width, rendered_height = width * scale, height * scale
    x = (1 - rendered_width * (right - left)) / 2 - rendered_width * left
    y = (frame_height - rendered_height * (bottom - top)) / 2 - rendered_height * top
    style = ';'.join(f'--kc-art-{key}:{value * 100:.5f}%'
                     for key, value in [('w', rendered_width), ('h', rendered_height / frame_height),
                                        ('x', x), ('y', y / frame_height)])
    return 'border-trim', style, ceil(rendered_width * 178)


def teaser(record, image=True, eager=False):
    attrs = record['attrs']
    picture = ''
    shape, ratio = artwork_layout(record['image']) if image else ('unknown', CARD_IMAGE_RATIO)
    if image:
        treatment, framing, rendered_width = artwork_presentation(record['image'])
        # Preserve image identity/focal metadata; request enough pixels for zoom.
        responsive_image = re.sub(r'sizes="[^"]*"', f'sizes="{rendered_width}px"', record['image'])
        if 'sizes=' not in responsive_image:
            responsive_image = responsive_image.replace('<img ', f'<img sizes="{rendered_width}px" ', 1)
        if eager:
            responsive_image = responsive_image.replace('loading="lazy"', 'loading="eager" fetchpriority="high"')
        picture = (f'<a class="kc-teaser-image" href="{record["href"]}" tabindex="-1" aria-hidden="true" '
                   f'data-artwork-treatment="{treatment}" style="{framing}">{responsive_image}</a>')
    return (f'<article class="kc-discovery-show" data-discovery-show data-artwork-shape="{shape}" '
            f'style="--kc-artwork-ratio:{ratio}" data-date="{attrs["data-date"]}" '
            f'data-end-date="{attrs.get("data-end-date") or attrs["data-date"]}">'
            f'{picture}<div class="kc-teaser-copy">{record["badges"]}'
            f'<p class="kc-teaser-date" title="{escape(record["meta"].get("Date", ""))}">{escape(record["meta"].get("Date", ""))}</p>'
            f'<h3><a href="{record["href"]}" title="{escape(record["name"])}">{escape(record["name"])}</a></h3>'
            f'{record["artists"]}<p class="kc-teaser-location" title="{escape(record["meta"].get("Location", ""))}">{escape(record["meta"].get("Location", ""))}</p>'
            f'<p class="kc-teaser-venue" title="{escape(record["meta"].get("Venue", ""))}">{escape(record["meta"].get("Venue", ""))}</p></div></article>')


def circle_portrait(artist):
    """Keep real image bytes/variants and scope reviewed framing to this shelf."""
    image = artist['image']
    slug = artist['href'].removeprefix(SITE_BASE + 'artists/').strip('/')
    crop = HOME_ARTIST_CIRCLE_CROPS.get(slug)
    if not crop:
        return image
    attrs = Document(image).one(lambda n: n.tag == 'img').attrs
    asset, width, height, position, scale, origin = crop
    if (Path(urlsplit(attrs.get('src', '')).path).name != asset
            or attrs.get('width') != str(width) or attrs.get('height') != str(height)):
        return image
    declarations = [s.strip() for s in attrs.get('style', '').split(';')
                    if s.strip() and s.partition(':')[0].strip() not in
                    ('object-position', 'transform', 'transform-origin')]
    declarations += [f'object-position:{position}', f'transform:scale({scale})',
                     f'transform-origin:{origin}']
    style = 'style="' + escape(';'.join(declarations), quote=True) + '"'
    if 'style' in attrs:
        return re.sub(r'style="[^"]*"', lambda _: style, image, count=1)
    return image.replace('<img ', '<img ' + style + ' ', 1)


def artist_tile(artist):
    # The adjacent visible name labels this single link; avoid reading it twice.
    image = re.sub(r'alt="[^"]*"', 'alt=""', circle_portrait(artist))
    image = re.sub(r'sizes="[^"]*"',
                   'sizes="(min-width: 1000px) 170px, (min-width: 700px) 30vw, 45vw"', image)
    count = artist['count']
    return (f'<a class="kc-discovery-artist" href="{artist["href"]}"><div>{image}</div>'
            f'<strong>{escape(artist["name"])}</strong><span>{count} upcoming show{"s" if count != 1 else ""}</span></a>')


def home_content(text, context):
    doc = Document(text)
    title = f'<h1 class="kc-rd-home-title">{HOME_HEADING}</h1>'
    states = context['states']
    state_finder = Document(mobile.finder(states))
    disclosure = state_finder.raw(state_finder.one(lambda n: n.tag == 'details'))
    primary, following = home_selection(context)
    options = ''.join(f'<option value="{s["code"] or s["name"]}" data-state-href="{s["href"]}">{escape(s["name"])}</option>' for s in states)
    tiles = ''.join(artist_tile(a) for a in context['artists'])
    out = f'''<div class="kc-discovery-home kc-fan-home" data-national-home>
<section class="kc-discovery-hero" aria-label="Find your next show">
<div class="kc-discovery-intro">{title}
<p class="kc-discovery-deck">{HOME_SUBTITLE}</p>
</div><form class="kc-discovery-search kc-fan-finder" action="{SITE_BASE}shows/" method="get" role="search" data-fan-finder>
<div class="kc-fan-where-when"><label for="kc-home-state">State<select id="kc-home-state" name="state"><option value="">All states</option>{options}</select></label>
<label for="kc-home-dates">Dates<select id="kc-home-dates" name="dates"><option value="all">All dates</option><option value="week">This week</option><option value="weekend">This weekend</option><option value="upcoming">Next week</option><option value="next30">Next 30 days</option><option value="month">This month</option></select></label></div>
<label class="kc-discovery-sr-only" for="kc-home-search">Search shows by artist, city, venue or show name</label><div class="kc-fan-search-line"><input id="kc-home-search" name="q" type="search" placeholder="Artist, city, venue or show" maxlength="160" autocomplete="off"><button type="submit">{SEARCH_ICON} Search</button></div></form>
</section>
<section class="kc-discovery-section" id="calendar" aria-labelledby="kc-weekend-heading" data-preview-week-end="{week_end(context['as_of'])}">
{section_heading(date_label(context['as_of'], week_end(context['as_of'])) + ' · Nationwide', 'Happening This Week', SITE_BASE + 'shows/?dates=week', 'View all', 'kc-weekend-heading')}
{shelf('kc-week-shelf', ''.join(teaser(r, eager=i == 0) for i, r in enumerate(primary)), 'Happening This Week')}
<p class="kc-discovery-empty" data-discovery-empty{' hidden' if primary else ''}>No more featured shows this week. Explore the next dates below or <a href="{SITE_BASE}shows/">browse all shows.</a></p></section>
'''
    if tiles:
        out += (f'<section class="kc-discovery-section" aria-labelledby="kc-artists-heading">'
                + section_heading('Follow the music', 'Artists with upcoming shows', SITE_BASE + 'artists/', 'All artists', 'kc-artists-heading')
                + shelf('kc-artist-shelf', tiles, 'Artists with upcoming shows', artists=True) + '</section>')
    out += f'''<section class="kc-discovery-section" aria-labelledby="kc-next-heading" data-preview-week-end="{week_end(context['as_of'])}">
{section_heading(date_label(week_end(context['as_of']) + timedelta(days=1), week_end(context['as_of']) + timedelta(days=7)) + ' · Nationwide', 'Coming Up Next', SITE_BASE + 'shows/?dates=upcoming', 'View all', 'kc-next-heading')}
{shelf('kc-next-shelf', ''.join(teaser(r) for r in following), 'Coming Up Next')}
<p class="kc-discovery-empty" data-discovery-empty{' hidden' if following else ''}>No featured shows listed for next week yet. <a href="{SITE_BASE}shows/">Explore all shows.</a></p></section>'''
    out += (f'<section class="kc-fan-explore" id="browse-states" aria-label="Browse shows by state">'
            '<h2>Find your next night out</h2><div class="kc-discovery-counts">'
            f'<a class="kc-discovery-primary" href="{SITE_BASE}shows/">Browse all {len(context["active"])} shows <span aria-hidden="true">↗</span></a>'
            f'<a class="kc-discovery-artist-count" href="{SITE_BASE}artists/"><strong>{context["artist_total"]}</strong> artists <span aria-hidden="true">↗</span></a></div>'
            f'<div class="kc-fan-explore-links"><a href="{SITE_BASE}festivals/">Festivals ↗</a><a href="{WEEKEND_HREF}">This weekend ↗</a><a href="{SITE_BASE}shows/this-month/">This month ↗</a></div>{disclosure}</section>')
    out += (f'<section class="kc-discovery-submit"><div><h2>Know a show we should list?</h2>'
            f'<p>Help more people find live Christian hip-hop.</p></div><a href="{SITE_BASE}submit/">Submit a show <span aria-hidden="true">↗</span></a></section></div>')
    main = doc.one(lambda n: n.tag == 'main')
    result = replace_spans(text, [(main.opening_end, main.closing_start, out)])
    # Home is now delivered content, not a duplicate app-rendered full calendar.
    return re.sub(r'<script\b[^>]*src="' + re.escape(SITE_BASE) + r'app\.js[^\"]*"[^>]*>\s*</script>',
                  f'<script src="{SITE_BASE}seo-static.js?v=1" defer></script>', result)


def shelf(ident, content, label, artists=False):
    cls = 'kc-discovery-artists' if artists else 'kc-teaser-grid'
    return (f'<div class="kc-fan-shelf-wrap" data-fan-shelf><div class="{cls} kc-fan-shelf" id="{ident}" '
            f'role="region" aria-label="{escape(label)}" tabindex="0">{content}</div>'
            f'<div class="kc-fan-shelf-controls" hidden><span>Swipe to explore</span><button type="button" data-shelf-prev aria-label="Previous {escape(label)}" aria-controls="{ident}">←</button>'
            f'<button type="button" data-shelf-next aria-label="Next {escape(label)}" aria-controls="{ident}">→</button></div></div>')


def add_shared_navigation(text, relative):
    doc = Document(text)
    footers = [n for n in doc.nodes if n.has('footer-links')]
    changes = []
    for actions in (n for n in doc.nodes if n.has('kc-rd-actions')):
        instagram = [n for n in actions.children if n.has('kc-rd-instagram-button')]
        if instagram:
            assert len(instagram) == 1 and not any(n.has('kc-facebook-button') for n in actions.children), 'Review changed upstream header social links'
            changes.append((instagram[0].end, instagram[0].end, FACEBOOK_BUTTON))
    for nav in (n for n in doc.nodes if n.has('kc-rd-nav')):
        links = [n for n in nav.children if n.tag == 'a']
        assert len(links) == 6, 'Primary navigation changed upstream; review the eight-link contract'
        content = ''
        for link in links:
            raw = doc.raw(link)
            if relative in {WEEKEND_PATH, ABOUT_PATH}:
                raw = raw.replace(' aria-current="page"', '')
            content += raw
            if link.attrs.get('href') == SITE_BASE + 'shows/':
                active = ' aria-current="page"' if relative == WEEKEND_PATH else ''
                content += f'<a href="{WEEKEND_HREF}"{active}>This Weekend</a>'
        active = ' aria-current="page"' if relative == ABOUT_PATH else ''
        content += f'<a href="{ABOUT_HREF}"{active}>About Us</a>'
        changes.append((nav.start, nav.end,
                        f'<nav class="kc-rd-nav" aria-label="Primary navigation" data-compact-navigation>{content}</nav>'))
    if footers:
        node = footers[0]
        changes.append((node.opening_end, node.opening_end,
                        f'<a href="{WEEKEND_HREF}">This Weekend</a><a href="{ABOUT_HREF}">About Us</a>'))
    # Existing artist identity, schedules, social links and archives are untouched.
    if relative.startswith('artists/') and relative != 'artists/index.html':
        shells = [n for n in doc.nodes if 'data-kc-rd-artist-profile' in n.attrs]
        if shells:
            title = doc.one(lambda n: n.tag == 'h1')
            crumb = (f'<nav class="kc-discovery-breadcrumb" aria-label="Breadcrumb">'
                     f'<a href="{SITE_BASE}">Home</a><span aria-hidden="true">/</span>'
                     f'<a href="{SITE_BASE}artists/">Artists</a><span aria-hidden="true">/</span>'
                     f'<span aria-current="page">{escape(doc.text(title))}</span></nav>')
            changes.append((shells[0].start, shells[0].start, crumb))
    if relative == 'artists/index.html':
        heading = doc.one(lambda n: n.tag == 'h1')
        changes.append((heading.end, heading.end,
                        '<p class="kc-directory-guide">Find artist profiles, official socials, and upcoming and past shows.</p>'))
    # Contextual destination for the existing in-place weekend filter, not a new
    # replacement filter or a page for every combination of controls.
    if relative in {'shows/index.html', 'shows/this-month/index.html', 'new-shows/index.html', 'festivals/index.html'}:
        heading = doc.one(lambda n: n.has('calendar-heading'))
        changes.append((heading.end, heading.end,
                        f'<p class="kc-weekend-route"><a href="{WEEKEND_HREF}">Explore this weekend’s CHH shows <span aria-hidden="true">↗</span></a></p>'))
    return replace_spans(text, changes)


def artist_details(text, context):
    """Keep the compact schedule; restore the original full cards directly below it."""
    doc = Document(text)
    shells = [n for n in doc.nodes if 'data-kc-rd-artist-profile' in n.attrs]
    if not shells:
        return text
    schedules = [n for n in doc.nodes if n.has('kc-rd-profile-shows')]
    if not schedules:
        return text
    hrefs = [n.attrs['href'] for n in doc.nodes if n.has('kc-rd-show-row')]
    if not hrefs:
        return text  # A truthful empty schedule, not fabricated filler.
    records = {r['href']: r for r in context['records']}
    missing = set(hrefs) - records.keys()
    assert not missing, f'Artist schedule lacks matching full event cards: {missing}'
    cards = ''.join(records[href]['html'] for href in hrefs)
    section = ('<section class="kc-artist-show-details" data-artist-show-details aria-labelledby="kc-full-show-details">'
               '<h2 id="kc-full-show-details">Upcoming show details</h2>'
               f'<div class="event-grid">{cards}</div></section>')
    return replace_spans(text, [(schedules[0].end, schedules[0].end, section)])


def nearby_state_section(text, name, context):
    state = next((s for s in context['states'] if s['relative'] == name), None)
    if not state or state['count']:
        return text
    neighbors = neighbor_states(state, context['states'])
    if not neighbors:
        return text  # Existing national fallback remains available.
    doc = Document(text)
    calendar = doc.one(lambda n: n.has('calendar'))
    links = ''.join(mobile.state_link(s) for s in neighbors)
    block = ('<section class="kc-neighbor-states" data-neighbor-states aria-labelledby="kc-neighbor-title">'
             '<h2 id="kc-neighbor-title">Explore shows in neighboring states</h2>'
             '<p>These states have upcoming shows. Check the city and travel distance before making plans.</p>'
             f'<nav class="kc-state-links" aria-label="Neighboring states with shows">{links}</nav></section>')
    return replace_spans(text, [(calendar.end, calendar.end, block)])


def transform(relative, source, context):
    name = relative.as_posix()
    if name == 'sitemap.xml':
        text = source.decode()
        additions = ''
        for path in ('/shows/this-weekend/', '/about-us/'):
            url = SITE_ORIGIN + path
            assert url not in text, f'{path} already exists in baseline; review the overlay'
            additions += f'<url><loc>{url}</loc></url>\n'
        return text.replace('</urlset>', additions + '</urlset>').encode()
    if relative.suffix != '.html' or name.startswith('test-'):
        return source
    text = source.decode()
    if '<main' not in text or 'class="site-footer"' not in text or not re.search(r'<h1\b', text):
        return source  # Redirect documents and error shells keep their exact behavior.
    if 'data-national-discovery' in text:
        raise ValueError('National discovery overlay must run once')
    if name == 'index.html':
        text = home_content(text, context)
    text = add_shared_navigation(text, name)
    text = artist_details(text, context)
    text = nearby_state_section(text, name, context)
    assets = (f'<link rel="stylesheet" href="{SITE_BASE}assets/{ASSETS[0]}?v={VERSION}" data-national-discovery>'
              f'<script src="{SITE_BASE}assets/{ASSETS[1]}?v={VERSION}" defer></script>'
              f'<link rel="stylesheet" href="{SITE_BASE}assets/{ASSETS[2]}?v={VERSION}">'
              f'<script src="{SITE_BASE}assets/{ASSETS[3]}?v={VERSION}" defer></script>')
    if 'data-event-filters' in text:
        # These pages already contain the complete route-specific calendar.
        # Do not let the old app bootstrap replace an empty state/week with all shows.
        text = re.sub(r'<script\b[^>]*src="' + re.escape(SITE_BASE) + r'app\.js[^\"]*"[^>]*>\s*</script>',
                      f'<script src="{SITE_BASE}seo-static.js?v=1" defer></script>', text)
    if 'data-event-filters' in text or 'data-fan-finder' in text:
        data = json.dumps(context.get('search_artists', []), ensure_ascii=True).replace('<', '\\u003c')
        assets += f'<script type="application/json" id="kc-fan-artists">{data}</script>'
        neighbors = {}
        for state in context['states']:
            entry = {'name': state['name'], 'href': state['href'],
                     'neighbors': [{k: s[k] for k in ('name', 'href', 'count')} for s in neighbor_states(state, context['states'])]}
            neighbors[state['code'] or state['name']] = entry
            neighbors[state['name']] = entry
        assets += '<script type="application/json" id="kc-fan-neighbors">' + json.dumps(neighbors, ensure_ascii=True).replace('<', '\\u003c') + '</script>'
    return text.replace('</head>', assets + '</head>', 1).encode()



def weekend_page(live, context):
    text = source_html(live, 'shows/index.html')
    text = mobile.transform(Path('shows/index.html'), text.encode(), context['states']).decode()
    doc = Document(text)
    first, last = weekend_window(context['as_of'])
    label = date_label(first, last)
    title = 'CHH Concerts & Shows This Weekend | Kingdom Circuit'
    description = f'Find Christian hip-hop concerts, Christian rap shows and festivals for {label} across the U.S. Browse artists, venues and official event details.'
    canonical = SITE_ORIGIN + '/shows/this-weekend/'
    changes = []
    hero = doc.one(lambda n: n.tag == 'section' and n.has('page-hero'))
    changes.append((hero.start, hero.end,
                    f'<section class="page-hero hero-compact kc-weekend-hero" data-weekend-page data-weekend-end="{last}">'
                    f'<p class="eyebrow">Friday through Sunday · {escape(label)}</p>'
                    f'<h1>Christian Hip-Hop Shows This Weekend</h1><p class="hero-text">'
                    f'Explore {len(context["weekend"])} upcoming CHH concerts, festivals and live events across the U.S. '
                    'Dates and times follow each event’s local listing.</p>'
                    f'<p class="kc-weekend-expired" hidden>These dates have passed. <a href="{SITE_BASE}shows/">Browse all upcoming shows.</a></p></section>'))
    grid = doc.one(lambda n: n.has('event-grid'))
    changes.append((grid.opening_end, grid.closing_start, ''.join(r['html'] for r in context['weekend'])))
    filters = doc.one(lambda n: 'data-event-filters' in n.attrs)
    form = doc.raw(filters)
    for attr in ('data-artist-filter', 'data-state-filter'):
        fd = Document(form)
        select = fd.one(lambda n: n.tag == 'select' and attr in n.attrs)
        first_option = select.children[0]
        form = replace_spans(form, [(first_option.end, select.closing_start, '')])
    changes.append((filters.start, filters.end, form))
    for n in doc.nodes:
        if n.has('quick-filters'):
            changes.append((n.start, n.end, ''))
        if n.tag == 'title':
            changes.append((n.start, n.end, f'<title>{escape(title)}</title>'))
        if n.tag == 'meta':
            key = n.attrs.get('name') or n.attrs.get('property')
            value = {'description': description, 'og:description': description, 'twitter:description': description,
                     'og:title': title, 'twitter:title': title, 'og:url': canonical}.get(key)
            if value:
                raw = re.sub(r'content="[^"]*"', f'content="{escape(value, quote=True)}"', doc.raw(n))
                changes.append((n.start, n.end, raw))
        if n.tag == 'link' and n.attrs.get('rel') == 'canonical':
            changes.append((n.start, n.end, f'<link rel="canonical" href="{canonical}">'))
        if n.tag == 'script' and n.attrs.get('type') == 'application/ld+json':
            schema = {'@context': 'https://schema.org', '@type': 'CollectionPage',
                      'name': 'Christian Hip-Hop Shows This Weekend', 'description': description,
                      'url': canonical, 'isPartOf': {'@type': 'WebSite', 'name': 'The Kingdom Circuit', 'url': SITE_ORIGIN + '/'}}
            changes.append((n.start, n.end, '<script type="application/ld+json">' + json.dumps(schema).replace('<', '\\u003c') + '</script>'))
        if n.tag == 'script' and n.attrs.get('src', '').startswith(SITE_BASE + 'app.js'):
            changes.append((n.start, n.end, f'<script src="{SITE_BASE}seo-static.js?v=1" defer></script>'))
        if n.has('calendar-heading'):
            changes.append((n.start, n.end,
                            f'<div class="calendar-heading"><div><h2 id="calendar-title">Weekend shows</h2><p>Filter this weekend’s listings by artist or location.</p></div>'
                            f'<p class="results-count" data-results-count role="status" aria-live="polite">{len(context["weekend"])} shows</p></div>'))
    text = replace_spans(text, changes).replace(' aria-current="page"', '')
    text = text.replace('No shows currently match those filters.',
                        f'No upcoming shows match this weekend’s selection. <a href="{SITE_BASE}shows/">Explore all upcoming shows.</a>')
    # Empty weekend still has a truthful usable fallback without executing the old
    # full-calendar bootstrap (which would otherwise repopulate all dates).
    if not context['weekend']:
        text = text.replace('data-filtered-empty hidden', 'data-filtered-empty')
    return transform(Path(WEEKEND_PATH), text.encode(), context)


def about_content(text, context):
    """Owner-supplied story, original mission, and build-derived catalog totals."""
    doc = Document(text)
    mission_node = doc.one(lambda n: n.has('mission-statement'))
    mission = doc.raw(mission_node)
    description = 'Kingdom Circuit brings Christian hip hop concerts and festivals together in one place so more fans find the shows and more artists play to packed rooms.'
    title = 'About Us | Kingdom Circuit'
    canonical = SITE_ORIGIN + '/about-us/'
    main = doc.one(lambda n: n.tag == 'main')
    content = f'''<article class="kc-about-page" data-about-page aria-labelledby="kc-about-title">
<header class="kc-about-intro"><p class="eyebrow">The Kingdom Circuit</p><h1 id="kc-about-title">About Us</h1>
<p class="kc-about-lead">{description}</p></header>
<section class="kc-about-section" aria-labelledby="kc-about-story"><h2 id="kc-about-story">How we started</h2>
<p>We started Kingdom Circuit in July 2026 after missing CHH shows near us simply because we didn’t know they were happening. The announcements seemed to get lost in Instagram Stories. We searched for a site bringing CHH concerts and festivals together, couldn’t find what we were looking for, and decided to build it ourselves.</p></section>
<section class="kc-about-section" aria-labelledby="kc-about-today"><h2 id="kc-about-today">What you’ll find here</h2>
<p class="kc-about-totals">Today, we have <strong><span data-about-upcoming-count>{len(context['active'])}</span> upcoming shows listed and are tracking <span data-about-artist-count>{context['artist_total']}</span> artists</strong>.</p>
<p class="kc-about-count-date">Catalog totals as of <time datetime="{context['as_of'].isoformat()}">{context['as_of']:%B} {context['as_of'].day}, {context['as_of'].year}</time>.</p>
<p>Many artists submit their shows directly to us, and we also gather information from artist announcements, venues, promoters, ticket platforms, and social media.</p>
<p>Fans can browse concerts and festivals, visit artist profiles to see their upcoming shows, and follow links to official event details and tickets. We also turn those listings into Instagram content to help the shows reach more people.</p></section>
<section class="kc-about-section kc-about-mission" aria-labelledby="kc-about-mission"><h2 id="kc-about-mission">Why we exist</h2>{mission}
<p>We support both established and emerging artists. We want every CHH show packed, with more fans showing up, supporting artists, and hearing the gospel.</p></section>
<section class="kc-about-section" aria-labelledby="kc-about-community"><h2 id="kc-about-community">Encouragement from the community</h2>
<p>The encouragement from artists has meant a lot to us. One artist shared:</p>
<blockquote><p>“I've been looking at The Kingdom Circuit and really appreciate what you're doing for the CHH community.”</p></blockquote>
<p>That kind of feedback reinforces why we started and motivates us to keep building.</p></section>
<section class="kc-about-section" aria-labelledby="kc-about-connect"><h2 id="kc-about-connect">Find a show. Share a show.</h2>
<div class="kc-about-links"><a class="kc-discovery-primary" href="{SITE_BASE}shows/">Find a show <span aria-hidden="true">↗</span></a>
<a href="{SITE_BASE}artists/">Explore artists</a><a href="{SITE_BASE}submit/">Submit a show</a><a href="{SITE_BASE}submit/artist/">Submit an artist</a></div>
<div class="kc-about-contact"><p>Website: <a href="https://kingdomcircuit.com">KingdomCircuit.com</a></p>
<p>Instagram: <a href="https://www.instagram.com/thekingdomcircuit/">@thekingdomcircuit</a></p></div></section>
</article>'''
    changes = [(main.opening_end, main.closing_start, content)]
    for n in doc.nodes:
        if n.tag == 'title':
            changes.append((n.start, n.end, f'<title>{title}</title>'))
        if n.tag == 'meta':
            key = n.attrs.get('name') or n.attrs.get('property')
            value = {'description': description, 'og:description': description, 'twitter:description': description,
                     'og:title': title, 'twitter:title': title, 'og:url': canonical}.get(key)
            if value:
                raw = re.sub(r'content="[^"]*"', f'content="{escape(value, quote=True)}"', doc.raw(n))
                changes.append((n.start, n.end, raw))
        if n.tag == 'link' and n.attrs.get('rel') == 'canonical':
            changes.append((n.start, n.end, f'<link rel="canonical" href="{canonical}">'))
        if n.tag == 'script' and n.attrs.get('type') == 'application/ld+json':
            schema = {'@context': 'https://schema.org', '@type': 'AboutPage', 'name': 'About Us',
                      'description': description, 'url': canonical,
                      'isPartOf': {'@type': 'WebSite', 'name': 'The Kingdom Circuit', 'url': SITE_ORIGIN + '/'}}
            changes.append((n.start, n.end, '<script type="application/ld+json">' + json.dumps(schema).replace('<', '\\u003c') + '</script>'))
        if n.tag == 'script' and n.attrs.get('src', '').startswith(SITE_BASE + 'app.js'):
            changes.append((n.start, n.end, f'<script src="{SITE_BASE}seo-static.js?v=1" defer></script>'))
    return replace_spans(text, changes)


def about_page(live, context):
    source = source_html(live, 'index.html')
    source = mobile.transform(Path('index.html'), source.encode(), context['states']).decode()
    return transform(Path(ABOUT_PATH), about_content(source, context).encode(), context)


def combined_transform(relative, source, context):
    return transform(relative, mobile.transform(relative, source, context['baseline_states']), context)


def apply(site, live):
    as_of = today()
    context = load_context(live, as_of)
    for path in sorted(site.rglob('*')):
        if path.is_file() and (path.suffix == '.html' or path.name == 'sitemap.xml'):
            before = path.read_bytes()
            after = transform(path.relative_to(site), before, context)
            if before != after:
                path.write_bytes(after)
    for relative, generate in ((WEEKEND_PATH, weekend_page), (ABOUT_PATH, about_page)):
        target = site / relative
        assert not target.exists(), f'New destination unexpectedly exists: {relative}'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(generate(live, context))
    for asset in ASSETS:
        (site / 'assets' / asset).write_bytes((ROOT / 'assets' / asset).read_bytes())
    manifest_path = site / 'assets/fan-discovery-manifest.json'
    manifest = {'deploymentEnvironment': 'production', 'sourceReview': '36be2c60'}
    manifest['nationalDiscovery'] = {'version': VERSION, 'asOfDate': as_of.isoformat(), 'timezone': 'America/Los_Angeles'}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'nationalDiscovery': VERSION, 'asOfDate': str(as_of), 'weekendShows': len(context['weekend'])}))


def verify(live, site, context):
    """Independent page/content invariants supplement exact recomputed byte parity."""
    home = Document((site / 'index.html').read_text())
    old_home = Document(source_html(live, 'index.html'))
    about = Document((site / ABOUT_PATH).read_text())
    assert (site / ABOUT_PATH).read_bytes() == about_page(live, context)
    assert about.raw(about.one(lambda n: n.has('mission-statement'))) == old_home.raw(old_home.one(lambda n: n.has('mission-statement')))
    assert about.text(about.one(lambda n: 'data-about-upcoming-count' in n.attrs)) == str(len(context['active']))
    assert about.text(about.one(lambda n: 'data-about-artist-count' in n.attrs)) == str(context['artist_total'])
    assert about.one(lambda n: n.tag == 'time').attrs['datetime'] == context['as_of'].isoformat()
    for section_id in ('kc-about-story', 'kc-about-today', 'kc-about-mission', 'kc-about-community', 'kc-about-connect'):
        assert about.one(lambda n: n.attrs.get('id') == section_id).tag == 'h2'
    assert f'href="{SITE_BASE}submit/artist/"' in about.source
    assert 'We started Kingdom Circuit in July 2026' in about.source
    assert "I've been looking at The Kingdom Circuit and really appreciate what you're doing for the CHH community." in about.source
    assert not re.search(r'canad(?:a|ian)', about.text(about.one(lambda n: 'data-about-page' in n.attrs)), re.I), 'Owner removed Canada outreach from About Us'
    assert not any(n.has('mission-statement') for n in home.nodes), 'Mission should live on About Us, not Home'
    assert home.text(home.one(lambda n: n.tag == 'h1')) == HOME_HEADING
    assert home.text(home.one(lambda n: n.has('kc-discovery-deck'))) == HOME_SUBTITLE
    intro = home.one(lambda n: n.has('kc-discovery-intro'))
    assert not any(n.has('eyebrow') for n in intro.children), 'Owner removed the homepage tagline'
    counts = home.one(lambda n: n.has('kc-discovery-counts'))
    assert f'Browse all {len(context["active"])} shows' in home.text(counts)
    assert f'{context["artist_total"]} artists' in home.text(counts)
    assert {n.attrs.get('href') for n in counts.children if n.tag == 'a'} == {SITE_BASE + 'shows/', SITE_BASE + 'artists/'}
    search = home.one(lambda n: n.has('kc-discovery-search'))
    assert search.attrs['action'] == SITE_BASE + 'shows/' and search.attrs['method'] == 'get'
    assert home.one(lambda n: n.tag == 'input' and n.attrs.get('id') == 'kc-home-search').attrs['name'] == 'q'
    assert home.text(home.one(lambda n: n.tag == 'label' and n.attrs.get('for') == 'kc-home-search'))
    assert not any(n.has('kc-discovery-when') for n in home.nodes), 'Date navigation is already available in the header'
    assert about.text(about.one(lambda n: n.tag == 'h1')) == 'About Us'
    assert about.one(lambda n: n.tag == 'link' and n.attrs.get('rel') == 'canonical').attrs['href'] == SITE_ORIGIN + '/about-us/'
    assert about.one(lambda n: n.tag == 'meta' and n.attrs.get('name') == 'robots').attrs['content'] == 'index,follow'
    all_cards = card_records((site / 'shows/index.html').read_text())
    assert [r['html'] for r in all_cards] == [r['html'] for r in context['records']], 'Full national calendar changed'
    # Search uses the original directory photo for every artist, including zero-show profiles.
    directory = Document(source_html(live, 'artists/index.html'))
    original_portraits = {}
    for node in directory.nodes:
        if 'data-artist-card' in node.attrs:
            item = Document(directory.raw(node))
            heading = item.one(lambda n: n.tag == 'h2')
            href = next(n.attrs['href'] for n in heading.children if n.tag == 'a')
            original_portraits[href] = search_portrait(item.raw(item.one(lambda n: n.tag == 'img')))
    search_data = json.loads(home.text(home.one(lambda n: n.attrs.get('id') == 'kc-fan-artists')))
    assert {a['href']: a['portrait'] for a in search_data} == original_portraits
    for artist in search_data:
        if artist['portrait']:
            path = artist['portrait']['src'].removeprefix(SITE_BASE)
            assert (site / path).is_file(), f'Missing search portrait: {path}'
    all_urls = {r['href'] for r in all_cards}
    assert {r['href'] for r in card_records(source_html(live, 'index.html'))} <= all_urls, 'A former home listing is missing from All Shows'
    teasers = [n for n in home.nodes if 'data-discovery-show' in n.attrs]
    assert len(teasers) == len(home_selection(context)[0]) + len(home_selection(context)[1]), 'Every eligible weekly show must be available'
    artist_shelves = [n for n in home.nodes if n.attrs.get('id') == 'kc-artist-shelf']
    if context['artists']:
        artist_shelf = artist_shelves[0]
        assert len(artist_shelf.children) == len(context['artists']) <= 40
        assert [n.attrs['href'] for n in artist_shelf.children] == [a['href'] for a in context['artists']], 'Homepage artist order changed'
        assert artist_shelf.start < home.one(lambda n: n.attrs.get('id') == 'kc-next-shelf').start
    expected_week, expected_next = home_selection(context)
    next_first = context['as_of'] + timedelta(days=7 - context['as_of'].weekday())
    next_last = next_first + timedelta(days=6)
    next_inventory = sorted((r for r in all_cards if feature_eligible(r)
                             and next_first.isoformat() <= r['attrs']['data-date'] <= next_last.isoformat()),
                            key=lambda r: r['attrs']['data-date'])
    assert [r['href'] for r in expected_next] == [r['href'] for r in next_inventory], 'Next week must include every eligible Monday–Sunday show, without a cap or later dates'
    next_section = home.one(lambda n: n.attrs.get('aria-labelledby') == 'kc-next-heading')
    assert date_label(next_first, next_last) + ' · Nationwide' in home.text(next_section)
    assert SITE_BASE + 'shows/?dates=upcoming' in home.raw(next_section)
    for ident, expected in (('kc-week-shelf', expected_week), ('kc-next-shelf', expected_next)):
        shelf_node = home.one(lambda n: n.attrs.get('id') == ident)
        part = Document(home.raw(shelf_node))
        assert [n.attrs['href'] for n in part.nodes if n.tag == 'a' and '/event/' in n.attrs.get('href', '')] == [r['href'] for r in expected for _ in range(2)], 'Each preview image and title must link to the correct event'
    assert len({r['href'] for r in expected_week + expected_next}) == len(teasers), 'Duplicate home shows'
    assert 'Recently added shows' not in home.source and 'Trending' not in home.source
    assert home.one(lambda n: n.attrs.get('id') == 'kc-home-state').attrs['name'] == 'state'
    assert home.one(lambda n: n.attrs.get('id') == 'kc-home-dates').attrs['name'] == 'dates'
    for node in teasers:
        item = Document(home.raw(node))
        h3 = item.one(lambda n: n.tag == 'h3')
        link = next(n for n in h3.children if n.tag == 'a')
        source = next(r for r in all_cards if r['href'] == link.attrs['href'])
        assert item.text(h3) == source['name']
        assert source['artists'] in item.source and source['badges'] in item.source
        original_image = Document(source['image']).one(lambda n: n.tag == 'img')
        shown_image = item.one(lambda n: n.tag == 'img')
        for attribute in ('src', 'srcset', 'width', 'height', 'alt', 'style'):
            assert shown_image.attrs.get(attribute) == original_image.attrs.get(attribute), f'Preview artwork changed: {attribute}'
        treatment, framing, rendered_width = artwork_presentation(source['image'])
        assert shown_image.attrs['sizes'] == f'{rendered_width}px'
        image_link = item.one(lambda n: n.has('kc-teaser-image'))
        assert image_link.attrs['data-artwork-treatment'] == treatment
        assert image_link.attrs['style'] == framing
        assert node.attrs['data-artwork-shape'] == artwork_layout(source['image'])[0]
        assert node.attrs['style'] == f'--kc-artwork-ratio:{CARD_IMAGE_RATIO}'
        for field in ('Date', 'Venue', 'Location'):
            assert escape(source['meta'].get(field, '')) in item.source
    assert not any(n.attrs.get('src', '').startswith(SITE_BASE + 'app.js') for n in home.nodes)
    for state in context['states']:
        assert state['href'] in home.source
    assert (site / WEEKEND_PATH).read_bytes() == weekend_page(live, context)
    weekend = Document((site / WEEKEND_PATH).read_text())
    assert [r['html'] for r in card_records(weekend.source)] == [r['html'] for r in context['weekend']]
    checked = 0
    checked_links = set()
    def check_new_links(before, after):
        def references(doc):
            return {n.attrs[attr] for n in doc.nodes for attr in ('href', 'src', 'action') if attr in n.attrs}
        for link in references(after) - references(before):
            parts = urlsplit(link)
            if parts.netloc and parts.netloc != urlsplit(SITE_ORIGIN).netloc:
                continue
            if not parts.path.startswith(SITE_BASE):
                continue
            relative = unquote(parts.path[len(SITE_BASE):])
            target = site / relative
            assert target.is_file() or (target / 'index.html').is_file(), f'New broken local link: {link}'
            checked_links.add(parts.path)
    check_new_links(Document(''), weekend)
    check_new_links(Document(''), about)
    def check_navigation(doc):
        for nav in (n for n in doc.nodes if n.has('kc-rd-nav')):
            links = [n for n in nav.children if n.tag == 'a']
            assert [doc.text(n) for n in links] == ['Home', 'All Shows', 'This Weekend', 'This Month', 'Festivals', 'New Shows', 'Artists', 'About Us']
            assert links[2].attrs['href'] == WEEKEND_HREF and links[-1].attrs['href'] == ABOUT_HREF
        for actions in (n for n in doc.nodes if n.has('kc-rd-actions')):
            links = [n for n in actions.children if n.tag == 'a']
            instagram = [i for i, n in enumerate(links) if n.has('kc-rd-instagram-button')]
            if instagram:
                facebook = [n for n in links if n.has('kc-facebook-button')]
                assert len(facebook) == 1 and links[instagram[0] + 1] is facebook[0]
                assert facebook[0].attrs['href'] == FACEBOOK_HREF
                assert facebook[0].attrs['target'] == '_blank'
                assert {'noopener', 'noreferrer'} <= set(facebook[0].attrs['rel'].split())
                assert facebook[0].attrs['aria-label'] == 'Kingdom Circuit on Facebook (opens in new tab)'
                assert doc.raw(facebook[0]) == FACEBOOK_BUTTON
    check_navigation(weekend)
    check_navigation(about)
    for doc, active_href in ((weekend, WEEKEND_HREF), (about, ABOUT_HREF)):
        nav = doc.one(lambda n: n.has('kc-rd-nav'))
        assert [n.attrs['href'] for n in nav.children if n.attrs.get('aria-current') == 'page'] == [active_href]
    for path in live.rglob('*.html'):
        rel = path.relative_to(live)
        before, after = Document(source_html(live, rel)), Document((site / rel).read_text())
        if not any('data-national-discovery' in n.attrs for n in after.nodes):
            continue
        check_new_links(before, after)
        check_navigation(after)
        assert len([n for n in after.nodes if n.tag == 'h1']) == 1, rel
        # No original metadata, canonical or structured-data changes on existing URLs.
        for predicate in (lambda n: n.tag in {'meta', 'title'} or (n.tag == 'link' and n.attrs.get('rel') == 'canonical'),
                          lambda n: n.tag == 'script' and n.attrs.get('type') == 'application/ld+json'):
            assert Counter(before.raw(n) for n in before.nodes if predicate(n)) == Counter(after.raw(n) for n in after.nodes if predicate(n)), rel
        if rel.as_posix() != 'index.html':
            # The owner's additive full-card section is verified independently,
            # then removed for exact preservation of the original compact profile.
            extra = [n for n in after.nodes if 'data-artist-show-details' in n.attrs]
            original_after = after
            if extra:
                assert len(extra) == 1
                expected_hrefs = [n.attrs['href'] for n in before.nodes if n.has('kc-rd-show-row')]
                actual_cards = card_records(after.raw(extra[0]))
                assert [r['href'] for r in actual_cards] == expected_hrefs, rel
                source_cards = {r['href']: r['html'] for r in context['records']}
                assert [r['html'] for r in actual_cards] == [source_cards[h] for h in expected_hrefs], rel
                after = Document(replace_spans(after.source, [(extra[0].start, extra[0].end, '')]))
            for predicate in (lambda n: 'data-event-card' in n.attrs or 'data-artist-card' in n.attrs or n.has('past-show-row'),
                              lambda n: 'data-event-filters' in n.attrs or 'data-artist-directory' in n.attrs,
                              lambda n: 'data-kc-rd-artist-profile' in n.attrs or n.has('event-detail-section')):
                assert Counter(before.raw(n) for n in before.nodes if predicate(n)) == Counter(after.raw(n) for n in after.nodes if predicate(n)), rel
            after = original_after
        checked += 1
    for asset in ASSETS:
        assert (site / 'assets' / asset).read_bytes() == (ROOT / 'assets' / asset).read_bytes()
    assert checked > 0
    return {'verifiedPages': checked, 'weekendShows': len(context['weekend']),
            'homepageShowPreviews': len(teasers), 'completeCalendarShows': len(all_cards),
            'verifiedNewLocalDestinations': len(checked_links),
            'allOriginalSeoIdentitiesPreserved': True, 'missionPreserved': True, 'missionLocation': ABOUT_HREF}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('site', type=Path)
    parser.add_argument('live', type=Path)
    args = parser.parse_args()
    apply(args.site, args.live)
