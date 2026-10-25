import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import collect_bandsintown_rest as collector
from apply_oct3_concert_corrections import apply, rejected, WRONG_NEHEMIAH_IDS, WRONG_ZEKE_IDS, ADRENALINE_DUPLICATE


class OctoberConcertCorrectionTests(unittest.TestCase):
    def test_harvest_fest_provider_refresh_keeps_one_corrected_show(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'config').mkdir()
            approved = json.loads((ROOT / 'config/oct3-verified-concerts.json').read_text())
            show = next(e for e in approved if e['id'] == 'bandsintown:1040178082')
            (root / 'config/oct3-verified-concerts.json').write_text(json.dumps([show]))
            stale = dict(show, title='Jon Keith at Word of Faith International Christian Center', startTime='18:30')
            for name in ['events.json', 'config/manual-events.json']:
                (root / name).write_text('[]')
            (root / 'supplemental-events.json').write_text(json.dumps([stale]))
            (root / 'event-history.json').write_text('{"events": []}')
            apply(root, today='2026-10-15')
            published = json.loads((root / 'events.json').read_text())
            self.assertEqual(len(published), 1)
            self.assertEqual(published[0]['title'], 'Harvest Fest 2026 — Jon Keith')
            self.assertEqual(published[0]['startTime'], '20:00')
            self.assertEqual(published[0]['firstSeen'], '2026-09-07T16:08:12Z')
            self.assertEqual(json.loads((root / 'supplemental-events.json').read_text()), [])

    def test_zeke_requires_verified_identity_and_preserves_flavor_fest(self):
        artist = {'name': 'ZEKE', 'aliases': ['ZEKE'], 'bandsintownRejectedArtistIds': ['32942']}
        with patch.object(collector, 'get_json') as fetch:
            self.assertEqual(collector.resolve_artist(artist)[2], 'ambiguous_name_requires_configured_id')
            fetch.assert_not_called()
            artist['bandsintownArtistId'] = '32942'
            self.assertEqual(collector.resolve_artist(artist)[2], 'configured_id_rejected')
            fetch.assert_not_called()
        for event_id in WRONG_ZEKE_IDS:
            self.assertTrue(rejected({'id': event_id}))
        self.assertTrue(rejected({'id': 'future-unrelated-show', 'bandsintownArtistId': '32942'}))
        self.assertFalse(rejected({'id': 'manual:flavor-fest-2026-friday-concerts', 'artists': ['ZEKE']}))
        self.assertFalse(rejected({'id': 'new-official-chh-show', 'artists': ['ZEKE']}))

    def test_name_collision_never_queries_generic_artist_search(self):
        artist = {'name':'Nehemiah', 'aliases':['Nehemiah','its_nehe02'], 'bandsintownRejectedArtistIds':['15347266']}
        with patch.object(collector,'get_json') as fetch:
            self.assertEqual(collector.resolve_artist(artist)[2], 'ambiguous_name_requires_configured_id')
            fetch.assert_not_called()
            artist['bandsintownArtistId']='15347266'
            self.assertEqual(collector.resolve_artist(artist)[2], 'configured_id_rejected')
            fetch.assert_not_called()
            artist['bandsintownArtistId']='99999'
            fetch.return_value=(200, {'name':'Nehemiah','id':'99999'})
            self.assertEqual(collector.resolve_artist(artist), ('99999','Nehemiah','configured_id'))

    def test_removal_is_provider_scoped_not_a_blanket_artist_ban(self):
        self.assertTrue(rejected({'id':'new-provider-show','bandsintownArtistId':'15347266'}))
        for event_id in WRONG_NEHEMIAH_IDS | {ADRENALINE_DUPLICATE}:
            self.assertTrue(rejected({'id':event_id}))
        self.assertFalse(rejected({'id':'manual:adrenaline-valrico-2026-10-17','artists':['Nehemiah']}))
        self.assertFalse(rejected({'id':'new-official-show','artists':['Nehemiah']}))

    def test_stale_refresh_is_cleaned_without_losing_history_or_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'config').mkdir()
            approved=json.loads((ROOT/'config/oct3-verified-concerts.json').read_text())
            (root/'config/oct3-verified-concerts.json').write_text(json.dumps(approved))
            saved=dict(approved[0],id='manual:'+approved[0]['id'],firstSeen='2026-10-02T12:00:00Z',status='cancelled')
            keep={'id':'adrenaline-valrico-2026-10-17','artists':['Nehemiah'],'firstSeen':'2026-10-01T00:00:00Z'}
            bad=[{'id':e,'artists':['Nehemiah']} for e in WRONG_NEHEMIAH_IDS | {ADRENALINE_DUPLICATE}]
            bad.extend({'id': e, 'artists': ['ZEKE']} for e in WRONG_ZEKE_IDS)
            bad.append({'id': 'future-unrelated-zeke-show', 'bandsintownArtistId': '32942'})
            paths=['events.json','supplemental-events.json','config/manual-events.json']
            for name in paths:(root/name).write_text(json.dumps([copy.deepcopy(saved),copy.deepcopy(keep),*bad]))
            (root/'event-history.json').write_text(json.dumps({'events':[{'event':e} for e in [saved,keep,*bad]]}))
            apply(root,today='2026-10-03')
            contents={name:(root/name).read_bytes() for name in paths+['event-history.json']}
            apply(root,today='2026-10-03')
            self.assertTrue(all((root/name).read_bytes()==value for name,value in contents.items()))
            events=json.loads((root/'events.json').read_text())
            show=next(e for e in events if e['id']==saved['id'])
            self.assertEqual(show['firstSeen'],saved['firstSeen'])
            self.assertEqual(show['status'],'cancelled')
            self.assertIn(keep,events)
            self.assertFalse(any(rejected(e) for e in events))
            history=json.loads((root/'event-history.json').read_text())['events']
            self.assertEqual(len(history),2)
            apply(root,today='2027-01-01')
            self.assertNotIn(saved['id'],[e['id'] for e in json.loads((root/'events.json').read_text())])
            self.assertEqual(len(json.loads((root/'event-history.json').read_text())['events']),2)

    def test_reapproved_rap_go_round_restores_current_billing_and_address(self):
        approved = json.loads((ROOT / 'config/oct3-verified-concerts.json').read_text())
        show = next(e for e in approved if e['id'] == 'rap-go-round-west-palm-beach-2026-11-20')
        event_id = 'manual:' + show['id']
        self.assertFalse(rejected({'id': event_id}))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'config').mkdir()
            (root / 'config/oct3-verified-concerts.json').write_text(json.dumps([show]))
            stale = dict(show, id=event_id, artists=['Naldo', 'DJ Eternitrock'],
                         advertisedBilling=['Naldo', 'DJ Eternitrock'], address='2470 Parker Avenue')
            for name in ['events.json', 'supplemental-events.json', 'config/manual-events.json']:
                (root / name).write_text(json.dumps([stale]))
            (root / 'event-history.json').write_text(json.dumps({'events': [{'event': stale}]}))
            apply(root, today='2026-10-24')
            rows = json.loads((root / 'events.json').read_text())
            self.assertEqual(len(rows), 1)
            for e in [rows[0], json.loads((root / 'event-history.json').read_text())['events'][0]['event']]:
                self.assertEqual(e['artists'], ['DJ Eternitrock'])
                self.assertEqual(e['advertisedBilling'], ['DJ Eternitrock'])
                self.assertEqual(e['address'], '2740 Parker Avenue')
                self.assertEqual(e['firstSeen'], '2026-10-12T19:39:04Z')
                self.assertEqual(e['startTime'], '21:00')
            self.assertEqual(json.loads((root / 'supplemental-events.json').read_text()), [])
