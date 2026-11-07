"""Preserve published URLs and meaningful change dates across static rebuilds.

The last build pass owns URL reconciliation because pinned presentation overlays
also generate paths. State is saved only after a successful deployment; unrelated
feed collectors never own this registry. No network requests are made here.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
from catalog_removals import public_event

ORIGIN = 'https://kingdomcircuit.com'
STATE_FILE = 'config/url-continuity.json'
RULES_FILE = 'config/event-identity-overrides.json'
WORK_FILE = '_url-continuity-state.json'
NS = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
FEEDS = ('events.json', 'supplemental-events.json')
SNAPSHOT_FIELDS = ('id', 'title', 'startDate', 'endDate', 'startTime', 'endTime',
                   'timezone', 'city', 'state', 'country', 'venue', 'address',
                   'postalCode', 'artists', 'headliner', 'status', 'eventType',
                   'officialUrl', 'ticketUrl', 'image', 'imageType', 'confidence',
                   'publicDescription', 'locationUnconfirmed', 'mergedFromIds', 'legacyEventPaths')
# Reviewed November 5: these published source IDs duplicate the retained manual
# Flavor Fest concert identities. Keep the old links without a false removal notice.
REVIEWED_EVENT_ALIASES = (
    ('flavor-fest-2026-friday-concerts', 'manual:flavor-fest-2026-friday-concerts', '2026-11-06'),
    ('flavor-fest-2026-saturday-concerts', 'manual:flavor-fest-2026-saturday-concerts', '2026-11-07'),
)


def load(path, default):
    return json.loads(path.read_text()) if path.is_file() else copy.deepcopy(default)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def empty_state():
    return {'version': 1, 'events': {}, 'redirects': {}, 'pages': {}}


def norm(value):
    return ' '.join(str(value or '').casefold().split())


def generated_path(event):
    from build_seo_site import event_path
    return event_path(event)


def safe_path(path):
    if not re.fullmatch(r'/(?:[a-z0-9-]+/)*', path) or path.startswith('//'):
        raise ValueError(f'Invalid retained URL path: {path!r}')
    return path


def internal_event_paths(links):
    """Record local relationships without stripping external ticket origins."""
    paths = set()
    for link in links:
        parsed = urlsplit(link)
        if parsed.scheme and parsed.scheme != 'https':
            continue
        if parsed.netloc:
            if parsed.netloc.casefold() != urlsplit(ORIGIN).netloc:
                continue
        elif parsed.scheme:
            continue
        if parsed.path.startswith('/event/'):
            paths.add(safe_path(parsed.path))
    return sorted(paths)


def target_file(site, path):
    return site / safe_path(path).lstrip('/') / 'index.html'


def source_events(root):
    result = [r['event'] for r in load(root / 'event-history.json', {}).get('events', [])
              if isinstance(r.get('event'), dict)]
    for name in (*FEEDS, 'config/manual-events.json'):
        result.extend(load(root / name, []))
    from catalog_removals import removed_event
    from owner_roster import filter_events
    return [public_event(e) for e in filter_events(result) if not removed_event(e)]


def event_url(value):
    url = urlsplit(str(value or ''))
    # A tour home page is not evidence that two performances are the same.
    if url.scheme not in ('http', 'https') or not url.netloc or url.path.count('/') < 2:
        return ''
    path = url.path.rstrip('/')
    if path.lower() in ('/pages/tour', '/pages/events', '/tour/dates'):
        return ''
    return url.netloc.lower().removeprefix('www.') + path + ('?' + url.query if url.query and 'utm_' not in url.query else '')


def same_performance(left, right):
    """Conservative cross-provider match; unknown/conflicting sessions stay apart."""
    if any(norm(left.get(k)) != norm(right.get(k)) or not left.get(k)
           for k in ('startDate', 'city', 'state')):
        return False
    lt, rt = left.get('startTime'), right.get('startTime')
    if lt and rt and lt != rt:
        return False
    if left.get('endDate') and right.get('endDate') and left['endDate'] != right['endDate']:
        return False
    if norm(left.get('status') or 'scheduled') != norm(right.get('status') or 'scheduled'):
        return False
    artists = {norm(a) for a in left.get('artists', [])} & {norm(a) for a in right.get('artists', [])}
    if not artists:
        return False
    urls = {event_url(left.get(k)) for k in ('ticketUrl', 'officialUrl')} & {event_url(right.get(k)) for k in ('ticketUrl', 'officialUrl')}
    venue = norm(left.get('venue'))
    venue_matches = venue not in ('', 'tbd', 'tba', 'venue to be announced', 'venue not provided') and venue == norm(right.get('venue'))
    title_matches = norm(left.get('title')) == norm(right.get('title'))
    return bool((urls - {''}) and venue_matches and title_matches and (lt and rt))


def merge_details(preferred, other):
    result = copy.deepcopy(preferred)
    for key, value in other.items():
        if not result.get(key) and value not in (None, '', [], {}):
            result[key] = copy.deepcopy(value)
    for key in ('artists', 'sources', 'mergedFromIds', 'legacyEventPaths'):
        values = [*preferred.get(key, []), *other.get(key, [])]
        result[key] = list({json.dumps(v, sort_keys=True): v for v in values}.values())
        if not result[key] and key not in preferred and key not in other:
            result.pop(key, None)
    result['id'] = preferred['id']
    result['mergedFromIds'] = sorted(set(result.get('mergedFromIds', [])) | ({other['id']} if other['id'] != preferred['id'] else set()))
    return public_event(result)


def prepare(root):
    state = load(root / STATE_FILE, empty_state())
    rules = load(root / RULES_FILE, {})
    aliases = {}
    for event_id, record in state['events'].items():
        for source_id in [event_id, *record.get('sourceIds', [])]:
            if source_id in aliases and aliases[source_id] != event_id:
                raise ValueError(f'Event identity collision: {source_id}')
            aliases[source_id] = event_id
    for group in rules.get('merges', []):
        for source_id in [group['keepId'], *group['aliasIds']]:
            aliases[source_id] = group['keepId']
    retired = set(rules.get('retiredPaths', [])) | set(state.get('retiredPaths', []))
    all_rows = source_events(root)
    by_id = {e['id']: e for e in all_rows if e.get('id')}
    for group in rules.get('merges', []):
        keep = group['keepId']
        if group['keepPath'] in retired: continue
        preferred = by_id.get(keep) or state['events'].get(keep, {}).get('event')
        if not preferred:
            raise ValueError(f'Reviewed duplicate has no surviving record: {keep}')
        record = state['events'].setdefault(keep, {'path': group['keepPath'], 'sourceIds': [], 'event': preferred})
        for source_id in group['aliasIds']:
            record['sourceIds'] = sorted(set(record['sourceIds']) | {source_id})
            previous = state['events'].pop(source_id, None)
            if previous:
                state['redirects'][previous['path']] = record['path']
                record['sourceIds'] = sorted(set(record['sourceIds']) | set(previous.get('sourceIds', [])))
            if source_id in by_id:
                preferred = merge_details(preferred, by_id[source_id])
        record['event'] = {k: preferred[k] for k in SNAPSHOT_FIELDS if k in preferred}
        for path in group['aliasPaths']:
            state['redirects'][safe_path(path)] = record['path']
    state['redirects'].update(rules.get('redirects', {}))
    selected = {}
    owners = {}
    # A known survivor, then reviewed/manual records, wins over a new provider ID.
    rows = [(name, e) for name in FEEDS for e in load(root / name, [])]
    current_by_id = {e['id']: e for _, e in rows if e.get('id') and e.get('status') != 'merged'}
    rows.sort(key=lambda pair: (pair[1].get('id') not in state['events'], not str(pair[1].get('id', '')).startswith('manual:')))
    for name, original in rows:
        event = public_event(original)
        event_id = event.get('id')
        if not event_id:
            raise ValueError('Published events require a persistent source ID')
        if event.get('status') == 'merged':
            keep = event.get('mergedIntoId')
            if not keep or keep not in by_id:
                raise ValueError(f'Merged event lacks a valid survivor: {event_id}')
            aliases[event_id] = aliases.get(keep, keep)
        keep = aliases.get(event_id, event_id)
        if keep == event_id and keep not in state['events']:
            matches = [key for key, rec in state['events'].items() if same_performance(event, rec['event'])]
            matches += [key for key, other in selected.items() if key not in matches and same_performance(event, other)]
            if len(matches) == 1:
                keep = matches[0]
                aliases[event_id] = keep
        # A new source ID carries current facts; history only supplies identity.
        # Keep the current canonical/manual record when it is still in the feeds.
        preferred = current_by_id.get(keep) if keep != event_id else event
        if preferred is None and original.get('status') != 'merged': preferred = event
        preferred = preferred or by_id.get(keep) or state['events'].get(keep, {}).get('event') or event
        preferred = dict(preferred, id=keep)
        event = merge_details(preferred, event)
        old_path = generated_path(original)
        record = state['events'].setdefault(keep, {'path': generated_path(preferred), 'sourceIds': [], 'event': {}})
        record['sourceIds'] = sorted(set(record['sourceIds']) | {event_id, *event.get('mergedFromIds', [])} - {keep})
        for candidate in (old_path, generated_path(event)):
            if candidate != record['path']: state['redirects'][candidate] = record['path']
        for path in original.get('legacyEventPaths', []):
            if path != record['path']:
                state['redirects'][safe_path(path)] = record['path']
        record['event'] = {k: event[k] for k in SNAPSHOT_FIELDS if k in event}
        if keep in selected:
            selected[keep] = merge_details(selected[keep], event)
        else:
            selected[keep] = event
            owners[keep] = set()
        owners[keep].add(name)
    for name in FEEDS:
        save(root / name, [event for key, event in selected.items() if name in owners[key]])
    for key, event in selected.items():
        state['events'][key]['event'] = {k: event[k] for k in SNAPSHOT_FIELDS if k in event}
    # Existing reviewed mergedFromIds must also retire old archived identities.
    for keep, record in list(state['events'].items()):
        if keep not in state['events']: continue
        for alias in list(record.get('sourceIds', [])):
            if alias == keep: raise ValueError(f'Self-merged event identity: {keep}')
            prior = state['events'].pop(alias, None)
            if prior:
                if prior['path'] != record['path']:
                    state['redirects'][prior['path']] = record['path']
                record['sourceIds'] = sorted(set(record['sourceIds']) | set(prior.get('sourceIds', [])))
    save(root / WORK_FILE, state)
    return {'events': len(selected), 'redirects': len(state['redirects'])}


class PageFacts(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.title = ''; self.canonical = ''; self.robots = ''; self.refresh = ''
        self.description = ''; self.main = 0; self.in_title = False; self.script = None
        self.values = []; self.schemas = []; self.links = []; self.h1 = ''
        self.in_h1 = False
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'title': self.in_title = True
        if tag == 'h1': self.in_h1 = True
        if tag == 'main': self.main += 1
        if tag == 'meta':
            key = attrs.get('name', '').lower()
            if key in ('robots', 'description'): setattr(self, key, attrs.get('content', ''))
            if attrs.get('http-equiv', '').lower() == 'refresh': self.refresh = attrs.get('content', '')
        if tag == 'link' and attrs.get('rel') == 'canonical': self.canonical = attrs.get('href', '')
        if tag == 'a' and attrs.get('href'): self.links.append(attrs['href'])
        if tag == 'script':
            self.script = [] if attrs.get('type') == 'application/ld+json' else False
        if self.main and tag in ('a', 'img', 'time', 'source'):
            self.values.append([tag, {k: attrs[k] for k in ('href', 'src', 'srcset', 'alt', 'datetime') if k in attrs}])

    def handle_endtag(self, tag):
        if tag == 'title': self.in_title = False
        if tag == 'h1': self.in_h1 = False
        if tag == 'main': self.main = max(0, self.main - 1)
        if tag == 'script':
            if isinstance(self.script, list):
                self.schemas.append(json.loads(''.join(self.script)))
            self.script = None

    def handle_data(self, value):
        if self.script is not None:
            if isinstance(self.script, list): self.script.append(value)
            return
        if self.in_title: self.title += value
        if self.in_h1: self.h1 += value
        if self.main and value.strip(): self.values.append(' '.join(value.split()))

    def fingerprint(self):
        value = [self.title, self.description, self.canonical, self.values, self.schemas]
        return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def flatten_redirects(redirects):
    result = {}
    for source, target in redirects.items():
        safe_path(source); safe_path(target)
        seen = {source}
        while target in redirects:
            if target in seen: raise ValueError(f'Redirect cycle: {source}')
            seen.add(target); target = redirects[target]
        if target == source: raise ValueError(f'Self redirect: {source}')
        result[source] = target
    return result


def forwarding_page(target):
    """Meta refresh works without JS; replace preserves campaign query and Back."""
    safe_path(target)
    absolute = ORIGIN + target
    return f'''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="0; url={absolute}">
<link rel="canonical" href="{absolute}"><meta name="robots" content="index,follow">
<meta property="og:url" content="{absolute}"><title>Taking you to the show | Kingdom Circuit</title>
<script>const destination={json.dumps(target)};window.location.replace(destination+window.location.search+window.location.hash);</script>
<style>body{{margin:0;background:#080808;color:#f4f4f4;font:16px/1.6 system-ui,sans-serif}}main{{max-width:34rem;margin:12vh auto;padding:24px}}h1{{font-size:1.65rem;line-height:1.25}}a{{display:inline-block;background:#df725c;color:#080808;padding:12px 18px;border-radius:8px;font-weight:600}}a:focus-visible{{outline:3px solid #fff;outline-offset:5px}}</style>
</head><body><main><p>THE KINGDOM CIRCUIT</p><h1>Taking you to the show…</h1><p>This listing has an updated link.</p><a href="{absolute}">Continue to show</a></main></body></html>'''


def retained_page(path, title, body, *, index=True):
    from build_seo_site import FAVICON_HTML, GA_ID
    robots = 'index,follow' if index else 'noindex,follow'
    # Use only the rendered, already-redacted copy; never raw history fields.
    visible = ' '.join(value for value in PageFacts('<main>' + body + '</main>').values
                       if isinstance(value, str))
    description = ' '.join((title.rstrip('. ') + '. ' + visible).split())
    if len(description) > 160:
        description = description[:157].rsplit(' ', 1)[0] + '…'
    analytics = f"""<script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','{GA_ID}');</script>"""
    return f'''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="{robots}"><meta name="description" content="{html.escape(description, quote=True)}"><link rel="canonical" href="{ORIGIN + path}"><title>{html.escape(title)} | Kingdom Circuit</title>{FAVICON_HTML}{analytics}<style>body{{margin:0;background:#080808;color:#eee;font:16px/1.65 system-ui,sans-serif}}main{{max-width:56rem;margin:auto;padding:24px}}a{{color:#ef9988}}li{{margin:12px 0}}h1{{font-size:1.8rem}}img{{max-width:100%;height:auto}}</style></head><body><main><p><a href="/">THE KINGDOM CIRCUIT</a></p><h1>{html.escape(title)}</h1>{body}<p><a href="/shows/">Browse upcoming shows</a> · <a href="/artists/">Browse artists</a></p></main></body></html>'''


def restore_location_review(site, path, event):
    """Retain the reviewed conflicting booking without publishing a location."""
    title = '1K Phew — Location under review'
    body = ('<p><strong>Location not confirmed.</strong> The artist calendar lists '
            'Texas Motorplex with a Florida locality; the venue website places '
            'Texas Motorplex in Ennis, Texas. Confirm the booking and location '
            'before making plans.</p><p>This listing is temporarily excluded from '
            'upcoming show and location searches. No cancellation has been confirmed.</p>')
    if event.get('startDate'):
        body += '<p>Recorded date: ' + html.escape(str(event['startDate'])) + '</p>'
    body += ('<p><a href="https://www.reachrecords.com/artists/1k-phew/" rel="noopener">'
             'Artist calendar</a> · <a href="https://www.texasmotorplex.com/" '
             'rel="noopener">Venue information</a></p>')
    file = target_file(site, path)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(retained_page(path, title, body, index=False))


def reconcile_reviewed_aliases(state, history, current_ids, site):
    """Consolidate only the two reviewed, still-matching published aliases."""
    for alias_id, keep_id, day in REVIEWED_EVENT_ALIASES:
        old = state['events'].get(alias_id)
        keep = state['events'].get(keep_id)
        if not old or not keep or keep_id not in current_ids:
            continue
        old_event = history.get(alias_id, old['event'])
        current = history.get(keep_id, keep['event'])
        # These exact IDs were reviewed together; their TicketSpice root and
        # festival schedule URLs do not qualify for generic provider matching.
        identity_fields = ('title', 'startDate', 'startTime', 'city', 'state', 'country', 'venue')
        matching = all(norm(old_event.get(k)) and norm(old_event.get(k)) == norm(current.get(k))
                       for k in identity_fields)
        shared_artists = {norm(a) for a in old_event.get('artists', [])} & {
            norm(a) for a in current.get('artists', [])}
        if (old_event.get('startDate') != day or current.get('startDate') != day
                or not matching or not shared_artists
                or norm(old_event.get('status') or 'scheduled') != norm(current.get('status') or 'scheduled')
                or (old_event.get('endDate') and current.get('endDate')
                    and old_event['endDate'] != current['endDate'])):
            continue
        destination = safe_path(keep['path'])
        file = target_file(site, destination)
        if not file.is_file():
            continue
        facts = PageFacts(file.read_text())
        if facts.refresh or facts.canonical != ORIGIN + destination:
            continue
        for path in {old['path'], generated_path(old_event), *old_event.get('legacyEventPaths', [])}:
            if path != destination:
                state['redirects'][safe_path(path)] = destination
        keep['sourceIds'] = sorted(set(keep.get('sourceIds', [])) | {alias_id, *old.get('sourceIds', [])})
        del state['events'][alias_id]


def restore_event(site, path, event, today, *, session_review=False):
    esc = html.escape
    status = norm(event.get('status'))
    day = event.get('endDate') or event.get('startDate', '')
    if status == 'private': notice = 'Private event. Not open to the public.'
    elif status in ('cancelled', 'canceled'): notice = 'This event was cancelled.'
    elif status == 'postponed': notice = 'This event was postponed. A new date has not been confirmed here.'
    elif day and day < today: notice = 'This date has passed. These recorded details are retained for reference.'
    else: notice = 'This previously listed show is no longer in our current calendar. Confirm its status with the organizer.'
    details = [(label, event.get(key)) for label, key in [('Recorded date', 'startDate'), ('Listed start time', 'startTime'), ('Venue', 'venue'), ('City', 'city'), ('State / region', 'state')]]
    body = '<p><strong>' + notice + '</strong></p><dl>'
    body += ''.join(f'<dt>{label}</dt><dd>{esc(str(value))}</dd>' for label, value in details if value)
    body += '</dl>'
    if session_review:
        body += ('<p>Archived source listings for this date record different start times. '
                 'Whether they describe separate performances has not been verified. '
                 'The time above belongs to this specific source listing.</p>')
    if event.get('artists'):
        body += '<p>' + esc(' · '.join(event['artists'])) + '</p>'
    if event.get('address') and status != 'private':
        body += '<p>' + esc(str(event['address'])) + '</p>'
    image = str(event.get('image') or '')
    if image.startswith(('assets/', '/assets/')) and (site / image.lstrip('/')).is_file():
        body += f'<img src="/{esc(image.lstrip("/"), quote=True)}" alt="{esc(str(event.get("title") or "Show artwork"), quote=True)}" loading="lazy">'
    link = event.get('officialUrl') or event.get('ticketUrl')
    if link and urlsplit(link).scheme in ('http', 'https'):
        body += f'<p><a href="{esc(link, quote=True)}" rel="noopener">Original official information</a></p>'
    target_file(site, path).parent.mkdir(parents=True, exist_ok=True)
    target_file(site, path).write_text(retained_page(path, event.get('title') or 'Show archive', body))


def rewrite_paths(text, mapping):
    if not mapping: return text
    # Exact path substrings include their trailing slash and cannot match another slug.
    pattern = re.compile('|'.join(re.escape(k) for k in sorted(mapping, key=len, reverse=True)))
    return pattern.sub(lambda match: mapping[match[0]], text)


def remember_reviewed_calendars(state, rules, allowed_artists):
    """Recover known calendars from retained identities, never guessed URLs."""
    from build_seo_site import slug
    for calendar in rules.get('retainedCalendars', []):
        path = safe_path(calendar['path'])
        artist = calendar.get('artist')
        if artist and slug(artist) not in allowed_artists:
            continue
        related = []
        for record in state['events'].values():
            event = record['event']
            if artist and norm(artist) not in {norm(a) for a in event.get('artists', [])}:
                continue
            if any(norm(event.get(field)) != norm(calendar[field])
                   for field in ('state', 'city') if field in calendar):
                continue
            if calendar.get('month') and not str(event.get('startDate', '')).startswith(calendar['month'] + '-'):
                continue
            related.append((event.get('startDate', ''), record['path']))
        if related:
            state['pages'].setdefault(path, {}).update(
                heading=calendar['title'], eventPaths=[p for _, p in sorted(set(related))])


def finalize(root, site, today=None):
    today = today or dt.datetime.now(dt.timezone.utc).date().isoformat()
    # Build overlays copy source trees; these registries are never public assets.
    for internal in (STATE_FILE, RULES_FILE, WORK_FILE):
        (site / internal).unlink(missing_ok=True)
    state = load(root / WORK_FILE, load(root / STATE_FILE, empty_state()))
    rules = load(root / RULES_FILE, {})
    history = {e['id']: e for e in source_events(root) if e.get('id')}
    # Reconciled current feeds outrank older manual seeds and archived snapshots.
    current_ids = set()
    for name in FEEDS:
        current = {e['id']: e for e in load(root / name, []) if e.get('id')}
        history.update(current)
        current_ids.update(current)
    aliases = {alias: key for key, rec in state['events'].items() for alias in rec.get('sourceIds', [])}
    # Remember only actual generated event pages, not every unverified history record.
    for key, event in history.items():
        if key in aliases: continue
        path = generated_path(event)
        file = target_file(site, path)
        if path in state['redirects']: continue
        if file.is_file() and key not in state['events']:
            facts = PageFacts(file.read_text())
            if facts.refresh or facts.canonical != ORIGIN + path: continue
            state['events'][key] = {'path': path, 'sourceIds': [], 'event': {k: event[k] for k in SNAPSHOT_FIELDS if k in event}}
    from catalog_removals import location_review_event, removed_event
    from owner_roster import filter_events
    excluded_paths = set(rules.get('retiredPaths', [])) | set(state.get('retiredPaths', []))
    session_review_paths = {p for group in rules.get('reviewRequired', []) for p in group.get('paths', [])}
    for key, record in list(state['events'].items()):
        if record['path'] not in excluded_paths and key not in current_ids and location_review_event(record['event']):
            preferred = safe_path(record['path'])
            restore_location_review(site, preferred, record['event'])
            state['pages'].pop(preferred, None)
            continue
        if record['path'] in excluded_paths or removed_event(record['event']) or not filter_events([record['event']]):
            excluded_paths.add(record['path'])
            del state['events'][key]
            continue
        event = history.get(key, record['event'])
        current = generated_path(event)
        preferred = safe_path(record['path'])
        source = target_file(site, current)
        target = target_file(site, preferred)
        if current != preferred and source.is_file() and not PageFacts(source.read_text()).refresh:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            state['redirects'][current] = preferred
        if not target.is_file():
            restore_event(site, preferred, record['event'], today)
        # Similar archived cards must not hide the source-specific clocks that
        # prevented a reviewed merge. No active performance is rewritten here.
        if preferred in session_review_paths and (record['event'].get('endDate') or record['event'].get('startDate', '9999')) < today:
            restore_event(site, preferred, record['event'], today, session_review=True)
        for old in event.get('legacyEventPaths', []):
            if old != preferred: state['redirects'][safe_path(old)] = preferred
    reconcile_reviewed_aliases(state, history, current_ids, site)
    # Existing artist/event aliases already carry a valid destination canonical.
    for file in site.rglob('index.html'):
        path = '/' + file.parent.relative_to(site).as_posix().strip('./') + '/'
        if path == '//': path = '/'
        facts = PageFacts(file.read_text())
        if facts.canonical.startswith(ORIGIN + '/'):
            canonical = urlsplit(facts.canonical).path
            if path != canonical and ('location.replace' in file.read_text() or facts.refresh):
                state['redirects'][path] = canonical
    state['redirects'] = flatten_redirects(state['redirects'])
    for source, target in state['redirects'].items():
        if target in excluded_paths: excluded_paths.add(source)
    for path in excluded_paths:
        target_file(site, path).unlink(missing_ok=True)
        state['pages'].pop(path, None)
    state['retiredPaths'] = sorted(excluded_paths)
    state['redirects'] = {a: b for a, b in state['redirects'].items() if a not in excluded_paths and b not in excluded_paths}
    state['redirects'] = flatten_redirects(state['redirects'])
    redirects = state['redirects']
    occupied = {}
    for event_id, record in state['events'].items():
        path = record['path']
        if path in occupied and occupied[path] != event_id:
            raise ValueError(f'Two event identities claim one URL: {path}')
        if path in redirects:
            raise ValueError(f'Canonical event URL is also an alias: {path}')
        occupied[path] = event_id
    # Retain previously published artist/location calendars when the last show passes.
    retired = excluded_paths
    from build_seo_site import slug
    allowed_artists = {slug(a.get('name')) for a in load(root / 'config/artists.json', []) if a.get('enabled') is not False}
    remember_reviewed_calendars(state, rules, allowed_artists)
    for path, record in state['pages'].items():
        if path in redirects or path in retired or target_file(site, path).exists(): continue
        if not path.startswith(('/artists/', '/shows/')): continue
        parts = path.strip('/').split('/')
        if parts[0] == 'artists' and len(parts) > 1 and parts[1] not in allowed_artists: continue
        title = record.get('heading') or record.get('title', '').split('|')[0].strip()
        body = '<p>No upcoming shows are currently confirmed on this calendar.</p>'
        # Older page snapshots also captured external ticket URL pathnames.
        # Relationships do not own URLs: retain only registered local events
        # and their aliases, without relaxing canonical/redirect validation.
        related = [p for p in record.get('eventPaths', []) if p in occupied or p in redirects]
        related = list(dict.fromkeys(redirects.get(p, p) for p in related))
        links = []
        for event_path in related:
            if target_file(site, event_path).is_file():
                facts = PageFacts(target_file(site, event_path).read_text())
                links.append(f'<li><a href="{event_path}">{html.escape(facts.h1 or facts.title)}</a></li>')
        if links: body += '<h2>Previously listed shows</h2><ul>' + ''.join(links) + '</ul>'
        target = target_file(site, path); target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(retained_page(path, title, body))
    for source, target in redirects.items():
        if not target_file(site, target).is_file():
            raise ValueError(f'Redirect target missing: {source} -> {target}')
    for file in site.rglob('*'):
        if file.suffix not in ('.html', '.json', '.js', '.xml'): continue
        if file.name.endswith('manifest.json') or file.name.endswith('report.json'): continue
        before = file.read_text()
        after = rewrite_paths(before, redirects)
        if before != after: file.write_text(after)
    identities = {source_id: record['path'] for key, record in state['events'].items()
                  for source_id in [key, *record.get('sourceIds', [])]}
    for name in FEEDS:
        file = site / name
        if not file.is_file(): continue
        rows = load(file, [])
        for event in rows:
            if event.get('id') in identities: event['canonicalPath'] = identities[event['id']]
        save(file, rows)
    app = site / 'app.js'
    if app.is_file():
        source = app.read_text()
        source = source.replace(' if (event.canonicalPath) return event.canonicalPath;', '')
        source, count = re.subn(r'function eventDetailUrl\(event\)\s*\{',
            'function eventDetailUrl(event) { if (event.canonicalPath) return event.canonicalPath;', source, count=1)
        if count != 1: raise ValueError('Cannot preserve runtime event links: eventDetailUrl missing')
        app.write_text(source)
    for source, target in redirects.items():
        file = target_file(site, source); file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(forwarding_page(target))
    sitemap = ET.Element('urlset', xmlns=NS['s'])
    dated = 0
    for file in sorted(site.rglob('index.html')):
        path = '/' + file.parent.relative_to(site).as_posix().strip('./') + '/'
        if path == '//': path = '/'
        if path in redirects or path.startswith(('/_','/chh-show-night/')): continue
        facts = PageFacts(file.read_text())
        if 'noindex' in facts.robots or facts.canonical != ORIGIN + path: continue
        previous = state['pages'].get(path, {})
        fingerprint = facts.fingerprint()
        # Unknown historical dates stay omitted. Changes from a recorded baseline
        # receive the observed publication date; identical rebuilds keep the date.
        lastmod = previous.get('lastmod')
        if previous.get('fingerprint') and previous['fingerprint'] != fingerprint:
            lastmod = today
        elif not previous and path not in rules.get('baselinePaths', []):
            lastmod = today
        state['pages'][path] = {'fingerprint': fingerprint, 'lastmod': lastmod, 'title': facts.title,
                                'heading': facts.h1, 'eventPaths': internal_event_paths(facts.links)}
        node = ET.SubElement(sitemap, 'url'); ET.SubElement(node, 'loc').text = ORIGIN + path
        if lastmod: ET.SubElement(node, 'lastmod').text = lastmod; dated += 1
    ET.indent(sitemap)
    (site / 'sitemap.xml').write_bytes(ET.tostring(sitemap, encoding='utf-8', xml_declaration=True))
    state['publishedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
    save(root / WORK_FILE, state)
    # Public receipt contains no source records or internal identity decisions.
    receipt = {'version': 1, 'redirects': redirects, 'pages': {p: {k: r[k] for k in ('fingerprint', 'lastmod')} for p, r in state['pages'].items() if p not in redirects and target_file(site, p).exists()}, 'datedPages': dated}
    save(site / 'url-continuity-manifest.json', receipt)
    verify(site)
    return {'redirects': len(redirects), 'canonicalPages': len(sitemap), 'datedPages': dated}


def verify(site):
    for internal in (STATE_FILE, RULES_FILE, WORK_FILE):
        if (site / internal).exists(): raise ValueError(f'Internal URL registry was published: {internal}')
    receipt = load(site / 'url-continuity-manifest.json', {})
    redirects = receipt.get('redirects', {})
    if redirects != flatten_redirects(redirects): raise ValueError('Redirect chains remain')
    urls = {}
    for node in ET.parse(site / 'sitemap.xml').getroot():
        loc = node.find('s:loc', NS).text
        path = urlsplit(loc).path
        if path in urls or path in redirects: raise ValueError(f'Invalid duplicate/alias sitemap entry: {path}')
        file = target_file(site, path)
        if not file.is_file(): raise ValueError(f'Missing sitemap target: {path}')
        facts = PageFacts(file.read_text())
        if facts.canonical != loc or 'noindex' in facts.robots: raise ValueError(f'Conflicting sitemap canonical: {path}')
        lastmod = node.find('s:lastmod', NS)
        if lastmod is not None:
            record = receipt.get('pages', {}).get(path, {})
            if record.get('lastmod') != lastmod.text or record.get('fingerprint') != facts.fingerprint():
                raise ValueError(f'Unverified sitemap lastmod: {path}')
            if dt.date.fromisoformat(lastmod.text) > dt.datetime.now(dt.timezone.utc).date(): raise ValueError('Future sitemap date')
        urls[path] = True
    for source, target in redirects.items():
        text = target_file(site, source).read_text(); facts = PageFacts(text)
        if facts.canonical != ORIGIN + target or facts.refresh != '0; url=' + ORIGIN + target:
            raise ValueError(f'Invalid forwarding signals: {source}')
        if not target_file(site, target).is_file() or PageFacts(target_file(site, target).read_text()).canonical != ORIGIN + target:
            raise ValueError(f'Invalid final destination: {source}')
        if facts.schemas or 'googletagmanager' in text or 'gtag(' in text:
            raise ValueError(f'Forwarding page emits event data or page views: {source}')
    for file in site.rglob('index.html'):
        path = '/' + file.parent.relative_to(site).as_posix().strip('./') + '/'
        if path in redirects: continue
        for link in PageFacts(file.read_text()).links:
            parsed = urlsplit(link)
            if parsed.netloc and parsed.netloc != 'kingdomcircuit.com': continue
            if parsed.path in redirects: raise ValueError(f'Internal link still uses an alias: {file} -> {link}')
    return {'redirects': len(redirects), 'sitemapPages': len(urls)}


def persist(root, incoming):
    new = load(incoming, {})
    old = load(root / STATE_FILE, empty_state())
    if new.get('version') != 1: raise ValueError('Invalid published URL state')
    if old.get('publishedAt', '') > new.get('publishedAt', ''):
        raise ValueError('Refusing to overwrite newer deployed URL state')
    # The completed artifact is authoritative. Unioning an older snapshot would
    # resurrect removals. Concurrent newer publications are rejected above.
    absorbed = {alias for record in new['events'].values() for alias in record.get('sourceIds', [])}
    for event_id in absorbed:
        new['events'].pop(event_id, None)
    new['redirects'] = flatten_redirects(new['redirects'])
    save(root / STATE_FILE, new)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--site', type=Path)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--persist', type=Path)
    args = parser.parse_args(); root = Path.cwd()
    if args.persist: persist(root, args.persist); return
    result = prepare(root) if args.prepare else verify(args.site) if args.check else finalize(root, args.site)
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
