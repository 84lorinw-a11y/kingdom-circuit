"""Restore reviewed missing facts without replacing newer production records.

An exact event/date/location match is required. The registry never creates a
show, changes billing/artwork/URLs, or substitutes TEST records for production.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = {'address', 'address2', 'postalCode', 'startTime', 'timezone',
          'organizer', 'registrationLocation', 'publicDescription', 'price'}


def text(value):
    return ' '.join(str(value or '').split()).casefold()


def missing(value):
    return value is None or value == '' or value == [] or value == {}


def enrich(event, reviewed):
    result = deepcopy(event)
    for item in reviewed:
        facts = item['facts']
        if set(facts) - FIELDS:
            raise ValueError(f"Unapproved show fields for {item['id']}: {set(facts) - FIELDS}")
        identities = {str(event.get('id') or ''), 'manual:' + str(event.get('id') or '')}
        if item['id'] not in identities or event.get('startDate') != item['startDate']:
            continue
        if any(text(event.get(k) or ('US' if k == 'country' else '')) != text(item.get(k))
               for k in ('city', 'state', 'country')):
            continue
        if text(event.get('venue')) != text(item.get('expectedVenue')):
            continue
        try:
            from .show_information_model import normalize
        except ImportError:
            from show_information_model import normalize
        private = normalize(event)['private']
        expected_address = item.get('expectedAddress') or facts.get('address')
        moved = bool(event.get('address') and expected_address
                     and text(event['address']) != text(expected_address))
        for field, value in facts.items():
            if not missing(result.get(field)) or missing(value):
                continue
            if field in {'address', 'address2', 'postalCode'} and (private or moved):
                continue
            if field == 'organizer' and not missing(result.get('organizerName')):
                continue
            if field == 'startTime' and not missing(result.get('startDateTime')):
                continue
            result[field] = deepcopy(value)
    return result


def apply(root=ROOT):
    config = root / 'config/verified-show-information.json'
    if not config.exists():
        return 0
    registry = json.loads(config.read_text())
    if registry.get('version') != 1:
        raise ValueError('Unsupported verified show information registry')
    changed = 0
    for name in ('events.json', 'supplemental-events.json'):
        path = root / name
        if not path.exists():
            continue
        before = json.loads(path.read_text())
        after = [enrich(event, registry['events']) for event in before]
        if after != before:
            path.write_text(json.dumps(after, indent=2, ensure_ascii=False) + '\n')
            changed += 1
    return changed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT)
    args = parser.parse_args()
    print(f'Restored reviewed missing show information in {apply(args.source)} feeds')
