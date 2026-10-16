import copy,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from apply_oct3_concert_corrections import apply,key
from build_seo_site import same_event

class AuthenticScheduleTests(unittest.TestCase):
    def test_verified_alias_survives_registry_sync(self):
        for filename in ['config/artists.json','config/verified-artist-registry-updates.json']:
            artist=next(x for x in json.loads((ROOT/filename).read_text()) if x['name']=='626authentic')
            self.assertIn('626 Authentic',artist['aliases'])

    def test_refresh_restores_distinct_upcoming_shows(self):
        approved=json.loads((ROOT/'config/oct3-verified-concerts.json').read_text())
        expected={e['id']:e for e in approved if '626authentic' in e.get('artists',[]) and e['startDate']>='2026-10-12'}
        self.assertTrue({
            'victory-over-darkness-fullerton-2026-10-24',
            'harvest-fest-ontario-2026-10-31',
            'westside-social-holy-ghost-hip-hop-venice-2026-10-25',
            'harvest-fest-crestline-2026-10-31',
        }.issubset(expected))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'config').mkdir()
            (root/'config/oct3-verified-concerts.json').write_text(json.dumps(approved))
            for name in ['events.json','supplemental-events.json','config/manual-events.json']:(root/name).write_text('[]')
            (root/'event-history.json').write_text('{"events":[]}')
            apply(root,today='2026-10-12')
            before=(root/'events.json').read_bytes();apply(root,today='2026-10-12')
            self.assertEqual(before,(root/'events.json').read_bytes())
            result={key(e):e for e in json.loads(before) if '626authentic' in e.get('artists',[])}
            self.assertEqual(set(result),set(expected))
            west=result['westside-social-holy-ghost-hip-hop-venice-2026-10-25']
            self.assertEqual(west['firstSeen'],'2026-10-06T21:10:10Z')
            self.assertIn('Nicko Ostby',west['advertisedBilling'])
            crest=result['harvest-fest-crestline-2026-10-31'];ontario=result['harvest-fest-ontario-2026-10-31']
            self.assertFalse(same_event(crest,ontario))
            self.assertEqual((crest['startTime'],crest['endTime']),('14:00','17:00'))
            self.assertIn('3:30 PM',crest['publicDescription'])
            self.assertEqual(ontario['startTime'],'')
