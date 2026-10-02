import json
import unittest
from pathlib import Path

from scripts.apply_sep22_artist_registry_batch import ROWS


ROOT = Path(__file__).resolve().parents[1]
PROFILE_FIELDS = (
    "aliases",
    "website",
    "instagramProfile",
    "spotifyProfile",
    "youtubeProfile",
    "officialImageSource",
    "imageUrl",
    "imagePosition",
)

VERIFIED_WEBSITE_ARTISTS = {
    "C4 Crotona",
    "Nathan Davis Jr.",
    "Monster Tarver",
    "Brinson",
    "Alex Zurdo",
    "Red Tips",
    "Ty Brasel",
}


class ArtistDatabaseSeptember22BatchTwoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Preserve the exact approved source identity while serving its saved
        # local copy. Socials and source roster positions remain unchanged.
        cls.portraits = json.loads((ROOT / "config/artist-portraits.json").read_text())
        cls.expected = {row["name"]: dict(row, imageUrl=cls.portraits[row["name"]]["asset"])
                        for row in ROWS}
        cls.updates = json.loads(
            (ROOT / "config" / "verified-artist-registry-updates.json").read_text(
                encoding="utf-8"
            )
        )
        cls.artists = json.loads(
            (ROOT / "config" / "artists.json").read_text(encoding="utf-8")
        )
        cls.image_overrides = json.loads(
            (ROOT / "config" / "verified-artist-image-overrides.json").read_text(
                encoding="utf-8"
            )
        )

    def test_sheet_rows_preserve_source_order_except_owner_removed_jay_kalyl(self):
        batch = [row for row in self.updates if 150 <= int(row["rosterOrder"]) <= 176]
        self.assertEqual([row["rosterOrder"] for row in batch], [n for n in range(150, 177) if n != 158])
        self.assertEqual([row["name"] for row in batch], [row["name"] for row in ROWS])
        for row in batch:
            expected = self.expected[row["name"]]
            with self.subTest(name=row["name"]):
                for field, value in expected.items():
                    self.assertEqual(value, row.get(field), field)

    def test_live_roster_has_verified_socials_and_pinned_portraits(self):
        artists = {row["name"]: row for row in self.artists}
        for name, expected in self.expected.items():
            with self.subTest(name=name):
                artist = artists[name]
                self.assertTrue(artist.get("sourceRegistryVerified"))
                # Public positions close the gap left by the removed artist;
                # sourceRegistryRosterOrder retains the reviewed source number.
                position = expected["rosterOrder"] - (expected["rosterOrder"] > 158)
                self.assertEqual(position, artist["rosterOrder"])
                self.assertEqual(
                    expected["rosterOrder"], artist["sourceRegistryRosterOrder"]
                )
                for field in PROFILE_FIELDS:
                    self.assertEqual(expected[field], artist.get(field), field)
                self.assertEqual(expected["imageUrl"], self.image_overrides[name])
                self.assertRegex(
                    self.portraits[name]["previousSource"],
                    r"^https://image-cdn-(?:ak|fa)\.spotifycdn\.com/image/",
                )
                self.assertIn("ab6761610000e5eb", self.portraits[name]["previousSource"])
                self.assertTrue((ROOT / expected["imageUrl"]).is_file())
                if name in VERIFIED_WEBSITE_ARTISTS:
                    self.assertTrue(artist.get("websiteRegistryVerified"))

    def test_app_contains_the_second_verified_sheet_batch(self):
        app = (ROOT / "app.js").read_text(encoding="utf-8")
        for name in self.expected:
            with self.subTest(name=name):
                self.assertIn(json.dumps(name), app)
                self.assertIn(json.dumps(name.casefold()), app)

    def test_show_audit_repairs_are_durable(self):
        for relative_path in ("config/manual-events.json", "supplemental-events.json"):
            events = json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
            by_id = {event["id"]: event for event in events}

            mayia = by_id["mayia-songs-that-speak-conference-pleasant-garden-2026"]
            self.assertEqual("2026-10-23", mayia["startDate"])
            self.assertEqual("16:00", mayia["startTime"])
            self.assertEqual("New Covenant Church", mayia["venue"])
            self.assertEqual("Pleasant Garden", mayia["city"])
            self.assertEqual(["MAYIA"], mayia["artists"])
            self.assertEqual("https://mayiawarren.org/home", mayia["officialUrl"])

            ty_brasel = by_id["ty-brasel-outlandish-fest-fort-worth-2026"]
            self.assertEqual("2026-11-14", ty_brasel["startDate"])
            self.assertEqual("18:00", ty_brasel["startTime"])
            self.assertEqual("The Rail", ty_brasel["venue"])
            self.assertEqual("Fort Worth", ty_brasel["city"])
            self.assertEqual(["Ty Brasel"], ty_brasel["artists"])
            self.assertEqual(
                "assets/events/outlandish-fest-2026-lineup.png", ty_brasel["image"]
            )
            self.assertTrue(ty_brasel["imageOverride"])
            self.assertEqual(
                "https://www.outlandishlive.org/event-details/outlandish-fest-2026",
                ty_brasel["officialUrl"],
            )

            turlock = by_id["cj-emulous-turlock-back-to-school-2026"]
            self.assertIn("MikeySoChristian", turlock["artists"])
            self.assertIn("MikeySoChristian", turlock["officialBill"])


if __name__ == "__main__":
    unittest.main()
