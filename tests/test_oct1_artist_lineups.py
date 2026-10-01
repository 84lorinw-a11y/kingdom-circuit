"""Protect reviewed co-billing from the daily collector and older seed writers."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from apply_sep26_requested_lineups import PATCHES, patch_event
from collect_bandsintown_rest import existing_duplicate
from run_bandsintown_refresh import is_refreshable_bit
from apply_sep11_catalog_audit import NEW_EVENTS


class ReviewedArtistLineupTests(unittest.TestCase):
    def test_sazon_survives_refresh_and_matches_both_artist_calendars(self):
        reviewed = dict(id='bandsintown:108902772', startDate='2026-10-17',
                        firstSeen='2026-09-01', image='approved-flyer.jpg')
        patch_event(reviewed)
        self.assertFalse(is_refreshable_bit(reviewed))
        self.assertEqual(reviewed['firstSeen'], '2026-09-01')
        self.assertEqual(reviewed['image'], 'approved-flyer.jpg')
        for name, provider_id in [('GIOVANI', '108646722'), ('Issac Mansfield', '108902772')]:
            candidate = dict(trackedArtist=name, bandsintownEventId=provider_id,
                             startDate='2026-10-17', startTime='06:00',
                             city='Lakeland Estates Mobile Home Community',
                             venue='1329 E Main St')
            self.assertTrue(existing_duplicate(candidate, [reviewed]))
            candidate.update(startDate='2026-11-17', bandsintownEventId='different-show',
                             city='Orlando', venue='Another venue')
            self.assertFalse(existing_duplicate(candidate, [reviewed]))

    def test_old_seed_keeps_latest_future_legacy_billing(self):
        key = 'future-legacy-hip-hop-showcase-nashville-2026'
        seed = next(row for event_id, row in NEW_EVENTS if event_id == key)
        for field in ('artists', 'advertisedBilling', 'officialBill', 'hosts'):
            self.assertEqual(seed[field], PATCHES[key][field])
        row = copy.deepcopy(seed)
        row['id'] = key
        self.assertTrue(patch_event(row))
        self.assertEqual(row['advertisedBilling'].count('Tommy Zuko'), 1)
        self.assertEqual(row['advertisedBilling'].count('CeJae'), 1)


if __name__ == '__main__':
    unittest.main()
