"""Keep approved Canadian bookings through automated source and site refreshes.

The baseline is the existing catalog, not a second hard-coded event registry.
Expired dates can roll off normally; explicit cancellations and merged records
remain editable. A collector's silence is never permission to delete a booking.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .catalog_removals import removed_event
    from .prune_past_events import is_past_event, today_cutoff
except ImportError:
    from catalog_removals import removed_event
    from prune_past_events import is_past_event, today_cutoff

FEEDS = ('events.json', 'supplemental-events.json')
INACTIVE = {'cancelled', 'canceled', 'postponed', 'merged'}


def is_canadian(event):
    return isinstance(event, dict) and str(event.get('country') or '').strip().upper() in {'CA', 'CAN', 'CANADA'}


def read_events(root):
    events = []
    for name in FEEDS:
        path = Path(root) / name
        if path.exists():
            rows = json.loads(path.read_text())
            if isinstance(rows, list):
                events.extend(row for row in rows if isinstance(row, dict))
    return events


def upcoming_canadian(events, day):
    return [event for event in events if is_canadian(event)
            and not is_past_event(event, day) and not removed_event(event)
            and str(event.get('status') or '').lower() not in INACTIVE]


def identity(event):
    return str(event.get('id') or json.dumps({key: event.get(key) for key in
        ('title', 'startDate', 'city', 'state')}, sort_keys=True))


def retention_errors(before, after, day):
    by_id = {}
    for event in after:
        for key in [identity(event), *event.get('mergedFromIds', [])]:
            by_id.setdefault(key, []).append(event)
    errors = []
    for event in upcoming_canadian(before, day):
        matches = by_id.get(identity(event), [])
        if not any(is_canadian(row) for row in matches):
            errors.append(f'Canadian show missing or country changed: {identity(event)}')
    return sorted(set(errors))


def catalog_errors(events, catalog, day):
    # Import lazily so the shared source-publication guard has no build dependency.
    try:
        from .build_seo_site import event_path
    except ImportError:
        from build_seo_site import event_path
    paths = {show.get('path') for show in catalog.get('shows', [])}
    return sorted({f'Canadian show missing from published catalog: {event_path(event)}'
                   for event in upcoming_canadian(events, day) if event_path(event) not in paths})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('.'))
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--site', type=Path)
    parser.add_argument('--day')
    args = parser.parse_args()
    day = args.day or today_cutoff()
    source = read_events(args.source)
    if args.snapshot:
        rows = [event for event in source if is_canadian(event)]
        args.snapshot.write_text(json.dumps(rows, indent=2, ensure_ascii=False)+'\n')
        print(f'Saved Canadian baseline: {len(rows)} records')
        return
    baseline = json.loads(args.baseline.read_text()) if args.baseline else source
    actual = read_events(args.site) if args.site else source
    errors = retention_errors(baseline, actual, day)
    if args.site:
        catalog = json.loads((args.site/'assets/fan-show-catalog.json').read_text())
        errors.extend(catalog_errors(actual, catalog, day))
    report = {'asOf': day, 'canadianShowsProtected': len(upcoming_canadian(baseline, day)), 'errors': errors}
    print(json.dumps(report, indent=2))
    raise SystemExit(bool(errors))


if __name__ == '__main__':
    main()
