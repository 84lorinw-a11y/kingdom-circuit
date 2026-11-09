import copy
import datetime as dt
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import url_continuity as uc
import catalog_removals as catalog


class URLContinuityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.site = self.root / '_site'; self.site.mkdir()
        self.review_file = self.root / 'config/review-held-events.json'
        boundary = patch.object(catalog, 'REVIEW_FILE', self.review_file, create=True)
        boundary.start()
        self.addCleanup(boundary.stop)
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

    def test_retained_calendar_has_truthful_description_and_single_production_analytics(self):
        import re
        title = 'Miles Minnick in Virginia'
        body = '<p>No upcoming shows are currently confirmed on this calendar.</p>'
        text = uc.retained_page('/artists/miles-minnick/virginia/', title, body)
        facts = uc.PageFacts(text)
        self.assertEqual(title + '. No upcoming shows are currently confirmed on this calendar.',
                         facts.description)
        self.assertEqual(uc.ORIGIN + '/artists/miles-minnick/virginia/', facts.canonical)
        self.assertEqual('index,follow', facts.robots)
        self.assertEqual(['G-N2KK9XF4TJ'], re.findall(
            r'<script async src="https://www.googletagmanager.com/gtag/js\?id=([^"]+)"', text))
        self.assertEqual(['G-N2KK9XF4TJ'], re.findall(r"gtag\('config','([^']+)'\)", text))
        self.assertEqual([], facts.schemas)

    def test_retained_description_uses_escaped_visible_text_without_script_contents(self):
        title = 'Hope "Live" & Friends'
        text = uc.retained_page('/event/retained/', title,
            '<p>Postponed &amp; awaiting a new date.</p><script>window.hiddenFact="unverified";</script>')
        self.assertEqual('Hope "Live" & Friends. Postponed & awaiting a new date.',
                         uc.PageFacts(text).description)
        self.assertIn('content="Hope &quot;Live&quot; &amp; Friends.', text)
        self.assertNotIn('hiddenFact', uc.PageFacts(text).description)

    def test_retained_description_is_bounded_without_adding_unconfirmed_facts(self):
        body = '<p>This date has passed. These recorded details are retained for reference.</p>'
        body += '<p>' + ('Previously listed performer ' * 20) + '</p>'
        text = uc.retained_page('/event/retained/', 'Example concert', body)
        description = uc.PageFacts(text).description
        self.assertTrue(description.startswith('Example concert. This date has passed.'))
        self.assertLessEqual(len(description), 160)
        self.assertNotIn('tickets', description.lower())
        self.assertEqual([], uc.PageFacts(text).schemas)

    def test_retained_private_description_does_not_restore_redacted_address_or_offers(self):
        event = dict(self.event, status='private', address='999 Private Retreat Road',
                     postalCode='99999', ticketUrl='https://tickets.example/private/')
        original = copy.deepcopy(event)
        uc.restore_event(self.site, self.path, event, '2026-11-01')
        text = uc.target_file(self.site, self.path).read_text()
        facts = uc.PageFacts(text)
        self.assertIn('Private event. Not open to the public.', facts.description)
        self.assertNotIn('999 Private Retreat Road', text)
        self.assertNotIn('99999', text)
        self.assertEqual([], facts.schemas)
        self.assertEqual(original, event)
        self.assertEqual(uc.ORIGIN + self.path, facts.canonical)

    def test_retained_location_review_keeps_noindex_with_factual_description(self):
        uc.restore_location_review(self.site, self.path, {'startDate': '2026-11-21'})
        facts = uc.PageFacts(uc.target_file(self.site, self.path).read_text())
        self.assertEqual('noindex,follow', facts.robots)
        self.assertIn('Location not confirmed.', facts.description)
        self.assertEqual(uc.ORIGIN + self.path, facts.canonical)
        self.assertEqual([], facts.schemas)

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

    def flavor_concert(self, day):
        weekday = 'friday' if day == '2026-11-06' else 'saturday'
        return {'id': f'manual:flavor-fest-2026-{weekday}-concerts',
                'title': f'Flavor Fest 2026 — {weekday.title()} Concerts',
                'startDate': day, 'startTime': '19:00', 'city': 'Tampa',
                'state': 'FL', 'country': 'US', 'venue': 'Crossover Church',
                'artists': ['Miles Minnick' if weekday == 'friday' else 'Lecrae'],
                'status': 'scheduled', 'ticketUrl': 'https://flavorfest.ticketspice.com/full-conference-'}

    def test_reviewed_flavor_aliases_forward_without_removing_current_concerts(self):
        current = [self.flavor_concert(day) for day in ('2026-11-06', '2026-11-07')]
        aliases = [dict(e, id=e['id'].removeprefix('manual:')) for e in current]
        state = uc.empty_state()
        for e in current + aliases:
            state['events'][e['id']] = {'path': uc.generated_path(e), 'sourceIds': [], 'event': e}
        self.write_inputs(primary=current, secondary=aliases, state=state)
        uc.prepare(self.root)
        for e in current:
            self.page(uc.generated_path(e), 'Current confirmed concert')
        for e in aliases:
            self.page(uc.generated_path(e), 'This previously listed show is no longer in our current calendar.')
        for name, events in zip(uc.FEEDS, (current, aliases)):
            uc.save(self.site / name, events)
        uc.finalize(self.root, self.site)
        first = uc.load(self.root / uc.WORK_FILE, {})
        for original, alias in zip(current, aliases):
            target, old = uc.generated_path(original), uc.generated_path(alias)
            text = uc.target_file(self.site, old).read_text()
            facts = uc.PageFacts(text)
            self.assertEqual(uc.ORIGIN + target, facts.canonical)
            self.assertEqual('0; url=' + uc.ORIGIN + target, facts.refresh)
            self.assertNotIn('no longer in our current calendar', text)
            self.assertEqual([], facts.schemas)
            self.assertIn('Current confirmed concert', uc.target_file(self.site, target).read_text())
            self.assertNotIn(uc.ORIGIN + old, (self.site / 'sitemap.xml').read_text())
            self.assertIn(uc.ORIGIN + target, (self.site / 'sitemap.xml').read_text())
            self.assertIn(original['id'], first['events'])
            self.assertNotIn(alias['id'], first['events'])
            self.assertIn(alias['id'], first['events'][original['id']]['sourceIds'])
        self.assertEqual([e['id'] for e in current], [e['id'] for e in uc.load(self.root / 'events.json', [])])
        self.assertEqual([e['id'] for e in aliases], [e['id'] for e in uc.load(self.site / 'supplemental-events.json', [])])
        self.assertEqual([uc.generated_path(e) for e in current],
                         [e['canonicalPath'] for e in uc.load(self.site / 'supplemental-events.json', [])])
        uc.persist(self.root, self.root / uc.WORK_FILE)
        uc.prepare(self.root)
        uc.finalize(self.root, self.site)
        self.assertEqual(set(e['id'] for e in current), set(uc.load(self.root / uc.WORK_FILE, {})['events']))
        uc.verify(self.site)

    def test_reviewed_flavor_alias_does_not_merge_conflicting_sessions_or_missing_survivor(self):
        original = self.flavor_concert('2026-11-06')
        for fields in ({'startDate': '2026-11-07'}, {'startTime': '21:00'},
                       {'venue': 'Other venue'}, {'status': 'private'}):
            with self.subTest(fields=fields):
                alias = dict(original, id=original['id'].removeprefix('manual:'), **fields)
                state = uc.empty_state()
                for e in (original, alias):
                    state['events'][e['id']] = {'path': uc.generated_path(e), 'sourceIds': [], 'event': e}
                self.page(uc.generated_path(original))
                uc.reconcile_reviewed_aliases(state, {e['id']: e for e in (original, alias)}, {original['id']}, self.site)
                self.assertIn(alias['id'], state['events'])
                self.assertEqual({}, state['redirects'])
        alias = dict(original, id=original['id'].removeprefix('manual:'))
        state = uc.empty_state()
        for e in (original, alias):
            state['events'][e['id']] = {'path': uc.generated_path(e), 'sourceIds': [], 'event': e}
        uc.reconcile_reviewed_aliases(state, {e['id']: e for e in (original, alias)}, set(), self.site)
        self.assertEqual({}, state['redirects'])

    def test_restored_unconfirmed_booking_preserves_canonical_and_raw_history(self):
        from catalog_removals import apply, public_event
        original = {'id': 'official:023c040d4ea33e120949', 'title': '1K Phew — Live at Texas Motorplex',
                    'startDate': '2026-11-21', 'startTime': '', 'artists': ['1K Phew'],
                    'venue': 'Texas Motorplex', 'city': 'Swiss Golf And Tennis Club Mobile Home Park',
                    'state': 'FL', 'country': 'US', 'status': 'scheduled'}
        original_path = uc.generated_path(original)
        state = copy.deepcopy(self.state)
        state['events'][original['id']] = {'path': original_path, 'sourceIds': [], 'event': original}
        self.write_inputs(primary=[self.event, original], state=state)
        history = {'events': [{'event': copy.deepcopy(original)}]}
        uc.save(self.root / 'event-history.json', history)
        before_history = (self.root / 'event-history.json').read_bytes()
        apply(self.root)
        uc.prepare(self.root)
        projected = public_event(original)
        self.page(self.path)
        self.page(original_path, 'Old Florida location <script type="application/ld+json">{"@type":"Event"}</script>')
        self.page(uc.generated_path(projected), 'Location not confirmed; venue and start time not confirmed.')
        for name in uc.FEEDS:
            uc.save(self.site / name, uc.load(self.root / name, []))
        uc.finalize(self.root, self.site, '2026-11-06')
        text = uc.target_file(self.site, original_path).read_text()
        facts = uc.PageFacts(text)
        self.assertEqual(uc.ORIGIN + original_path, facts.canonical)
        self.assertEqual('index,follow', facts.robots)
        self.assertIn('Location not confirmed', text)
        self.assertNotIn('Old Florida location', text)
        self.assertNotIn('temporarily excluded', text)
        self.assertEqual([], facts.schemas)
        self.assertIn(uc.ORIGIN + original_path, (self.site / 'sitemap.xml').read_text())
        self.assertEqual(before_history, (self.root / 'event-history.json').read_bytes())
        public = next(e for e in uc.load(self.site / 'events.json', []) if e['id'] == original['id'])
        self.assertEqual(original_path, public['canonicalPath'])
        self.assertTrue(public['locationUnconfirmed'])
        self.assertEqual(('', '', ''), (public['city'], public['state'], public['venue']))
        self.assertEqual({self.event['id'], original['id']}, {e['id'] for e in uc.load(self.root / 'events.json', [])})
        uc.finalize(self.root, self.site, '2026-11-06')
        self.assertEqual(text, uc.target_file(self.site, original_path).read_text())

    def test_resolved_location_prepare_merges_reviewed_aliases_into_original_canonical(self):
        canonical_id = 'official:023c040d4ea33e120949'
        manual_alias_id = 'manual:' + canonical_id
        provider_id = 'bandsintown:1040798191'
        retained = '/event/1k-phew-live-at-texas-motorplex-2026-11-21-swiss-golf-and-tennis-club-mobile-home-park-a168a7/'
        provider_path = '/event/1k-phew-live-performance-2026-11-21-item-fd1047/'
        source = {
            'id': canonical_id, 'title': '1K Phew at Texas Motorplex',
            'startDate': '2026-11-21', 'startTime': '18:00',
            'venue': 'Texas Motorplex', 'city': 'Swiss Golf And Tennis Club Mobile Home Park',
            'state': 'FL', 'country': 'US', 'status': 'scheduled',
            'artists': ['1K Phew'], 'firstSeen': '2026-11-06T12:00:00Z',
            'officialUrl': 'https://www.reachrecords.com/artists/1k-phew/',
            'ticketUrl': 'https://www.bandsintown.com/e/1040798191',
        }
        manual = dict(source, id=manual_alias_id)
        provider = dict(source, id=provider_id, bandsintownEventId='1040798191')
        resolved = {
            'id': canonical_id, 'title': 'Cars & Christ Dallas',
            'startDate': '2026-11-21', 'endDate': '2026-11-21',
            'startTime': '17:00', 'endTime': '21:00',
            'startDateTime': '2026-11-21T17:00:00-06:00',
            'endDateTime': '2026-11-21T21:00:00-06:00',
            'timezone': 'America/Chicago', 'venue': 'Texas Motorplex',
            'address': '7500 W Hwy 287', 'postalCode': '75119',
            'city': 'Ennis', 'state': 'TX', 'country': 'US',
            'status': 'scheduled', 'eventType': 'concert',
            'artists': ['1K Phew', 'Trendsetter Sense'], 'headliner': '1K Phew',
            'advertisedBilling': ['1K Phew', 'DJ Trendsetter Sense'],
            'officialBill': ['1K Phew', 'DJ Trendsetter Sense'],
            'musicConfirmed': True, 'lineupExplicit': True,
            'officialUrl': 'https://www.zeffy.com/en-US/ticketing/cars-and-christ-dallas-2026',
            'ticketUrl': 'https://www.zeffy.com/en-US/ticketing/cars-and-christ-dallas-2026',
            'ticketUrlVerified': False, 'registrationUrlVerified': False,
            'price': 'Free', 'locationUnconfirmed': False,
            'firstSeen': '2026-11-03T18:56:47Z', 'confidence': 'high',
        }
        state = uc.empty_state()
        state['events'][canonical_id] = {'path': retained, 'sourceIds': [], 'event': source}
        state['events'][provider_id] = {'path': provider_path, 'sourceIds': [], 'event': provider}
        rules = {'merges': [{
            'keepId': canonical_id, 'keepPath': retained,
            'aliasIds': [manual_alias_id, provider_id], 'aliasPaths': [provider_path],
        }]}
        self.write_inputs(primary=[manual], secondary=[provider], state=state, rules=rules)
        uc.save(self.root / 'config/manual-events.json', [resolved])
        uc.save(self.review_file, [{'excludedEventId': canonical_id,
                                   'reviewStatus': 'resolved_location_confirmed',
                                   'publish': True, 'resolvedEvent': resolved}])
        uc.save(self.root / 'event-history.json', {'events': [{'event': source}, {'event': provider}]})
        raw_history = (self.root / 'event-history.json').read_bytes()

        result = uc.prepare(self.root)
        self.assertEqual(result['events'], 1)
        for filename in uc.FEEDS:
            rows = uc.load(self.root / filename, [])
            self.assertEqual([row['id'] for row in rows], [canonical_id])
            self.assertEqual((rows[0]['city'], rows[0]['state'], rows[0]['startTime']), ('Ennis', 'TX', '17:00'))
            self.assertIs(rows[0]['locationUnconfirmed'], False)
            self.assertEqual(rows[0]['firstSeen'], '2026-11-03T18:56:47Z')
            self.assertEqual(rows[0]['advertisedBilling'], ['1K Phew', 'DJ Trendsetter Sense'])
        prepared = uc.load(self.root / uc.WORK_FILE, {})
        self.assertEqual(set(prepared['events']), {canonical_id})
        self.assertEqual(prepared['events'][canonical_id]['path'], retained)
        self.assertEqual(set(prepared['events'][canonical_id]['sourceIds']), {manual_alias_id, provider_id})
        self.assertEqual(prepared['redirects'][provider_path], retained)
        self.assertEqual((self.root / 'event-history.json').read_bytes(), raw_history)

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

    def test_external_ticket_paths_are_not_recorded_as_local_event_relationships(self):
        self.page(self.path)
        external = 'https://liberty.evenue.net/event/SA26/SA-02'
        other_external = 'https://tickets.example/event/provider-show/'
        links = (f'<a href="{self.path}">Local show</a>'
                 f'<a href="{uc.ORIGIN}{self.path}?source=calendar#tickets">Same site</a>'
                 f'<a href="//kingdomcircuit.com{self.path}">Same site relative scheme</a>'
                 f'<a href="{external}">Tickets</a>'
                 f'<a href="{other_external}">Other tickets</a>')
        calendar = self.page('/shows/', links)
        uc.prepare(self.root)
        uc.finalize(self.root, self.site)
        state = uc.load(self.root / uc.WORK_FILE, {})
        self.assertEqual([self.path], state['pages']['/shows/']['eventPaths'])
        self.assertIn(external, calendar.read_text())
        self.assertIn(other_external, calendar.read_text())
        self.assertEqual(uc.ORIGIN + self.path, uc.PageFacts(uc.target_file(self.site, self.path).read_text()).canonical)
        uc.verify(self.site)

    def test_rollover_restores_calendar_despite_legacy_external_ticket_relationship(self):
        calendar = '/artists/miles-minnick/virginia/'
        alias = '/event/previous-show-link/'
        self.state['redirects'][alias] = self.path
        self.state['pages'][calendar] = {
            'title': 'Miles Minnick Virginia shows', 'heading': 'Miles Minnick in Virginia',
            'eventPaths': [self.path, alias, '/event/SA26/SA-02', '/event/provider-show/']}
        self.write_inputs(primary=[])
        uc.save(self.root / 'config/artists.json', [{'name': 'Miles Minnick', 'enabled': True}])
        uc.prepare(self.root)
        uc.finalize(self.root, self.site)
        text = uc.target_file(self.site, calendar).read_text()
        self.assertIn('No upcoming shows are currently confirmed', text)
        self.assertIn(f'href="{self.path}"', text)
        self.assertNotIn('/event/SA26/SA-02', text)
        self.assertNotIn('/event/provider-show/', text)
        self.assertEqual(uc.ORIGIN + calendar, uc.PageFacts(text).canonical)
        self.assertEqual('0; url=' + uc.ORIGIN + self.path,
                         uc.PageFacts(uc.target_file(self.site, alias).read_text()).refresh)
        state = uc.load(self.root / uc.WORK_FILE, {})
        self.assertEqual([self.path], state['pages'][calendar]['eventPaths'])
        self.assertEqual(self.path, state['events'][self.event['id']]['path'])
        self.assertEqual('noindex,follow', uc.PageFacts(text).robots)
        self.assertNotIn(uc.ORIGIN + calendar, (self.site / 'sitemap.xml').read_text())
        self.assertIn(uc.ORIGIN + self.path, (self.site / 'sitemap.xml').read_text())
        uc.persist(self.root, self.root / uc.WORK_FILE)
        uc.finalize(self.root, self.site)
        self.assertEqual(text, uc.target_file(self.site, calendar).read_text())
        uc.verify(self.site)

    def test_empty_city_rollover_retains_historical_links_without_sitemap_entry(self):
        calendar = '/shows/berkeley-california/'
        self.state['pages'][calendar] = {
            'title': 'Berkeley shows', 'eventPaths': [self.path]}
        self.write_inputs(primary=[])
        uc.prepare(self.root)
        uc.finalize(self.root, self.site)
        text = uc.target_file(self.site, calendar).read_text()
        self.assertIn('No upcoming shows are currently confirmed', text)
        self.assertIn(f'href="{self.path}"', text)
        self.assertEqual(uc.ORIGIN + calendar, uc.PageFacts(text).canonical)
        self.assertEqual('noindex,follow', uc.PageFacts(text).robots)
        self.assertNotIn(uc.ORIGIN + calendar, (self.site / 'sitemap.xml').read_text())
        self.assertEqual([self.path], uc.load(self.root / uc.WORK_FILE, {})['pages'][calendar]['eventPaths'])
        uc.persist(self.root, self.root / uc.WORK_FILE)
        uc.finalize(self.root, self.site)
        self.assertEqual(text, uc.target_file(self.site, calendar).read_text())
        uc.verify(self.site)

    def test_existing_empty_calendars_are_corrected_on_repeat_finalization(self):
        calendars = ['/artists/miles-minnick/california/', '/shows/berkeley-california/']
        for calendar in calendars:
            self.page(calendar, f'No upcoming shows. <a href="{self.path}">Earlier show</a>')
        uc.prepare(self.root)
        uc.finalize(self.root, self.site)
        expected = {}
        for calendar in calendars:
            text = uc.target_file(self.site, calendar).read_text()
            self.assertEqual('noindex,follow', uc.PageFacts(text).robots)
            self.assertIn('Earlier show', text)
            expected[calendar] = text
            uc.target_file(self.site, calendar).write_text(text.replace('noindex,follow', 'index,follow'))
        uc.finalize(self.root, self.site)
        for calendar in calendars:
            self.assertEqual(expected[calendar], uc.target_file(self.site, calendar).read_text())
            self.assertNotIn(uc.ORIGIN + calendar, (self.site / 'sitemap.xml').read_text())

    def test_returning_upcoming_show_reindexes_same_retained_calendar_urls(self):
        calendars = ['/artists/miles-minnick/california/', '/shows/berkeley-california/']
        card = f'<article data-event-card data-date="2026-12-17"><a href="{self.path}">New verified show</a></article>'
        for calendar in calendars:
            self.state['pages'][calendar] = {
                'title': 'Previously empty calendar', 'eventPaths': [],
                'fingerprint': 'previous-empty-calendar', 'lastmod': '2026-11-08'}
            page = self.page(calendar, card)
            page.write_text(page.read_text().replace('index,follow', 'noindex,follow'))
        self.write_inputs()
        uc.prepare(self.root)
        uc.finalize(self.root, self.site)
        for calendar in calendars:
            text = uc.target_file(self.site, calendar).read_text()
            self.assertIn(card, text)
            self.assertEqual('index,follow', uc.PageFacts(text).robots)
            self.assertEqual(uc.ORIGIN + calendar, uc.PageFacts(text).canonical)
            self.assertIn(uc.ORIGIN + calendar, (self.site / 'sitemap.xml').read_text())
        uc.verify(self.site)

    def test_final_gate_rejects_reenabled_empty_calendar_outside_sitemap(self):
        calendar = '/shows/berkeley-california/'
        page = self.page(calendar, 'No upcoming shows')
        page.write_text(page.read_text().replace('index,follow', 'noindex,follow'))
        uc.prepare(self.root)
        uc.finalize(self.root, self.site)
        page.write_text(page.read_text().replace('noindex,follow', 'index,follow'))
        with self.assertRaisesRegex(ValueError, 'Calendar indexing policy.*berkeley-california'):
            uc.verify(self.site)

    def test_final_gate_rejects_excluded_populated_calendar_outside_sitemap(self):
        calendar = '/artists/miles-minnick/california/'
        page = self.page(calendar, f'<article data-event-card><a href="{self.path}">Upcoming show</a></article>')
        uc.prepare(self.root)
        uc.finalize(self.root, self.site)
        page.write_text(page.read_text().replace('index,follow', 'noindex,follow'))
        sitemap = ET.parse(self.site / 'sitemap.xml')
        for node in list(sitemap.getroot()):
            if node.find('s:loc', uc.NS).text == uc.ORIGIN + calendar:
                sitemap.getroot().remove(node)
        sitemap.write(self.site / 'sitemap.xml')
        with self.assertRaisesRegex(ValueError, 'Calendar indexing policy.*miles-minnick/california'):
            uc.verify(self.site)

    def test_final_gate_rejects_missing_populated_calendar_sitemap_entry(self):
        calendar = '/shows/berkeley-california/'
        self.page(calendar, f'<article data-event-card><a href="{self.path}">Upcoming show</a></article>')
        uc.prepare(self.root)
        uc.finalize(self.root, self.site)
        sitemap = ET.parse(self.site / 'sitemap.xml')
        for node in list(sitemap.getroot()):
            if node.find('s:loc', uc.NS).text == uc.ORIGIN + calendar:
                sitemap.getroot().remove(node)
        sitemap.write(self.site / 'sitemap.xml')
        with self.assertRaisesRegex(ValueError, 'Missing eligible calendar.*berkeley-california'):
            uc.verify(self.site)

    def test_calendar_policy_preserves_archive_profile_state_and_reviewed_noindex(self):
        preserved = ['/artists/miles-minnick/', '/shows/california/', '/shows/october-2026/', self.path]
        for path in preserved:
            self.page(path, 'Retained history')
        review = '/event/location-review/'
        review_page = uc.target_file(self.site, review)
        review_page.parent.mkdir(parents=True)
        review_page.write_text(uc.retained_page(review, 'Location review', 'Location unconfirmed', index=False))
        before = {path: uc.target_file(self.site, path).read_text() for path in [*preserved, review]}
        uc.prepare(self.root)
        uc.finalize(self.root, self.site)
        for path, text in before.items():
            self.assertEqual(text, uc.target_file(self.site, path).read_text())
            self.assertEqual(path != review, uc.ORIGIN + path in (self.site / 'sitemap.xml').read_text())
        uc.verify(self.site)

    def test_malformed_same_origin_event_link_still_fails_validation(self):
        self.page(self.path)
        self.page('/shows/', '<a href="https://kingdomcircuit.com/event/../../">Invalid local link</a>')
        uc.prepare(self.root)
        with self.assertRaisesRegex(ValueError, 'Invalid retained URL path'):
            uc.finalize(self.root, self.site)

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
