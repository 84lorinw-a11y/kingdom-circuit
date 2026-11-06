"""An accepted artist booking can stay listed without inventing its location."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_seo_site import event_card, event_schema, head, merge_events
from catalog_removals import public_event, removed_event
from mobile_discovery import Document
from show_information import detail_transform, event_schemas, patched_schema, schema_blocks
from show_information_model import normalize
from url_continuity import merge_details


class UnconfirmedBookingPublicationTests(unittest.TestCase):
    def source(self, **changes):
        return {
            'id': 'official:023c040d4ea33e120949', 'startDate': '2026-11-21',
            'title': '1K Phew — Live at Texas Motorplex', 'artists': ['1K Phew'],
            'headliner': '1K Phew', 'status': 'scheduled', 'country': 'US',
            'venue': 'Texas Motorplex', 'city': 'Swiss Golf And Tennis Club Mobile Home Park',
            'state': 'FL', 'address': 'A conflicting street', 'postalCode': '12345',
            'latitude': 28, 'longitude': -81, 'timezone': 'America/New_York',
            'startTime': '19:00', 'startDateTime': '2026-11-21T19:00:00-05:00',
            'ticketUrl': 'https://www.eventbrite.com/e/example-tickets-1234567890',
            'ticketUrlVerified': True, 'officialUrl': 'https://www.reachrecords.com/artists/1k-phew/',
            **changes,
        }

    def test_raw_refresh_and_merge_cannot_restore_conflicting_geography_or_ticket_offer(self):
        source = self.source()
        original = copy.deepcopy(source)
        row = public_event(source)
        self.assertFalse(removed_event(source))
        self.assertTrue(row['locationUnconfirmed'])
        self.assertEqual(row['title'], '1K Phew — Live performance')
        for field in ('venue', 'city', 'state', 'address', 'postalCode', 'latitude',
                      'longitude', 'timezone', 'startTime', 'startDateTime', 'ticketUrl'):
            self.assertEqual(row[field], '', field)
        self.assertEqual(source, original)
        self.assertEqual(public_event(row), row)
        merged = merge_details(row, source)
        self.assertEqual(merged['city'], '')
        self.assertEqual(merged['venue'], '')
        self.assertEqual(merged['ticketUrl'], '')
        self.assertEqual(len(merge_events([source], [row])), 1)
        info = normalize(source)
        self.assertIsNone(info['offer'])
        self.assertNotIn('startTimeLabel', info)
        self.assertEqual(info['officialDestination'], {
            'url': 'https://www.reachrecords.com/artists/1k-phew/',
            'label': 'Official details', 'kind': 'details'})

    def test_card_and_detail_keep_booking_and_admit_unknowns_without_event_markup(self):
        row = public_event(self.source())
        card = event_card(row, [])
        self.assertIn('1K Phew', card)
        self.assertIn('2026-11-21', card)
        self.assertIn('Location not confirmed', card)
        self.assertIn('data-state=""', card)
        self.assertNotIn('Texas Motorplex', card)
        self.assertNotIn('Swiss Golf', card)
        self.assertIsNone(event_schema(row))
        self.assertNotIn('application/ld+json', head('Show', 'Description', '/event/test/', [event_schema(row)]))
        stale_schema = {'@type': 'MusicEvent', 'location': {'name': 'Texas Motorplex'},
                        'offers': {'@type': 'Offer', 'url': self.source()['ticketUrl']}}
        source = ('<html><head><script type="application/ld+json">' + json.dumps(stale_schema) +
                  '</script></head><body><div class="event-detail-copy"><h1>1K Phew — Live performance</h1>'
                  '<dl class="detail-list"><div><dt>Date</dt><dd>Nov 21</dd></div>'
                  '<div><dt>Venue</dt><dd>Texas Motorplex</dd></div>'
                  '<div><dt>Location</dt><dd>Swiss Golf, FL</dd></div></dl>'
                  '<a class="primary-button" href="https://example.com/old">Official details</a>'
                  '</div></body></html>')
        info = normalize(row)
        rendered = detail_transform(source, info)
        doc = Document(rendered)
        self.assertIn('Location not confirmed', doc.text(doc.one(lambda n: n.has('event-detail-copy'))))
        self.assertIn('Start time not confirmed', rendered)
        self.assertIn('Venue not confirmed', rendered)
        self.assertNotIn('Texas Motorplex', rendered)
        self.assertNotIn('Swiss Golf', rendered)
        self.assertEqual([], [s for _, value in schema_blocks(rendered) for s in event_schemas(value)])
        self.assertEqual(detail_transform(rendered, info), rendered)

    def test_private_and_cancellation_protections_survive_location_projection(self):
        for changes in ({'private': True}, {'status': 'private'},
                        {'title': 'Private event'}, {'admissionRestriction': 'Invitation only'}):
            with self.subTest(changes=changes):
                source = self.source(**changes)
                info = normalize(source)
                self.assertTrue(info['private'])
                self.assertIsNone(info['offer'])
                self.assertIsNone(patched_schema({'@type': 'Event'}, info))
        for status in ('cancelled', 'postponed'):
            self.assertEqual(public_event(self.source(status=status))['status'], status)
        other = self.source(id='another-booking')
        self.assertEqual(public_event(other), other)

    def test_runtime_card_reads_same_location_flag_and_keeps_geographic_filter_empty(self):
        source = (Path(__file__).resolve().parents[1] / 'app.js').read_text()
        function = 'function eventCard(event) {' + source.split('function eventCard(event) {', 1)[1].split('function filterEvents', 1)[0]
        helpers = '''const normalize=x=>String(x||'').toLowerCase();
          const esc=x=>String(x||''); const eventImage=()=>'/photo.png';
          const eventDetailUrl=()=>'/event/preserved/'; const imageClass=()=>'';
          const imagePosition=()=>''; const FALLBACK_EVENT_IMAGE='/fallback.png';
          const eventTypeLabel=()=> 'Concert'; const artistLinks=()=> '1K Phew';
          const hostsLine=()=>''; const formatDate=()=> 'Nov 21';
          const eventVenueLabel=()=> 'Venue not confirmed'; const sourceText=()=> 'Reach Records';'''
        rendered = subprocess.check_output(['node', '-e', helpers + function +
            '\nconsole.log(eventCard(' + json.dumps(public_event(self.source())) + '));'], text=True)
        self.assertIn('Location not confirmed', rendered)
        self.assertIn('data-state=""', rendered)
        self.assertNotIn('Texas Motorplex', rendered)
        self.assertNotIn('Swiss Golf', rendered)


if __name__ == '__main__':
    unittest.main()
