#!/usr/bin/env python3
"""Verify this collection pass attempted the current roster, without networking.

Completion means the configured attempts ran and wrote fresh, consistent reports.
It does not mean every provider was accessible or that publication succeeded.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlparse

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
from collect_artist_website_events import eligible_website
from scan_all_artist_sources_legacy import SOCIAL_OR_STREAMING_HOSTS, safe_url

ATTEMPTED = {'ok', 'no_events', 'unmatched', 'identity_mismatch', 'blocked_by_robots',
             'failed', 'delegated_to_structured_rest'}
LIMITED = {'unmatched', 'identity_mismatch', 'blocked_by_robots', 'failed'}


def timestamp(value):
    if not isinstance(value, str) or not value:
        raise ValueError('Missing timestamp')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp lacks a timezone')
    return parsed


def enabled_roster(artists):
    if not isinstance(artists, list) or not artists:
        raise ValueError('Tracking roster must be a nonempty array')
    result = {}
    for artist in artists:
        if not isinstance(artist, dict) or type(artist.get('enabled', True)) is not bool:
            raise ValueError('Tracking roster contains an invalid enabled flag or record')
        if not artist.get('enabled', True):
            continue
        name = artist.get('name')
        if not isinstance(name, str) or not name.strip():
            raise ValueError('Enabled tracked artist has no identity')
        name = name.strip()
        if name in result:
            raise ValueError(f'Duplicate tracked artist identity: {name}')
        result[name] = artist
    if not result:
        raise ValueError('Tracking roster has no enabled artists')
    return result


def expected_surfaces(roster):
    expected = set()
    for name, artist in roster.items():
        expected.update((name, source, '') for source in ('Bandsintown', 'Songkick'))
        urls = set()
        for field, source in (('website', 'official website'), ('officialProfile', 'official profile')):
            url = safe_url(artist.get(field))
            if (not url or any(host in urlparse(url).netloc.lower() for host in SOCIAL_OR_STREAMING_HOSTS)
                    or url in urls):
                continue
            urls.add(url)
            expected.add((name, source, url))
        spotify = safe_url(artist.get('spotifyProfile'))
        if spotify:
            expected.add((name, 'Spotify profile', spotify))
    return expected


def verify_receipts(artists, full, bit, websites, eventbrite, started_at, now=None):
    now = now or datetime.now(timezone.utc)
    result = {'schemaVersion': 1, 'status': 'incomplete', 'collectionStartedAt': started_at,
              'verifiedAt': now.isoformat(), 'publicationVerified': False, 'artistsExpected': 0,
              'stages': {}, 'limitations': [], 'errors': []}
    errors, limitations = result['errors'], result['limitations']
    try:
        started = timestamp(started_at)
        if now.tzinfo is None or started > now:
            raise ValueError('Collection start is in the future or current time lacks a timezone')
        roster = enabled_roster(artists)
    except (ValueError, TypeError) as exc:
        errors.append(str(exc))
        return result
    names = set(roster)
    result['artistsExpected'] = len(names)
    result['rosterSha256'] = hashlib.sha256(json.dumps(sorted(names), ensure_ascii=False).encode()).hexdigest()
    reports = {'expanded': full, 'bandsintown': bit, 'websites': websites, 'eventbrite': eventbrite}
    times = {}
    for stage, report in reports.items():
        if not isinstance(report, dict):
            errors.append(f'{stage}: missing report object')
            reports[stage] = {}
            report = {}
        try:
            stamp = timestamp(report.get('generatedAt'))
            if not started <= stamp <= now:
                raise ValueError('timestamp is outside the current pass')
            times[stage] = stamp
        except (ValueError, TypeError) as exc:
            errors.append(f'{stage}: invalid current pass timestamp ({exc})')
        result['stages'][stage] = {'status': 'incomplete', 'generatedAt': report.get('generatedAt')}
    full, bit, websites, eventbrite = (reports[key] for key in ('expanded', 'bandsintown', 'websites', 'eventbrite'))

    def count(report, field, stage, expected=None):
        value = report.get(field)
        if type(value) is not int or value < 0:
            errors.append(f'{stage}: invalid {field}')
            return None
        if expected is not None and value != expected:
            errors.append(f'{stage}: {field} is {value}, expected {expected}')
        return value

    def rows(report, field, stage):
        value = report.get(field)
        if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
            errors.append(f'{stage}: missing or malformed {field}')
            return []
        return value

    count(full, 'artistsChecked', 'expanded', len(names))
    source_rows = rows(full, 'sourceResults', 'expanded')
    actual, statuses, attempted_names = set(), Counter(), set()
    for row in source_rows:
        name, source, url, status = (row.get(key, '') for key in ('artist', 'source', 'url', 'status'))
        if not all(isinstance(value, str) and value for value in (name, source, status)) or not isinstance(url, str):
            errors.append('expanded: malformed source identity/status')
            continue
        key = (name, source, url)
        if key in actual:
            errors.append(f'expanded: duplicate attempt for {name}: {source} {url}')
        actual.add(key)
        attempted_names.add(name)
        statuses[status] += 1
        if status not in ATTEMPTED:
            errors.append(f'expanded: unattempted or unknown status {status} for {name}: {source}')
        if source == 'Bandsintown' and status != 'delegated_to_structured_rest':
            errors.append(f'expanded: Bandsintown was not delegated for {name}')
        count(row, 'eventsFound', f'expanded {name}: {source}')
        if status in LIMITED:
            limitations.append({'stage': 'expanded', **row})
    expected = expected_surfaces(roster)
    for name, source, url in sorted(expected - actual):
        errors.append(f'expanded: missing attempt for {name}: {source} {url}')
    for name, source, url in sorted(actual - expected):
        errors.append(f'expanded: unexpected attempt for {name}: {source} {url}')
    declared = full.get('sourceStatusCounts')
    if (not isinstance(declared, dict) or any(type(value) is not int or value < 0 for value in declared.values())
            or declared != dict(statuses)):
        errors.append('expanded: sourceStatusCounts differs from actual sourceResults')
    result['stages']['expanded'].update(evidence='per_artist', artistsAttempted=len(names & attempted_names),
                                       sourceAttempts=len(source_rows), sourceStatusCounts=dict(statuses))

    summary = full.get('bandsintown')
    if not isinstance(summary, dict):
        summary = {}
    if summary.get('discoveryMode') != 'structured_rest' or summary.get('status') != 'ok':
        errors.append('bandsintown: Bandsintown pass did not finish with a current structured REST report')
    count(bit, 'artistsChecked', 'bandsintown', len(names))
    mapping = {'artistsAttempted': 'artistsChecked', 'resolved': 'artistsResolved',
               'rawUpcomingUSRows': 'rawUpcomingUSRows', 'rawUpcomingCARows': 'rawUpcomingCARows',
               'rawUpcomingRows': 'rawUpcomingRows', 'newEventsPublished': 'newNonFestivalShowsPublished',
               'festivalCandidatesHeld': 'festivalCandidatesHeld', 'requestErrors': 'requestErrors'}
    for summary_field, report_field in mapping.items():
        full_value = count(summary, summary_field, 'bandsintown summary')
        bit_value = count(bit, report_field, 'bandsintown')
        if full_value != bit_value:
            errors.append(f'bandsintown: embedded {summary_field} does not match {report_field}')
    if ('expanded' in times and 'bandsintown' in times
            and times['bandsintown'] >= times['expanded'] + timedelta(seconds=1)):
        errors.append('bandsintown: report was written after expanded summary')
    if all(type(bit.get(key)) is int for key in ('rawUpcomingRows', 'rawUpcomingUSRows', 'rawUpcomingCARows')):
        if bit['rawUpcomingRows'] != bit['rawUpcomingUSRows'] + bit['rawUpcomingCARows']:
            errors.append('bandsintown: rawUpcomingRows does not match US and Canadian totals')
    bit_errors = rows(bit, 'errors', 'bandsintown')
    request_errors = bit.get('requestErrors')
    if type(request_errors) is int:
        if request_errors < len(bit_errors) or (request_errors > 0 and not bit_errors):
            errors.append('bandsintown: requestErrors is inconsistent with reported error evidence')
        if request_errors:
            limitations.append({'stage': 'bandsintown', 'status': 'request_errors', 'count': request_errors,
                                'reportedErrors': len(bit_errors)})
    for item in bit_errors:
        if (not isinstance(item.get('artist'), str) or item['artist'] not in names
                or not isinstance(item.get('error'), str) or not item['error']):
            errors.append('bandsintown: invalid request-error artist identity or explanation')
        limitations.append({'stage': 'bandsintown', **item})
    resolved = bit.get('artistsResolved')
    if type(resolved) is int:
        if resolved > len(names):
            errors.append('bandsintown: artistsResolved exceeds tracked roster')
        elif resolved < len(names):
            limitations.append({'stage': 'bandsintown', 'status': 'artist_identity_not_resolved',
                                'count': len(names) - resolved})
    result['stages']['bandsintown'].update(evidence='aggregate_aligned_with_expanded_delegation',
        artistsAttempted=bit.get('artistsChecked'), resolved=resolved, requestErrors=bit.get('requestErrors'),
        retainedMissingProviderShows=bit.get('missingProviderShowsRetained', 0))

    count(websites, 'artistsConfigured', 'websites', len(names))
    count(websites, 'officialWebsitesChecked', 'websites', sum(bool(eligible_website(artist)) for artist in roster.values()))
    if websites.get('mode') != 'all-tracked-artists-official-website-scan':
        errors.append('websites: wrong collection mode')
    warning_count = count(websites, 'warningCount', 'websites')
    warnings = websites.get('warnings')
    if not isinstance(warnings, list) or not all(isinstance(item, str) for item in warnings):
        errors.append('websites: invalid warnings')
        warnings = []
    if warning_count is not None and warning_count < len(warnings):
        errors.append('websites: warningCount understates warnings')
    if warning_count:
        limitations.append({'stage': 'websites', 'status': 'provider_warnings', 'count': warning_count,
                            'reportedWarnings': warnings})
    # The cache may include accepted missing-provider rows restored by the
    # safeguard. eventsFound describes fresh discovery, not that retained cache.
    result['stages']['websites'].update(evidence='aggregate_current_roster_and_eligible_sites',
        artistsConfigured=websites.get('artistsConfigured'), sitesAttempted=websites.get('officialWebsitesChecked'),
        warningCount=warning_count, retainedMissingProviderShows=websites.get('missingProviderShowsRetained', 0))

    count(eventbrite, 'artistsChecked', 'eventbrite', len(names))
    event_rows = rows(eventbrite, 'artistResults', 'eventbrite')
    event_names, failed = set(), 0
    for row in event_rows:
        name, status = row.get('artist'), row.get('status')
        if not isinstance(name, str) or not name:
            errors.append('eventbrite: invalid artist identity')
            continue
        if name in event_names:
            errors.append(f'eventbrite: duplicate attempt for {name}')
        event_names.add(name)
        if not isinstance(status, str) or status not in {'ok', 'failed'}:
            errors.append(f'eventbrite: unattempted or unknown status for {name}: {status}')
        if status == 'failed':
            failed += 1
            if not isinstance(row.get('error'), str) or not row['error']:
                errors.append(f'eventbrite: failed attempt lacks explanation for {name}')
            limitations.append({'stage': 'eventbrite', **row})
    for name in sorted(names - event_names):
        errors.append(f'eventbrite: missing attempt for {name}')
    for name in sorted(event_names - names):
        errors.append(f'eventbrite: unexpected artist {name}')
    count(eventbrite, 'searchFailures', 'eventbrite', failed)
    detail_failures = count(eventbrite, 'detailFailures', 'eventbrite')
    if detail_failures:
        limitations.append({'stage': 'eventbrite', 'status': 'event_detail_failures', 'count': detail_failures})
    result['stages']['eventbrite'].update(evidence='per_artist', artistsAttempted=len(event_names & names),
                                        searchFailures=failed, detailFailures=detail_failures)
    for stage, evidence in result['stages'].items():
        evidence['status'] = 'incomplete' if any(error.startswith(stage + ':') or error.startswith(stage + ' ')
                                                for error in errors) else 'complete'
    result['status'] = 'incomplete' if errors else 'complete_with_limitations' if limitations else 'complete'
    return result


def verify_source(root, started_at, now=None):
    paths = ('config/artists.json', 'full-scan-status.json', 'bandsintown-status.json',
             'artist-website-status.json', 'eventbrite-scan-status.json')
    values, errors = [], []
    for name in paths:
        try:
            values.append(json.loads((root / name).read_text()))
        except (OSError, ValueError) as exc:
            errors.append(f'{name}: report unavailable or invalid ({type(exc).__name__})')
            values.append(None)
    result = verify_receipts(*values, started_at, now)
    result['errors'].extend(errors)
    if errors:
        result['status'] = 'incomplete'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('.'))
    parser.add_argument('--started-at', default=os.environ.get('KC_COLLECTION_STARTED_AT', ''))
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = verify_source(args.source, args.started_at)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'limitations'}, indent=2))
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as summary:
            summary.write(f"\n### Discovery receipt\n\nResult: {result['status']}. "
                          f"Tracked artists: {result['artistsExpected']}. "
                          f"Reported limitations: {len(result['limitations'])}.\n\n"
                          'This proves recorded collection attempts, not access to every source or publication.\n')
            for error in result['errors']:
                summary.write(f'\n- {error}\n')
    return int(bool(result['errors']))


if __name__ == '__main__':
    raise SystemExit(main())
