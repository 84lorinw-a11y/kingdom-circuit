import copy
import datetime as dt
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import url_continuity as uc


class URLContinuityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.site = self.root / '_site'; self.site.mkdir()
        self.event = {'id': 'manual:show', 'title': 'Example concert', 'startDate': '2026-12-17',
                      'startTime': '19:00', 'city': 'Berkeley', 'state': 'CA', 'venue': 'Cornerstone',
                      'artists': ['Miles Minnick'], 'status': 'scheduled',
                      'officialUrl': 'https://www.prekindle.com/event/52416-miles-minnick-berkeley'}
        self.path = uc.generated_path(self.event)
        self.state = uc.empty_state()
        self.state['events']['manual:show'] = {'path': self.path, 'sourceIds': [], 'event': self.event}
        self.write_inputs()

    def write_inputs(self, primary=None, secondary=None, state=None, rules=None):
        uc.save(self.root / 'events.json', primary if primary is not None else [self.event])
        uc.save(self.root / 'supplemental-events.json', secondary or [])
        uc.save(self.root / uc.STATE_FILE, state if state is not None else self.state)
        uc.save(self.root / uc.RULES_FILE, rules or {})

    def page(self, path, content='Details', canonical=None):
        text = f'<html><head><title>Show</title><meta name="robots" content="index,follow"><link rel="canonical" href="{uc.ORIGIN + (canonical or path)}"></head><body><main><h1>Show</h1><p>{content}</p></main></body></html>'
        file = uc.target_file(self.site, path); file.parent.mkdir(parents=True, exist_ok=True); file.write_text(text)
        return file

    def test_reimported_duplicate_is_merged_and_old_url_survives(self):
        duplicate = dict(self.event, id='ticketmaster:duplicate', postalCode='94704')
        self.write_inputs(primary=[duplicate, self.event])
        uc.prepare(self.root)
        events = uc.load(self.root / 'events.json', [])
        self.assertEqual(['manual:show'], [e['id'] for e in events])
        self.assertEqual('94704', events[0]['postalCode'])
        self.assertIn('ticketmaster:duplicate', events[0]['mergedFromIds'])
        self.page(self.path)
        uc.finalize(self.root, self.site)
        alias = uc.generated_path(duplicate)
        forwarded = uc.PageFacts(uc.target_file(self.site, alias).read_text())
        self.assertEqual('0; url=' + uc.ORIGIN + self.path, forwarded.refresh)
        self.assertEqual(uc.ORIGIN + self.path, forwarded.canonical)
        uc.persist(self.root, self.root / uc.WORK_FILE)
        uc.save(self.root / 'events.json', [duplicate])
        uc.prepare(self.root)
        self.assertEqual(['manual:show'], [e['id'] for e in uc.load(self.root / 'events.json', [])])

    def test_title_date_and_city_edits_keep_the_published_path(self):
        edited = dict(self.event, title='Corrected title', startDate='2026-12-18', city='Oakland')
        self.write_inputs(primary=[edited]); uc.prepare(self.root)
        generated = uc.generated_path(edited)
        self.page(generated, 'Corrected details')
        self.page('/shows/', '<a href="' + generated + '">Show</a>')
        uc.finalize(self.root, self.site)
        self.assertIn('Corrected details', uc.target_file(self.site, self.path).read_text())
        self.assertIn(self.path, uc.target_file(self.site, '/shows/').read_text())
        self.assertNotIn(generated, uc.target_file(self.site, '/shows/').read_text())
        self.assertEqual(uc.ORIGIN + self.path, uc.PageFacts(uc.target_file(self.site, self.path).read_text()).canonical)
        uc.finalize(self.root, self.site)
        self.assertIn('Corrected details', uc.target_file(self.site, self.path).read_text())
        self.assertEqual('', uc.PageFacts(uc.target_file(self.site, self.path).read_text()).refresh)

    def test_conflicting_sessions_and_venues_are_not_merged(self):
        for update in ({'startTime': '21:00'}, {'venue': 'Different venue'}, {'startTime': ''}, {'state': 'TX'}, {'status': 'private'}):
            with self.subTest(update=update):
                other = dict(self.event, id='separate', **update)
                self.assertFalse(uc.same_performance(self.event, other))
        unknown = dict(self.event, startTime='')
        self.assertFalse(uc.same_performance(unknown, dict(unknown, id='unknown-session')))
        self.write_inputs(primary=[self.event, dict(self.event, id='late-set', startTime='21:00')])
        uc.prepare(self.root)
        self.assertEqual(2, len(uc.load(self.root / 'events.json', [])))

    def test_current_alias_details_replace_stale_registered_details(self):
        self.state['events'][self.event['id']]['sourceIds'] = ['provider:new']
        updated = dict(self.event, id='provider:new', startDate='2026-12-18', status='cancelled')
        self.write_inputs(primary=[updated])
        uc.save(self.root / 'event-history.json', {'events': [{'event': self.event}]})
        uc.save(self.root / 'config/manual-events.json', [self.event])
        uc.prepare(self.root)
        event = uc.load(self.root / 'events.json', [])[0]
        self.assertEqual(self.event['id'], event['id'])
        self.assertEqual('2026-12-18', event['startDate'])
        self.assertEqual('cancelled', event['status'])
        generated = uc.generated_path(event)
        self.page(generated, 'Updated cancellation')
        uc.finalize(self.root, self.site)
        self.assertIn('Updated cancellation', uc.target_file(self.site, self.path).read_text())
        self.assertEqual('0; url=' + uc.ORIGIN + self.path, uc.PageFacts(uc.target_file(self.site, generated).read_text()).refresh)
        self.assertEqual(self.path, uc.load(self.root / uc.WORK_FILE, {})['events'][self.event['id']]['path'])

    def test_explicit_retirement_is_not_restored_or_persisted(self):
        self.state['pages'][self.path] = {'title': 'Old show'}
        self.state['redirects']['/event/older/'] = '/event/old/'
        self.state['redirects']['/event/old/'] = self.path
        self.write_inputs(rules={'retiredPaths': [self.path]})
        self.page(self.path); self.page('/event/old/'); self.page('/event/older/')
        uc.prepare(self.root); uc.finalize(self.root, self.site)
        self.assertFalse(uc.target_file(self.site, self.path).exists())
        self.assertFalse(uc.target_file(self.site, '/event/old/').exists())
        self.assertNotIn(self.path, (self.site / 'sitemap.xml').read_text())
        uc.persist(self.root, self.root / uc.WORK_FILE)
        published = uc.load(self.root / uc.STATE_FILE, {})
        self.assertNotIn(self.event['id'], published['events'])
        self.assertNotIn(self.path, published['pages'])
        self.assertNotIn('/event/old/', published['redirects'])
        uc.save(self.root / 'events.json', [])
        uc.save(self.root / uc.RULES_FILE, {'merges': [{'keepId': self.event['id'], 'keepPath': self.path, 'aliasIds': ['provider:new'], 'aliasPaths': ['/event/old/']}]})
        uc.prepare(self.root)
        uc.finalize(self.root, self.site)
        self.assertFalse(uc.target_file(self.site, self.path).exists())

    def test_same_identity_retains_required_presence_in_both_feeds(self):
        private = dict(self.event, status='private')
        self.write_inputs(primary=[private], secondary=[private])
        uc.prepare(self.root)
        for name in uc.FEEDS:
            rows = uc.load(self.root / name, [])
            self.assertEqual(1, len(rows))
            self.assertEqual('private', rows[0]['status'])
            self.assertEqual(self.event['id'], rows[0]['id'])

    def test_shared_tour_homepage_is_not_an_identity(self):
        a = dict(self.event, officialUrl='https://example.org/pages/tour')
        self.assertFalse(uc.same_performance(a, dict(a, id='different')))

    def test_intentionally_empty_lineup_is_preserved(self):
        event = dict(self.event, artists=[])
        self.assertEqual([], uc.merge_details(event, event)['artists'])

    def test_redirect_cycle_and_missing_target_fail(self):
        with self.assertRaisesRegex(ValueError, 'cycle'):
            uc.flatten_redirects({'/event/a/': '/event/b/', '/event/b/': '/event/a/'})
        self.state['redirects']['/event/old/'] = '/event/nonexistent/'
        self.write_inputs(); uc.prepare(self.root)
        with self.assertRaisesRegex(ValueError, 'target missing'):
            uc.finalize(self.root, self.site)

    def test_chains_collapse_to_one_final_target(self):
        self.assertEqual({'/a/': '/c/', '/b/': '/c/'}, uc.flatten_redirects({'/a/': '/b/', '/b/': '/c/'}))

    def test_unknown_merge_target_cannot_fall_back_to_all_shows(self):
        self.write_inputs(primary=[dict(self.event, id='old', status='merged', mergedIntoId='absent')])
        with self.assertRaisesRegex(ValueError, 'valid survivor'): uc.prepare(self.root)

    def test_meaningful_content_changes_update_lastmod_but_rebuilds_do_not(self):
        page = self.page(self.path)
        self.state['pages'][self.path] = {'fingerprint': uc.PageFacts(page.read_text()).fingerprint(), 'lastmod': None}
        self.write_inputs(); uc.prepare(self.root)
        uc.finalize(self.root, self.site, '2026-10-30')
        self.assertNotIn('<lastmod>', (self.site / 'sitemap.xml').read_text())
        page.write_text(page.read_text().replace('Details', 'New verified details'))
        uc.finalize(self.root, self.site, '2026-10-31')
        self.assertIn('<lastmod>2026-10-31</lastmod>', (self.site / 'sitemap.xml').read_text())
        page.write_text(page.read_text().replace('</head>', '<script>/* deployment-only change */</script></head>'))
        uc.finalize(self.root, self.site, '2026-11-01')
        self.assertIn('<lastmod>2026-10-31</lastmod>', (self.site / 'sitemap.xml').read_text())
        self.assertNotIn('<lastmod>2026-11-01</lastmod>', (self.site / 'sitemap.xml').read_text())

    def test_forged_sitemap_date_fails_final_gate(self):
        self.page(self.path); uc.prepare(self.root); uc.finalize(self.root, self.site)
        sitemap = self.site / 'sitemap.xml'; text = sitemap.read_text()
        text = text.replace('<lastmod>', '<lastmod>2000-01-01<!--').replace('</lastmod>', '--></lastmod>')
        sitemap.write_text(text)
        with self.assertRaisesRegex(ValueError, 'Unverified'): uc.verify(self.site)

    def test_forwarder_has_no_analytics_or_event_schema_and_keeps_query(self):
        text = uc.forwarding_page(self.path)
        self.assertNotIn('gtag(', text); self.assertNotIn('application/ld+json', text)
        self.assertIn('window.location.search+window.location.hash', text)
        self.assertIn('location.replace', text)
        self.assertIn('<meta http-equiv="refresh" content="0;', text)
        self.assertIn('Continue to show', text)

    def test_retained_private_event_never_becomes_public_schema(self):
        uc.restore_event(self.site, self.path, dict(self.event, status='private'), '2026-11-01')
        text = uc.target_file(self.site, self.path).read_text()
        self.assertIn('Not open to the public', text)
        self.assertEqual([], uc.PageFacts(text).schemas)

    def test_archived_alias_page_does_not_register_a_second_canonical_identity(self):
        old = dict(self.event, id='archived:old')
        old_path = uc.generated_path(old)
        self.write_inputs(); uc.prepare(self.root)
        uc.save(self.root / 'event-history.json', {'events': [{'event': old}]})
        self.page(self.path)
        file = self.page(old_path, canonical=self.path)
        file.write_text(file.read_text().replace('</body>', '<script>location.replace("' + self.path + '");</script></body>'))
        uc.finalize(self.root, self.site)
        state = uc.load(self.root / uc.WORK_FILE, {})
        self.assertNotIn(old['id'], state['events'])
        self.assertEqual(self.path, state['redirects'][old_path])

    def test_runtime_cards_use_registered_path_after_rename(self):
        import subprocess
        edited = dict(self.event, title='New title')
        self.write_inputs(primary=[edited]); uc.prepare(self.root)
        self.page(uc.generated_path(edited))
        uc.save(self.site / 'events.json', [edited])
        app = self.site / 'app.js'
        app.write_text('function eventDetailUrl(event) { return "/wrong/"; }')
        uc.finalize(self.root, self.site); uc.finalize(self.root, self.site)
        public = uc.load(self.site / 'events.json', [])[0]
        self.assertEqual(self.path, public['canonicalPath'])
        code = app.read_text() + '\nconsole.log(eventDetailUrl(' + uc.json.dumps(public) + '));'
        self.assertEqual(self.path, subprocess.check_output(['node', '-e', code], text=True).strip())

    def test_internal_identity_records_are_removed_from_public_artifact(self):
        self.page(self.path); uc.prepare(self.root)
        for path in (uc.STATE_FILE, uc.RULES_FILE, uc.WORK_FILE):
            uc.save(self.site / path, {'internal': True})
        uc.finalize(self.root, self.site)
        self.assertTrue((self.site / 'url-continuity-manifest.json').is_file())
        self.assertTrue(all(not (self.site / p).exists() for p in (uc.STATE_FILE, uc.RULES_FILE, uc.WORK_FILE)))

    def test_paths_cannot_escape_site_or_redirect_offsite(self):
        for path in ('https://evil.example/', '//evil.example/', '/../../', '/event/a/?url=x'):
            with self.subTest(path=path):
                with self.assertRaises(ValueError): uc.forwarding_page(path)

    def test_older_deploy_cannot_overwrite_newer_registry(self):
        self.state['publishedAt'] = '2026-11-01T10:00:00+00:00'; self.write_inputs()
        incoming = self.root / 'incoming.json'; old = copy.deepcopy(self.state); old['publishedAt'] = '2026-11-01T09:00:00+00:00'
        uc.save(incoming, old)
        with self.assertRaisesRegex(ValueError, 'newer deployed'): uc.persist(self.root, incoming)


if __name__ == '__main__': unittest.main()
