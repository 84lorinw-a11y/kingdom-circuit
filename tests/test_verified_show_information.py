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

    def test_reviewed_correction_replaces_only_the_exact_prior_values(self):
        current = {**self.event, 'startTime': '18:00', 'startDateTime': '2027-01-29T18:00:00-06:00'}
        pin = {**self.pin, 'facts': {}, 'corrections': [{
            'expected': {'startTime': '18:00', 'startDateTime': '2027-01-29T18:00:00-06:00'},
            'facts': {'startTime': '19:30', 'startDateTime': '2027-01-29T19:30:00-06:00'}}]}
        changed = enrich(current, [pin])
        self.assertEqual(changed['startTime'], '19:30')
        self.assertEqual(enrich(changed, [pin]), changed)
        newer = {**current, 'startTime': '20:00'}
        self.assertEqual(enrich(newer, [pin]), newer)
        partially_refreshed = {**changed, 'startTime': '18:00'}
        self.assertEqual(enrich(partially_refreshed, [pin]), changed)

    def test_correction_cannot_replace_unlisted_fields_or_expose_private_address(self):
        unsafe = {**self.pin, 'facts': {}, 'corrections': [{
            'expected': {'image': 'a.jpg'}, 'facts': {'image': 'b.jpg'}}]}
        with self.assertRaises(ValueError):
            enrich(self.event, [unsafe])
        private = {**self.event, 'admission': 'private'}
        pin = {**self.pin, 'facts': {}, 'corrections': [{
            'expected': {'address': ''}, 'facts': {'address': '100 Hidden St'}}]}
        self.assertFalse(enrich(private, [pin]).get('address'))

    def test_correction_does_not_replace_a_newer_legacy_organizer(self):
        current = {**self.event, 'organizerName': 'New Presenter'}
        pin = {**self.pin, 'facts': {}, 'corrections': [{
            'expected': {'organizer': None}, 'facts': {'organizer': {'name': 'Old Presenter'}}}]}
        self.assertEqual(enrich(current, [pin]), current)

    def test_verification_flags_follow_only_the_reviewed_destination(self):
        from scripts.show_information_model import normalize
        for url_field, flag in [('ticketUrl', 'ticketUrlVerified'),
                                ('registrationUrl', 'registrationUrlVerified')]:
            with self.subTest(field=url_field):
                old, approved = 'https://old.test/details', 'https://approved.test/admission'
                pin = {**self.pin, 'facts': {flag: True}, 'corrections': [{
                    'expected': {url_field: old}, 'facts': {url_field: approved}}]}
                current = {**self.event, url_field: old}
                changed = enrich(current, [pin])
                self.assertEqual(changed[url_field], approved)
                self.assertIs(changed[flag], True)
                self.assertEqual(enrich(changed, [pin]), changed)
                newer = {**current, url_field: 'https://new.test/information'}
                result = enrich(newer, [pin])
                self.assertEqual(result, newer)
                self.assertIsNone(normalize(result)['offer'])
                rejected = {**current, url_field: approved, flag: False}
                self.assertEqual(enrich(rejected, [pin]), rejected)

    def test_negative_verification_does_not_suppress_a_new_destination(self):
        pin = {**self.pin, 'facts': {'ticketUrlVerified': False}, 'corrections': [{
            'expected': {'ticketUrl': 'https://old.test/wrong-event'},
            'facts': {'ticketUrl': ''}}]}
        current = {**self.event, 'ticketUrl': 'https://old.test/wrong-event'}
        self.assertEqual(enrich(current, [pin])['ticketUrl'], '')
        self.assertIs(enrich(current, [pin])['ticketUrlVerified'], False)
        newer = {**current, 'ticketUrl': 'https://new.test/tickets'}
        self.assertEqual(enrich(newer, [pin]), newer)

    def test_unbound_verification_cannot_certify_a_url(self):
        current = {**self.event, 'ticketUrl': 'https://new.test/information'}
        pin = {**self.pin, 'facts': {'ticketUrlVerified': True}}
        self.assertEqual(enrich(current, [pin]), current)
        pin['facts'] = {}
        pin['corrections'] = [{'expected': {'ticketUrlVerified': None},
                               'facts': {'ticketUrlVerified': True}}]
        with self.assertRaises(ValueError):
            enrich(current, [pin])

    def test_clock_correction_requires_guard_for_an_existing_iso_timestamp(self):
        for prefix in ('start', 'end'):
            with self.subTest(prefix=prefix):
                clock, iso = prefix + 'Time', prefix + 'DateTime'
                current = {**self.event, clock: '18:00', iso: '2027-01-29T20:00:00-06:00'}
                pin = {**self.pin, 'facts': {}, 'corrections': [{
                    'expected': {clock: '18:00'}, 'facts': {clock: '19:30'}}]}
                self.assertEqual(enrich(current, [pin]), current)
                without_iso = {k: v for k, v in current.items() if k != iso}
                self.assertEqual(enrich(without_iso, [pin])[clock], '19:30')

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
