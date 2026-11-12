"""Known organizer websites must survive into Google's final Event data."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent))
import show_information as show
from show_information_model import normalize
from apply_verified_show_information import enrich
from test_show_information import fixture, record


class OrganizerURLPublicationTests(unittest.TestCase):
    def test_verified_website_survives_final_schema_and_repeated_rendering(self):
        for organizer in ({'name': 'Real promoter'}, 'Real promoter'):
            for labels in ({}, {'organizerWebsiteName': 'Real promoter'},
                           {'organizerLinkName': 'Real promoter'}):
                with self.subTest(organizer=organizer, labels=labels):
                    row = record(organizer=organizer,
                                 organizerWebsite='https://promoter.example/', **labels)
                    rendered = show.detail_transform(fixture(), row)
                    schema = next(show.event_schemas(show.schema_blocks(rendered)[0][1]))
                    self.assertEqual(schema['organizer']['url'], 'https://promoter.example/')
                    self.assertEqual(show.detail_transform(rendered, normalize(row)), rendered)

    def test_explicit_url_wins_and_scoped_coorganizer_website_is_not_borrowed(self):
        row = record(organizer={'name': 'One / Two', 'url': 'https://joint.example/'},
                     organizerWebsite='https://two.example/', organizerWebsiteName='Two')
        self.assertEqual(row['organizerUrl'], 'https://joint.example/')
        row = record(organizer={'name': 'One / Two'},
                     organizerWebsite='https://two.example/', organizerLinkName='Two')
        self.assertNotIn('organizerUrl', row)
        self.assertEqual(row['organizerWebsite'], 'https://two.example/')

    def test_no_name_unsafe_social_ticket_or_legacy_url_is_invented(self):
        for url in ('javascript:alert(1)', 'https://user:password@example.com/',
                    'https://www.instagram.com/promoter/',
                    'https://www.eventbrite.com/e/show-tickets-123'):
            self.assertNotIn('organizerUrl', record(organizer='Promoter', organizerWebsite=url))
        self.assertNotIn('organizerUrl', record(organizerWebsite='https://promoter.example/'))
        row = record(organizer={'name': 'Current'}, organizerName='Old',
                     organizerUrl='https://old.example/', ticketUrl='https://tickets.example/')
        self.assertNotIn('organizerUrl', row)

    def test_private_events_still_have_no_public_event_markup(self):
        row = record(organizer='Promoter', organizerWebsite='https://promoter.example/', status='private')
        rendered = show.detail_transform(fixture(True), row)
        self.assertFalse([s for _, value in show.schema_blocks(rendered) for s in show.event_schemas(value)])

    def test_all_winter_jam_reviewed_links_repair_only_the_verified_identity(self):
        links = json.loads((ROOT / 'config/verified-show-links.json').read_text())['events']
        winter = [x for x in links if x['id'].startswith('manual:winter-jam-2027-')]
        self.assertEqual(len(winter), 34)
        for reviewed in winter:
            with self.subTest(id=reviewed['id']):
                event = {key: reviewed[key] for key in ('id', 'startDate', 'city', 'state', 'country')}
                event.update(title='Winter Jam 2027', venue=reviewed['expectedVenue'],
                             organizer={'name': 'NewSong / TPR'})
                before = deepcopy(event)
                fixed = enrich(event, [reviewed])
                self.assertEqual(fixed['organizer'], {'name': 'NewSong / TPR', 'url': 'https://jamtour.com/'})
                self.assertEqual(enrich(fixed, [reviewed]), fixed)
                self.assertEqual(event, before)
                moved = {**event, 'organizer': {'name': 'New organizer', 'url': 'https://new.example/'}}
                self.assertEqual(enrich(moved, [reviewed]), moved)
                updated = {**event, 'organizer': {'name': 'NewSong / TPR', 'url': 'https://new.example/'}}
                self.assertEqual(enrich(updated, [reviewed])['organizer'], updated['organizer'])


if __name__ == '__main__':
    unittest.main()
