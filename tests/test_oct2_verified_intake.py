import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from apply_oct2_verified_shows import apply
from apply_sep26_requested_lineups import patch_event
from catalog_removals import removed_event
from artist_portraits import load_portraits


class OctoberIntakeTests(unittest.TestCase):
    def test_refresh_restores_bill_and_art_without_resetting_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'config').mkdir()
            wanted = json.loads((ROOT / 'config/oct2-verified-shows.json').read_text())
            (root / 'config/oct2-verified-shows.json').write_text(json.dumps(wanted))
            stale = dict(wanted[0], id='manual:' + wanted[0]['id'], artists=['Zenwi'],
                         image='expired-social-url', firstSeen='2026-09-30T00:00:00Z')
            for name in ['events.json', 'supplemental-events.json', 'config/manual-events.json']:
                (root / name).write_text(json.dumps([copy.deepcopy(stale)]))
            (root / 'event-history.json').write_text(json.dumps({'events': [{'event': stale}]}))
            apply(root, today='2026-10-02')
            first = {p: (root / p).read_bytes() for p in ['events.json', 'config/manual-events.json', 'event-history.json']}
            apply(root, today='2026-10-02')
            self.assertTrue(all((root / p).read_bytes() == content for p, content in first.items()))
            row = json.loads((root / 'events.json').read_text())[0]
            self.assertEqual(row['firstSeen'], '2026-09-30T00:00:00Z')
            self.assertIn('Jayde Eliyah', row['advertisedBilling'])
            self.assertTrue(row['image'].startswith('assets/events/'))
            apply(root, today='2027-01-01')
            self.assertEqual(json.loads((root / 'events.json').read_text()), [])
            manual = json.loads((root / 'config/manual-events.json').read_text())
            self.assertEqual(len(manual), 4)
            self.assertFalse(any(str(row.get('id')) == 'alex-jean-dallas-2026-11-19' for row in manual))

    def test_owner_hold_removes_alex_dallas_from_every_live_feed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'config').mkdir()
            wanted = json.loads((ROOT / 'config/oct2-verified-shows.json').read_text())
            (root / 'config/oct2-verified-shows.json').write_text(json.dumps(wanted))
            held = next(row for row in wanted if row['id'] == 'alex-jean-dallas-2026-11-19')
            for name in ['events.json', 'supplemental-events.json', 'config/manual-events.json']:
                row = copy.deepcopy(held)
                row['id'] = ('manual:' if name != 'config/manual-events.json' else '') + held['id']
                (root / name).write_text(json.dumps([row]))
            (root / 'event-history.json').write_text(json.dumps({'events': []}))
            apply(root, today='2026-10-03')
            for name in ['events.json', 'supplemental-events.json', 'config/manual-events.json']:
                rows = json.loads((root / name).read_text())
                self.assertFalse(any('alex-jean-dallas-2026-11-19' in str(row.get('id')) for row in rows))

    def test_visalia_keeps_its_identity_and_host_separate_from_performers(self):
        row = {'id': 'manual:egr-2026-10-10-visalia-ca', 'startDate': '2026-10-10',
               'title': 'EGR Live — Visalia', 'artists': ['EGR'], 'image': 'old-portrait'}
        self.assertTrue(patch_event(row))
        self.assertEqual(row['id'], 'manual:egr-2026-10-10-visalia-ca')
        self.assertEqual(row['startTime'], '12:00')
        self.assertEqual(len(row['artists']), 11)
        self.assertEqual(row['hosts'], ['Antwoine Hill'])
        self.assertNotIn('Antwoine Hill', row['artists'])
        self.assertEqual(row['firstSeen'], '2026-08-09T00:00:00Z')
        self.assertTrue(row['legacyEventPaths'])

    def test_removed_performances_cannot_return_from_legacy_feed(self):
        self.assertTrue(removed_event({'artists': ['Propaganda']}))
        self.assertTrue(removed_event({'title': 'Propaganda Live', 'artists': []}))
        self.assertTrue(removed_event({'officialBill': ['Propaganda']}))
        self.assertFalse(removed_event({'artists': ['DJ Promote'], 'hosts': ['Propaganda'], 'title': 'Real Ones Day Party'}))

    def test_every_verified_intake_artist_has_a_saved_registered_portrait(self):
        roster = json.loads((ROOT / 'config/verified-artist-registry-updates.json').read_text())
        intake = [r for r in roster if 190 <= int(r.get('sheetRosterOrder') or 0) <= 213]
        self.assertEqual(len(intake), 24)
        # This unit suite runs before the image backend is installed. Check the
        # saved files, digests and registry here; verify_oct2_verified_intake
        # mandatorily decodes originals and responsive variants after the build.
        photos = load_portraits(ROOT)
        active = {r['name']: r for r in json.loads((ROOT / 'config/artists.json').read_text())}
        for row in intake:
            self.assertIn(row['name'], photos)
            self.assertEqual(row['imageUrl'], photos[row['name']]['asset'])
            self.assertTrue(active[row['name']]['sourceRegistryVerified'])


if __name__ == '__main__':
    unittest.main()
