"""Read-only source-to-publication inventory acceptance.

The input repository is the post-refresh, post-identity-reconciliation checkout.
Its source feeds and reviewed URL state supply expectations independently of
the generated catalog and pages. Expiration and approved source additions are
therefore ordinary changes, rather than changes to a frozen count baseline.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import re

from build_seo_site import artist_path, event_path, merge_events, norm, scheduled
from url_continuity import flatten_redirects, merge_details, safe_path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = 'assets/fan-show-catalog.json'


def read_json(path, kind):
    value = json.loads(path.read_text())
    if not isinstance(value, kind):
        raise ValueError(f'{path.name} must be a {kind.__name__}')
    return value


def source_inventory(repo, day):
    """Project publication rules from sources, without invoking any writer."""
    date.fromisoformat(day)
    artists = read_json(repo / 'config/artists.json', list)
    feeds = [read_json(repo / filename, list) for filename in ('events.json', 'supplemental-events.json')]
    if any(not isinstance(row, dict) for rows in [artists, *feeds] for row in rows):
        raise ValueError('Source artist and event arrays must contain objects')
    roster = read_json(repo / 'config/owner-reviewed-roster.json', dict)
    removed = {norm(name) for name in roster.get('removedArtists', [])}

    def retained(event):
        names = {norm(name) for name in [*event.get('artists', []), event.get('headliner'), event.get('trackedArtist')] if name}
        return not names or not names.issubset(removed)

    # Reuse the production publication/hold/geography and cross-feed merge
    # policies. They operate on copies; the input checkout is never normalized
    # or repaired by this acceptance check.
    rows = merge_events(*[[row for row in feed if retained(row)] for feed in feeds])
    state_file = repo / '_url-continuity-state.json'
    if not state_file.is_file():
        state_file = repo / 'config/url-continuity.json'
    state = read_json(state_file, dict)
    rules = read_json(repo / 'config/event-identity-overrides.json', dict)
    identities = {}
    for event_id, record in state.get('events', {}).items():
        path = safe_path(record['path'])
        for source_id in [event_id, *record.get('sourceIds', [])]:
            if source_id in identities and identities[source_id] != path:
                raise ValueError(f'Conflicting retained identity: {source_id}')
            identities[source_id] = path
    for group in rules.get('merges', []):
        for source_id in [group['keepId'], *group.get('aliasIds', [])]:
            identities[source_id] = safe_path(group['keepPath'])
    redirects = flatten_redirects({**state.get('redirects', {}), **rules.get('redirects', {})})
    retired = set(state.get('retiredPaths', [])) | set(rules.get('retiredPaths', []))

    expected = {}
    for event in rows:
        if not scheduled(event):
            continue
        start = str(event.get('startDate') or '')[:10]
        end = str(event.get('endDate') or start)[:10]
        date.fromisoformat(start)
        date.fromisoformat(end)
        if end < start:
            raise ValueError(f'Source event ends before it starts: {event.get("id")}')
        if end < day:
            continue
        event_id = event.get('id')
        if not isinstance(event_id, str) or not event_id:
            raise ValueError('Current source event has no persistent ID')
        path = identities.get(event_id) or event_path(event)
        path = redirects.get(path, path)
        if not re.fullmatch(r'/event/[a-z0-9-]+/', path):
            raise ValueError(f'Invalid source event path: {path}')
        if path in retired:
            continue
        if path not in expected:
            expected[path] = {'date': start, 'end': end, 'artists': set(), 'sourceIds': [],
                              'event': deepcopy(event)}
        else:
            expected[path]['event'] = merge_details(expected[path]['event'], event)
        record = expected[path]
        if (record['date'], record['end']) != (start, end):
            raise ValueError(f'Conflicting source dates for retained URL: {path}')
        record['artists'].update(norm(name) for name in event.get('artists', []) if name)
        record['sourceIds'].append(event_id)

    # Real roster names take precedence over aliases. Ambiguous nicknames do
    # not silently assign another artist's show to the wrong profile.
    profiles = {}
    aliases = defaultdict(set)
    names = {}
    for artist in artists:
        if artist.get('enabled') is False:
            continue
        name = artist.get('name')
        if not isinstance(name, str) or not name.strip():
            raise ValueError('Enabled source artist has no name')
        path = artist_path(name)
        if path in profiles:
            raise ValueError(f'Duplicate source artist profile: {path}')
        profiles[path] = set()
        names[norm(name)] = path
        for alias in artist.get('aliases', []):
            aliases[norm(alias)].add(path)
    names.update({alias: next(iter(paths)) for alias, paths in aliases.items()
                  if alias and alias not in names and len(paths) == 1})
    for path, record in expected.items():
        for name in record['artists']:
            if name in names:
                profiles[names[name]].add(path)
    return expected, profiles, sum(map(len, feeds))


def source_records(repo, day):
    """Return normalized authoritative facts for the independent schema check.

    These records may contain private source details. They are comparison input
    only and must not be copied into the public release manifest or catalog.
    """
    from show_information_model import normalize
    repo = Path(repo)
    expected, _, _ = source_inventory(repo, day)
    artists = read_json(repo / 'config/artists.json', list)
    return {path: normalize(record['event'], artists=artists) for path, record in expected.items()}


def verify(site, day, repo=None):
    """Return errors and counts; never modify sources or the final artifact."""
    site, repo = Path(site), Path(repo) if repo is not None else ROOT
    result = {'asOf': day, 'expectedShows': 0, 'expectedArtists': 0,
              'sourceRows': 0, 'catalogShows': 0, 'errors': []}
    errors = result['errors']
    try:
        expected, profiles, source_rows = source_inventory(repo, day)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        errors.append(f'Cannot verify source inventory: {error}')
        return result
    result.update(expectedShows=len(expected), expectedArtists=len(profiles), sourceRows=source_rows)
    try:
        catalog = read_json(site / CATALOG, dict)
        shows, memberships = catalog['shows'], catalog['artists']
        if not isinstance(shows, list) or not isinstance(memberships, dict):
            raise ValueError('Catalog shows/artists have invalid types')
        if any(not isinstance(show, dict) or not isinstance(show.get('path'), str) for show in shows):
            raise ValueError('Catalog shows must contain objects with paths')
        if any(not isinstance(paths, list) or any(not isinstance(path, str) for path in paths)
               for paths in memberships.values()):
            raise ValueError('Catalog artist memberships must be lists of paths')
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        errors.append(f'Cannot verify published inventory: {error}')
        return result
    result['catalogShows'] = len(shows)
    if catalog.get('asOf') != day:
        errors.append(f'Catalog asOf differs from acceptance date: {catalog.get("asOf")} != {day}')
    actual = {show['path']: show for show in shows}
    for path, count in Counter(show['path'] for show in shows).items():
        if count > 1:
            errors.append(f'duplicate catalog path: {path} ({count})')
    for path in sorted(expected.keys() - actual.keys()):
        errors.append(f'Source show missing from catalog: {path}')
    for path in sorted(actual.keys() - expected.keys()):
        errors.append(f'Unexpected catalog show absent from current source: {path}')
    for path, record in sorted(expected.items()):
        if not (site / path.lstrip('/') / 'index.html').is_file():
            errors.append(f'Source show missing event page: {path}')
        if path in actual:
            show = actual[path]
            for key in ('date', 'end'):
                value = show.get(key) or (show.get('date') if key == 'end' else None)
                if value != record[key]:
                    errors.append(f'Catalog source date mismatch: {path} {key}: {value} != {record[key]}')
    for path in sorted(profiles.keys() - memberships.keys()):
        errors.append(f'Source roster missing artist profile: {path}')
    for path in sorted(memberships.keys() - profiles.keys()):
        errors.append(f'Catalog has unexpected artist profile: {path}')
    for artist, paths in sorted(memberships.items()):
        if len(paths) != len(set(paths)):
            errors.append(f'duplicate artist membership: {artist}')
        if artist in profiles and set(paths) != profiles[artist]:
            missing = sorted(profiles[artist] - set(paths))
            extra = sorted(set(paths) - profiles[artist])
            errors.append(f'Source artist membership mismatch: {artist}; missing={missing}; unexpected={extra}')
    return result
