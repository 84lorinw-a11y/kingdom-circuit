import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import apply_verified_show_artwork as artwork


class VerifiedShowArtworkTests(unittest.TestCase):
    def test_refresh_restores_artwork_without_changing_event_identity_or_details(self):
        for pin in artwork.PINS:
            with self.subTest(event=pin["id"]):
                event = {"id": "manual:" + pin["id"], "startDate": pin["startDate"],
                         "startTime": "19:30", "venue": "Approved venue", "city": "Approved city",
                         "firstSeen": "2026-08-01", "artists": ["Existing curated artist"],
                         "image": "https://example.com/stale-artist.jpg", "imageType": "artist"}
                before = copy.deepcopy(event)
                self.assertTrue(artwork.patch_event(event))
                for key in ("id", "startDate", "startTime", "venue", "city", "firstSeen", "artists"):
                    self.assertEqual(event[key], before[key])
                self.assertEqual(event["image"], pin["image"])
                self.assertTrue((artwork.ROOT / pin["image"]).is_file())
                once = copy.deepcopy(event)
                artwork.patch_event(event)
                self.assertEqual(event, once)

    def test_date_change_and_unrelated_show_do_not_borrow_a_poster(self):
        for event in ({"id": artwork.PINS[0]["id"], "startDate": "2027-09-26"},
                      {"id": "unrelated-event", "startDate": "2026-10-03"}):
            before = copy.deepcopy(event)
            self.assertFalse(artwork.patch_event(event))
            self.assertEqual(event, before)

    def test_ticket_sources_survive_refresh_without_losing_calendar_evidence(self):
        for event_id, provider in (("bandsintown:108945796", "eventbrite.com"),
                                   ("bandsintown:108144023", "ticketmaster.com"),
                                   ("bandsintown:108144061", "ticketmaster.com")):
            pin = artwork.BY_ID[event_id]
            old_source = {"name": "Bandsintown", "url": "https://www.bandsintown.com/e/original"}
            event = {"id": event_id, "startDate": pin["startDate"], "sources": [old_source],
                     "officialUrl": old_source["url"], "ticketUrl": old_source["url"],
                     "firstSeen": "2026-08-01"}
            artwork.patch_event(event)
            artwork.patch_event(event)
            self.assertIn(provider, event["officialUrl"])
            self.assertEqual(event["ticketUrl"], event["officialUrl"])
            self.assertEqual(event["sources"], [event["sources"][0], old_source])
            self.assertEqual(event["sources"][0]["url"], pin["officialUrl"])
            self.assertEqual(event["firstSeen"], "2026-08-01")

    def test_saved_by_grace_lists_all_five_without_creating_artist_profiles(self):
        pin = artwork.BY_ID["supplemental:issac-mansfield-saved-by-grace-2026"]
        self.assertEqual(pin["advertisedBilling"],
                         ["Issac Mansfield", "Josh Morgan", "DJ Cam", "Lev Nova", "Junado"])
        self.assertEqual(pin["officialBill"], pin["advertisedBilling"])
        self.assertNotIn("artists", pin)

    def test_same_title_tour_stops_keep_their_own_artwork(self):
        from finalize_sep12_complete_closeout import apply_artwork_replacements, event_path
        from pin_verified_event_artwork import patch_event_detail
        rows = [dict(id="manual:jay-kalyl-desde-antes-elizabeth-2026", title="Jay Kalyl — Desde Antes Tour",
                     startDate="2026-10-02", city="Elizabeth", image="/october-2.jpg"),
                dict(id="manual:jay-kalyl-desde-antes-rockville-centre-2026", title="Jay Kalyl — Desde Antes Tour",
                     startDate="2026-10-03", city="Rockville Centre", image="/old-photo.jpg")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "events.json").write_text(json.dumps(rows))
            (root / "supplemental-events.json").write_text("[]")
            for row in rows:
                page = root / event_path(row) / "index.html"
                page.parent.mkdir(parents=True)
                detail = f'<h1>{row["title"]}</h1><div class="event-detail-media"><img src="{row["image"]}"></div>'
                page.write_text(patch_event_detail(detail, row["startDate"])[0])
            apply_artwork_replacements(root, rows)
            earlier = (root / event_path(rows[0]) / "index.html").read_text()
            later = (root / event_path(rows[1]) / "index.html").read_text()
            self.assertIn("/october-2.jpg", earlier)
            self.assertIn("jay-kalyl-desde-antes-tour-2026.png", later)


if __name__ == "__main__":
    unittest.main()
