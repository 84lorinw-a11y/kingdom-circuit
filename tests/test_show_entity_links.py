import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from show_information_model import normalize


class ShowEntityLinksTests(unittest.TestCase):
    def test_tracked_performer_aliases_match_without_replacing_internal_identity(self):
        artists = [{'name': 'EGR', 'aliases': ['egr music'], 'enabled': True,
                    'instagramProfile': 'https://www.instagram.com/egrmusic/?hl=en'}]
        event = {'artists': ['egr music', 'EGR', 'Unknown'], 'title': 'Fargo'}
        before = copy.deepcopy(event)
        result = normalize(event, artists=artists)
        self.assertEqual(result['performerInstagrams'], [
            {'name': 'EGR', 'url': 'https://www.instagram.com/egrmusic/'}])
        self.assertEqual(event, before)
        self.assertEqual(result['artists'], event['artists'])

    def test_ambiguous_disabled_untracked_and_nonprofile_accounts_are_omitted(self):
        artists = [
            {'name': 'One', 'aliases': ['Shared'], 'enabled': True,
             'instagramProfile': 'https://instagram.com/one/'},
            {'name': 'Two', 'aliases': ['Shared'], 'enabled': True,
             'instagramProfile': 'https://instagram.com/two/'},
            {'name': 'Disabled', 'enabled': False, 'instagramProfile': 'https://instagram.com/disabled/'},
            {'name': 'Post', 'enabled': True, 'instagramProfile': 'https://instagram.com/p/ABC/'},
        ]
        result = normalize({'artists': ['Shared', 'Disabled', 'Post', 'Not tracked'],
                            'performerInstagrams': [{'name': 'Unsafe', 'url': 'https://instagram.com/unsafe/'}]}, artists=artists)
        self.assertNotIn('performerInstagrams', result)

    def test_entities_keep_separate_verified_social_and_website_roles(self):
        result = normalize({'venue': 'The Hall', 'venueUrl': 'https://hall.example/faq/',
            'venueInstagram': 'https://instagram.com/the.hall/?igsh=abc',
            'organizer': {'name': 'Promoter', 'url': 'https://promoter.example/',
                          'instagram': 'https://www.instagram.com/promoter/'},
            'eventInstagram': 'https://instagram.com/event.brand/'})
        self.assertEqual(result['venueUrl'], 'https://hall.example/faq/')
        self.assertEqual(result['venueInstagram'], 'https://www.instagram.com/the.hall/')
        self.assertEqual(result['organizerWebsite'], 'https://promoter.example/')
        self.assertEqual(result['organizerInstagram'], 'https://www.instagram.com/promoter/')
        self.assertEqual(result['eventInstagram'], 'https://www.instagram.com/event.brand/')

    def test_ticketing_and_social_profiles_are_not_labeled_as_organization_websites(self):
        for url in ('https://www.eventbrite.com/o/promoter-12345',
                    'https://www.tickettailor.com/events/promoter/1234567',
                    'https://www.instagram.com/promoter/', 'javascript:alert(1)',
                    'https://user:secret@promoter.example/'):
            with self.subTest(url=url):
                result = normalize({'venue': 'Hall', 'venueUrl': url,
                    'organizer': {'name': 'Promoter', 'url': url}})
                self.assertNotIn('venueUrl', result)
                self.assertNotIn('organizerWebsite', result)

    def test_unknown_entities_and_unsafe_instagram_destinations_are_not_published(self):
        for url in ('https://instagram.com.evil.example/person/',
                    'https://instagram.com/accounts/login/', 'https://instagram.com/reel/ABC/',
                    'https://instagram.com/stories/person/', 'https://user:secret@instagram.com/person/',
                    'https://www.instagram.com:bad/person/',
                    'javascript:alert(1)'):
            with self.subTest(url=url):
                result = normalize({'venue': 'Hall', 'venueInstagram': url,
                                    'organizer': {'name': 'Org', 'instagram': url}, 'eventInstagram': url})
                for key in ('venueInstagram', 'organizerInstagram', 'eventInstagram'):
                    self.assertNotIn(key, result)
        result = normalize({'title': 'Tour', 'venue': 'Tour',
                            'venueUrl': 'https://hall.example/', 'venueInstagram': 'https://instagram.com/hall/',
                            'organizerInstagram': 'https://instagram.com/org/'})
        self.assertNotIn('venueUrl', result)
        self.assertNotIn('venueInstagram', result)
        self.assertNotIn('organizerInstagram', result)

    def test_flat_organizer_social_is_bound_to_the_named_organizer(self):
        result = normalize({'organizerName': 'Promoter',
                            'organizerInstagram': 'https://instagram.com/promoter/',
                            'organizerWebsite': 'https://promoter.example/'})
        self.assertEqual(result['organizerInstagram'], 'https://www.instagram.com/promoter/')
        self.assertEqual(result['organizerWebsite'], 'https://promoter.example/')


if __name__ == '__main__':
    unittest.main()
