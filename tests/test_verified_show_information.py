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

    def test_entity_links_require_the_reviewed_organizer_and_survive_replay(self):
        event = {**self.event, 'organizer': {'name': 'Presenter'}}
        pin = {**self.pin, 'expectedOrganizerName': 'Presenter', 'facts': {
            'organizerInstagram': 'https://www.instagram.com/presenter/',
            'venueUrl': 'https://hall.example/'}}
        result = enrich(event, [pin])
        self.assertEqual(result['organizerInstagram'], pin['facts']['organizerInstagram'])
        self.assertEqual(enrich(result, [pin]), result)
        newer = {**event, 'organizer': {'name': 'New Presenter'}}
        self.assertEqual(enrich(newer, [pin]), newer)

    def test_separate_verified_links_registry_is_applied_to_the_feeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'config').mkdir()
            (root / 'events.json').write_text(json.dumps([self.event]))
            pin = {**self.pin, 'facts': {'venueUrl': 'https://hall.example/'}}
            (root / 'config/verified-show-links.json').write_text(json.dumps({'version': 1, 'events': [pin]}))
            self.assertEqual(apply(root), 1)
            self.assertEqual(json.loads((root / 'events.json').read_text())[0]['venueUrl'], 'https://hall.example/')
            self.assertEqual(apply(root), 0)

    def test_private_street_and_postal_are_not_added(self):
        result = enrich({**self.event, 'admission': 'private'}, [self.pin])
        self.assertFalse(result.get('address'))
        self.assertNotIn('postalCode', result)

    def test_links_bind_after_a_reviewed_venue_and_organizer_correction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'config').mkdir()
            (root / 'events.json').write_text(json.dumps([self.event]))
            information = {**self.pin, 'facts': {'organizer': {'name': 'Presenter'}},
                           'corrections': [{'expected': {'venue': 'Hall'}, 'facts': {'venue': 'New Hall'}}]}
            links = {**self.pin, 'expectedVenue': 'New Hall', 'expectedOrganizerName': 'Presenter',
                     'facts': {'organizerInstagram': 'https://www.instagram.com/presenter/'}}
            for filename, pin in [('verified-show-information.json', information), ('verified-show-links.json', links)]:
                (root / 'config' / filename).write_text(json.dumps({'version': 1, 'events': [pin]}))
            self.assertEqual(apply(root), 1)
            row = json.loads((root / 'events.json').read_text())[0]
            self.assertEqual(row['organizerInstagram'], links['facts']['organizerInstagram'])
            self.assertEqual(apply(root), 0)

    def test_reviewed_city_correction_preserves_identity_and_rejects_later_moves(self):
        current = {**self.event, 'canonicalPath': '/event/original-city/'}
        pin = {**self.pin, 'facts': {}, 'corrections': [{
            'expected': {'city': 'City', 'venue': 'Hall', 'address': ''},
            'facts': {'city': 'Correct city', 'venue': 'Confirmed hall', 'address': '10 Main St'}}]}
        changed = enrich(current, [pin])
        self.assertEqual(changed['city'], 'Correct city')
        self.assertEqual(changed['id'], current['id'])
        self.assertEqual(changed['canonicalPath'], current['canonicalPath'])
        self.assertEqual(enrich(changed, [pin]), changed)
        for field, value in [('city', 'Later city'), ('venue', 'Later hall'),
                             ('state', 'NY'), ('startDate', '2027-02-01')]:
            later = {**changed, field: value}
            self.assertEqual(enrich(later, [pin]), later)
        with self.assertRaises(ValueError):
            enrich(current, [{**self.pin, 'facts': {'city': 'Unguarded city'}}])

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

    def test_reviewed_followup_keeps_later_clocks_and_location_corrections_independent(self):
        registry = json.loads((Path(__file__).resolve().parents[1] /
                               'config/verified-show-information.json').read_text())['events']
        pins = {p['id']: p for p in registry}
        beyond = pins['ticketmaster:vv1AAZk3FGkdmpCG1']
        event = {k: beyond[k] for k in ('id', 'startDate', 'city', 'state', 'country')}
        event.update(venue=beyond['expectedVenue'], startTime='21:00', startDateTime='',
                     primaryTimeKind='', ageRestriction='All ages')
        changed = enrich(event, [beyond])
        self.assertEqual(changed['startTime'], '21:00')
        self.assertFalse(changed.get('startDateTime'))
        cocoa = pins['manual:cj-emulous-state-youth-conference-cocoa-2026']
        event = {k: cocoa[k] for k in ('id', 'startDate', 'city', 'state', 'country')}
        event.update(venue=cocoa['expectedVenue'], address='', startTime='20:00')
        changed = enrich(event, [cocoa])
        self.assertEqual(changed['city'], 'Orlando')
        self.assertEqual(changed['venue'], 'Rosen Centre Hotel')
        self.assertEqual(changed['startTime'], '20:00')
        self.assertEqual(enrich(changed, [cocoa]), changed)
        moved = {**event, 'venue': 'Later venue', 'address': '20 New Rd'}
        self.assertEqual(enrich(moved, [cocoa]), moved)

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
