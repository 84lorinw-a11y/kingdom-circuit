"""Keep organizer-confirmed private bookings out of public show discovery.

Preserve the complete records and their established URLs with a private-event
notice. Provider calendar imports cannot reopen admission without owner review.
"""
import argparse
import copy
import json
from pathlib import Path
import re

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


def apply(root=ROOT):
    private = records(root)
    def find(event):
        return next((item for item in private if matches(event, item)), None)
    removed = 0
    for name in ('events.json', 'supplemental-events.json', 'config/manual-events.json'):
        path = root / name
        if not path.exists():
            continue
        rows = json.loads(path.read_text())
        kept = [event for event in rows if not find(event)]
        removed += len(rows) - len(kept)
        if rows != kept:
            path.write_text(json.dumps(kept, indent=2, ensure_ascii=False) + '\n')
    # Retain historical records and original identities; only annotate admission.
    for name in ('event-history.json', 'config/artist-website-seed-events.json'):
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
    return removed


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
<dl class="detail-list"><div><dt>Status</dt><dd>Private event</dd></div><div><dt>Date</dt><dd>{esc(format_date(event))}</dd></div>
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
    assert not paths & {show['path'] for show in catalog['shows']}, 'Private event in discovery'
    for name in ('events.json', 'supplemental-events.json'):
        assert not any(matches(event, held) for event in json.loads((site / name).read_text())
                       for held in private), name
    for path in paths:
        text = (site / path.strip('/') / 'index.html').read_text()
        assert 'Private event — not open to the public.' in text, path
        assert 'Explore public shows' in text, path
        assert 'bandsintown.com' not in text, (path, 'admission link remains')
        for raw in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', text, re.S):
            assert not re.search(r'"@type"\s*:\s*"(?:MusicEvent|Event|Festival|Offer)"', raw), path
    artist = (site / 'artists/808-beezy/index.html').read_text()
    assert not any(path in artist for path in paths), 'Private event in artist recommendations'
    assert not artist_errors(artist, catalog['shows'], catalog['asOf'])
    return {'privateBookings': len(private), 'retainedUrls': len(paths),
            'excludedFromPublicListings': True, 'upcoming': len(catalog['shows'])}


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
    parser.add_argument('--public-history', type=Path)
    args = parser.parse_args()
    print(json.dumps({'publicHistoryRecords': public_history(args.public_history, args.source)} if args.public_history else
                    verify(args.site, args.source) if args.check else
                    {'privatePages': write_pages(args.site, args.source)} if args.site
                     else {'publicRecordsRemoved': apply(args.source)}))
