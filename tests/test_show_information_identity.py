"""Bind public facts to exact event identities before and after URL reconciliation."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import show_information as show
import url_continuity as continuity
from build_seo_site import event_path
from publication_audit import event_fact_errors


MANUAL_ID = 'manual:jackie-hill-perry-blameless-birmingham-2027-02-20'
PROVIDER_ID = 'ticketmaster:1kFZvPQoGAC-Uwi'


def reviewed_event():
    return {'id': MANUAL_ID, 'title': 'Blameless: The Tour with Jackie Hill Perry',
            'startDate': '2027-02-20', 'endDate': '2027-02-20', 'timezone': 'America/Chicago',
            'venue': 'Iron City', 'address': '513 22nd Street South', 'postalCode': '35233',
            'city': 'Birmingham', 'state': 'AL', 'country': 'US', 'artists': ['Jackie Hill Perry'],
            'status': 'scheduled', 'officialUrl': 'https://stillblameless.com/tour',
            'firstSeen': '2026-11-09', 'scheduleNote': 'Show time to be announced.'}


def provider_event():
    event = dict(reviewed_event(), id=PROVIDER_ID, startTime='19:00')
    event.pop('postalCode')
    event.pop('scheduleNote')
    return event


def detail(row, path):
    schema = {'@context': 'https://schema.org', '@type': 'MusicEvent', 'name': row['title'],
              'startDate': row['startDate'], 'url': continuity.ORIGIN + path,
              'eventStatus': 'https://schema.org/EventScheduled',
              'eventAttendanceMode': 'https://schema.org/OfflineEventAttendanceMode',
              'performer': [{'@type': 'Person', 'name': name} for name in row['artists']],
              'location': {'@type': 'Place', 'name': row['venue'],
                           'address': {'@type': 'PostalAddress', 'addressLocality': row['city']}}}
    return ('<html><head><link rel="canonical" href="' + continuity.ORIGIN + path + '">'
            '<script type="application/ld+json">' + json.dumps(schema) + '</script></head><body>'
            '<div class="event-detail-copy"><h1>' + row['title'] + '</h1>'
            '<dl class="detail-list"><div><dt>Date</dt><dd>Feb 20</dd></div>'
            '<div><dt>Venue</dt><dd>Iron City</dd></div>'
            '<div><dt>Location</dt><dd>Birmingham, AL</dd></div></dl>'
            '<a class="primary-button" href="https://stillblameless.com/tour">Official details</a>'
            '</div></body></html>')


class ShowInformationIdentityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.site = Path(temporary.name)
        (self.site / 'assets').mkdir()
        (self.site / 'config').mkdir()
        self.write('config/artists.json', [{'name': 'Jackie Hill Perry'}])

    def write(self, name, value):
        (self.site / name).write_text(json.dumps(value))

    def inputs(self, events, pages):
        self.write('events.json', events)
        self.write('supplemental-events.json', [])
        self.write('assets/fan-show-catalog.json', {'shows': [
            {'path': path, 'date': row['startDate']} for path, row in pages.items()]})
        for path, row in pages.items():
            target = self.site / path.lstrip('/') / 'index.html'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(detail(row, path))

    def test_exact_id_paths_keep_same_title_bookings_separate_in_either_source_order(self):
        manual, provider = reviewed_event(), provider_event()
        pages = {event_path(row): row for row in (manual, provider)}
        for events in ([manual, provider], [provider, manual]):
            with self.subTest(order=[e['id'] for e in events]):
                self.inputs(events, pages)
                records = show.context(self.site)['paths']
                self.assertEqual('2027-02-20', records[event_path(manual)]['schemaStartDate'])
                self.assertEqual('35233', records[event_path(manual)]['postalCode'])
                self.assertEqual('2027-02-20T19:00:00-06:00', records[event_path(provider)]['schemaStartDate'])
                self.assertFalse(records[event_path(provider)].get('postalCode'))
                for path, row in pages.items():
                    rendered = show.detail_transform(detail(row, path), records[path])
                    schema = next(show.event_schemas(show.schema_blocks(rendered)[0][1]))
                    self.assertEqual(schema['startDate'], records[path]['schemaStartDate'])
                    self.assertEqual(schema['location']['address'].get('postalCode'), row.get('postalCode'))

    def test_retained_canonical_path_wins_over_an_old_provider_hash(self):
        provider = provider_event()
        old_path = event_path(provider)
        manual = dict(reviewed_event(), canonicalPath=old_path)
        self.inputs([provider, manual], {old_path: manual})
        bound = show.context(self.site)['paths'][old_path]
        self.assertEqual('2027-02-20', bound['schemaStartDate'])
        self.assertEqual('35233', bound['postalCode'])

    def test_ambiguous_descriptive_fallback_fails_instead_of_borrowing_facts(self):
        self.inputs([reviewed_event(), provider_event()], {'/event/unidentified/': reviewed_event()})
        with self.assertRaisesRegex(ValueError, 'Ambiguous catalog/source identity'):
            show.context(self.site)

    def test_ambiguous_hash_fails_instead_of_selecting_the_last_source(self):
        self.inputs([reviewed_event(), provider_event()], {'/event/collision-aaaaaa/': reviewed_event()})
        with patch.object(show, 'digest', return_value='aaaaaa'), \
                self.assertRaisesRegex(ValueError, 'Ambiguous catalog/source identity'):
            show.context(self.site)

    def test_unique_legacy_descriptive_fallback_still_works(self):
        self.inputs([reviewed_event()], {'/event/retained-legacy-path/': reviewed_event()})
        record = show.context(self.site)['paths']['/event/retained-legacy-path/']
        self.assertEqual('2027-02-20', record['schemaStartDate'])
        self.assertEqual('35233', record['postalCode'])

    def test_publication_audit_still_rejects_time_and_zip_drift(self):
        row = reviewed_event()
        path = event_path(row)
        self.inputs([row], {path: row})
        record = show.context(self.site)['paths'][path]
        rendered = show.detail_transform(detail(row, path), record)
        schema = next(show.event_schemas(show.schema_blocks(rendered)[0][1]))
        self.assertEqual([], event_fact_errors(path, record, [schema]))
        wrong = deepcopy(schema)
        wrong['startDate'] = '2027-02-20T19:00:00-06:00'
        wrong['location']['address'].pop('postalCode')
        failures = event_fact_errors(path, record, [wrong])
        self.assertEqual({('source_schema_fact_mismatch', 'startDate'),
                          ('source_location_mismatch', 'postalCode')},
                         {(failure['kind'], failure['field']) for failure in failures})

    def test_reviewed_birmingham_alias_keeps_url_unknown_time_and_zip_on_reimports(self):
        manual, provider = reviewed_event(), provider_event()
        rules = json.loads((ROOT / continuity.RULES_FILE).read_text())
        rule = next(rule for rule in rules['merges'] if rule['keepId'] == MANUAL_ID)
        self.assertTrue(rule['identityOnly'])
        self.assertEqual([PROVIDER_ID], rule['aliasIds'])
        self.assertEqual('/event/blameless-the-tour-with-jackie-hill-perry-2027-02-20-birmingham-7cfada/', rule['keepPath'])
        self.assertEqual([event_path(provider)], rule['aliasPaths'])
        state = continuity.empty_state()
        state['events'][MANUAL_ID] = {'path': rule['keepPath'], 'sourceIds': [], 'event': manual}
        self.write(continuity.STATE_FILE, state)
        self.write(continuity.RULES_FILE, {'version': 1, 'merges': [rule]})
        separate = dict(provider, id='unreviewed:separate-birmingham-session', startTime='21:00')
        for _ in range(2):
            self.inputs([provider, manual, separate], {rule['keepPath']: manual})
            continuity.prepare(self.site)
            source = json.loads((self.site / 'events.json').read_text())
            self.assertEqual({MANUAL_ID, separate['id']}, {row['id'] for row in source})
            survivor = next(row for row in source if row['id'] == MANUAL_ID)
            self.assertNotIn('startTime', survivor)
            self.assertEqual('35233', survivor['postalCode'])
            self.assertEqual('2026-11-09', survivor['firstSeen'])
            saved = json.loads((self.site / continuity.WORK_FILE).read_text())
            self.assertEqual(rule['keepPath'], saved['events'][MANUAL_ID]['path'])
            self.assertEqual(rule['keepPath'], saved['redirects'][event_path(provider)])
            self.assertIn(PROVIDER_ID, saved['events'][MANUAL_ID]['sourceIds'])
            self.write(continuity.STATE_FILE, saved)


if __name__ == '__main__':
    unittest.main()
