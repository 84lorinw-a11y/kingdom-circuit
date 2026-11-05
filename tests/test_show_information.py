"""Production contract for facts, visibility, identity and repeated refreshes."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import show_information as show
from show_information_model import normalize
from mobile_discovery import Document


def record(**changes):
    return normalize({'id': 'example-123', 'title': 'Sample concert', 'startDate': '2027-01-29',
        'startTime': '21:00', 'endTime': '22:00', 'timezone': 'America/Chicago',
        'venue': 'Chapel', 'city': 'Kansas City', 'state': 'MO', 'country': 'US',
        'address': '5001 N Oak Trafficway', 'postalCode': '64118',
        'officialUrl': 'https://example.com/details', **changes})


def fixture(private=False):
    schema = {'@context': 'https://schema.org', '@type': 'MusicEvent', 'name': 'Sample concert',
        'startDate': '2027-01-29T21:00', 'url': 'https://kingdomcircuit.com/event/sample/',
        'image': ['https://kingdomcircuit.com/assets/flyer.jpg'],
        'performer': [{'@type': 'MusicGroup', 'name': 'Artist'}],
        'location': {'@type': 'Place', 'name': 'Chapel', 'address': {'@type': 'PostalAddress', 'addressLocality': 'Kansas City'}},
        'organizer': {'@type': 'Organization', 'name': 'Some ticket platform'},
        'offers': {'@type': 'Offer', 'url': 'https://example.com/incorrect-registration'}}
    date = '<time data-kc-private-date datetime="2027-01-29" data-end-date="2027-01-29">Jan 29</time>' if private else 'Jan 29'
    button = '<a class="primary-button" href="/shows/">Explore public shows</a>' if private else '<a class="primary-button" href="https://example.com/details">Official details</a>'
    return ('<html><head><meta name="robots" content="index,follow">'
        '<link rel="canonical" href="https://kingdomcircuit.com/event/sample/">'
        '<script async src="https://www.googletagmanager.com/gtag/js?id=G-REAL"></script>'
        '<script type="application/ld+json">' + json.dumps(schema) + '</script></head><body>'
        '<div class="event-detail-media"><img src="/assets/flyer.jpg" alt="Full flyer"></div>'
        '<div class="event-detail-copy"><h1>Sample concert</h1><p class="artist-line">Artist</p>'
        '<dl class="detail-list"><div><dt>Status</dt><dd>Scheduled</dd></div>'
        '<div><dt>Date</dt><dd>' + date + '</dd></div><div><dt>Venue</dt><dd>Chapel</dd></div>'
        '<div><dt>Location</dt><dd>Kansas City, MO</dd></div></dl>' + button +
        '<p class="disclaimer">Confirm details.</p></div></body></html>')


class ProductionShowInformationTests(unittest.TestCase):
    def test_confirmed_organizer_is_main_row_after_location_and_matches_schema(self):
        row = record(organizer={'name': 'Real promoter', 'url': 'https://promoter.example/'}, price='$15 concert only')
        rendered = show.detail_transform(fixture(), row)
        doc = Document(rendered)
        facts = doc.one(lambda n: n.has('detail-list'))
        labels = [doc.text(n) for n in doc.nodes if n.tag == 'dt' and facts.start < n.start < facts.end]
        self.assertEqual(labels, ['Status', 'Date', 'Venue', 'Location', 'Organizer / promoter'])
        panel = doc.one(lambda n: n.has('kc-more-details'))
        self.assertNotIn('Organizer', doc.text(panel))
        self.assertIn('$15 concert only', doc.text(panel))
        schema = next(show.event_schemas(show.schema_blocks(rendered)[0][1]))
        self.assertEqual(schema['organizer'], {'@type': 'Organization', 'name': 'Real promoter', 'url': 'https://promoter.example/'})
        self.assertEqual(schema['startDate'], '2027-01-29T21:00:00-06:00')
        self.assertEqual(schema['location']['address']['postalCode'], '64118')
        self.assertEqual(show.detail_transform(rendered, row), rendered)

    def test_unknown_organizer_is_omitted_even_when_source_platform_was_in_schema(self):
        rendered = show.detail_transform(fixture(), record(sourceName='Ticketmaster'))
        self.assertNotIn('Organizer / promoter', rendered)
        schema = next(show.event_schemas(show.schema_blocks(rendered)[0][1]))
        self.assertNotIn('organizer', schema)
        self.assertNotIn('offers', schema)

    def test_local_clock_and_unknown_venue_match_visible_and_google_facts(self):
        row = record(title='RWG TOUR 2026', venue='RWG TOUR 2026', timezone='', startTime='08:15')
        rendered = show.detail_transform(fixture(), row)
        schema = next(show.event_schemas(show.schema_blocks(rendered)[0][1]))
        self.assertEqual(schema['startDate'], '2027-01-29T08:15:00')
        self.assertNotIn('name', schema['location'])
        self.assertIn('<dt>Venue</dt><dd>Venue not confirmed</dd>', rendered)
        self.assertIn('8:15 AM', rendered)

    def test_primary_and_compact_links_match_verified_direct_ticket_offer(self):
        url = 'https://www.eventbrite.com/e/sample-concert-tickets-1234567890'
        row = record(ticketUrl=url, price={'amount': 15, 'currency': 'USD', 'includesAllFeesConfirmed': True})
        rendered = show.detail_transform(fixture(), row)
        doc = Document(rendered)
        self.assertEqual(doc.one(lambda n: n.has('primary-button')).attrs['href'], url)
        schema = next(show.event_schemas(show.schema_blocks(rendered)[0][1]))
        self.assertEqual(schema['offers'], {'@type': 'Offer', 'url': url, 'price': 15, 'priceCurrency': 'USD'})
        compact = '<article class="event-card" data-date="2027-01-29"><h3><a href="/event/sample/">Sample</a></h3><div class="event-footer"><a class="official-button" href="https://example.com/info">Official details</a></div></article>'
        changed = show.listing_transform(compact, {'paths': {'/event/sample/': row}})
        self.assertEqual(changed, compact.replace('https://example.com/info', url))

    def test_private_record_stays_listed_without_address_event_or_offer(self):
        row = record(status='private', ticketUrl='https://www.eventbrite.com/e/private-tickets-1234567890')
        rendered = show.detail_transform(fixture(True), row)
        self.assertIn('Explore public shows', rendered)
        self.assertIn('Private Event', rendered)
        self.assertIn('data-kc-private-date', rendered)
        self.assertNotIn('5001 N Oak', rendered)
        self.assertNotIn('64118', rendered)
        self.assertFalse([s for _, value in show.schema_blocks(rendered) for s in show.event_schemas(value)])
        self.assertEqual(show.detail_transform(rendered, row), rendered)

    def test_initial_html_contains_details_and_preserves_existing_schedule_facts(self):
        row = record(publicDescription='The specific concert description.', scheduleDetails=[{'label': 'Pre-Jam', 'text': '6 PM'}, {'label': 'Doors', 'text': '5 PM'}], doorsTime='17:00', ageRestriction='18+')
        source = fixture().replace('</dl><a class="primary-button"', '</dl><section data-kc-event-schedule><h2>Schedule</h2></section><a class="primary-button"')
        rendered = show.detail_transform(source, row)
        self.assertNotIn('data-kc-event-schedule', rendered)
        self.assertEqual(rendered.count('<details class="kc-more-details">'), 1)
        self.assertIn('The specific concert description.', rendered)
        self.assertIn('Pre-Jam', rendered)
        self.assertEqual(rendered.count('<dt>Doors</dt>'), 1)
        self.assertLess(rendered.index('kc-admission-restriction'), rendered.index('class="primary-button"'))

    def test_safe_text_and_existing_identity_media_analytics_remain_unchanged(self):
        row = record(organizer={'name': '<img src=x onerror=alert(1)>', 'url': 'javascript:alert(1)'}, publicDescription='</script><script>alert(1)</script>')
        original = fixture()
        rendered = show.detail_transform(original, row)
        self.assertNotIn('<img src=x', rendered)
        self.assertNotIn('javascript:', rendered)
        self.assertNotIn('<script>alert', rendered)
        for needle in ('<link rel="canonical" href="https://kingdomcircuit.com/event/sample/">', '<meta name="robots" content="index,follow">', '<script async src="https://www.googletagmanager.com/gtag/js?id=G-REAL"></script>', '<img src="/assets/flyer.jpg" alt="Full flyer">', '<h1>Sample concert</h1>', '<p class="artist-line">Artist</p>'):
            self.assertIn(needle, rendered)

    def test_current_catalog_controls_scope_and_source_json_never_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            (site / 'assets').mkdir()
            (site / 'config').mkdir()
            (site / 'event/sample').mkdir(parents=True)
            (site / 'event/old-archive').mkdir(parents=True)
            current = {**record(), 'canonicalPath': '/event/sample/'}
            (site / 'events.json').write_text(json.dumps([current]))
            (site / 'supplemental-events.json').write_text('[]')
            (site / 'config/artists.json').write_text('[{"name":"Artist"}]')
            (site / 'assets/fan-show-catalog.json').write_text(json.dumps({'shows': [{'path': '/event/sample/', 'date': '2027-01-29'}]}))
            (site / 'event/sample/index.html').write_text(fixture())
            (site / 'event/old-archive/index.html').write_text('ARCHIVED RECORD')
            before = show.source_hashes(site)
            report = show.build(site)
            self.assertEqual(report['eventPages'], 1)
            self.assertEqual(show.source_hashes(site), before)
            self.assertEqual((site / 'event/old-archive/index.html').read_text(), 'ARCHIVED RECORD')
            saved = (site / 'event/sample/index.html').read_bytes()
            self.assertEqual(show.verify(site), report)
            self.assertEqual(show.build(site), report)
            self.assertEqual((site / 'event/sample/index.html').read_bytes(), saved)
            self.assertEqual(saved.count(b'data-kc-show-information'), 1)

    def test_official_ticket_page_gets_offer_without_extra_button(self):
        row = record(officialUrl='https://events.humanitix.com/an-actual-event')
        self.assertEqual(row['offer']['url'], row['officialUrl'])
        self.assertEqual(row['officialDestination']['kind'], 'tickets')
        self.assertIsNone(record(officialUrl=row['officialUrl'], ticketUrlVerified=False)['offer'])


if __name__ == '__main__':
    unittest.main()
