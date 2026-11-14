"""Provider recommendations must supply actual performer identity evidence."""
import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import collect_bandsintown_rest as bit
import collect_artist_website_events as websites
import scan_all_artist_sources_legacy as expanded
import sync_verified_artist_registry as registry
import update_events as events

CHECKED = "2026-11-14T12:30:25Z"
ARTIST = {"name": "MAYIA", "aliases": ["MAYIA", "Mayia"]}
ALIASES = expanded.build_alias_lookup([ARTIST, {"name": "Hulvey"}])
FIXTURES = json.loads((ROOT / "tests/fixtures/songkick-unrelated-performers.json").read_text())


def html(event):
    return '<script type="application/ld+json">' + json.dumps(event) + '</script>'


class ProviderPerformerTests(unittest.TestCase):
    def collect(self, event, require=False):
        source = expanded.source_record("MAYIA calendar", "https://example.com/artist", "MAYIA")
        source["requirePerformerMatch"] = require
        return events.collect_jsonld_source_from_html(source, FIXTURES[0]["sourceUrl"], html(event), ALIASES, CHECKED)

    def test_all_nine_failed_run_ids_match_exact_sources_and_cannot_be_assigned_to_mayia(self):
        for fixture in FIXTURES:
            with self.subTest(url=fixture["sourceUrl"]):
                raw = fixture["event"]
                location = raw["location"]
                address = location["address"]
                identifier = events.event_hash([fixture["sourceUrl"], raw["name"], raw["startDate"][:10],
                                                location["name"], address["addressLocality"], address["addressRegion"]])
                self.assertEqual(fixture["failedRunId"], "official:" + identifier)
                self.assertEqual(self.collect(raw), [])

    def test_recommendation_with_other_tracked_artist_or_missing_performer_is_rejected(self):
        for performer in ([{"name": "Hulvey"}], []):
            raw = dict(FIXTURES[0]["event"], performer=performer)
            self.assertEqual(self.collect(raw, require=True), [])

    def test_explicit_conflicting_performer_cannot_be_overridden_by_title(self):
        raw = dict(FIXTURES[0]["event"], name="MAYIA special concert")
        self.assertEqual(self.collect(raw), [])

    def test_matching_headliner_or_support_is_accepted_and_order_is_preserved(self):
        for names in (["MAYIA", "Hulvey"], ["Hulvey", "Mayia"]):
            raw = dict(FIXTURES[0]["event"], performer=[{"name": name} for name in names])
            rows = self.collect(raw, require=True)
            self.assertEqual(len(rows), 1)
            expected = ["MAYIA" if name == "Mayia" else name for name in names]
            self.assertEqual(rows[0]["artists"], expected)
            self.assertEqual(rows[0]["headliner"], expected[0])

    def test_festival_never_inherits_artist_without_matching_lineup(self):
        for performer in ([], [{"name": "Unrelated Artist"}]):
            raw = dict(FIXTURES[0]["event"], name="Summer Music Festival", performer=performer)
            self.assertEqual(self.collect(raw), [])
        raw["performer"] = [{"name": "Mayia"}]
        self.assertEqual(self.collect(raw, require=True)[0]["artists"], ["MAYIA"])

    def test_dedicated_calendar_without_lineup_keeps_existing_fallback(self):
        raw = dict(FIXTURES[0]["event"], name="Night of Hope", performer=[])
        self.assertEqual(self.collect(raw)[0]["artists"], ["MAYIA"])

    def test_songkick_recommendation_links_require_actual_target_performer(self):
        artist_url = "https://www.songkick.com/artists/8204298-mayia"
        search_url = "https://www.songkick.com/search?query=MAYIA&type=artists"
        valid_url = "https://www.songkick.com/concerts/99999999-confirmed-mayia-show"
        links = ''.join('<a href="' + row["sourceUrl"] + '">Recommended</a>' for row in FIXTURES)
        pages = {search_url: '<a href="' + artist_url + '">MAYIA</a>',
                 artist_url: '<h1>Mayia</h1>' + links + '<a href="' + valid_url + '">Confirmed show</a>',
                 valid_url: html(dict(FIXTURES[0]["event"], name="Night of Hope", performer=[{"name": "Mayia"}]))}
        pages.update({row["sourceUrl"]: html(row["event"]) for row in FIXTURES})
        class Client:
            def get_text(self, url):
                return pages[url]
        with patch.object(expanded, "robots_allows", return_value=True):
            rows, status = expanded.collect_songkick_for_artist(ARTIST, Client(), ALIASES, CHECKED)
        self.assertEqual([row["title"] for row in rows], ["Night of Hope"])
        self.assertEqual(status["eventsFound"], 1)

    def test_bandsintown_hidden_links_and_public_cards_require_target_performer(self):
        profile_url = "https://www.bandsintown.com/a/123-mayia"
        detail_url = "https://www.bandsintown.com/e/456"
        link = '<a href="' + detail_url + '">Recommended show</a>'
        public_html = '<h2>All Concerts and Live Streams</h2>' + link + '<h2>Past Shows</h2>'
        source = websites.website_source(ARTIST, profile_url, "official Bandsintown calendar")
        for collect, profile_html in ((websites.collect_bandsintown_profile, link),
                                      (events.collect_bandsintown_public_source, public_html)):
            for names in ([], ["Maelo Ruiz"], ["Hulvey"], ["Hulvey", "Mayia"]):
                with self.subTest(collector=collect.__name__, performers=names):
                    raw = dict(FIXTURES[0]["event"], performer=[{"name": name} for name in names])
                    requested = []
                    class Client:
                        def get_text(self, url):
                            requested.append(url)
                            return html(raw)
                    with patch.object(websites, "robots_allows", return_value=True), \
                         patch.object(events, "robots_allows", return_value=True):
                        rows = collect(source, profile_url, profile_html, Client(), ALIASES, CHECKED)
                    self.assertEqual(requested, [detail_url])
                    if "Mayia" in names:
                        self.assertEqual(rows[0]["artists"], ["Hulvey", "MAYIA"])
                        self.assertEqual(rows[0]["headliner"], "Hulvey")
                    else:
                        self.assertEqual(rows, [])
        self.assertNotIn("requirePerformerMatch", source)


class BandsintownIdentityHoldTests(unittest.TestCase):
    def milla(self):
        return next(row for row in json.loads((ROOT / "config/artists.json").read_text()) if row["name"] == "Milla")

    def test_documented_milla_hold_blocks_name_or_stale_id_resolution(self):
        artist = self.milla()
        self.assertTrue(artist["bandsintownIdentityHold"])
        for override in ({}, {"bandsintownArtistId": "15583088"}):
            with patch.object(bit, "get_json") as request:
                self.assertEqual(bit.resolve_artist(dict(artist, **override)), ("", "", "provider_identity_review_required"))
                request.assert_not_called()

    def test_legacy_search_and_linked_provider_profiles_cannot_bypass_hold(self):
        artist = self.milla()
        class Client:
            def get_text(self, url):
                raise AssertionError("Held provider identity must not be requested")
        with patch.object(expanded, "robots_allows") as robots:
            rows, status = expanded.collect_bandsintown_for_artist(artist, Client(), {}, CHECKED)
        robots.assert_not_called()
        self.assertEqual(rows, [])
        self.assertEqual(status["status"], "identity_mismatch")
        self.assertEqual(status["reason"], "provider_identity_review_required")
        profile = "https://www.bandsintown.com/a/15583088-milla"
        artist["bandsintownProfile"] = profile
        self.assertEqual(websites.bandsintown_profiles(artist, '<a href="' + profile + '">Shows</a>', artist["website"]), [])
        self.assertEqual(websites.eligible_website(artist), artist["website"])

    def test_hold_is_reported_without_publishing_and_official_booking_is_preserved(self):
        official = {"id": "manual:milla-confirmed", "artists": ["Milla"], "title": "Confirmed booking",
                    "authority": "official_event", "startDate": "2099-11-20"}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, data in (("artists", [self.milla()]), ("events", []), ("supplemental", [official])):
                (root / (name + ".json")).write_text(json.dumps(data))
            with patch.multiple(bit, ARTISTS_FILE=root/"artists.json", EVENTS_FILE=root/"events.json",
                                SUPPLEMENTAL_FILE=root/"supplemental.json", STATUS_FILE=root/"status.json",
                                CANDIDATES_FILE=root/"candidates.json"), patch.object(bit, "get_json") as request, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(bit.main(), 0)
                request.assert_not_called()
            self.assertEqual(json.loads((root/"supplemental.json").read_text()), [official])
            status = json.loads((root/"status.json").read_text())
            self.assertEqual(status["requestErrors"], 0)
            self.assertEqual(status["artistsHeldForIdentity"], 1)
            self.assertEqual(status["identityHolds"], [{"artist": "Milla", "status": "held", "reason": "provider_identity_review_required"}])

    def test_registry_sync_restores_hold_without_changing_verified_artist_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artists = json.loads((ROOT/"config/artists.json").read_text())
            before = deepcopy(next(row for row in artists if row["name"] == "Milla"))
            next(row for row in artists if row["name"] == "Milla").pop("bandsintownIdentityHold")
            (root/"artists.json").write_text(json.dumps(artists))
            (root/"updates.json").write_bytes((ROOT/"config/verified-artist-registry-updates.json").read_bytes())
            with patch.multiple(registry, ARTISTS_FILE=root/"artists.json", UPDATES_FILE=root/"updates.json"), \
                 patch.object(registry, "apply_owner_roster"), patch.object(registry, "load_portraits", return_value={}), \
                 patch.object(registry, "apply_to_records", return_value=0):
                synced, _, _ = registry.sync_config()
            after = next(row for row in synced if row["name"] == "Milla")
            self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
