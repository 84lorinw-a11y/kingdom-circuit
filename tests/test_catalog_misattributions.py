import copy
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from catalog_removals import apply, location_review_event, public_event, removed_event
from build_seo_site import merge_events
import add_past_show_archives as archives
import url_continuity as continuity
from permanent_state_pages import eligible as state_eligible


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


class LocationUnconfirmedBookingTests(unittest.TestCase):
    def event(self, **fields):
        return {'id': 'official:023c040d4ea33e120949',
                'title': '1K Phew — Live at Texas Motorplex',
                'startDate': '2026-11-21', 'startTime': '', 'timezone': '',
                'venue': 'Texas Motorplex', 'city': 'Swiss Golf And Tennis Club Mobile Home Park',
                'state': 'FL', 'country': 'US', 'artists': ['1K Phew'],
                'headliner': '1K Phew', 'status': 'scheduled', 'confidence': 'high',
                'officialUrl': 'https://www.reachrecords.com/artists/1k-phew/',
                **fields}

    def other_show(self):
        return self.event(id='official:other-1k-phew-show', title='1K Phew concert',
                          venue='Concert Hall', city='Orlando')

    def test_exact_dated_booking_is_retained_but_never_assigned_a_location(self):
        variants = [self.event(), self.event(id='manual:official:023c040d4ea33e120949'),
                    self.event(id='reimported', officialUrl='https://www.bandsintown.com/e/1040798191-1k-phew?ref=calendar'),
                    self.event(id='reimported', ticketUrl='https://bandsintown.com/t/1040798191/'),
                    self.event(id='reimported', bandsintownEventId='1040798191'),
                    self.event(id='reimported', bandsintownEventId=1040798191)]
        good = self.other_show()
        for event in variants:
            with self.subTest(event=event):
                before = copy.deepcopy(event)
                self.assertTrue(location_review_event(event))
                self.assertFalse(removed_event(event))
                self.assertEqual(merge_events([good], [event]), [good, public_event(event)])
                self.assertFalse(state_eligible(event))
                self.assertEqual(event, before)
                for day in ('2026-11-20', '2026-11-22', '2027-11-21'):
                    changed_date = {**event, 'startDate': day}
                    self.assertFalse(location_review_event(changed_date))
                    self.assertFalse(removed_event(changed_date))
        self.assertTrue(state_eligible(good))
        self.assertFalse(location_review_event(good))

    def test_similar_ids_unsafe_hosts_and_other_artist_shows_remain_eligible(self):
        variants = [self.other_show(),
                    self.event(id='official:023c040d4ea33e1209490'),
                    self.event(id='manual:manual:official:023c040d4ea33e120949'),
                    self.event(id='reimported', bandsintownEventId='10407981910')]
        for url in (
            'https://www.bandsintown.com/e/10407981910',
            'https://www.bandsintown.com/e/01040798191',
            'https://bandsintown.com.attacker.example/e/1040798191',
            'https://attackerbandsintown.com/e/1040798191',
            'https://bandsintown.com@attacker.example/e/1040798191',
            'https://user:password@bandsintown.com/e/1040798191',
            'https://bandsintown.com:invalid/e/1040798191',
            'https://bandsintown.com:8443/e/1040798191',
            'https://attacker.example/?url=https://bandsintown.com/e/1040798191',
            'https://www.bandsintown.com/artist/1040798191',
            'https://www.bandsintown.com/e/1040798191extra',
            'https://www.bandsintown.com/e/1040798191/../another-show',
            'https://www.bandsintown.com/e/1040798191\n',
            'javascript://bandsintown.com/e/1040798191',
            '//bandsintown.com/e/1040798191',
        ):
            variants.extend(self.event(id='reimported', **{field: url})
                            for field in ('officialUrl', 'ticketUrl'))
        for event in variants:
            with self.subTest(event=event):
                self.assertFalse(location_review_event(event))
                self.assertFalse(removed_event(event))

    def test_refresh_sanitizes_public_copies_but_preserves_raw_manual_seed_and_history(self):
        held, good = self.event(), self.other_show()
        history = {'events': [{'event': held, 'firstSeenOnCalendar': '2026-11-03',
                               'observedOnOrAfterEventDate': False}, {'event': good}]}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'config').mkdir()
            for name in ('events.json', 'supplemental-events.json'):
                (root / name).write_text(json.dumps([held, good]))
            (root / 'config/manual-events.json').write_text(json.dumps({'events': [held, good], 'version': 1}))
            (root / 'event-history.json').write_text(json.dumps(history))
            history_bytes = (root / 'event-history.json').read_bytes()
            apply(root)
            for name in ('events.json', 'supplemental-events.json'):
                self.assertEqual(json.loads((root / name).read_text()), [public_event(held), good])
            self.assertEqual(json.loads((root / 'config/manual-events.json').read_text()),
                             {'events': [held, good], 'version': 1})
            self.assertEqual((root / 'event-history.json').read_bytes(), history_bytes)
            once = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*.json')}
            apply(root)
            self.assertEqual({str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*.json')}, once)
        self.assertEqual(held['status'], 'scheduled')
        self.assertEqual((held['city'], held['state']), ('Swiss Golf And Tennis Club Mobile Home Park', 'FL'))

    def test_unconfirmed_booking_never_becomes_a_claimed_past_performance(self):
        held, good = self.event(), self.other_show()
        history = {'events': [{'event': event, 'observedOnOrAfterEventDate': True}
                              for event in (held, good)]}

        class AfterShowDate(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 11, 23, tzinfo=tz)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'config').mkdir()
            (root / 'event-history.json').write_text(json.dumps(history))
            (root / 'config/artists.json').write_text(json.dumps([{'name': '1K Phew'}]))
            original = (root / 'event-history.json').read_bytes()
            with patch('add_past_show_archives.dt.datetime', AfterShowDate):
                selected, _ = archives.load_events(root)
            self.assertEqual([event['id'] for event in selected], [good['id']])
            self.assertEqual((root / 'event-history.json').read_bytes(), original)

    def test_review_record_keeps_original_location_and_pending_status(self):
        root = Path(__file__).resolve().parents[1]
        records = json.loads((root / 'config/review-held-events.json').read_text())
        held = [record for record in records if location_review_event(record.get('event', {}))]
        self.assertEqual(len(held), 1)
        record = held[0]
        self.assertEqual(record['reviewStatus'], 'listed_location_unconfirmed')
        self.assertIs(record['publish'], True)
        self.assertEqual(record['event']['status'], 'scheduled')
        self.assertEqual((record['event']['venue'], record['event']['city'], record['event']['state']),
                         ('Texas Motorplex', 'Swiss Golf And Tennis Club Mobile Home Park', 'FL'))
        self.assertIn('https://www.reachrecords.com/artists/1k-phew/', record['sources'])
        self.assertIn('https://www.texasmotorplex.com/', record['sources'])
        self.assertTrue(record['event']['sources'])
        self.assertTrue(record['reason'])
        self.assertTrue(record['evidence'])


if __name__ == '__main__':
    unittest.main()
