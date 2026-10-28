"""Regression checks for U.S./Puerto Rico/Canada publishing and curated venue provenance."""
import json
import pathlib
import sys
import subprocess
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_seo_site import domestic_event, merge_events, state_path, city_path, event_schema


class GeographyAndVenueGuards(unittest.TestCase):
    def test_us_puerto_rico_and_canada_are_public(self):
        us = {"id": "test-us", "title": "US show", "startDate": "2027-01-01", "city": "Austin", "state": "TX", "country": "US", "artists": ["A"]}
        pr = {"id": "test-pr", "title": "PR show", "startDate": "2027-01-02", "city": "San Juan", "state": "PR", "country": "US", "artists": ["B"]}
        ca = {"id": "test-ca", "title": "Canada show", "startDate": "2027-01-03", "city": "Saskatoon", "state": "SK", "country": "CA", "artists": ["C"]}
        bad = {"id": "test-bad", "title": "Canada mislabeled", "startDate": "2027-01-04", "city": "Toronto", "state": "ON", "country": "US", "artists": ["D"]}
        self.assertTrue(domestic_event(us))
        self.assertTrue(domestic_event(pr))
        self.assertTrue(domestic_event(ca))
        self.assertFalse(domestic_event(bad))
        self.assertEqual({e["id"] for e in merge_events([us, ca], [pr, bad])}, {"test-us", "test-pr", "test-ca"})


    def test_country_and_region_must_agree(self):
        cases = [("US", "CA", True), ("CA", "SK", True), ("CANADA", "ON", True),
                 ("CAN", "BC", True), ("CA", "CA", False), ("US", "ON", False),
                 ("GB", "BC", False), ("US", "TX", True), ("PR", "PR", True)]
        for country, state, expected in cases:
            with self.subTest(country=country, state=state):
                self.assertEqual(domestic_event({"country": country, "state": state}), expected)
        js = (ROOT / "app.js").read_text()
        names = re.search(r"const STATE_NAMES = .*?;", js)[0]
        guard = js[js.index("function isDomesticEvent(event)"):js.index("function mergeEventLists(")]
        setup = "\n".join(re.findall(r"const (?:CANADIAN_REGIONS|CANADIAN_CODES) = .*?;", js))
        program = names + "\n" + setup + "\n" + guard + "\nconsole.log(JSON.stringify(" + json.dumps(cases) + ".map(([country,state])=>isDomesticEvent({country,state}))));"
        actual = json.loads(subprocess.check_output(["node", "-e", program], text=True))
        self.assertEqual(actual, [True, True, True, True, False, False, False, True, True])

    def test_canadian_urls_remain_stable_and_schema_keeps_local_time(self):
        self.assertEqual(state_path("SK"), "/shows/sk/")
        self.assertEqual(state_path("ON"), "/shows/on/")
        self.assertEqual(city_path("Saskatoon", "SK"), "/shows/saskatoon-sk/")
        event = next(e for e in json.loads((ROOT / "supplemental-events.json").read_text())
                     if e.get("id") == "submitted:jj-stone-nrg-saskatoon-2026-11-13")
        self.assertIn(event["id"], [e["id"] for e in merge_events([], [event])])
        schema = event_schema(event)
        self.assertEqual(schema["startDate"], "2026-11-13T21:00:00-06:00")
        self.assertEqual(schema["location"]["address"]["addressCountry"], "CA")
        self.assertEqual([x["name"] for x in schema["performer"]], ["JJ Stone", "Alibii", "Heaven Lee"])

    def test_browser_calendar_uses_same_guard(self):
        js = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn("function isDomesticEvent(event)", js)
        self.assertIn("if (!isDomesticEvent(raw)) return;", js)
        self.assertIn('PR:"Puerto Rico"', js)

    def test_808_beezy_venues_and_original_first_seen(self):
        events = json.loads((ROOT / "events.json").read_text(encoding="utf-8"))
        supplemental = json.loads((ROOT / "supplemental-events.json").read_text(encoding="utf-8"))
        seeds = json.loads((ROOT / "config/artist-website-seed-events.json").read_text(encoding="utf-8"))
        private = json.loads((ROOT / "config/private-events.json").read_text())
        for num, venue in {"108856031": "Indiana Tech", "108856562": "North Canton Chapel", "108856576": "North Canton Chapel"}.items():
            with self.subTest(num=num):
                if num in {'108856562', '108856576'}:
                    retained = next(e for e in private if e['id'] == f'manual:808-beezy-bandsintown-{num}')
                    self.assertEqual(retained['venue'], venue)
                    self.assertEqual(retained['firstSeen'], '2026-09-02T14:46:37Z')
                    self.assertEqual(retained['status'], 'private')
                    for rows in (events, supplemental):
                        published = [e for e in rows if e.get('id') == retained['id']]
                        self.assertEqual(len(published), 1)
                        self.assertEqual(published[0]['status'], 'private')
                        self.assertEqual(published[0]['firstSeen'], retained['firstSeen'])
                    continue
                published = next(e for e in events if e.get("id") == f"manual:808-beezy-bandsintown-{num}")
                source = next(e for e in supplemental if e.get("id") == f"manual:808-beezy-bandsintown-{num}")
                seed = next(e for e in seeds if e.get("id") == f"808-beezy-bandsintown-{num}")
                self.assertEqual((published["venue"], source["venue"], seed["venue"]), (venue, venue, venue))
                self.assertEqual(published["firstSeen"], "2026-09-02T14:46:37Z")
                self.assertEqual(source["firstSeen"], "2026-09-02T14:46:37Z")


if __name__ == "__main__":
    unittest.main()
