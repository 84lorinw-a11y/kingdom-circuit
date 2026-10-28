"""Keep organizer-confirmed private bookings listed with clear admission labels.

Preserve the complete records and their established URLs with a private-event
notice. Provider calendar imports cannot reopen admission without owner review.
"""
import argparse
import copy
from datetime import datetime
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def records(root=ROOT):
    path = root / 'config/private-events.json'
    return json.loads(path.read_text()) if path.exists() else []


def matches(event, private):
    if event.get('startDate') != private.get('startDate'):
        return False
    ids = {private['id'], *private.get('mergedFromIds', [])}
    ids |= {value.removeprefix('manual:') for value in list(ids)}
    if event.get('id') in ids:
        return True
    numbers = set(re.findall(r'bandsintown\.com/[et]/(\d+)',
                            str(private.get('officialUrl') or '')))
    return any(re.search(r'bandsintown\.com/[et]/' + num + r'(?:[/?#-]|$)',
                         str(event.get(field) or ''))
               for num in numbers for field in ('officialUrl', 'ticketUrl'))


def apply(root=ROOT, as_of=None):
    private = records(root)
    def find(event):
        return next((item for item in private if matches(event, item)), None)
    day = as_of or datetime.now(ZoneInfo('America/Los_Angeles')).date().isoformat()
    changed_files = 0
    for name in ('events.json', 'supplemental-events.json'):
        path = root / name
        if not path.exists():
            continue
        rows = json.loads(path.read_text())
        kept = []
        seen = set()
        # Retain one canonical listing per performance, including after a
        # provider refresh drops it or republishes it as publicly scheduled.
        for event in rows:
            pinned = find(event)
            if not pinned:
                kept.append(event)
            elif pinned['id'] not in seen and (pinned.get('endDate') or pinned['startDate']) >= day:
                kept.append(copy.deepcopy(pinned))
                seen.add(pinned['id'])
        kept.extend(copy.deepcopy(event) for event in private if event['id'] not in seen
                    and (event.get('endDate') or event['startDate']) >= day)
        if rows != kept:
            path.write_text(json.dumps(kept, indent=2, ensure_ascii=False) + '\n')
            changed_files += 1
    # Retain historical records and original identities; only annotate admission.
    for name in ('event-history.json', 'config/artist-website-seed-events.json', 'config/manual-events.json'):
        path = root / name
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        rows = data['events'] if isinstance(data, dict) else data
        changed = False
        for entry in rows:
            event = entry.get('event', entry)
            pinned = find(event)
            if pinned:
                patch = {key: pinned[key] for key in ('status', 'admission',
                         'publicDescription', 'admissionVerifiedAt', 'admissionSource')}
                changed |= any(event.get(key) != value for key, value in patch.items())
                event.update(copy.deepcopy(patch))
        if changed:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
            changed_files += 1
    return changed_files


def label_cards(source, root=ROOT):
    """Apply admission to cards after imported templates, before discovery builds."""
    from build_seo_site import event_path, esc
    from mobile_discovery import Document, replace_spans
    paths = {event_path(e): e for e in records(root)}
    doc = Document(source)
    changes = []
    for card in doc.nodes:
        if 'data-event-card' not in card.attrs:
            continue
        fragment = Document(doc.raw(card))
        headings = [n for n in fragment.nodes if n.tag == 'h3']
        if not headings:
            continue
        link = next((n for n in headings[0].children if n.tag == 'a'), None)
        if not link or link.attrs.get('href') not in paths:
            continue
        href = link.attrs['href']
        edits = [(link.opening_end, link.closing_start,
                  esc(paths[href]['title'] + ' — Private Event'))]
        badges = fragment.one(lambda n: n.has('event-badges'))
        edits.append((badges.start, badges.end,
                      '<div class="event-badges"><span class="badge badge-gold">Private Event</span></div>'))
        footer = fragment.one(lambda n: n.has('event-footer'))
        edits.append((footer.start, footer.end,
                      '<div class="event-footer"><p><strong>Not open to the public.</strong></p>'
                      f'<a class="official-button" href="{esc(href)}">Event details</a></div>'))
        changes.append((card.start, card.end, replace_spans(fragment.source, edits)))
    return replace_spans(source, changes)


def label_listings(site, root=ROOT):
    changed = 0
    for path in site.rglob('*.html'):
        before = path.read_text()
        after = label_cards(before, root)
        if before != after:
            path.write_text(after)
            changed += 1
    return changed


def write_pages(site, root=ROOT):
    from build_seo_site import page, esc, event_path, format_date, image_url, breadcrumb_schema
    written = []
    for event in records(root):
        canonical = event_path(event)
        paths = [canonical, *event.get('legacyEventPaths', [])]
        for path in dict.fromkeys(paths):
            if not re.fullmatch(r'/event/[a-z0-9-]+/', path):
                raise ValueError('Invalid private event path: ' + path)
            crumbs = [('Shows', '/shows/'), ('Private event', canonical)]
            body = f'''<section class="event-detail-section">
<div class="empty-panel" role="status"><strong>Private event — not open to the public.</strong>
<p>North Canton Chapel confirmed this booking is for a retreat. Public attendance has not been approved. Please do not make plans to attend unless the church confirms that it is open.</p></div>
<article class="event-detail"><div class="event-detail-media"><img class="artist-photo" src="{esc(image_url(event['image']))}" alt="808 BEEZY" width="1200" height="675"></div>
<div class="event-detail-copy"><p class="eyebrow">Private event</p><h1>808 BEEZY — AMPLIFY</h1>
<p class="artist-line"><a href="/artists/808-beezy/">808 BEEZY</a></p>
<dl class="detail-list"><div><dt>Status</dt><dd>Private Event — not open to the public</dd></div><div><dt>Date</dt><dd><time data-kc-private-date datetime="{esc(event['startDate'])}" data-end-date="{esc(event.get('endDate') or event['startDate'])}">{esc(format_date(event))}</time></dd></div>
<div><dt>Venue</dt><dd>{esc(event['venue'])}</dd></div><div><dt>Location</dt><dd>{esc(event['city'])}, {esc(event['state'])}</dd></div></dl>
<p>This listing is retained for reference. We will update it if the church confirms public admission.</p>
<a class="primary-button" href="/shows/">Explore public shows</a></div></article></section>'''
            # Private bookings are not eligible for public Event rich results.
            document = page('808 BEEZY — AMPLIFY | Private Event | Kingdom Circuit',
                            event['publicDescription'], canonical, body,
                            [breadcrumb_schema(crumbs)])
            target = site / path.strip('/') / 'index.html'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(document)
            written.append(path)
    return written


def verify(site, root=ROOT):
    from build_seo_site import event_path
    from calendar_maintenance import artist_errors
    private = records(root)
    catalog = json.loads((site / 'assets/fan-show-catalog.json').read_text())
    paths = {path for event in private for path in
             [event_path(event), *event.get('legacyEventPaths', [])]}
    upcoming = [event for event in private if (event.get('endDate') or event['startDate']) >= catalog['asOf']]
    by_path = {show['path']: show for show in catalog['shows']}
    for event in upcoming:
        assert 'Private Event' in by_path[event_path(event)]['name'], 'Private listing missing or unlabeled'
    for name in ('events.json', 'supplemental-events.json'):
        rows = json.loads((site / name).read_text())
        for held in upcoming:
            found = [event for event in rows if matches(event, held)]
            assert len(found) == 1 and found[0]['status'] == 'private', name
    for path in paths:
        text = (site / path.strip('/') / 'index.html').read_text()
        assert 'Private event — not open to the public.' in text, path
        assert 'Explore public shows' in text, path
        assert 'bandsintown.com' not in text, (path, 'admission link remains')
        for raw in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', text, re.S):
            assert not re.search(r'"@type"\s*:\s*"(?:MusicEvent|Event|Festival|Offer)"', raw), path
    artist = (site / 'artists/808-beezy/index.html').read_text()
    from mobile_discovery import Document
    from national_discovery import card_records
    doc = Document(artist)
    for event in upcoming:
        rows = [n for n in doc.nodes if n.has('kc-rd-show-row') and n.attrs.get('href') == event_path(event)]
        assert rows and all('Private Event' in doc.text(n) for n in rows), 'Artist private label missing'
    for relative in ('shows/index.html', 'shows/ohio/index.html', 'artists/808-beezy/ohio/index.html'):
        cards = {r['href']: r for r in card_records((site / relative).read_text())}
        for event in upcoming:
            card = cards[event_path(event)]
            assert 'Private Event' in card['name'] and 'Not open to the public.' in card['html'], relative
            assert 'bandsintown.com' not in card['html'], relative
    assert not artist_errors(artist, catalog['shows'], catalog['asOf'])
    return {'privateBookings': len(private), 'retainedUrls': len(paths),
            'listedWithPrivateLabels': True, 'upcoming': len(catalog['shows'])}


def public_history(target, root=ROOT):
    data = json.loads((root / 'event-history.json').read_text())
    private = records(root)
    data['events'] = [entry for entry in data['events']
                      if entry.get('event', {}).get('status') != 'private'
                      and not any(matches(entry.get('event', {}), held) for held in private)]
    target.write_text(json.dumps(data, ensure_ascii=False) + '\n')
    return len(data['events'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=ROOT)
    parser.add_argument('--site', type=Path)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--label-listings', action='store_true')
    parser.add_argument('--public-history', type=Path)
    args = parser.parse_args()
    print(json.dumps({'publicHistoryRecords': public_history(args.public_history, args.source)} if args.public_history else
                    verify(args.site, args.source) if args.check else
                    {'listingPagesLabeled': label_listings(args.site, args.source)} if args.label_listings else
                    {'privatePages': write_pages(args.site, args.source)} if args.site
                     else {'sourceFilesUpdated': apply(args.source)}))
