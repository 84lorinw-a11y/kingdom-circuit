import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

EXPECTED = {
    "CJ Emulous": {
        "rosterOrder": 145,
        "website": "https://www.cjemulous.com/",
        "instagramProfile": "https://www.instagram.com/cjemulous",
        "spotifyProfile": "https://open.spotify.com/artist/5Jgv9sRXt4V3TwSU1H41eQ",
        "youtubeProfile": "https://www.youtube.com/user/HisImageM",
        "officialImageSource": "https://www.cjemulous.com/",
        "imageUrl": "https://static.wixstatic.com/media/9c331a_5c82923764b24c52bb151559692af340~mv2.jpeg",
    },
    "NXTMIKE": {
        "rosterOrder": 146,
        "website": "https://www.nxtmike.com/",
        "instagramProfile": "https://www.instagram.com/NXTMIKE_",
        "spotifyProfile": "https://open.spotify.com/artist/2yMOYu5UEVMeoZmBczRR5g",
        "youtubeProfile": "https://www.youtube.com/NXTMIKE",
        "officialImageSource": "https://www.nxtmike.com/",
        "imageUrl": "https://images.squarespace-cdn.com/content/v1/6003aea016cd050c913c5549/1618423643863-7SFKRAEQNVYLINRNLL5B/IMG-8256.jpg?format=1500w",
    },
    "CHVRCH562": {
        "rosterOrder": 147,
        "website": "https://www.instagram.com/chvrch562/",
        "instagramProfile": "https://www.instagram.com/chvrch562/",
        "spotifyProfile": "https://open.spotify.com/artist/5kQpwGLE4RmDMsIPqJ4Y5i",
        "youtubeProfile": "https://www.youtube.com/channel/UCpOq5kyjcag3fOkfOjG8qxw",
        "officialImageSource": "https://www.instagram.com/chvrch562/",
        "imageUrl": "https://open.voidware.de/artist/5kQpwGLE4RmDMsIPqJ4Y5i",
    },
    "Mission": {
        "rosterOrder": 148,
        "website": "https://www.instagram.com/missionismusic/?hl=en",
        "instagramProfile": "https://www.instagram.com/missionismusic/?hl=en",
        "spotifyProfile": "https://open.spotify.com/artist/02gxa3HE5O0zBKRjeDh6Ba",
        "youtubeProfile": "https://www.youtube.com/channel/UCBaU_Xh4fyokc-ckyCeYv3w",
        "officialImageSource": "https://www.instagram.com/missionismusic/?hl=en",
        "imageUrl": "https://i.scdn.co/image/ab6761610000e5ebe70afe5f418013a0c86ddbb6",
    },
    "BigBreeze": {
        "rosterOrder": 149,
        "website": "https://mokbpresents.com/artist/bigbreeze/",
        "instagramProfile": "https://www.instagram.com/_markelofficial/",
        "spotifyProfile": "https://open.spotify.com/artist/7wrWSJHfACjw7s7gYXOXTt",
        "youtubeProfile": "https://www.youtube.com/@TheOfficialMarkel",
        "officialImageSource": "https://open.spotify.com/artist/7wrWSJHfACjw7s7gYXOXTt",
        "imageUrl": "https://i.scdn.co/image/ab6761610000e5eb3bec4aaaca84d070b7383e2a",
    },
}


class ArtistDatabaseSeptember22Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artists = json.loads(
            (ROOT / "config" / "artists.json").read_text(encoding="utf-8")
        )
        cls.updates = json.loads(
            (ROOT / "config" / "verified-artist-registry-updates.json").read_text(
                encoding="utf-8"
            )
        )
        cls.image_overrides = json.loads(
            (ROOT / "config" / "verified-artist-image-overrides.json").read_text(
                encoding="utf-8"
            )
        )

    def test_sheet_rows_145_through_149_are_exact(self):
        updates = {item["name"]: item for item in self.updates}
        for name, expected in EXPECTED.items():
            with self.subTest(name=name):
                self.assertIn(name, updates)
                for field, value in expected.items():
                    self.assertEqual(value, updates[name].get(field), field)

    def test_live_roster_has_verified_profiles_and_pinned_images(self):
        artists = {item["name"]: item for item in self.artists}
        for name, expected in EXPECTED.items():
            with self.subTest(name=name):
                self.assertIn(name, artists)
                artist = artists[name]
                self.assertTrue(artist.get("sourceRegistryVerified"))
                self.assertEqual(expected["rosterOrder"], artist.get("rosterOrder"))
                for field in (
                    "website",
                    "instagramProfile",
                    "spotifyProfile",
                    "youtubeProfile",
                    "officialImageSource",
                    "imageUrl",
                ):
                    self.assertEqual(expected[field], artist.get(field), field)
                self.assertEqual(expected["imageUrl"], self.image_overrides.get(name))

    def test_new_artists_are_in_the_public_roster_javascript(self):
        app = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn('"NXTMIKE"', app)
        self.assertIn('"CHVRCH562"', app)
        self.assertIn('"nxtmike": {', app)
        self.assertIn('"chvrch562": {', app)


if __name__ == "__main__":
    unittest.main()
