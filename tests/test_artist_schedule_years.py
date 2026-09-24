from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import finalize_artist_schedule_years as years


class ArtistScheduleYearTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.today = dt.date(2026, 9, 24)

    def event(self, slug, start, end=None):
        page = self.root / "event" / slug / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        schema = {"@type": "MusicEvent", "startDate": start, "endDate": end or start}
        page.write_text('<script type="application/ld+json">' + json.dumps(schema) + '</script>')
        return f'/event/{slug}/'

    def profile(self, dates, name="DEON"):
        rows = []
        for i, date in enumerate(dates):
            href = self.event(str(i), date)
            rows.append(f'<a class="kc-rd-show-row" href="{href}" aria-label="{date}, Tyler, TX"><span class="kc-rd-show-date"><span>APR</span><strong>24</strong></span><span class="kc-rd-show-place">Tyler, TX</span></a>')
        next_show = '<a class="kc-rd-next kc-rd-next-show" href="/event/0/"><span class="kc-rd-next-kicker">Next show · APR 24</span><span>Venue · 7 PM</span></a>' if dates else ''
        return f'''<html><head><title>{name} Concerts &amp; Tour Dates 2026 | Kingdom Circuit</title>
<meta property="og:title" content="Old title"><meta name="twitter:title" content="Old title">
<link rel="canonical" href="https://kingdomcircuit.com/artists/deon/"></head>
<body><article data-kc-rd-artist-profile><h1 id="kc-rd-artist-name">{name}</h1>
{next_show}{''.join(rows)}<section data-past-shows-archive>Past shows: 2025, 2024</section></article></body></html>'''

    def patch(self, document, today=None):
        return years.patch_profile(document, self.root, today or self.today)

    def test_current_year_only_keeps_2026_title_without_extra_date_year(self):
        result = self.patch(self.profile(["2026-11-14"]))
        self.assertIn("DEON Concerts &amp; Tour Dates 2026 | Kingdom Circuit", result)
        self.assertNotIn('class="kc-rd-show-year"', result)

    def test_next_year_only_updates_all_titles_and_both_visible_dates(self):
        original = self.profile(["2027-04-24"])
        result = self.patch(original)
        self.assertEqual(result.count("DEON Concerts &amp; Tour Dates 2027 | Kingdom Circuit"), 3)
        self.assertIn("Next show · APR 24, 2027", result)
        self.assertIn('<span class="kc-rd-show-year">2027</span>', result)
        for unchanged in ('href="/event/0/"', 'Venue · 7 PM', 'Tyler, TX', 'Past shows: 2025, 2024', 'https://kingdomcircuit.com/artists/deon/'):
            self.assertEqual(result.count(unchanged), original.count(unchanged))

    def test_mixed_years_exclude_archive_years(self):
        result = self.patch(self.profile(["2026-10-08", "2027-02-12"]))
        self.assertIn("Concerts &amp; Tour Dates 2026–2027 | Kingdom Circuit", result)
        self.assertEqual(result.count('class="kc-rd-show-year"'), 1)

    def test_no_upcoming_shows_removes_year(self):
        result = self.patch(self.profile([]))
        self.assertEqual(result.count("DEON Concerts &amp; Tour Dates | Kingdom Circuit"), 3)
        self.assertNotIn("2026", result)

    def test_year_rollover_hides_now_current_year_in_compact_dates(self):
        first = self.patch(self.profile(["2027-04-24"]))
        result = self.patch(first, dt.date(2027, 1, 1))
        self.assertIn("Tour Dates 2027 | Kingdom Circuit", result)
        self.assertNotIn('class="kc-rd-show-year"', result)
        self.assertNotIn("APR 24, 2027", result)

    def test_multiday_show_stays_upcoming_through_last_day(self):
        document = self.profile(["2026-09-23"])
        self.event("0", "2026-09-23T19:00:00-07:00", "2026-09-24T23:00:00-07:00")
        self.assertIn("Tour Dates 2026", self.patch(document))
        with self.assertRaisesRegex(ValueError, "Expired show"):
            self.patch(document, dt.date(2026, 9, 25))

    def test_multiday_new_year_show_covers_both_years(self):
        document = self.profile(["2026-12-31"])
        self.event("0", "2026-12-31", "2027-01-02")
        self.assertIn("Tour Dates 2026–2027", self.patch(document))

    def test_refresh_is_idempotent_and_verifier_rejects_stale_output(self):
        page = self.root / "artists" / "deon" / "index.html"
        page.parent.mkdir(parents=True)
        page.write_text(self.profile(["2027-04-24"]))
        with self.assertRaisesRegex(ValueError, "stale"):
            years.apply(self.root, today=self.today, check_only=True)
        self.assertEqual(years.apply(self.root, today=self.today), 1)
        first = page.read_text()
        years.apply(self.root, today=self.today)
        self.assertEqual(page.read_text(), first)
        self.assertEqual(years.apply(self.root, today=self.today, check_only=True), 1)

    def test_name_entities_are_not_double_escaped(self):
        result = self.patch(self.profile([], name="A &amp; B"))
        self.assertIn("A &amp; B Concerts", result)
        self.assertNotIn("&amp;amp;", result)

    def test_sparse_years_do_not_claim_unlisted_year(self):
        self.assertEqual(years.title_for("Artist", {2026, 2028}), "Artist Concerts & Tour Dates 2026, 2028 | Kingdom Circuit")

    def test_missing_event_date_blocks_publication(self):
        document = self.profile(["2027-04-24"])
        (self.root / "event/0/index.html").write_text("<html>No event schema</html>")
        with self.assertRaisesRegex(ValueError, "no dated event"):
            self.patch(document)

    def test_other_published_event_types_and_graph_schema(self):
        for event_type in ("Event", "Festival", ["Event", "MusicEvent"]):
            document = self.profile(["2027-04-24"])
            schema = {"@graph": [{"@type": event_type, "startDate": "2027-04-24"}]}
            (self.root / "event/0/index.html").write_text('<script type="application/ld+json">' + json.dumps(schema) + '</script>')
            self.assertIn("Tour Dates 2027", self.patch(document))


if __name__ == "__main__":
    unittest.main()
