import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from owner_roster import order_records, filter_events, filter_source_records, verify_records, snapshot, removed_names
from verify_owner_roster import verify
from sync_verified_artist_registry import registry_payload


class OwnerRosterTests(unittest.TestCase):
    def test_reviewed_roster_socials_and_portraits_are_complete(self):
        reviewed = snapshot()
        self.assertEqual(verify(), {
            "artists": len(reviewed),
            "verified": sum(row["verified"] for row in reviewed),
            "removed": len(removed_names()),
        })

    def test_stale_writer_cannot_restore_deleted_artists(self):
        artists = json.loads((ROOT / "config/artists.json").read_text())
        stale = copy.deepcopy(artists) + [{"name": name} for name in removed_names()]
        self.assertEqual(order_records(stale), artists)
        with self.assertRaises(ValueError):
            verify_records(stale)

    def test_deleted_only_show_removed_but_mixed_festival_bill_preserved(self):
        removed = {"artists": ["MC Jin"], "headliner": "MC Jin"}
        mixed = {"artists": ["Hollyn", "Lecrae"], "officialBill": ["Hollyn", "Lecrae"]}
        self.assertEqual(filter_events([removed, mixed]), [mixed])
        self.assertEqual(mixed["officialBill"], ["Hollyn", "Lecrae"])

    def test_shared_calendars_survive_dedicated_source_removal(self):
        shared = {"name": "Reach Records"}
        deleted = {"artist": "Alexxander"}
        kept = {"artist": "Lecrae"}
        self.assertEqual(filter_source_records([shared, deleted, kept]), [shared, kept])

    def test_owner_reapproved_madiel_booking_does_not_restore_artist_or_other_shows(self):
        event = next(e for e in json.loads((ROOT / "config/oct3-verified-concerts.json").read_text())
                     if e['id'] == 'madiel-lara-columbus-2026-12-12')
        self.assertEqual(filter_events([event, dict(event, id='manual:' + event['id'])]),
                         [event, dict(event, id='manual:' + event['id'])])
        for update in ({'id': 'another-madiel-show'}, {'startDate': '2026-12-13'},
                       {'city': 'Cleveland'}, {'state': 'PA'}, {'country': 'CA'},
                       {'officialUrl': 'https://boletos.com/another-show/90705/'}):
            with self.subTest(update=update):
                self.assertEqual(filter_events([dict(event, **update)]), [])
        self.assertIn('Madiel Lara', removed_names())
        self.assertNotIn('madiel lara', {a['name'].casefold() for a in snapshot()})
        self.assertEqual(filter_source_records([{'artist': 'Madiel Lara'}]), [])

    def test_blank_reviewed_social_does_not_fall_back_to_an_old_runtime_link(self):
        payload = registry_payload({"name": "Selah the Corner", "youtubeProfile": ""})
        self.assertEqual({"youtubeProfile": "old-wrong-link", **payload}["youtubeProfile"], "")


if __name__ == "__main__":
    unittest.main()
