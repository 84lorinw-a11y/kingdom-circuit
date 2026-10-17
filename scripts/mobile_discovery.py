"""Production navigation/reading-order layer, promoted from reviewed test 36be2c60.

Never edits event data, artist data, images, URLs, canonicals or event schema.
The final parity gate recomputes these exact transformations from the live snapshot.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
from html import escape, unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re

SITE_BASE = "/"

ROOT = Path(__file__).resolve().parents[1]
VERSION = "20261017-1"
ASSETS = ("mobile-seo-preview.css", "mobile-seo-preview.js")
VOID = set("area base br col embed hr img input link meta param source track wbr".split())


@dataclass
class Node:
    tag: str
    attrs: dict
    start: int
    opening_end: int
    end: int = 0
    closing_start: int = 0
    children: list = field(default_factory=list)

    def has(self, cls):
        return cls in self.attrs.get("class", "").split()


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.source = source
        self.lines = [0]
        self.lines.extend(m.end() for m in re.finditer("\n", source))
        self.nodes = []
        self.stack = []
        self.feed(source)

    def source_offset(self):
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def handle_starttag(self, tag, attrs):
        start = self.source_offset()
        node = Node(tag, dict(attrs), start, start + len(self.get_starttag_text()))
        if self.stack:
            self.stack[-1].children.append(node)
        self.nodes.append(node)
        if tag in VOID:
            node.end = node.opening_end
            node.closing_start = node.end
        else:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            node = self.stack.pop()
            node.end = node.opening_end
            node.closing_start = node.end

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index].tag == tag:
                start = self.source_offset()
                end = self.source.index(">", start) + 1
                for node in self.stack[index:]:
                    node.closing_start = start
                    node.end = end
                del self.stack[index:]
                break

    def one(self, predicate):
        found = [n for n in self.nodes if predicate(n)]
        if len(found) != 1:
            raise ValueError(f"Expected one structural landmark, got {len(found)}")
        return found[0]

    def raw(self, node):
        if not node.end:
            raise ValueError(f"Unclosed {node.tag}")
        return self.source[node.start:node.end]

    def text(self, node):
        return unescape(re.sub(r"<[^>]+>", "", self.raw(node))).strip()


def replace_spans(text, changes):
    previous = len(text) + 1
    for start, end, replacement in sorted(changes, reverse=True):
        if end > previous:
            raise ValueError("Overlapping overlay changes")
        text = text[:start] + replacement + text[end:]
        previous = start
    return text


def source_html(live, relative):
    return (live / relative).read_text()


def catalog(live):
    doc = Document(source_html(live, "shows/index.html"))
    nav = doc.one(lambda n: "data-permanent-state-navigation" in n.attrs)
    states = []
    for link in doc.nodes:
        if link.tag != "a" or not nav.start < link.start < nav.end:
            continue
        href = link.attrs["href"]
        if not re.fullmatch(re.escape(SITE_BASE) + r"shows/[a-z-]+/", href):
            raise ValueError(f"Unexpected permanent-state URL: {href}")
        relative = href.removeprefix(SITE_BASE) + "index.html"
        page = Document(source_html(live, relative))
        cards = [n for n in page.nodes if "data-event-card" in n.attrs]
        states.append({"name": doc.text(link), "href": href, "relative": relative,
                       "count": len(cards), "code": cards[0].attrs.get("data-state", "") if cards else ""})
    if not states or len({s["relative"] for s in states}) != len(states):
        raise ValueError("Missing or duplicate permanent state pages")
    return sorted(states, key=lambda state: state["name"])


def state_link(state):
    label = f'{state["count"]} upcoming' if state["count"] else "Check for dates"
    return (f'<a href="{escape(state["href"])}"><span>{escape(state["name"])}</span>'
            f'<small>{label}</small></a>')


def finder(states, compact=False):
    popular = sorted((s for s in states if s["count"]), key=lambda s: (-s["count"], s["name"]))[:4]
    options = ''.join(f'<option value="{s["href"]}">{escape(s["name"])}</option>' for s in states)
    links = ''.join(state_link(s) for s in states)
    featured = ''.join(state_link(s) for s in popular)
    if compact:
        return (f'<section class="kc-state-finder kc-state-finder-compact" id="browse-states" aria-label="State show pages">'
                f'<details class="kc-all-states"><summary>Browse CHH shows by state</summary>'
                f'<nav class="kc-state-links" aria-label="All {len(states)} state and region show pages">{links}</nav></details></section>')
    return f'''<section class="kc-state-finder" id="browse-states" aria-labelledby="kc-state-title">
<h2 id="kc-state-title">Find CHH shows by state</h2>
<p>Christian hip-hop concerts, closer to you.</p>
<div class="kc-state-picker" data-state-picker hidden>
<label for="kc-state-destination">Choose your state</label>
<div><select id="kc-state-destination"><option value="">Select a state</option>{options}</select>
<button type="button" data-open-state disabled>View shows <span aria-hidden="true">↗</span></button></div></div>
<nav class="kc-state-links kc-featured-states" aria-label="States with the most upcoming shows">{featured}</nav>
<details class="kc-all-states"><summary>Browse all {len(states)} states &amp; regions</summary>
<nav class="kc-state-links" aria-label="All state show pages">{links}</nav></details>
</section>'''


def reorder_home(text, states):
    doc = Document(text)
    hero = doc.one(lambda n: n.tag == "section" and n.has("kc-rd-home-hero"))
    title = doc.one(lambda n: n.tag == "h1")
    intro = text[hero.opening_end:title.end]
    about = text[title.end:hero.closing_start]
    replacement = (text[hero.start:hero.opening_end]
                   + '<div class="kc-home-intro">' + intro + '</div>'
                   + finder(states) + '<div class="kc-home-about">' + about + '</div></section>')
    return replace_spans(text, [(hero.start, hero.end, replacement)])


def reorder_all_shows(text, states):
    doc = Document(text)
    old = doc.one(lambda n: "data-permanent-state-navigation" in n.attrs)
    hero = doc.one(lambda n: n.tag == "section" and n.has("page-hero"))
    return replace_spans(text, [(old.start, old.end, ""), (hero.end, hero.end, finder(states, compact=True))])


def reorder_location(text):
    doc = Document(text)
    featured = [n for n in doc.nodes if n.tag == "section" and n.has("seo-location-strip")
                and "Featured artists" in doc.raw(n)]
    calendar = doc.one(lambda n: n.tag == "section" and n.has("calendar"))
    hero = doc.one(lambda n: n.tag == "section" and n.has("seo-location-hero"))
    cities = [n for n in doc.nodes if n.tag == "section" and n.has("seo-location-strip")
              and "Browse cities" in doc.raw(n)]
    archive = [n for n in doc.nodes if "data-past-shows-archive" in n.attrs]
    changes = []
    # The heading already names the genre and location. Keep the useful count,
    # but remove the repeated eyebrow and long date sentence above the same dates.
    for n in hero.children:
        if n.tag == 'p' and n.has('eyebrow') and doc.text(n).startswith('Christian hip-hop in '):
            changes.append((n.start, n.end, ''))
    cards = [n for n in doc.nodes if 'data-event-card' in n.attrs]
    if cards:
        titles = [n for n in hero.children if n.tag == 'h1']
        summaries = [n for n in hero.children if n.tag == 'p' and n.has('hero-text')]
        if len(titles) == len(summaries) == 1 and ' in ' in doc.text(titles[0]):
            location = doc.text(titles[0]).rsplit(' in ', 1)[1]
            total = len(cards)
            city_count = sum(n.tag == 'a' and cities[0].start < n.start < cities[0].end for n in doc.nodes) if cities else 0
            where = f'across {city_count} {location} cities' if city_count > 1 else f'in {location}'
            summary = (f'<p class="hero-text"><strong>{total} upcoming show{"s" if total != 1 else ""} {escape(where)}.</strong> '
                       'Browse dates, venues and official event details below.</p>')
            n = summaries[0]
            changes.append((n.start, n.end, summary))
    if featured:
        if len(featured) != 1:
            raise ValueError("Ambiguous featured-artists section")
        node = featured[0]
        moved = doc.raw(node).replace('<section ', '<section id="state-artists" ', 1)
        changes += [(node.start, node.end, ""), (calendar.end, calendar.end, moved)]
    links = '<a href="#upcoming-shows">Upcoming shows</a>'
    if featured:
        links += '<a href="#state-artists">Artists</a>'
    if archive:
        links += '<a href="#past-shows">Past shows</a>'
        n = archive[0]
        changes.append((n.start, n.opening_end, text[n.start:n.opening_end].replace('<section ', '<section id="past-shows" ', 1)))
    changes.append((hero.end, hero.end, f'<nav class="kc-page-jumps" aria-label="On this page">{links}</nav>'))
    changes.append((calendar.start, calendar.opening_end, text[calendar.start:calendar.opening_end].replace('<section ', '<section id="upcoming-shows" ', 1)))
    for n in cities:
        changes.append((n.start, n.opening_end, text[n.start:n.opening_end].replace('seo-location-strip', 'seo-location-strip kc-city-links')))
    return replace_spans(text, changes)


def add_calendar_tools(text, states):
    doc = Document(text)
    grids = [n for n in doc.nodes if n.has("event-grid")]
    if not grids:
        return text
    if len(grids) != 1:
        raise ValueError("Expected one main event grid")
    tools = '''<div class="kc-calendar-tools" data-calendar-tools hidden>
<a class="kc-selected-state" data-selected-state hidden></a></div>'''
    # Small, non-executable configuration derived only from existing live state pages.
    data = {s["code"]: {"href": s["href"], "name": s["name"]} for s in states if s["code"]}
    tools += '<script type="application/json" id="kc-state-destinations">' + json.dumps(data, ensure_ascii=True).replace('<', '\\u003c') + '</script>'
    return text[:grids[0].start] + tools + text[grids[0].start:]


def eligible(relative, text):
    if relative in {"index.html", "shows/index.html", "shows/this-month/index.html", "festivals/index.html", "new-shows/index.html"}:
        return True
    return relative.startswith("shows/") and relative.endswith("/index.html") and 'seo-location-hero' in text


def transform(relative, source, states):
    if relative.suffix != ".html":
        return source
    text = source.decode()
    name = relative.as_posix()
    if not eligible(name, text):
        return source
    if 'data-mobile-seo-preview' in text:
        raise ValueError("Overlay must run once on the unmodified mirror")
    if name == "index.html":
        text = reorder_home(text, states)
    elif name == "shows/index.html":
        text = reorder_all_shows(text, states)
    elif 'seo-location-hero' in text:
        text = reorder_location(text)
    text = add_calendar_tools(text, states)
    assets = (f'<link rel="stylesheet" href="{SITE_BASE}assets/{ASSETS[0]}?v={VERSION}" data-mobile-seo-preview>'
              f'<script src="{SITE_BASE}assets/{ASSETS[1]}?v={VERSION}" defer></script>')
    return text.replace('</head>', assets + '</head>', 1).encode()


def apply(site, live):
    states = catalog(live)
    changed = []
    for path in sorted(site.rglob('*.html')):
        relative = path.relative_to(site)
        before = path.read_bytes()
        after = transform(relative, before, states)
        if before != after:
            path.write_bytes(after)
            changed.append(relative.as_posix())
    for asset in ASSETS:
        (site / 'assets' / asset).write_bytes((ROOT / 'assets' / asset).read_bytes())
    print(json.dumps({'overlay': VERSION, 'changedPageCount': len(changed), 'states': len(states)}, indent=2))


def verify_overlay(live, site, *, national_home=False):
    """Independent invariants in addition to final byte-for-byte transform parity."""
    states = catalog(live)
    checked = []
    shows = 0
    for path in sorted(live.rglob('*.html')):
        relative = path.relative_to(live)
        before = source_html(live, relative)
        if not eligible(relative.as_posix(), before):
            continue
        if national_home and relative.as_posix() == 'index.html':
            # The owner subsequently approved replacing the duplicate home calendar
            # with national discovery. The national verifier independently checks
            # every preview against All Shows and preserves its complete inventory.
            assert 'data-national-home' in (site / relative).read_text()
            continue
        after = (site / relative).read_text()
        old, new = Document(before), Document(after)
        assert len([n for n in new.nodes if n.tag == 'h1']) == 1, relative
        def raw_nodes(doc, predicate):
            return Counter(doc.raw(n) for n in doc.nodes if predicate(n))
        # Reordering and the optional display view must not lose or rewrite any show.
        for predicate in (
            lambda n: 'data-event-card' in n.attrs,
            lambda n: n.has('past-show-row'),
            lambda n: n.tag == 'img',
            lambda n: n.tag == 'script' and n.attrs.get('type') == 'application/ld+json',
            lambda n: n.tag in {'title', 'meta'} or (n.tag == 'link' and n.attrs.get('rel') == 'canonical'),
            lambda n: 'data-event-filters' in n.attrs,
        ):
            assert raw_nodes(old, predicate) == raw_nodes(new, predicate), f'Preservation failure: {relative}'
        old_links = {n.attrs['href'] for n in old.nodes if n.tag == 'a' and 'href' in n.attrs}
        new_links = {n.attrs['href'] for n in new.nodes if n.tag == 'a' and 'href' in n.attrs}
        assert old_links <= new_links, f'Lost navigation: {relative}: {old_links - new_links}'
        cards = [n for n in new.nodes if 'data-event-card' in n.attrs]
        shows += len(cards)
        if relative.as_posix() in {'index.html', 'shows/index.html'}:
            finder_node = new.one(lambda n: n.attrs.get('id') == 'browse-states')
            assert not cards or finder_node.end < cards[0].start, relative
            for state in states:
                assert state['href'] in new.raw(finder_node), state
                assert (site / state['relative']).is_file(), state
        if 'seo-location-hero' in before:
            cal = new.one(lambda n: n.attrs.get('id') == 'upcoming-shows')
            artists = [n for n in new.nodes if n.attrs.get('id') == 'state-artists']
            assert not artists or cal.end <= artists[0].start, relative
        ids = {n.attrs['id'] for n in new.nodes if n.attrs.get('id')}
        for link in new.nodes:
            href = link.attrs.get('href', '')
            if link.tag == 'a' and href in {'#upcoming-shows', '#past-shows', '#state-artists'}:
                assert href[1:] in ids, (relative, href)
        checked.append(relative.as_posix())
    for asset in ASSETS:
        assert (site / 'assets' / asset).read_bytes() == (ROOT / 'assets' / asset).read_bytes(), asset
    assert checked, 'No preview pages verified'
    result = {'verifiedPages': len(checked), 'permanentStatePages': len(states),
              'preservedEventCardInstances': shows, 'urlsMetadataSchemaAndDataPreserved': True}
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('site', type=Path)
    parser.add_argument('live', type=Path)
    args = parser.parse_args()
    apply(args.site, args.live)
