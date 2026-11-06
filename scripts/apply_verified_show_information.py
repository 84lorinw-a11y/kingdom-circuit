"""Restore reviewed missing facts without replacing newer production records.

An exact event/date/location match is required. The registry never creates a
show, changes billing/artwork, or substitutes TEST records for production.
Reviewed old-to-new corrections may update official ticket destinations.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = {'address', 'address2', 'postalCode', 'venue', 'startTime', 'startDateTime',
          'endTime', 'endDateTime', 'endDate', 'doorsTime', 'timezone',
          'organizer', 'registrationLocation', 'registrationTime', 'publicDescription',
          'publicNotice', 'price', 'ageRestriction', 'admissionRestriction',
          'parking', 'accessibility', 'entryRequirements', 'refundPolicy',
          'scheduleNote', 'scheduleDetails', 'ticketUrl', 'ticketUrlVerified',
          'registrationUrl', 'registrationUrlVerified', 'primaryTimeKind', 'officialUrl'}
VERIFICATION_URLS = {'ticketUrlVerified': 'ticketUrl',
                     'registrationUrlVerified': 'registrationUrl'}


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
        corrections = item.get('corrections', [])
        for correction in corrections:
            expected, replacements = correction['expected'], correction['facts']
            if not replacements or set(expected) != set(replacements) or set(replacements) - FIELDS:
                raise ValueError(f"Unsafe reviewed correction for {item['id']}")
            if any(flag in replacements and url not in replacements
                   for flag, url in VERIFICATION_URLS.items()):
                raise ValueError(f"Unbound destination verification for {item['id']}")
        identities = {str(event.get('id') or ''), 'manual:' + str(event.get('id') or '')}
        if item['id'] not in identities or event.get('startDate') != item['startDate']:
            continue
        if any(text(event.get(k) or ('US' if k == 'country' else '')) != text(item.get(k))
               for k in ('city', 'state', 'country')):
            continue
        accepted_venues = [item.get('expectedVenue')]
        accepted_venues += [c['facts']['venue'] for c in corrections if 'venue' in c['facts']]
        if text(event.get('venue')) not in {text(v) for v in accepted_venues}:
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
            # A verification flag belongs to an exact URL, not to the show.
            # Defer it until the guarded destination correction has settled.
            if field in VERIFICATION_URLS:
                continue
            if field in {'address', 'address2', 'postalCode'} and (private or moved):
                continue
            if field == 'organizer' and not missing(result.get('organizerName')):
                continue
            if field == 'startTime' and not missing(result.get('startDateTime')):
                continue
            result[field] = deepcopy(value)
        # Corrections are explicit, reviewed old→new transitions. Apply a group
        # atomically so a changed clock cannot retain its old ISO timestamp.
        # A subsequent source update wins whenever any protected old value differs.
        for correction in corrections:
            expected, replacements = correction['expected'], correction['facts']
            if ('organizer' in replacements and missing(result.get('organizer'))
                    and not missing(result.get('organizerName'))):
                continue
            if private and set(replacements) & {'address', 'address2', 'postalCode'}:
                continue
            if moved and set(replacements) & {'address', 'address2', 'postalCode'}:
                continue
            if any(prefix + 'Time' in replacements
                   and prefix + 'DateTime' not in expected
                   and not missing(result.get(prefix + 'DateTime'))
                   for prefix in ('start', 'end')):
                continue
            if all(result.get(field) in (value, replacements[field]) for field, value in expected.items()):
                result.update(deepcopy(replacements))
        for flag, url in VERIFICATION_URLS.items():
            if flag not in facts or not missing(result.get(flag)):
                continue
            reviewed_urls = ([facts[url]] if url in facts else [])
            reviewed_urls += [c['facts'][url] for c in corrections if url in c['facts']]
            if result.get(url) in reviewed_urls:
                result[flag] = deepcopy(facts[flag])
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
