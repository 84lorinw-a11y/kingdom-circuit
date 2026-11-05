import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.apply_verified_show_information import enrich, apply


class VerifiedShowInformationTests(unittest.TestCase):
    def setUp(self):
        self.event = dict(id='manual:show', startDate='2027-01-29', city='City',
                          state='TN', country='US', venue='Hall', address='', startTime='')
        self.pin = {**self.event, 'expectedVenue': 'Hall', 'facts': {
            'address': '100 Main St', 'postalCode': '12345', 'startTime': '19:00',
            'timezone': 'America/Chicago', 'organizer': {'name': 'Presenter'}},
            'sources': [{'url': 'https://example.test/concert'}]}

    def test_fills_missing_collector_facts_without_mutation_or_duplicate_changes(self):
        original = copy.deepcopy(self.event)
        result = enrich(self.event, [self.pin])
        self.assertEqual(result['address'], '100 Main St')
        self.assertEqual(result['organizer'], {'name': 'Presenter'})
        self.assertEqual(enrich(result, [self.pin]), result)
        self.assertEqual(self.event, original)
        seed = {**self.event, 'id': 'show'}
        self.assertEqual(enrich(seed, [self.pin])['postalCode'], '12345')

    def test_later_facts_and_aliases_win_over_old_research(self):
        current = {**self.event, 'address': '200 New St', 'startTime': '20:00',
                   'organizerName': 'New Presenter', 'image': 'new.jpg', 'ticketUrl': 'https://new.test'}
        result = enrich(current, [self.pin])
        self.assertEqual(result['address'], '200 New St')
        self.assertEqual(result['startTime'], '20:00')
        self.assertNotIn('organizer', result)
        self.assertEqual(result['image'], 'new.jpg')
        self.assertEqual(result['ticketUrl'], 'https://new.test')
        self.assertNotIn('postalCode', result)  # an old address must not supply a ZIP for a new one

    def test_changed_identity_or_venue_never_reuses_old_facts(self):
        for key, value in [('id', 'other'), ('startDate', '2027-02-01'), ('city', 'Elsewhere'),
                           ('state', 'CA'), ('country', 'CA'), ('venue', 'New Hall')]:
            current = {**self.event, key: value}
            self.assertEqual(enrich(current, [self.pin]), current)

    def test_private_street_and_postal_are_not_added(self):
        result = enrich({**self.event, 'admission': 'private'}, [self.pin])
        self.assertFalse(result.get('address'))
        self.assertNotIn('postalCode', result)

    def test_disallowed_fact_fails_instead_of_overwriting_artwork_or_identity(self):
        bad = {**self.pin, 'facts': {'image': 'old.jpg'}}
        with self.assertRaises(ValueError):
            enrich(self.event, [bad])

    def test_refresh_restores_only_existing_matching_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'config').mkdir()
            (root / 'config/verified-show-information.json').write_text(json.dumps({'version': 1, 'events': [self.pin]}))
            (root / 'events.json').write_text(json.dumps([self.event]))
            (root / 'supplemental-events.json').write_text('[]')
            self.assertEqual(apply(root), 1)
            self.assertEqual(apply(root), 0)
            self.assertEqual(json.loads((root / 'supplemental-events.json').read_text()), [])
            self.assertEqual(json.loads((root / 'events.json').read_text())[0]['startTime'], '19:00')


if __name__ == '__main__':
    unittest.main()
