import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from catalog_removals import apply, removed_event
from apply_sep26_requested_lineups import PATCHES, patch_event
from build_seo_site import billing_links, event_schema, hosts_line, merge_events


class September28CatalogTests(unittest.TestCase):
    def test_removal_covers_feeds_archive_and_old_unassociated_ids(self):
        retired = [dict(id="old", artists=["Jay Kalyl", "Other artist"]),
                   dict(id="manual:jay-kalyl-desde-antes-elizabeth-2026"),
                   dict(title="JAY KALYL live", artists=[])]
        kept = dict(id="keep", artists=["Jay-Way"], firstSeen="2026-08-01")
        self.assertTrue(all(removed_event(event) for event in retired))
        self.assertFalse(removed_event(kept))
        self.assertEqual(merge_events(retired + [kept], retired), [kept])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            for relative in ("events.json", "supplemental-events.json", "config/manual-events.json"):
                (root / relative).write_text(json.dumps(retired + [kept]))
            history = {"version": 1, "events": [{"event": e, "firstSeen": "2026-08-01"} for e in retired + [kept]]}
            (root / "event-history.json").write_text(json.dumps(history))
            apply(root)
            once = {p: p.read_text() for p in root.rglob("*.json")}
            apply(root)
            self.assertEqual(once, {p: p.read_text() for p in root.rglob("*.json")})
            self.assertEqual(json.loads((root / "events.json").read_text()), [kept])
            history["events"] = history["events"][-1:]
            self.assertEqual(json.loads((root / "event-history.json").read_text()), history)

    def test_oceanside_refresh_preserves_artwork_identity_and_discovery(self):
        event = dict(id="official:cd8c382d5cc4126a49a4", startDate="2026-10-03",
                     title="Old title", firstSeen="2026-08-15T11:53:29Z", image="approved-flyer.jpg",
                     artists=["1K Phew"], sources=[{"url": "https://original-calendar.example"}])
        before = copy.deepcopy(event)
        patch_event(event)
        for key in ("id", "firstSeen", "image", "artists"):
            self.assertEqual(event[key], before[key])
        self.assertEqual(event["title"], "Worship Night")
        self.assertEqual(event["startTime"], "17:00")
        self.assertEqual(event_schema(event)["startDate"], "2026-10-03T17:00:00-07:00")
        self.assertEqual(event["officialUrl"], event["ticketUrl"])
        once = copy.deepcopy(event)
        patch_event(event)
        self.assertEqual(event, once)

    def test_future_legacy_hosts_are_separate_and_unlisted_guests_stay_unlinked(self):
        event = PATCHES["future-legacy-hip-hop-showcase-nashville-2026"]
        artists = [{"name": "Trendsetter Sense", "aliases": ["DJ Trendsetter Sense"]}]
        billing = billing_links(event, artists)
        self.assertIn('href="/artists/trendsetter-sense/">DJ Trendsetter Sense</a>', billing)
        for name in ("ADIA", "JustCordell"):
            self.assertIn(f"<span>{name}</span>", billing)
        self.assertIn("Hosted by DJ Focus and Keal K", hosts_line(event))
        self.assertNotIn("DJ Focus", billing)
        self.assertEqual([p["name"] for p in event_schema(event)["performer"]], event["advertisedBilling"])
