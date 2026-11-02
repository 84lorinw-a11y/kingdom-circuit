"""Exercise Canadian discovery and retention through the production refresh."""
import contextlib
import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import collect_bandsintown_rest as collector
import run_bandsintown_refresh as refresh
from build_seo_site import domestic_event, event_path, event_schema, merge_events

ARTIST = {"name": "Ant Lee", "enabled": True, "country": "CA",
          "bandsintownProfile": "https://www.bandsintown.com/a/15592988-ant-lee"}


def raw_event(event_id="new-ca", country="Canada", region="Ontario", **changes):
    return dict({"id": event_id, "datetime": "2099-11-13T19:00:00",
                 "url": f"https://www.bandsintown.com/e/{event_id}",
                 "title": "Light Up The City", "artist_id": "15592988",
                 "venue": {"name": "Bethel Church", "city": "Sarnia",
                           "region": region, "country": country,
                           "timezone": "America/Toronto"}, "offers": []}, **changes)


class BandsintownCanadaTests(unittest.TestCase):
    def run_refresh(self, raw, prior=(), primary=(), status=200, profile_status=200, wrapped=True):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, data in (("artists", [ARTIST]), ("events", list(primary)),
                               ("supplemental", list(prior)), ("status", {})):
                (root / f"{name}.json").write_text(json.dumps(data))
            def get_json(url):
                if "/events/" in url:
                    return status, raw
                return profile_status, {"id": "15592988", "name": "Ant Lee"}
            with patch.multiple(collector, ARTISTS_FILE=root/"artists.json",
                                EVENTS_FILE=root/"events.json", SUPPLEMENTAL_FILE=root/"supplemental.json",
                                STATUS_FILE=root/"status.json", CANDIDATES_FILE=root/"candidates.json"), \
                 patch.multiple(refresh, SUPPLEMENTAL=root/"supplemental.json", STATUS=root/"status.json"), \
                 patch.object(collector, "get_json", side_effect=get_json), \
                 patch.object(collector.time, "sleep"), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual((refresh.main if wrapped else collector.main)(), 0)
            return tuple(json.loads((root/f"{name}.json").read_text())
                         for name in ("supplemental", "status", "candidates"))

    def test_imports_canada_and_us_by_venue_not_artist_home_country(self):
        rows, status, holds = self.run_refresh([
            raw_event(), raw_event("california", "United States", "CA"),
            raw_event("uk", "United Kingdom", "England")])
        self.assertEqual({row["id"] for row in rows}, {"bandsintown:new-ca", "bandsintown:california"})
        ca = next(row for row in rows if row["country"] == "CA")
        self.assertEqual((ca["state"], ca["startTime"], ca["timezone"]), ("ON", "19:00", "America/Toronto"))
        self.assertTrue(domestic_event(ca))
        self.assertEqual(event_schema(ca)["startDate"], "2099-11-13T19:00:00-05:00")
        self.assertEqual(merge_events([], [ca]), [ca])
        self.assertEqual(status["rawUpcomingCARows"], 1)
        self.assertEqual(status["rawUpcomingUSRows"], 1)
        self.assertEqual(status["rawUpcomingRows"], 2)
        self.assertEqual(holds, [])

    def test_all_provinces_and_country_aliases_normalize(self):
        for country in ("Canada", "CA", "CAN", " canada "):
            for code, name in collector.CANADIAN_REGIONS.items():
                for region in (code, code.lower(), name):
                    with self.subTest(country=country, region=region):
                        row = collector.compact_event(raw_event(country=country, region=region), ARTIST, "Ant Lee", "configured_id")
                        self.assertEqual((row["country"], row["state"]), ("CA", code))
                        self.assertTrue(domestic_event(row))
        self.assertEqual(collector.region_code("Québec", "CA"), "QC")

    def test_source_offset_and_prior_verified_datetime_are_preserved(self):
        raw = raw_event(datetime="2099-11-13T19:00:00-07:00")
        raw["venue"].pop("timezone")
        prior, _, _ = self.run_refresh([raw])
        self.assertEqual(prior[0]["startDateTime"], "2099-11-13T19:00:00-07:00")
        raw["datetime"] = "2099-11-13T19:00:00"
        same, _, _ = self.run_refresh([raw], prior)
        self.assertEqual(same[0]["startDateTime"], prior[0]["startDateTime"])
        raw["datetime"] = "2099-11-13T20:00:00"
        changed, _, _ = self.run_refresh([raw], prior)
        self.assertNotIn("startDateTime", changed[0])

    def test_us_artist_canadian_shows_are_in_scope(self):
        with patch.dict(ARTIST, country="US"):
            rows, status, _ = self.run_refresh([raw_event()])
        self.assertEqual(rows[0]["country"], "CA")
        self.assertEqual(status["rawUpcomingCARows"], 1)

    def test_second_refresh_updates_without_duplicates_or_losing_artwork(self):
        first, _, _ = self.run_refresh([raw_event()])
        first[0].update(image="assets/events/selected.jpg", imageOverride=True,
                        endDate="2099-11-14", timezone="America/Toronto")
        raw = raw_event(datetime="2099-11-13T20:30:00")
        raw["venue"].pop("timezone")
        second, _, _ = self.run_refresh([raw], first)
        self.assertEqual(len(second), 1)
        self.assertEqual(second[0]["startTime"], "20:30")
        self.assertEqual(second[0]["endDate"], "2099-11-14")
        self.assertEqual(second[0]["timezone"], "America/Toronto")
        self.assertEqual(second[0]["image"], "assets/events/selected.jpg")
        self.assertEqual(event_path(first[0]), event_path(second[0]))
        moved, _, _ = self.run_refresh([raw_event(datetime="2099-12-01T20:30:00")], second)
        self.assertEqual(moved[0]["startDate"], "2099-12-01")
        self.assertNotIn("endDate", moved[0])

    def test_empty_failed_malformed_and_partial_responses_keep_canadian_rows(self):
        first, _, _ = self.run_refresh([raw_event("one"), raw_event("two", region="BC")])
        for response, status, profile in (([], 200, 200), (None, 503, 200),
                                           ({"error": "bad"}, 200, 200), ([], 200, 503)):
            with self.subTest(response=response, status=status, profile=profile):
                rows, summary, _ = self.run_refresh(response, first, status=status, profile_status=profile)
                self.assertEqual(rows, first)
                self.assertEqual(summary["preservedCanadianShows"], 2)
        rows, summary, _ = self.run_refresh([raw_event("one")], first)
        self.assertEqual({row["id"] for row in rows}, {row["id"] for row in first})
        self.assertEqual(summary["preservedCanadianShows"], 1)

    def test_official_and_cancelled_records_are_not_overwritten(self):
        first, _, _ = self.run_refresh([raw_event()])
        for extra in ({"authority": "official_event"}, {"status": "cancelled"}):
            original = dict(first[0], **extra)
            rows, _, _ = self.run_refresh([raw_event(datetime="2099-11-13T21:00:00")], [original])
            self.assertEqual(rows, [original])

    def test_known_official_multiday_appearance_is_not_duplicated(self):
        known = collector.compact_event(raw_event(), ARTIST, "Ant Lee", "configured_id")
        known.update(id="manual:approved", authority="official_event", endDate="2099-11-14")
        rows, _, _ = self.run_refresh([raw_event("next-day", datetime="2099-11-14T19:00:00")], [known])
        self.assertEqual(rows, [known])

    def test_same_city_and_venue_across_borders_or_provinces_do_not_dedupe(self):
        primary = collector.compact_event(raw_event("us", "US", "MI"), ARTIST, "Ant Lee", "configured_id")
        rows, _, _ = self.run_refresh([raw_event(), raw_event("other-province", region="BC")], primary=[primary])
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(merge_events([primary], rows)), 3)

    def test_canadian_conference_still_requires_lineup_review(self):
        rows, status, holds = self.run_refresh([raw_event(title="Youth Conference")])
        self.assertEqual(rows, [])
        self.assertEqual(status["festivalCandidatesHeld"], 1)
        self.assertEqual(holds[0]["country"], "CA")

    def test_browser_keeps_cross_border_and_different_province_shows_separate(self):
        app = (ROOT / "app.js").read_text()
        function = app[app.index("function sameEvent("):app.index("function eventSourcePriority(")]
        base = {"startDate": "2099-11-13", "artists": ["Ant Lee"], "city": "Windsor",
                "venue": "First Community Church", "country": "CA", "state": "ON"}
        cases = [[base, dict(base, country="US", state="CA")],
                 [base, dict(base, country="CANADA", state="NS")]]
        program = "const normalize = x => String(x || '').trim().toLowerCase();\n" + function
        program += "\nconsole.log(JSON.stringify(" + json.dumps(cases) + ".map(([a,b])=>sameEvent(a,b))));"
        self.assertEqual(json.loads(subprocess.check_output(["node", "-e", program], text=True)), [False, False])

    def test_invalid_province_does_not_publish_or_replace_prior_show(self):
        first, _, _ = self.run_refresh([raw_event()])
        rows, status, _ = self.run_refresh([raw_event(region="XX")], first)
        self.assertEqual(rows, first)
        self.assertEqual(status["requestErrors"], 1)


if __name__ == "__main__":
    unittest.main()
