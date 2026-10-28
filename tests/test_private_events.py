import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import private_events as private
from build_seo_site import scheduled, event_path, event_card, event_schema


class PrivateEventsTests(unittest.TestCase):
    def test_provider_refresh_cannot_reopen_admission_or_remove_history(self):
        pinned = private.records()[0]
        stale = dict(pinned, status='scheduled', id='bandsintown:108856562')
        other = dict(stale, id='another-booking', startDate='2027-02-14')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'config').mkdir()
            (root / 'config/private-events.json').write_text(json.dumps([pinned]))
            for filename in ('events.json', 'supplemental-events.json', 'config/manual-events.json'):
                (root / filename).write_text(json.dumps([stale, other]))
            (root / 'event-history.json').write_text(json.dumps({'events': [{'event': stale}, {'event': other}]}))
            (root / 'config/artist-website-seed-events.json').write_text(json.dumps([stale, other]))
            self.assertGreater(private.apply(root), 0)
            self.assertEqual(private.apply(root), 0)
            self.assertEqual(json.loads((root / 'events.json').read_text()), [pinned, other])
            history = json.loads((root / 'event-history.json').read_text())['events']
            self.assertEqual(len(history), 2)
            self.assertEqual(history[0]['event']['id'], stale['id'])
            self.assertEqual(history[0]['event']['status'], 'private')
            self.assertEqual(history[1]['event'], other)
            self.assertTrue(scheduled(history[0]['event']))
            self.assertNotIn('offers', event_schema(pinned))
            exported = root / 'public-history.json'
            self.assertEqual(private.public_history(exported, root), 1)
            self.assertEqual(json.loads(exported.read_text())['events'], [{'event': other}])
            self.assertEqual(len(json.loads((root / 'event-history.json').read_text())['events']), 2)

    def test_private_listing_labels_preserve_other_cards_and_urls(self):
        event = private.records()[0]
        other = dict(event, id='other-event', title='Public show', status='scheduled')
        source = event_card(event, []) + event_card(other, [])
        output = private.label_cards(source)
        self.assertIn('AMPLIFY — Private Event', output)
        self.assertIn('Not open to the public.', output)
        self.assertIn(event_card(other, []), output)
        self.assertIn('href="' + event_path(event) + '"', output)
        self.assertEqual(private.label_cards(output), output)

    def test_expired_private_dates_are_not_restored_to_upcoming_feeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'config').mkdir()
            (root / 'config/private-events.json').write_text(json.dumps(private.records()))
            (root / 'events.json').write_text('[]')
            self.assertEqual(private.apply(root, as_of='2027-02-14'), 0)
            self.assertEqual(json.loads((root / 'events.json').read_text()), [])

    def test_all_existing_urls_explain_private_admission_without_ticket_offers(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            paths = private.write_pages(site)
            self.assertEqual(len(paths), 6)
            for path in paths:
                text = (site / path.strip('/') / 'index.html').read_text()
                self.assertIn('Private event — not open to the public.', text)
                self.assertIn('Explore public shows', text)
                self.assertNotIn('bandsintown.com', text)
                self.assertNotIn('"@type":"MusicEvent"', text)
                self.assertNotIn('EventCancelled', text)
                self.assertNotIn('EventPostponed', text)
            for event in private.records():
                self.assertIn(event_path(event), paths)
                from finalize_artist_schedule_years import event_dates
                start, end = event_dates(site, '<a href="' + event_path(event) + '">')
                self.assertEqual(start.isoformat(), event['startDate'])
                self.assertEqual(end, start)


if __name__ == '__main__':
    unittest.main()
