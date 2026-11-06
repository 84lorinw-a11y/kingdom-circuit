"""Secondary show profiles preserve facts, navigation, privacy and identity."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import show_information as show
from mobile_discovery import Document
from test_show_information import fixture, record


class ShowInformationLinksTests(unittest.TestCase):
    def test_verified_profiles_are_secondary_and_do_not_change_event_navigation_or_offer(self):
        row = record()
        row.update({
            'performerInstagrams': [{'name': 'Artist & Friend', 'url': 'https://www.instagram.com/artist/'}],
            'eventInstagram': 'https://www.instagram.com/concert_brand/',
            'venueInstagram': 'https://www.instagram.com/the_chapel/',
            'organizerInstagram': 'https://www.instagram.com/real_promoter/',
            'venueUrl': 'https://chapel.example/calendar',
            'organizerWebsite': 'https://promoter.example/',
            'organizerName': 'Real promoter',
        })
        original = fixture().replace('<p class="artist-line">Artist</p>', '<p class="artist-line"><a href="/artists/artist/">Artist</a></p>')
        result = show.detail_transform(original, row)
        doc = Document(result)
        panel = doc.one(lambda n: n.has('kc-more-details'))
        links = [n for n in doc.nodes if n.tag == 'a' and panel.start < n.start < panel.end]
        self.assertEqual(len(links), 6)
        for link in links:
            self.assertEqual(link.attrs.get('target'), '_blank')
            self.assertEqual(link.attrs.get('rel'), 'noopener noreferrer')
        self.assertIn('Artist &amp; Friend (@artist)', result)
        for label in ['Performer Instagram', 'Event Instagram', 'Venue Instagram', 'Organizer Instagram', 'Venue website', 'Organizer website']:
            self.assertIn('<dt>' + label + '</dt>', result)
        self.assertEqual(len([n for n in doc.nodes if n.has('primary-button')]), 1)
        self.assertIn('<a href="/artists/artist/">Artist</a>', result)
        self.assertIn('<link rel="canonical" href="https://kingdomcircuit.com/event/sample/">', result)
        schema = next(show.event_schemas(show.schema_blocks(result)[0][1]))
        self.assertNotIn('offers', schema)
        self.assertEqual(show.detail_transform(result, row), result)

    def test_performer_profile_alone_creates_honest_details_without_fabricating_facts(self):
        row = record(startTime='', endTime='', address='', postalCode='', description='', publicDescription='')
        row['performerInstagrams'] = [{'name': 'EGR', 'url': 'https://www.instagram.com/egr/' }]
        result = show.detail_transform(fixture(), row)
        self.assertIn('<summary>More show details</summary>', result)
        self.assertIn('EGR (@egr)', result)
        self.assertIn('Start time not confirmed', result)
        self.assertIn('Address not confirmed', result)
        self.assertNotIn('<dt>Price</dt>', result)
        self.assertNotIn('<dt>Organizer / promoter</dt>', result)

    def test_description_paragraphs_remain_safe_initial_html_and_full_schema_text(self):
        description = 'A specific concert with <script>untrusted markup</script>.\n\nDoors and entry information.\n\nCommunity activities & performances.'
        row = record(publicDescription=description)
        result = show.detail_transform(fixture(), row)
        doc = Document(result)
        panel = doc.one(lambda n: n.has('kc-more-details'))
        paragraphs = [n for n in doc.nodes if n.tag == 'p' and panel.start < n.start < panel.end]
        self.assertEqual(len(paragraphs), 3)
        self.assertNotIn('<script>untrusted', result)
        self.assertIn('&lt;script&gt;untrusted', result)
        schema = next(show.event_schemas(show.schema_blocks(result)[0][1]))
        self.assertEqual(schema['description'], description)
        self.assertEqual(show.detail_transform(result, row), result)

    def test_private_details_keep_profiles_without_disclosing_address_or_public_event_offer(self):
        row = record(status='private')
        row['performerInstagrams'] = [{'name': 'Artist', 'url': 'https://www.instagram.com/artist/'}]
        result = show.detail_transform(fixture(True), row)
        self.assertIn('Private Event — not open to the public', result)
        self.assertIn('Artist (@artist)', result)
        self.assertIn('Explore public shows', result)
        self.assertNotIn('5001 N Oak', result)
        self.assertNotIn('64118', result)
        self.assertFalse([s for _, v in show.schema_blocks(result) for s in show.event_schemas(v)])

    def test_context_derives_profiles_from_published_registry_without_source_mutations(self):
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            (site/'assets').mkdir()
            (site/'config').mkdir()
            (site/'event/sample').mkdir(parents=True)
            event = {'id':'example-123', 'title':'Sample concert', 'startDate':'2027-01-29', 'canonicalPath':'/event/sample/', 'artists':['Artist Alias'], 'venue':'Chapel', 'city':'Kansas City','state':'MO','country':'US'}
            artists = [{'name':'Artist', 'aliases':['Artist Alias'], 'enabled':True, 'instagramProfile':'https://www.instagram.com/official_artist/'}]
            (site/'events.json').write_text(json.dumps([event]))
            (site/'supplemental-events.json').write_text('[]')
            (site/'config/artists.json').write_text(json.dumps(artists))
            (site/'assets/fan-show-catalog.json').write_text(json.dumps({'shows':[{'path':'/event/sample/','date':'2027-01-29'}]}))
            (site/'event/sample/index.html').write_text(fixture())
            before = show.source_hashes(site)
            result = show.context(site)['pages']['event/sample/index.html']
            self.assertEqual(result['performerInstagrams'], [{'name':'Artist','url':'https://www.instagram.com/official_artist/'}])
            self.assertEqual(before, show.source_hashes(site))


if __name__ == '__main__':
    unittest.main()
