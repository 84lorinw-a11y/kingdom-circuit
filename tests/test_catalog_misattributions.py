import copy
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from catalog_removals import apply, removed_event
from build_seo_site import merge_events
import add_past_show_archives as archives
import url_continuity as continuity


class CatalogMisattributionTests(unittest.TestCase):
    def event(self, **fields):
        return dict(id='bandsintown:1040781482', title='Ryan Ellis at The Betsy Hotel',
                    startDate='2026-11-13', startTime='18:00', venue='The Betsy Hotel',
                    city='Miami Beach', state='FL', country='US', artists=['Ryan Ellis'],
                    headliner='Ryan Ellis', status='scheduled', confidence='high',
                    officialUrl='https://www.bandsintown.com/e/1040781482', **fields)

    def test_idol_duo_booking_does_not_match_the_chh_group(self):
        wrong = dict(id='bandsintown:1040675970', startDate='2027-01-23', artists=['Altar Ego'],
                     officialUrl='https://www.eventbrite.com/e/idol-game-lost-destination-6-month-anniversary-live-tickets-2003227249629')
        self.assertTrue(removed_event(wrong))
        self.assertTrue(removed_event({**wrong, 'id': 'new-provider-id'}))
        self.assertFalse(removed_event({**wrong, 'startDate': '2027-02-23'}))
        self.assertFalse(removed_event({**wrong, 'id': 'valid-chh', 'officialUrl': 'https://www.instagram.com/altaregorecords/'}))

    def other_show(self):
        return {**self.event(), 'id': 'official:ryan-valid', 'title': 'Ryan Ellis concert',
                'venue': 'Concert Hall', 'city': 'Los Angeles', 'state': 'CA',
                'officialUrl': 'https://ryanellismusic.com/tour/'}

    def test_exact_reviewed_booking_and_reimported_links_are_not_published(self):
        source = self.event()
        before = copy.deepcopy(source)
        variants = [source, {**source, 'id': 'manual:bandsintown:1040781482'},
                    {**source, 'id': 'reimported', 'officialUrl':
                     'https://www.bandsintown.com/t/1040781482?ref=calendar'},
                    {**source, 'id': 'reimported', 'officialUrl':
                     'https://www.thebetsyhotel.com/event-calendar/live-music-intergenerational-jazz-ellis-duo-13'}]
        good = self.other_show()
        for row in variants:
            with self.subTest(id=row['id'], url=row['officialUrl']):
                self.assertTrue(removed_event(row))
                self.assertEqual(merge_events([good], [row]), [good])
        self.assertEqual(source, before)

    def test_other_dates_venues_and_same_name_artists_are_not_banned(self):
        source = self.event()
        for row in (self.other_show(), {**source, 'startDate': '2027-11-13'},
                    {**source, 'id': 'different', 'officialUrl': 'https://www.bandsintown.com/e/10407814820'},
                    {**source, 'id': 'different', 'officialUrl': 'https://bandsintown.com.attacker.example/e/1040781482'},
                    {**source, 'id': 'different', 'officialUrl': 'https://www.thebetsyhotel.com/event-calendar/another-concert'}):
            with self.subTest(row=row):
                self.assertFalse(removed_event(row))

    def test_refresh_filters_public_feeds_but_preserves_the_original_history(self):
        bad, good = self.event(), self.other_show()
        history = {'events': [{'event': bad, 'firstSeenOnCalendar': '2026-11-01'}, {'event': good}]}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'config').mkdir()
            for name in ('events.json', 'supplemental-events.json', 'config/manual-events.json'):
                (root / name).write_text(json.dumps([bad, good]))
            (root / 'event-history.json').write_text(json.dumps(history))
            history_bytes = (root / 'event-history.json').read_bytes()
            apply(root)
            for name in ('events.json', 'supplemental-events.json', 'config/manual-events.json'):
                self.assertEqual(json.loads((root / name).read_text()), [good])
            self.assertEqual((root / 'event-history.json').read_bytes(), history_bytes)
            once = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*.json')}
            apply(root)
            self.assertEqual({str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*.json')}, once)

    def test_retained_wrong_identity_never_becomes_an_artist_archive_or_restored_page(self):
        bad, good = self.event(), self.other_show()
        history = {'events': [{'event': event, 'observedOnOrAfterEventDate': True}
                              for event in (bad, good)]}

        class AfterShowDate(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 11, 20, tzinfo=tz)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'config').mkdir()
            (root / 'event-history.json').write_text(json.dumps(history))
            (root / 'config/artists.json').write_text(json.dumps([{'name': 'Ryan Ellis'}]))
            with patch('add_past_show_archives.dt.datetime', AfterShowDate):
                selected, _ = archives.load_events(root)
            self.assertEqual([e['id'] for e in selected], ['official:ryan-valid'])
            self.assertEqual(json.loads((root / 'event-history.json').read_text()), history)
            state = continuity.empty_state()
            for event in (bad, good):
                state['events'][event['id']] = {'path': continuity.generated_path(event),
                                                'sourceIds': [], 'event': event}
            continuity.save(root / continuity.STATE_FILE, state)
            site = root / '_site'
            site.mkdir()
            continuity.finalize(root, site)
            self.assertFalse(continuity.target_file(site, continuity.generated_path(bad)).exists())
            self.assertTrue(continuity.target_file(site, continuity.generated_path(good)).exists())
            self.assertEqual(json.loads((root / 'event-history.json').read_text()), history)


if __name__ == '__main__':
    unittest.main()
