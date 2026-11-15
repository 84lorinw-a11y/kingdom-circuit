"""Restoring accepted sources must never reopen completed overnight bookings."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import apply_oct2_verified_shows as october2
import apply_oct3_concert_corrections as october3
import apply_egr_bizzle_updates as egr
import apply_man_of_faith_joz_shows as submissions
import preserve_reviewed_discoveries as reviewed
import coordinated_source_refresh as source_refresh


def accepted():
    rows = json.loads((ROOT / 'config/oct3-verified-concerts.json').read_text())
    return copy.deepcopy(next(row for row in rows if row['id'] == 'the-holy-ghost-experience-chattanooga-2026-11-14'))


def fixture(root, event):
    (root / 'config').mkdir()
    for name in ('events.json', 'supplemental-events.json', 'config/manual-events.json', 'config/artists.json'):
        (root / name).write_text('[]')
    (root / 'event-history.json').write_text(json.dumps({'events': [{'event': copy.deepcopy(event)}]}))
    for name in ('config/oct2-verified-shows.json', 'config/oct3-verified-concerts.json'):
        (root / name).write_text(json.dumps([event]))


class SourceRestorationExpiryTests(unittest.TestCase):
    def test_missing_provider_retention_obeys_expiry_and_conservative_date_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            event = accepted()
            fixture(root, event)
            artists = [{'name': name, 'enabled': True} for name in event['artists']]
            self.assertTrue(source_refresh.eligible_prior(event, root, artists, '2026-11-14'))
            self.assertFalse(source_refresh.eligible_prior(event, root, artists, '2026-11-15'))
            uncertain = dict(event, endDateTime='')
            self.assertTrue(source_refresh.eligible_prior(uncertain, root, artists, '2026-11-15'))
            self.assertFalse(source_refresh.eligible_prior(uncertain, root, artists, '2026-11-16'))
            malformed = dict(event, endDate='unconfirmed', endDateTime='')
            self.assertFalse(source_refresh.eligible_prior(malformed, root, artists, '2026-11-15'))

    def test_intake_and_constant_seeds_expire_without_erasing_accepted_records(self):
        for module in (october2, october3, egr, submissions):
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                event = accepted()
                fixture(root, event)
                with patch.object(module, 'EVENTS', (event,), create=True):
                    module.apply(root, today='2026-11-14')
                    current = json.loads((root / 'events.json').read_text())
                    self.assertEqual(1, len(current))
                    for field in ('startDateTime', 'endDateTime', 'endDate', 'venue', 'artists', 'image', 'firstSeen'):
                        self.assertEqual(event[field], current[0][field])
                    module.apply(root, today='2026-11-15')
                    self.assertEqual([], json.loads((root / 'events.json').read_text()))
                    self.assertEqual([], json.loads((root / 'supplemental-events.json').read_text()))
                    manual = json.loads((root / 'config/manual-events.json').read_text())
                    self.assertEqual(1, len(manual))
                    for field in ('startDateTime', 'endDateTime', 'endDate', 'venue', 'artists', 'image', 'firstSeen'):
                        self.assertEqual(event[field], manual[0][field])
                    history = json.loads((root / 'event-history.json').read_text())['events']
                    self.assertTrue(history)
                    source = history[0].get('event', history[0])
                    self.assertEqual(event['endDateTime'], source['endDateTime'])
                    before = {name: (root / name).read_bytes() for name in (
                        'events.json', 'supplemental-events.json', 'config/manual-events.json', 'event-history.json')}
                    module.apply(root, today='2026-11-15')
                    self.assertTrue(all((root / name).read_bytes() == data for name, data in before.items()))

    def test_reviewed_discovery_seed_does_not_reappear_after_pruning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            event = accepted()
            event['editorialBatch'] = reviewed.BATCH
            fixture(root, event)
            (root / 'config/manual-events.json').write_text(json.dumps([event]))
            source = (root / 'config/manual-events.json').read_bytes()
            for day, count in [('2026-11-14', 1), ('2026-11-15', 0), ('2027-01-01', 0)]:
                events, supplemental = [], []
                reviewed.apply(root, events, supplemental, today=day)
                self.assertEqual(count, len(events))
                self.assertEqual([], supplemental)
                self.assertEqual(source, (root / 'config/manual-events.json').read_bytes())

    def test_unknown_end_remains_through_raw_date_and_frozen_day_controls_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            event = accepted()
            event.pop('endDateTime')
            fixture(root, event)
            with patch.dict(os.environ, {'KC_CATALOG_DAY': '2026-11-15'}):
                october3.apply(root)
            self.assertEqual(1, len(json.loads((root / 'events.json').read_text())))
            with patch.dict(os.environ, {'KC_CATALOG_DAY': '2026-11-16'}):
                october3.apply(root)
            self.assertEqual([], json.loads((root / 'events.json').read_text()))
            self.assertEqual(event['endDate'], json.loads((root / 'config/manual-events.json').read_text())[0]['endDate'])


if __name__ == '__main__':
    unittest.main()
