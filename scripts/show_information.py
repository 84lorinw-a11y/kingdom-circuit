"""Publish verified show facts from the current catalog without changing sources.

Runs after the approved presentation layers. No discovery, TEST overrides,
artwork replacement, artist mutation or URL creation happens here. The same
normalized record supplies visible facts, the official action and Event schema.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
from html import escape
import json
from pathlib import Path
import re

from mobile_discovery import Document, replace_spans
from show_information_model import normalize
from private_events import redact_public_feeds, verify_public_feeds

ROOT = Path(__file__).resolve().parents[1]
VERSION = '20261105-1'
CSS = 'assets/show-information.css'
EVENT_TYPES = {'Event', 'MusicEvent', 'Festival'}
SOURCE_FILES = ('events.json', 'supplemental-events.json', 'config/artists.json', 'assets/fan-show-catalog.json')


def norm(value):
    return str(value or '').strip().casefold()


def key(row):
    return norm(row.get('title')), str(row.get('startDate') or '')[:10], norm(row.get('city'))


def digest(value):
    hashed = 0x811C9DC5
    for byte in str(value).encode():
        hashed = ((hashed ^ byte) * 0x01000193) & 0xFFFFFFFF
    return f'{hashed:08x}'[:6]


def event_schemas(value):
    if isinstance(value, list):
        for child in value:
            yield from event_schemas(child)
    elif isinstance(value, dict):
        if value.get('@type') in EVENT_TYPES:
            yield value
        for child in value.values():
            if isinstance(child, (list, dict)):
                yield from event_schemas(child)


def schema_blocks(text):
    doc = Document(text)
    return [(n, json.loads(text[n.opening_end:n.closing_start])) for n in doc.nodes
            if n.tag == 'script' and n.attrs.get('type') == 'application/ld+json']


def schema_key(schema):
    address = (schema.get('location') or {}).get('address') or {}
    return norm(schema.get('name')), str(schema.get('startDate') or '')[:10], norm(address.get('addressLocality'))


def context(site):
    rows = {}
    for filename in ('events.json', 'supplemental-events.json'):
        for row in json.loads((site / filename).read_text()):
            identity = row.get('id') or key(row)
            if identity not in rows:
                rows[identity] = deepcopy(row)
            else:
                for field, value in row.items():
                    if field not in rows[identity] or rows[identity][field] in ('', None, []):
                        rows[identity][field] = deepcopy(value)
    by_key, by_hash, by_path = {}, {}, {}
    for row in rows.values():
        record = normalize(row)
        by_key.setdefault(key(row), record)
        if row.get('id'):
            by_hash[digest(row['id'])] = record
        if str(row.get('canonicalPath') or '').startswith('/event/'):
            by_path[row['canonicalPath']] = record
    catalog = json.loads((site / 'assets/fan-show-catalog.json').read_text())
    pages = {}
    for show in catalog['shows']:
        path = show['path']
        if not re.fullmatch(r'/event/[a-z0-9-]+/', path):
            raise ValueError(f'Unexpected published event path: {path}')
        rel = path.lstrip('/') + 'index.html'
        text = (site / rel).read_text()
        if 'http-equiv="refresh"' in text or 'class="event-detail-copy"' not in text:
            raise ValueError(f'Upcoming show has no canonical detail page: {path}')
        schemas = [s for _, value in schema_blocks(text) for s in event_schemas(value)]
        record = by_path.get(path) or next((by_key[schema_key(s)] for s in schemas if schema_key(s) in by_key), None)
        if record is None:
            match = re.search(r'-([0-9a-f]{6})/$', path)
            record = by_hash.get(match[1]) if match else None
        if record is None or record.get('startDate') != show['date']:
            raise ValueError(f'Current catalog/source identity mismatch: {path}')
        pages[rel] = record
    return {'pages': pages, 'paths': {'/' + rel.removesuffix('index.html'): row for rel, row in pages.items()}}


def attributes(opening, values):
    for name, value in values.items():
        pattern = r'(?<![\w:-])' + re.escape(name) + r'\s*=\s*(?:"[^"]*"|\'[^\']*\')'
        attribute = name + '="' + escape(str(value), quote=True) + '"'
        if re.search(pattern, opening):
            opening = re.sub(pattern, lambda _: attribute, opening, count=1)
        else:
            opening = re.sub(r'\s*/?>$', lambda m: ' ' + attribute + m[0], opening, count=1)
    return opening


def address_html(record):
    if record.get('locationUnconfirmed'):
        return '<address class="kc-address">Location not confirmed</address>'
    locality = ', '.join(str(record.get(k) or '').strip() for k in ('venueLocality', 'state') if record.get(k))
    if not record.get('private') and record.get('postalCode'):
        locality += ' ' + str(record['postalCode'])
    country = {'US': 'United States', 'CA': 'Canada', 'PR': 'Puerto Rico'}.get(record.get('country'), record.get('country', ''))
    lines = ([] if record.get('private') else [record.get('address'), record.get('address2') or record.get('suite')]) + [locality, country]
    if not record.get('private') and not record.get('address'):
        lines.insert(0, 'Address not confirmed')
    return '<address class="kc-address">' + '<br> '.join(escape(str(x)) for x in lines if x) + '</address>'


def organizer_html(record):
    if not record.get('organizerName'):
        return ''
    name = escape(record['organizerName'])
    if record.get('organizerUrl'):
        name = f'<a href="{escape(record["organizerUrl"], quote=True)}" target="_blank" rel="noopener noreferrer">{name}</a>'
    return '<div data-kc-organizer><dt>Organizer / promoter</dt><dd>' + name + '</dd></div>'


def more_details(record):
    facts = []
    if record.get('priceLabel') and not record.get('private'):
        facts.append(('Price', escape(record['priceLabel'])))
    for source, label in (('doorsTimeLabel', 'Doors'), ('registrationTimeLabel', 'Concert registration'), ('endTimeLabel', 'Ends')):
        if source == 'doorsTimeLabel' and record.get('primaryTimeKind') == 'doors' and not record.get('startTimeLabel'):
            continue
        if record.get(source):
            value = record[source]
            if source == 'registrationTimeLabel' and record.get('registrationLocation'):
                value += ' · ' + record['registrationLocation']
            facts.append((label, escape(value)))
    for source, label in (('headliner', 'Headliner'), ('supportActs', 'Support'), ('hosts', 'Hosts')):
        value = record.get(source)
        if value and (source != 'headliner' or record.get('supportActs')):
            facts.append((label, escape(' · '.join(value) if isinstance(value, list) else str(value))))
    for source, label in (('accessibility', 'Accessibility'), ('parking', 'Parking'), ('entryRequirements', 'Entry'), ('refundPolicy', 'Refund policy')):
        if isinstance(record.get(source), str) and record[source].strip():
            facts.append((label, escape(record[source])))
    labels = {label.casefold() for label, _ in facts}
    for item in record.get('scheduleDetails') or []:
        if not isinstance(item, dict):
            continue
        label, value = str(item.get('label') or '').strip(), str(item.get('text') or '').strip()
        if label and value and label.casefold() not in labels and label.casefold() not in {'address', 'organizer', 'promoter', 'organizer / promoter'}:
            facts.append((escape(label), escape(value)))
            labels.add(label.casefold())
    description = record.get('description') or ''
    if not facts and not description and not record.get('scheduleNote'):
        return ''
    content = f'<p>{escape(description)}</p>' if description else ''
    if facts:
        content += '<dl class="kc-extra-facts">' + ''.join(f'<div><dt>{label}</dt><dd>{value}</dd></div>' for label, value in facts) + '</dl>'
    if record.get('scheduleNote'):
        content += '<p>' + escape(record['scheduleNote']) + '</p>'
    return '<details class="kc-more-details"><summary>More show details</summary><div class="kc-more-body">' + content + '</div></details>'


def patched_schema(value, record):
    if isinstance(value, list):
        return [v for child in value if (v := patched_schema(child, record)) is not None]
    if not isinstance(value, dict):
        return value
    value = deepcopy(value)
    if (record.get('private') or record.get('locationUnconfirmed')) and value.get('@type') in EVENT_TYPES | {'Offer', 'AggregateOffer'}:
        return None
    if value.get('@type') in EVENT_TYPES:
        for source, target in (('schemaStartDate', 'startDate'), ('schemaEndDate', 'endDate'), ('description', 'description')):
            if record.get(source):
                value[target] = record[source]
            elif target == 'endDate':
                value.pop(target, None)
        value.pop('organizer', None)
        if record.get('organizerName'):
            value['organizer'] = {'@type': 'Organization', 'name': record['organizerName']}
            if record.get('organizerUrl'):
                value['organizer']['url'] = record['organizerUrl']
        location = value.setdefault('location', {'@type': 'Place'})
        if record.get('venue'):
            location['name'] = record['venue']
        else:
            location.pop('name', None)
        address = location.setdefault('address', {'@type': 'PostalAddress'})
        for source, target in (('address', 'streetAddress'), ('venueLocality', 'addressLocality'), ('state', 'addressRegion'), ('postalCode', 'postalCode'), ('country', 'addressCountry')):
            if record.get(source):
                address[target] = record[source]
            elif source in {'address', 'postalCode', 'venueLocality'}:
                address.pop(target, None)
        if record.get('address2') or record.get('suite'):
            address['streetAddress'] = ', '.join(x for x in [record.get('address'), record.get('address2') or record.get('suite')] if x)
        value.pop('offers', None)
        if record.get('offer'):
            value['offers'] = record['offer']
        return value
    for name, child in list(value.items()):
        if isinstance(child, (dict, list)):
            replacement = patched_schema(child, record)
            if replacement is None:
                value.pop(name)
            else:
                value[name] = replacement
    return value


def detail_transform(text, record):
    # Remove only this layer's prior output to keep repeat builds byte-idempotent.
    doc = Document(text)
    prior = [n for n in doc.nodes if n.has('kc-more-details') or n.has('kc-admission-restriction') or 'data-kc-organizer' in n.attrs]
    text = replace_spans(text, [(n.start, n.end, '') for n in prior])
    doc = Document(text)
    copy = doc.one(lambda n: n.has('event-detail-copy'))
    lists = [n for n in copy.children if n.has('detail-list')]
    if len(lists) != 1:
        raise ValueError('Expected one main Status/Date/Venue/Location list')
    details = lists[0]
    changes = []
    organizer_position = details.closing_start
    for node in copy.children:
        if 'data-kc-event-schedule' in node.attrs and record.get('scheduleDetails'):
            changes.append((node.start, node.end, ''))
    for row in details.children:
        labels = [n for n in row.children if n.tag == 'dt']
        values = [n for n in row.children if n.tag == 'dd']
        if not labels or not values:
            continue
        label, value = doc.text(labels[0]), values[0]
        replacement = None
        if label == 'Location':
            replacement = address_html(record)
            organizer_position = row.end
        elif label == 'Date' and record.get('dateLabel'):
            replacement = escape(record['dateLabel'])
            if not record.get('startTimeLabel'):
                replacement += '<br> <span class="kc-unconfirmed">Start time not confirmed</span>'
            # Private calendar verification relies on this explicit date marker.
            marker = next((n for n in value.children if 'data-kc-private-date' in n.attrs), None)
            if marker:
                replacement = text[marker.start:marker.opening_end] + replacement + text[marker.closing_start:marker.end]
        elif label == 'Venue':
            replacement = escape(record['venueLabel'])
        elif label == 'Status' and record.get('private'):
            replacement = 'Private Event — not open to the public'
        elif label == 'Status' and record.get('soldOut') and norm(record.get('status')) not in {'cancelled', 'canceled', 'postponed'}:
            replacement = 'Sold out'
        elif label in {'Age restriction', 'Organizer / promoter', 'Organizer', 'Promoter'}:
            changes.append((row.start, row.end, ''))
        if replacement is not None:
            changes.append((value.opening_end, value.closing_start, replacement))
    if organizer_html(record):
        changes.append((organizer_position, organizer_position, organizer_html(record)))
    primary = [n for n in doc.nodes if n.tag == 'a' and n.has('primary-button') and copy.start < n.start < copy.end and doc.text(n).casefold() == 'official details']
    if len(primary) > 1:
        raise ValueError('Expected at most one primary Official details action')
    if primary and record.get('officialDestination') and not record.get('private'):
        n = primary[0]
        changes.append((n.start, n.opening_end, attributes(text[n.start:n.opening_end], {'href': record['officialDestination']['url']})))
    insertion = primary[0].end if primary else details.end
    admission = record.get('admissionLabel') or ''
    if admission:
        position = primary[0].start if primary else details.end
        changes.append((position, position, f'<p class="kc-admission-restriction">{escape(admission)}</p>'))
    if more_details(record):
        changes.append((insertion, insertion, more_details(record)))
    for node, value in schema_blocks(text):
        replacement = patched_schema(value, record)
        if replacement is None or replacement == []:
            changes.append((node.start, node.end, ''))
        elif replacement != value:
            changes.append((node.opening_end, node.closing_start, json.dumps(replacement, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')))
    return replace_spans(text, changes)


def listing_transform(text, ctx):
    doc = Document(text)
    changes = []
    # Artist schedules use compact links rather than the full event-card
    # markup. The pinned redesign copies their venue text before this shared
    # fact layer runs, so reconcile that one label without rebuilding the row.
    for link in doc.nodes:
        if link.tag != 'a' or not (link.has('kc-rd-show-row') or link.has('kc-rd-next-show')):
            continue
        record = ctx['paths'].get(link.attrs.get('href'))
        if not record:
            continue
        expected = record['venueLabel']
        for venue in doc.nodes:
            if not (link.start < venue.start < link.end and (venue.has('kc-rd-show-venue') or venue.has('kc-rd-next-venue'))):
                continue
            current = doc.text(venue)
            if current == expected or (venue.has('kc-rd-next-venue') and current.startswith(expected + ' · ')):
                continue
            # The Next Show line may append a time. Keep the existing clock
            # exactly; a middot within a venue name alone is not a clock.
            clock = re.search(r'( · \d{1,2}(?::\d{2})?\s*[AP]M(?:\s+[A-Z]{2,5})?)$', current) if venue.has('kc-rd-next-venue') else None
            suffix = clock[1] if clock else ''
            previous = current[:-len(suffix)] if suffix else current
            changes.append((venue.opening_end, venue.closing_start, escape(expected + suffix)))
            aria = link.attrs.get('aria-label', '')
            base, separator, title_status = aria.partition(' | ')
            old_suffix = ', ' + previous
            if base.endswith(old_suffix):
                corrected = base[:-len(old_suffix)] + ', ' + expected + separator + title_status
                changes.append((link.start, link.opening_end, attributes(text[link.start:link.opening_end], {'aria-label': corrected})))
    for card in doc.nodes:
        if not (card.has('event-card') or card.has('kc-discovery-show')):
            continue
        links = [n for n in doc.nodes if n.tag == 'a' and card.start < n.start < card.end]
        record = next((ctx['paths'][n.attrs['href']] for n in links if n.attrs.get('href') in ctx['paths']), None)
        if not record or record.get('private') or not record.get('officialDestination'):
            continue
        for link in links:
            if link.has('official-button') and doc.text(link).casefold() == 'official details':
                changes.append((link.start, link.opening_end, attributes(text[link.start:link.opening_end], {'href': record['officialDestination']['url']})))
    return replace_spans(text, changes)


def transform(relative, data, ctx):
    if not str(relative).endswith('.html'):
        return data
    text = data.decode()
    if str(relative) in ctx['pages']:
        text = detail_transform(text, ctx['pages'][str(relative)])
        link = f'<link data-kc-show-information rel="stylesheet" href="/{CSS}?v={VERSION}">'
        doc = Document(text)
        styles = [n for n in doc.nodes if n.tag == 'link' and ('data-kc-show-information' in n.attrs or n.attrs.get('href', '').split('?')[0] == '/' + CSS)]
        text = replace_spans(text, [(n.start, n.end, '') for n in styles])
        text = text.replace('</head>', link + '</head>', 1)
    else:
        text = listing_transform(text, ctx)
    return text.encode()


def source_hashes(site):
    return {name: hashlib.sha256((site / name).read_bytes()).hexdigest() for name in SOURCE_FILES if (site / name).is_file()}


def verify(site, ctx=None):
    ctx = ctx or context(site)
    verify_public_feeds(site)
    assert (site / CSS).read_bytes() == (ROOT / CSS).read_bytes(), 'Show information stylesheet drift'
    report = {'version': VERSION, 'eventPages': len(ctx['pages']), 'organizerRows': 0, 'detailsPanels': 0, 'ticketOffers': 0, 'privatePages': 0, 'canadianPages': 0}
    for relative, record in ctx['pages'].items():
        data = (site / relative).read_bytes()
        assert transform(relative, data, ctx) == data, f'Unapplied or duplicate show information: {relative}'
        doc = Document(data.decode())
        main = doc.one(lambda n: n.has('event-detail-copy'))
        facts = next(n for n in main.children if n.has('detail-list'))
        rows = [n for n in facts.children if 'data-kc-organizer' in n.attrs]
        assert len(rows) == int(bool(record.get('organizerName'))), f'Organizer row mismatch: {relative}'
        if rows:
            value = next(n for n in rows[0].children if n.tag == 'dd')
            assert doc.text(value) == record['organizerName'], f'Organizer text mismatch: {relative}'
            report['organizerRows'] += 1
        schemas = [s for _, value in schema_blocks(doc.source) for s in event_schemas(value)]
        if record.get('private'):
            assert not schemas, f'Private event has public schema: {relative}'
            report['privatePages'] += 1
        if record.get('locationUnconfirmed'):
            assert not schemas, f'Unconfirmed location has public Event schema: {relative}'
        for schema in schemas:
            assert schema.get('offers') == record.get('offer'), f'Offer mismatch: {relative}'
            assert schema.get('startDate') == record.get('schemaStartDate'), f'Start time mismatch: {relative}'
            assert (schema.get('organizer') or {}).get('name') == record.get('organizerName'), f'Organizer schema mismatch: {relative}'
            assert (schema.get('location', {}).get('address') or {}).get('addressLocality') == record.get('venueLocality'), f'Venue municipality mismatch: {relative}'
            if record.get('offer'):
                buttons = [n for n in doc.nodes if n.tag == 'a' and n.has('primary-button') and doc.text(n).casefold() == 'official details']
                assert len(buttons) == 1 and buttons[0].attrs.get('href') == record['offer']['url'], f'Visible ticket/Offer mismatch: {relative}'
                report['ticketOffers'] += 1
        panels = [n for n in doc.nodes if n.has('kc-more-details')]
        assert len(panels) == int(bool(more_details(record))), f'More details mismatch: {relative}'
        report['detailsPanels'] += len(panels)
        report['canadianPages'] += record.get('country') == 'CA'
    for source in site.rglob('*.html'):
        rel = source.relative_to(site).as_posix()
        if rel not in ctx['pages']:
            data = source.read_bytes()
            assert transform(rel, data, ctx) == data, f'Listing destination mismatch: {rel}'
    return report


def build(site):
    # These are generated public copies, not the repository's raw source feeds.
    # Redact before taking the rendering invariant snapshot; no other source
    # facts, catalog identities, listing counts or archive records may change.
    redact_public_feeds(site)
    before = source_hashes(site)
    ctx = context(site)
    for source in site.rglob('*.html'):
        data = source.read_bytes()
        updated = transform(source.relative_to(site).as_posix(), data, ctx)
        if updated != data:
            source.write_bytes(updated)
    (site / CSS).write_bytes((ROOT / CSS).read_bytes())
    assert source_hashes(site) == before, 'Source records changed during information rendering'
    return verify(site, ctx)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--site', required=True, type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(json.dumps(verify(args.site) if args.check else build(args.site), indent=2))
