import importlib.util
import datetime as dt
import json
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('artist_details', ROOT / 'scripts/finalize_artist_details.py')
details = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(details)


class ArtistDetailsTests(unittest.TestCase):
    def fixture(self, site, base=details.BASE, status='Sold Out'):
        profile = site / 'artists/example/index.html'
        profile.parent.mkdir(parents=True)
        event = site / 'event/example/index.html'
        event.parent.mkdir(parents=True)
        event.write_text('<h1>Example &amp; Friends — Night One</h1>' +
                         (f'<dl><dt>Status</dt><dd>{status}</dd></dl>' if status else ''))
        state = profile.parent / 'florida/index.html'
        state.parent.mkdir()
        state.write_text(f'<link rel="canonical" href="https://example.com{base}artists/example/florida/">'
                         '<h1>Example Concerts in Florida</h1><article class="event-card"></article>')
        source = ('<html><head><title>Existing SEO title 2027</title></head><body>'
                  '<article data-kc-rd-artist-profile><h1 id="kc-rd-artist-name">Example</h1>'
                  '<img src="portrait.jpg"><a href="https://instagram.com/example">Social</a>'
                  f'<a class="kc-rd-next kc-rd-next-show" href="{base}event/example/">'
                  '<span><span class="kc-rd-next-kicker">Next show · APR 2, 2027</span>'
                  '<span class="kc-rd-next-venue">Hall · 7 PM</span></span><span>›</span></a>'
                  '<section class="kc-rd-profile-shows" aria-labelledby="kc-rd-shows-title">'
                  '<h2 id="kc-rd-shows-title">All Example Shows</h2>'
                  f'<a class="kc-rd-show-row" href="{base}event/example/" aria-label="Apr 2, 2027, Miami, Hall">'
                  '<span class="kc-rd-show-date">APR 2<span>2027</span></span>'
                  '<span class="kc-rd-show-place"><strong>Miami, FL</strong>'
                  '<span class="kc-rd-show-venue">Hall</span></span><span class="kc-rd-chevron">›</span></a></section>'
                  '<section data-past-shows-archive><details><summary>Past shows</summary>History</details></section>'
                  '</article></body></html>')
        profile.write_text(source)
        (site / 'assets').mkdir()
        (site / details.CSS).write_text('test stylesheet')
        return profile, source

    def test_preserves_identity_dates_socials_and_archive_and_is_repeat_safe(self):
        with tempfile.TemporaryDirectory() as temp:
            site = Path(temp)
            profile, before = self.fixture(site)
            after = details.render_profile(site, profile, before, details.BASE)
            profile.write_text(after)
            self.assertEqual(after, details.render_profile(site, profile, after, details.BASE))
            for fragment in ['<title>Existing SEO title 2027</title>', '<img src="portrait.jpg">',
                             'href="https://instagram.com/example"', 'APR 2<span>2027</span>',
                             '<section data-past-shows-archive><details><summary>Past shows</summary>History</details></section>']:
                self.assertIn(fragment, after)
            self.assertEqual(after.count('class="kc-rd-event-title"'), 2)
            self.assertEqual(after.count('class="kc-rd-event-status"'), 2)
            self.assertEqual(details.check(site), dict(profiles=1, showRows=1, statusRows=1, stateLinks=1))

    def test_only_useful_canonical_state_pages_linked(self):
        with tempfile.TemporaryDirectory() as temp:
            site = Path(temp)
            profile, source = self.fixture(site)
            for state, canonical, content in [('empty', 'empty', ''), ('duplicate', 'florida', '<article class="event-card"></article>'),
                                               ('history', 'history', '<article class="past-show-row"></article>')]:
                page = profile.parent / state / 'index.html'
                page.parent.mkdir()
                page.write_text(f'<link rel="canonical" href="{details.BASE}artists/example/{canonical}/">'
                                f'<h1>Example Concerts in {state.title()}</h1>{content}')
            self.assertEqual([label for label, _ in details.state_links(profile, 'Example', details.BASE)], ['Florida', 'History'])

    def test_root_paths_work_without_test_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            site = Path(temp)
            profile, source = self.fixture(site, base='/', status='Cancelled')
            after = details.render_profile(site, profile, source, '/')
            profile.write_text(after)
            self.assertNotIn('kingdom-circuit-test', after)
            self.assertIn('>Cancelled</span>', after)
            details.check(site, '/')

    def test_schema_status_and_mixed_offers(self):
        with tempfile.TemporaryDirectory() as temp:
            site = Path(temp)
            profile, source = self.fixture(site, status='')
            event = site / 'event/example/index.html'
            for event_type in ['Event', 'MusicEvent', 'Festival']:
                payload = {'@graph': [{'@type': event_type, 'eventStatus': 'https://schema.org/EventPostponed',
                                      'offers': [{'availability': 'https://schema.org/SoldOut'}, {'availability': 'https://schema.org/InStock'}]}]}
                event.write_text('<h1>Show</h1><script type="application/ld+json">' + json.dumps(payload) + '</script>')
                self.assertEqual(details.event_details(site, details.BASE+'event/example/', details.BASE), ('Show', 'Postponed'))

    def test_unknown_status_not_invented_and_empty_profile_supported(self):
        with tempfile.TemporaryDirectory() as temp:
            site = Path(temp)
            profile, source = self.fixture(site, status='')
            after = details.render_profile(site, profile, source, details.BASE)
            self.assertNotIn('class="kc-rd-event-status"', after)
            empty = details.ROW.sub('', details.NEXT.sub('', source))
            after = details.render_profile(site, profile, empty, details.BASE)
            profile.write_text(after)
            self.assertEqual(details.check(site)['showRows'], 0)

    def test_scheduled_is_not_an_alert_and_existing_head_whitespace_is_repeat_safe(self):
        with tempfile.TemporaryDirectory() as temp:
            site = Path(temp)
            profile, source = self.fixture(site, status='Scheduled')
            source = source.replace('</head>', '\n\n  </head>')
            after = details.render_profile(site, profile, source, details.BASE)
            self.assertNotIn('class="kc-rd-event-status"', after)
            self.assertEqual(after, details.render_profile(site, profile, after, details.BASE))

    def test_final_gate_catches_late_overwrite_wrong_status_and_missing_links(self):
        with tempfile.TemporaryDirectory() as temp:
            site = Path(temp)
            profile, before = self.fixture(site)
            after = details.render_profile(site, profile, before, details.BASE)
            for broken in [before, after.replace('Sold Out</span>', 'Available</span>'), details.NAV.sub('', after),
                           after.replace('Example concerts &amp; tour dates', 'Shows')]:
                profile.write_text(broken)
                with self.assertRaises(ValueError):
                    details.check(site)

    def test_missing_event_fails_instead_of_silently_dropping_details(self):
        with tempfile.TemporaryDirectory() as temp:
            site = Path(temp)
            profile, source = self.fixture(site)
            (site / 'event/example/index.html').unlink()
            with self.assertRaises(ValueError):
                details.render_profile(site, profile, source, details.BASE)

    def test_final_gate_is_after_all_overlays_and_before_upload(self):
        workflow = (ROOT / '.github/workflows/update-and-deploy.yml').read_text()
        gate = workflow.index('python scripts/finalize_artist_details.py _site --check')
        self.assertGreater(gate, workflow.index('python scripts/verify_owner_roster.py _site'))
        self.assertLess(gate, workflow.index('uses: actions/upload-pages-artifact'))

    def test_production_metadata_indexing_and_analytics_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            site = Path(temp)
            profile, source = self.fixture(site)
            metadata = ('<link rel="canonical" href="https://kingdomcircuit.com/artists/example/">'
                        '<meta name="robots" content="index,follow">'
                        '<meta property="og:title" content="Existing SEO title 2027">'
                        '<script>gtag("config","G-N2KK9XF4TJ");</script>'
                        '<script type="application/ld+json">{"@type":"MusicGroup","name":"Example"}</script>')
            source = source.replace('</head>', metadata + '</head>')
            after = details.render_profile(site, profile, source, details.BASE)
            self.assertIn(metadata, after)
            self.assertNotIn('noindex', after)
            self.assertNotIn('kingdom-circuit-test', after)

    def test_existing_next_year_finalizer_remains_repeat_safe(self):
        spec = importlib.util.spec_from_file_location('artist_years', ROOT / 'scripts/finalize_artist_schedule_years.py')
        years = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(years)
        with tempfile.TemporaryDirectory() as temp:
            site = Path(temp)
            profile, source = self.fixture(site)
            source = source.replace('APR 2<span>2027</span>', '<span>APR</span><strong>2</strong>')
            event = site / 'event/example/index.html'
            event.write_text(event.read_text() + '<script type="application/ld+json">' +
                             json.dumps({'@type':'MusicEvent','startDate':'2027-04-02'}) + '</script>')
            today = dt.date(2026, 10, 7)
            source = years.patch_profile(source, site, today)
            after = details.render_profile(site, profile, source, details.BASE)
            self.assertEqual(after, details.render_profile(site, profile, after, details.BASE))
            self.assertEqual(after, years.patch_profile(after, site, today))
            self.assertIn('<span class="kc-rd-show-year">2027</span>', after)

    def test_production_manifest_detects_missing_profile_or_row(self):
        with tempfile.TemporaryDirectory() as temp:
            site = Path(temp)
            profile, source = self.fixture(site)
            profile.write_text(details.render_profile(site, profile, source, details.BASE))
            manifest = site / 'assets/live-redesign-manifest.json'
            manifest.write_text(json.dumps({'profilePageCount':1,'profileShowRowCount':1}))
            details.check(site)
            for wrong in [{'profilePageCount':2,'profileShowRowCount':1}, {'profilePageCount':1,'profileShowRowCount':2}]:
                manifest.write_text(json.dumps(wrong))
                with self.assertRaises(ValueError):
                    details.check(site)


if __name__ == '__main__':
    unittest.main()
