"""A trusted location resolution must replace stale provider facts everywhere.

These fixtures use a real temporary review registry. Only that file boundary
and the archive clock are patched; publication, schemas and selection are real.
"""
import copy
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import add_past_show_archives as archives
import catalog_removals as catalog
import permanent_state_pages as states
import url_continuity as continuity
from build_seo_site import event_schema
from show_information import patched_schema
from show_information_model import normalize


CANONICAL_ID = 'official:023c040d4ea33e120949'
DISCOVERED = '2026-11-03T18:56:47Z'
EVENT_URL = 'https://www.zeffy.com/en-US/ticketing/cars-and-christ-dallas-2026'
_REAL_DATETIME = dt.datetime


class DayAfterShow(_REAL_DATETIME):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 11, 22, 12, tzinfo=dt.timezone.utc)
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)


class ResolvedLocationReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'config').mkdir()
        self.review_file = self.root / 'config/review-held-events.json'
        boundary = patch.object(catalog, 'REVIEW_FILE', self.review_file, create=True)
        boundary.start()
        self.addCleanup(boundary.stop)
        self.resolution = {
            'id': CANONICAL_ID,
            'title': 'Cars & Christ Dallas',
            'startDate': '2026-11-21',
            'endDate': '2026-11-21',
            'startTime': '17:00',
            'endTime': '21:00',
            'startDateTime': '2026-11-21T17:00:00-06:00',
            'endDateTime': '2026-11-21T21:00:00-06:00',
            'timezone': 'America/Chicago',
            'venue': 'Texas Motorplex',
            'address': '7500 W Hwy 287',
            'city': 'Ennis',
            'state': 'TX',
            'postalCode': '75119',
            'country': 'US',
            'artists': ['1K Phew', 'Trendsetter Sense'],
            'headliner': '1K Phew',
            'advertisedBilling': ['1K Phew', 'DJ Trendsetter Sense'],
            'officialBill': ['1K Phew', 'DJ Trendsetter Sense'],
            'lineupExplicit': True,
            'musicConfirmed': True,
            'eventType': 'concert',
            'status': 'scheduled',
            'officialUrl': EVENT_URL,
            'ticketUrl': EVENT_URL,
            'ticketUrlVerified': False,
            'registrationUrlVerified': False,
            'price': 'Free',
            'firstSeen': DISCOVERED,
            'locationUnconfirmed': False,
            'confidence': 'high',
            'publicDescription': 'Cars & Christ Dallas features 1K Phew and DJ Trendsetter Sense. Free event, 5–9 PM Central.',
        }
        self.write_review()

    def write_review(self, **changes):
        record = {
            'excludedEventId': CANONICAL_ID,
            'reviewStatus': 'resolved_location_confirmed',
            'publish': True,
            'resolvedEvent': copy.deepcopy(self.resolution),
            **changes,
        }
        self.review_file.write_text(json.dumps([record]))

    def raw(self, **changes):
        return {
            'id': CANONICAL_ID,
            'title': '1K Phew at Texas Motorplex',
            'startDate': '2026-11-21',
            'startTime': '18:00',
            'startDateTime': '2026-11-21T18:00:00-05:00',
            'timezone': 'America/New_York',
            'venue': 'Texas Motorplex',
            'address': '7500 US-287',
            'city': 'Swiss Golf And Tennis Club Mobile Home Park',
            'state': 'FL',
            'postalCode': '33881',
            'country': 'US',
            'latitude': 28.1,
            'longitude': -81.6,
            'lat': 28.1,
            'lng': -81.6,
            'geo': {'latitude': 28.1, 'longitude': -81.6},
            'coordinates': [-81.6, 28.1],
            'artists': ['1K Phew'],
            'headliner': '1K Phew',
            'eventType': 'concert',
            'status': 'scheduled',
            'officialUrl': 'https://www.reachrecords.com/artists/1k-phew/',
            'ticketUrl': 'https://www.bandsintown.com/e/1040798191',
            'ticketUrlVerified': True,
            'price': '$99 from stale provider',
            'firstSeen': '2026-11-06T12:00:00Z',
            'confidence': 'high',
            **changes,
        }

    def assert_resolved(self, actual):
        self.assertIs(actual.get('locationUnconfirmed'), False)
        for field, expected in {
            'title': 'Cars & Christ Dallas', 'city': 'Ennis', 'state': 'TX',
            'venue': 'Texas Motorplex', 'address': '7500 W Hwy 287',
            'postalCode': '75119', 'timezone': 'America/Chicago',
            'startTime': '17:00', 'endTime': '21:00',
            'startDateTime': '2026-11-21T17:00:00-06:00',
            'endDateTime': '2026-11-21T21:00:00-06:00',
            'officialUrl': EVENT_URL, 'ticketUrl': EVENT_URL,
            'artists': ['1K Phew', 'Trendsetter Sense'],
            'advertisedBilling': ['1K Phew', 'DJ Trendsetter Sense'],
            'officialBill': ['1K Phew', 'DJ Trendsetter Sense'],
            'price': 'Free',
        }.items():
            self.assertEqual(actual.get(field), expected, field)

    def final_schema(self, event):
        return patched_schema(event_schema(event), normalize(event))

    def write_history(self, event):
        document = {'events': [{'event': event, 'observedOnOrAfterEventDate': True}]}
        path = self.root / 'event-history.json'
        path.write_text(json.dumps(document))
        (self.root / 'config/artists.json').write_text(json.dumps([
            {'name': '1K Phew', 'enabled': True},
            {'name': 'Trendsetter Sense', 'enabled': True},
        ]))
        return path

    def test_confirmed_registry_replaces_conflicting_location_clock_ticket_and_bill(self):
        actual = catalog.public_event(self.raw())
        self.assert_resolved(actual)
        self.assertEqual(actual['id'], CANONICAL_ID)
        self.assertEqual(actual['firstSeen'], DISCOVERED)
        for field in ('latitude', 'longitude', 'lat', 'lng', 'geo', 'coordinates'):
            self.assertFalse(actual.get(field), f'Stale Florida coordinates survived: {field}')
        self.assertFalse(actual.get('ticketUrlVerified'))
        self.assertFalse(actual.get('registrationUrlVerified'))

    def test_exact_dated_provider_variants_receive_the_same_verified_facts(self):
        variants = [
            {'id': 'manual:' + CANONICAL_ID},
            {'id': 'bandsintown:1040798191', 'bandsintownEventId': '1040798191'},
            {'id': 'provider-import', 'officialUrl': 'https://www.bandsintown.com/e/1040798191?utm_source=test'},
            {'id': 'provider-ticket', 'officialUrl': '', 'ticketUrl': 'https://bandsintown.com/t/1040798191'},
        ]
        for changes in variants:
            with self.subTest(changes=changes):
                self.assert_resolved(catalog.public_event(self.raw(**changes)))

    def test_projection_is_idempotent_without_mutating_raw_source_or_review_file(self):
        source = self.raw()
        original = copy.deepcopy(source)
        review_bytes = self.review_file.read_bytes()
        once = catalog.public_event(source)
        twice = catalog.public_event(once)
        self.assert_resolved(once)
        self.assertEqual(twice, once)
        self.assertEqual(source, original)
        self.assertEqual(self.review_file.read_bytes(), review_bytes)

    def test_a_legitimate_earlier_discovery_is_never_reset_by_resolution(self):
        actual = catalog.public_event(self.raw(firstSeen='2026-10-30T10:00:00Z'))
        self.assert_resolved(actual)
        self.assertEqual(actual['firstSeen'], '2026-10-30T10:00:00Z')

    def test_private_input_remains_private_with_no_public_event_or_offer_schema(self):
        for changes in ({'status': 'private'}, {'private': True}, {'admissionRestriction': 'Invitation only'}):
            with self.subTest(changes=changes):
                actual = catalog.public_event(self.raw(**changes))
                self.assertIs(actual.get('locationUnconfirmed'), False)
                info = normalize(actual)
                self.assertTrue(info['private'])
                self.assertIsNone(info['offer'])
                self.assertIsNone(self.final_schema(actual))

    def test_cancellation_and_postponement_override_scheduled_resolution(self):
        for status, schema_status in [('cancelled', 'EventCancelled'), ('canceled', 'EventCancelled'), ('postponed', 'EventPostponed')]:
            with self.subTest(status=status):
                actual = catalog.public_event(self.raw(status=status, statusNotes='Owner decision', cancellationReason='Confirmed separately'))
                self.assertIs(actual.get('locationUnconfirmed'), False)
                self.assertEqual(actual['status'], status)
                self.assertEqual(actual['statusNotes'], 'Owner decision')
                self.assertEqual(actual['cancellationReason'], 'Confirmed separately')
                schema = self.final_schema(actual)
                self.assertIsNotNone(schema)
                self.assertEqual(schema['eventStatus'], 'https://schema.org/' + schema_status)
                self.assertNotIn('offers', schema)

    def test_missing_or_unapproved_registry_keeps_existing_unknown_location_projection(self):
        cases = [None, {'reviewStatus': 'listed_location_unconfirmed'}, {'publish': False}]
        for changes in cases:
            with self.subTest(changes=changes):
                if changes is None:
                    self.review_file.unlink()
                else:
                    self.write_review(**changes)
                actual = catalog.public_event(self.raw())
                self.assertTrue(actual['locationUnconfirmed'])
                self.assertEqual(actual['city'], '')
                self.assertEqual(actual['state'], '')
                self.assertEqual(actual['startTime'], '')
                self.assertEqual(actual['ticketUrl'], '')
                self.assertIsNone(event_schema(actual))

    def test_merged_source_stays_merged_without_offer(self):
        actual = catalog.public_event(self.raw(status='merged', mergedIntoId='retained-other-id'))
        self.assertEqual(actual['status'], 'merged')
        self.assertEqual(actual['mergedIntoId'], 'retained-other-id')
        self.assertIsNone(normalize(actual)['offer'])
        self.assertNotIn('offers', self.final_schema(actual))

    def test_scheduled_seed_cannot_reopen_later_provider_status_during_native_merge(self):
        seed = catalog.public_event(self.raw(id='manual:' + CANONICAL_ID))
        for status in ('cancelled', 'postponed', 'rescheduled', 'private'):
            with self.subTest(status=status):
                provider = catalog.public_event(self.raw(id='bandsintown:1040798191',
                    status=status, statusNotes='Later provider update', cancellationReason='Organizer decision'))
                actual = continuity.merge_details(dict(seed, id=CANONICAL_ID), provider)
                self.assertEqual(actual['status'], status)
                self.assertEqual(actual['statusNotes'], 'Later provider update')
                self.assertEqual(actual['cancellationReason'], 'Organizer decision')

    def test_similar_id_other_date_and_spoofed_provider_urls_are_unchanged(self):
        cases = [
            self.raw(id=CANONICAL_ID + '0', officialUrl='https://other.test/show', ticketUrl=''),
            self.raw(startDate='2026-11-22'),
        ]
        for url in [
            'https://bandsintown.com.evil.test/e/1040798191',
            'https://evil.test/bandsintown.com/e/1040798191',
            'https://bandsintown.com/e/10407981910',
            'https://bandsintown.com/e/1040798191/another-event',
            'https://bandsintown.com@evil.test/e/1040798191',
            'https://bandsintown.com:444/e/1040798191',
            'https://bandsintown.com/e/1040798191 trailing',
        ]:
            cases.append(self.raw(id='unrelated-provider-id', officialUrl=url, ticketUrl=url))
        for source in cases:
            with self.subTest(source=source):
                original = copy.deepcopy(source)
                self.assertEqual(catalog.public_event(source), original)
                self.assertEqual(source, original)

    def test_real_schema_uses_confirmed_texas_window_without_unverified_free_offer(self):
        actual = catalog.public_event(self.raw())
        schema = self.final_schema(actual)
        self.assertIsNotNone(schema)
        self.assertEqual(schema['startDate'], '2026-11-21T17:00:00-06:00')
        self.assertEqual(schema['endDate'], '2026-11-21T21:00:00-06:00')
        self.assertEqual(schema['location']['address']['addressLocality'], 'Ennis')
        self.assertEqual(schema['location']['address']['addressRegion'], 'TX')
        self.assertEqual(schema['location']['address']['streetAddress'], '7500 W Hwy 287')
        self.assertEqual([p['name'] for p in schema['performer']], ['1K Phew', 'DJ Trendsetter Sense'])
        self.assertNotIn('offers', schema)
        self.assertIsNone(normalize(actual)['offer'])

    def test_state_discovery_projects_raw_history_before_geographic_selection(self):
        history = self.write_history(self.raw())
        original = history.read_bytes()
        self.assertEqual(states.discover_codes(self.root), ['TX'])
        self.assertEqual(history.read_bytes(), original)

    def test_archive_projects_raw_history_to_texas_before_eligibility_without_rewriting_it(self):
        history = self.write_history(self.raw())
        original = history.read_bytes()
        with patch.object(archives.dt, 'datetime', DayAfterShow):
            selected, _ = archives.load_events(self.root)
        self.assertEqual(len(selected), 1)
        self.assert_resolved(selected[0])
        self.assertEqual(history.read_bytes(), original)

    def test_archive_still_excludes_private_booking_after_location_is_resolved(self):
        for changes in ({'status': 'private'}, {'private': True}):
            with self.subTest(changes=changes):
                history = self.write_history(self.raw(**changes))
                original = history.read_bytes()
                with patch.object(archives.dt, 'datetime', DayAfterShow):
                    selected, _ = archives.load_events(self.root)
                self.assertEqual(selected, [])
                self.assertEqual(history.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
