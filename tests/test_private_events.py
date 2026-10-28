import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import private_events as private
from build_seo_site import scheduled, event_path


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
            self.assertEqual(private.apply(root), 3)
            self.assertEqual(private.apply(root), 0)
            self.assertEqual(json.loads((root / 'events.json').read_text()), [other])
            history = json.loads((root / 'event-history.json').read_text())['events']
            self.assertEqual(len(history), 2)
            self.assertEqual(history[0]['event']['id'], stale['id'])
            self.assertEqual(history[0]['event']['status'], 'private')
            self.assertEqual(history[1]['event'], other)
            self.assertFalse(scheduled(history[0]['event']))
            exported = root / 'public-history.json'
            self.assertEqual(private.public_history(exported, root), 1)
            self.assertEqual(json.loads(exported.read_text())['events'], [{'event': other}])
            self.assertEqual(len(json.loads((root / 'event-history.json').read_text())['events']), 2)

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


if __name__ == '__main__':
    unittest.main()
