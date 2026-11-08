import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_seo_site import merge_events
from catalog_removals import apply, removed_artist, removed_event, withheld_event
from permanent_state_pages import eligible
from run_bandsintown_refresh import retained_missing
from url_continuity import source_events


class OwnerRejectedOccurrenceTests(unittest.TestCase):
    def rejected(self):
        return [
            dict(id='provider:praise-party', title='Praise Party: Skate Night Edition',
                 startDate='2026-11-11', city='Newark', state='NJ', country='US',
                 venue='Branch Brook Park Roller Skating Center', artists=['DJ Mar'],
                 officialUrl='https://posh.vip/e/praise-party-skate-night-edition'),
            dict(id='provider:big-igloo', title='Big Igloo presents B-SHOC',
                 startDate='2026-11-15', city='Kearney', state='NE', country='US',
                 venue='Merryman Performing Arts Center', artists=['B-SHOC'],
                 officialUrl='https://merrymancenter.org/events/b-shoc/'),
            dict(id='provider:re-up', title='The Re-Up Hemet',
                 startDate='2027-02-20', city='Hemet', state='CA', country='US',
                 venue='Living Way Hemet', artists=['even bkim', 'DJ Shondo'],
                 officialUrl='https://www.kingdomtix.org/events/1ee1aa0a-f1c7-472e-9b04-f3bb56d79cbc'),
        ]

    def sacramento(self):
        return dict(id='manual:hookd-on-god-sacramento-2026-11-20',
                    title='Hook’d On God', startDate='2026-11-20', startTime='20:00',
                    timezone='America/Los_Angeles', city='Sacramento', state='CA',
                    country='US', address='7833 Center Pkwy',
                    artists=['KC and the Kingdom'], advertisedBilling=['KC and the Kingdom'],
                    speakers=['Sevin'], musicConfirmed=True, status='scheduled',
                    officialUrl='https://www.hookdonlifecoaching.com/events')

    def test_exact_links_survive_provider_reimports_and_url_tracking(self):
        for original in self.rejected():
            before = copy.deepcopy(original)
            for field in ('officialUrl', 'ticketUrl', 'registrationUrl'):
                for url in (original['officialUrl'],
                            original['officialUrl'].rstrip('/') + '/?ref=calendar#tickets',
                            original['officialUrl'].replace('https://', 'http://')):
                    row = {**original, 'id': 'reimported', 'officialUrl': '', field: url}
                    with self.subTest(date=row['startDate'], field=field, url=url):
                        self.assertTrue(withheld_event(row))
                        self.assertTrue(removed_event(row))
            self.assertEqual(original, before)

    def test_both_reup_provider_ids_and_ticket_paths_are_excluded_on_exact_day(self):
        original = self.rejected()[2]
        for provider_id in ('108711786', '109041557'):
            variants = [
                dict(id='bandsintown:' + provider_id),
                dict(id='manual:bandsintown:' + provider_id),
                dict(bandsintownEventId=provider_id),
                dict(bandsintownEventId=int(provider_id)),
            ]
            for kind in ('e', 't'):
                for host in ('bandsintown.com', 'www.bandsintown.com'):
                    variants.append(dict(ticketUrl=f'https://{host}/{kind}/{provider_id}-the-re-up/?ref=calendar'))
            for fields in variants:
                row = {**original, 'officialUrl': '', **fields}
                with self.subTest(fields=fields):
                    self.assertTrue(removed_event(row))
                    self.assertFalse(removed_event({**row, 'startDate': '2027-02-21'}))

    def test_dates_and_other_same_artist_performances_remain_eligible(self):
        for event in self.rejected():
            self.assertFalse(removed_event({**event, 'startDate': '2027-11-11'}))
            # Names, title and locality alone do not identify a rejected occurrence.
            other = {**event, 'id': 'different-event', 'officialUrl': 'https://example.org/other-concert'}
            self.assertFalse(removed_event(other))
            for name in event['artists']:
                self.assertFalse(removed_artist(name))
        approved = self.sacramento()
        self.assertFalse(removed_event(approved))
        self.assertTrue(eligible(approved))
        self.assertEqual(merge_events([approved], []), [approved])

    def test_similar_urls_and_untrusted_host_variants_do_not_match(self):
        for event in self.rejected():
            exact = event['officialUrl'].rstrip('/')
            authority, path = exact.split('://', 1)[1].split('/', 1)
            urls = [
                exact + '-other', exact + '/different-event',
                f'https://{authority}.example.org/{path}',
                f'https://{authority}@example.org/{path}',
                f'https://user@{authority}/{path}',
                f'https://{authority}:8443/{path}',
                f'https://{authority}:invalid/{path}',
                f'ftp://{authority}/{path}',
                f'https://{authority}/\n{path}',
                f'https://[invalid/{path}',
            ]
            for url in urls:
                with self.subTest(url=url):
                    self.assertFalse(removed_event({**event, 'officialUrl': url}))
        for url in ('https://bandsintown.com/e/1087117860',
                    'https://bandsintown.com/e/1090415570',
                    'https://bandsintown.com.example.org/e/108711786',
                    'https://bandsintown.com/e/108711786/another-event'):
            self.assertFalse(removed_event({**self.rejected()[2], 'officialUrl': url}))

    def test_source_refresh_and_final_projections_exclude_only_reviewed_events(self):
        rejected, approved = self.rejected(), self.sacramento()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'config').mkdir()
            for name in ('events.json', 'supplemental-events.json', 'config/manual-events.json'):
                (root / name).write_text(json.dumps([*rejected, approved]))
            (root / 'event-history.json').write_text(json.dumps({'events': [
                {'event': event} for event in [*rejected, approved]]}))
            # The final publication projection blocks reimports before source cleanup.
            self.assertEqual(merge_events(rejected, [approved]), [approved])
            self.assertTrue(all(not eligible(row) for row in rejected))
            self.assertEqual(source_events(root), [approved] * 4)
            for row in rejected:
                self.assertIsNone(retained_missing(row, '2026-11-07', set(), lambda value: value))
            apply(root)
            for name in ('events.json', 'supplemental-events.json', 'config/manual-events.json'):
                self.assertEqual(json.loads((root / name).read_text()), [approved])
            self.assertEqual(json.loads((root / 'event-history.json').read_text()),
                             {'events': [{'event': approved}]})
            once = {p: p.read_bytes() for p in root.rglob('*.json')}
            apply(root)
            self.assertEqual(once, {p: p.read_bytes() for p in once})


if __name__ == '__main__':
    unittest.main()
