"""Compare visitor facing show names across the final published surfaces."""
from __future__ import annotations

from collections import Counter
import json
from urllib.parse import urljoin, urlsplit

from mobile_discovery import Document
from private_events import display_title

ORIGIN = 'https://kingdomcircuit.com'


def normalized(value):
    return ' '.join(str(value or '').split())


def expected_titles(records):
    return {path: display_title(record) if record.get('private') else record['title']
            for path, record in records.items()}


def page_checks(doc, path, expected, redirects=None, include_inventory=True):
    """Check named show links, not navigation labels such as Event details."""
    errors, counts = [], Counter()
    redirects = redirects or {}

    def target(href):
        parsed = urlsplit(urljoin(ORIGIN + path, href))
        if parsed.hostname not in {'kingdomcircuit.com', 'www.kingdomcircuit.com'}:
            return None
        route = parsed.path.removesuffix('index.html')
        return redirects.get(route, route)

    def check(route, actual, surface):
        if route not in expected:
            return
        counts[surface] += 1
        if normalized(actual) != normalized(expected[route]):
            errors.append(dict(kind='show_title_mismatch', path=path, event=route,
                               surface=surface, expected=expected[route], actual=actual))

    # The event's H1 is the visitor facing identity, not its longer SEO title.
    if path in expected:
        headings = [n for n in doc.nodes if n.tag == 'h1']
        if len(headings) != 1:
            errors.append(dict(kind='show_title_heading_count', path=path, count=len(headings)))
        else:
            check(path, doc.text(headings[0]), 'eventHeading')

    headings = [n for n in doc.nodes if n.tag in {'h2', 'h3', 'h4'}]
    for link in (n for n in doc.nodes if n.tag == 'a' and n.attrs.get('href')):
        route = target(link.attrs['href'])
        if route not in expected:
            continue
        if any(h.start < link.start < h.end for h in headings):
            check(route, doc.text(link), 'listingTitle')
        if link.has('kc-rd-show-row') or link.has('kc-rd-next-show'):
            names = [n for n in doc.nodes if n.has('kc-rd-event-title')
                     and link.start < n.start < link.end]
            if len(names) != 1:
                errors.append(dict(kind='artist_show_title_count', path=path,
                                   event=route, count=len(names)))
            else:
                check(route, doc.text(names[0]), 'artistScheduleTitle')

    # These HTML fragments become the homepage cards when the date rolls over.
    for node in doc.nodes:
        if node.tag != 'script' or node.attrs.get('type') != 'application/json':
            continue
        ident = node.attrs.get('id')
        if ident not in {'kc-weekly-shows', 'kc-fan-config'}:
            continue
        value = json.loads(doc.source[node.opening_end:node.closing_start])
        if ident == 'kc-fan-config' and path in expected:
            check(path, value.get('show'), 'eventClientTitle')
        elif ident == 'kc-weekly-shows' and include_inventory:
            for row in value:
                result = page_checks(Document(row['html']), '/', expected, redirects, False)
                for error in result['errors']:
                    error.update(path=path, surface='homepageRolloverTitle')
                errors.extend(result['errors'])
                counts['homepageRolloverTitle'] += result['counts'].get('listingTitle', 0)
    return {'errors': errors, 'counts': dict(counts)}


def catalog_checks(catalog, expected):
    errors = []
    for row in catalog['shows']:
        route = row['path']
        if route in expected and normalized(row.get('name')) != normalized(expected[route]):
            errors.append(dict(kind='show_title_mismatch', path='/assets/fan-show-catalog.json',
                               event=route, surface='catalogTitle', expected=expected[route],
                               actual=row.get('name')))
    return {'errors': errors, 'counts': {'catalogTitle': len(catalog['shows'])}}
