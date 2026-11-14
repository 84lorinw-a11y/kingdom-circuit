import contextlib
from copy import deepcopy
from datetime import date
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_seo_site as builder
from page_render_cache import RenderCache, digest


class RenderCacheTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def cache(self, code='code-v1'):
        return RenderCache('fixture', root=self.root, code=code)

    def test_optional_cache_preserves_rendering_and_creates_no_storage(self):
        render = Mock(return_value='<p>current</p>')
        cache = RenderCache('fixture', root='')
        self.assertEqual(cache.render('page', {}, render), cache.render('page', {}, render))
        self.assertEqual(render.call_count, 2)
        self.assertEqual([], list(self.root.iterdir()))

    def test_cold_and_warm_result_is_exact_and_skips_renderer(self):
        value = {'/event/example/': '<h1>Show &amp; guests</h1>', '/event/old/': '<a href="/event/example/">Current</a>'}
        render = Mock(return_value=value)
        cache = self.cache()
        self.assertEqual(value, cache.render('event', {'record': {'id': 'one'}}, render, expected_paths=set(value)))
        self.assertEqual(value, self.cache().render('event', {'record': {'id': 'one'}}, render, expected_paths=set(value)))
        self.assertEqual(render.call_count, 1)

    def test_all_inputs_order_context_code_and_templates_invalidate(self):
        render = Mock(return_value='<p>rendered</p>')
        initial = {'shows': ['a', 'b'], 'template': '<main/>', 'year': 2026}
        self.cache().render('page', initial, render)
        for changed in [dict(initial, shows=['b', 'a']), dict(initial, template='<main class="new"/>'),
                        dict(initial, year=2027), dict(initial, shows=['a'])]:
            self.cache().render('page', changed, render)
        self.cache('new-code').render('page', initial, render)
        self.assertEqual(6, render.call_count)

    def test_corruption_and_unexpected_output_paths_are_cache_misses(self):
        expected = {'/event/current/': '<p>Current</p>'}
        for corruption in ('not JSON', '[]', 'null', 'digest', 'paths', 'duplicate'):
            with self.subTest(corruption=corruption):
                render = Mock(return_value=expected)
                cache = self.cache()
                cache.render(corruption, {}, render, expected_paths=set(expected))
                entry = max((self.root/'renders/v1').glob('*.json'), key=lambda p:p.stat().st_mtime_ns)
                if corruption in ('not JSON', '[]', 'null'):
                    entry.write_text(corruption)
                elif corruption == 'duplicate':
                    entry.write_text('{"value":"a","value":"b"}')
                else:
                    record = json.loads(entry.read_text())
                    record['value'] = {'/event/retired/': 'wrong'} if corruption == 'paths' else expected
                    record['sha256'] = digest(record['value']) if corruption == 'paths' else 'bad'
                    entry.write_text(json.dumps(record))
                self.assertEqual(expected, cache.render(corruption, {}, render, expected_paths=set(expected)))
                self.assertEqual(2, render.call_count)
                self.assertEqual(1, cache.counts['corrupt'])

    def test_symlink_roots_and_public_output_are_rejected(self):
        destination = self.root/'actual'
        destination.mkdir()
        link = self.root/'link'
        link.symlink_to(destination, target_is_directory=True)
        unsafe = RenderCache('fixture', root=link, code='v1')
        self.assertIsNone(unsafe.root)
        self.assertEqual('fresh', unsafe.render('page', {}, lambda:'fresh'))
        self.assertEqual([], list(destination.iterdir()))
        with self.assertRaisesRegex(ValueError, 'outside the public'):
            RenderCache('fixture', root=self.root/'_site/cache', public_root=self.root/'_site', code='v1')
        (destination/'renders').symlink_to(self.root, target_is_directory=True)
        self.assertIsNone(RenderCache('fixture', root=destination, code='v1').root)

    def test_symlink_entry_is_a_miss_and_target_is_untouched(self):
        cache = self.cache()
        cache.render('text', {}, lambda:'original')
        entry = next((self.root/'renders/v1').glob('*.json'))
        other = self.root/'external.json'
        other.write_bytes(entry.read_bytes())
        before = other.read_bytes()
        entry.unlink()
        entry.symlink_to(other)
        self.assertEqual('fresh', cache.render('text', {}, lambda:'fresh'))
        self.assertEqual(before, other.read_bytes())
        self.assertEqual(1, cache.counts['corrupt'])
        self.assertFalse(entry.is_symlink())

    def test_deep_json_and_nonregular_members_do_not_block_fresh_rendering(self):
        cache = self.cache()
        cache.render('text', {}, lambda:'original')
        entry = next((self.root/'renders/v1').glob('*.json'))
        entry.write_text('[' * 2000 + ']' * 2000)
        self.assertEqual('fresh', cache.render('text', {}, lambda:'fresh'))
        entry.unlink()
        os.mkfifo(entry)
        self.assertEqual('fresh', cache.render('text', {}, lambda:'fresh'))
        self.assertEqual(2, cache.counts['corrupt'])
        report = self.root/'report.json'
        report.write_text('[' * 2000 + ']' * 2000)
        cache.report = report
        cache.finish()
        self.assertEqual(1, json.loads(report.read_text())['version'])

    def test_unavailable_cache_does_not_block_rendering(self):
        cache = self.cache()
        with patch('page_render_cache.atomic_json', side_effect=OSError('unavailable')):
            self.assertEqual('fresh', cache.render('text', {}, lambda:'fresh'))
        self.assertEqual(1, cache.counts['writeErrors'])

    def test_pure_wrapper_keeps_full_arguments_and_context(self):
        render = Mock(side_effect=lambda name, shows: name + str(shows))
        context = {'year': 2026}
        wrapped = self.cache().wrap('artist', render, context=lambda: context)
        before = wrapped('Artist', [{'id':'a', 'venue':'Original'}])
        self.assertEqual(before, wrapped('Artist', [{'id':'a', 'venue':'Original'}]))
        wrapped('Artist', [{'id':'a', 'venue':'Changed'}])
        context['year'] = 2027
        wrapped('Artist', [{'id':'a', 'venue':'Original'}])
        self.assertEqual(3, render.call_count)

    def test_reports_accumulate_separate_stage_counts_outside_site(self):
        report = self.root/'incremental-page-build.json'
        for stage in ('base-seo', 'approved-seo'):
            cache = RenderCache(stage, root=self.root, report=report, code='same')
            cache.render('text', {}, lambda:'output')
            cache.finish()
        value = json.loads(report.read_text())
        self.assertEqual({'base-seo','approved-seo'}, set(value['stages']))
        self.assertTrue(all(s['misses'] == 1 for s in value['stages'].values()))


class BasePageCacheIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.source = self.directory/'source'
        self.source.mkdir()
        self.cache = self.directory/'cache'
        self.artists = [{'name':f'Fixture Artist {n}', 'enabled':True} for n in range(400)]
        self.events = [{'id':f'fixture:{n}', 'title':f'Fixture Concert {n}', 'startDate':'2026-12-20',
                        'city':f'Fixture City {n}', 'state':'TX', 'country':'US', 'venue':'Hall',
                        'artists':[self.artists[n]['name']], 'status':'scheduled',
                        'officialUrl':f'https://example.com/show/{n}', 'firstSeen':'2026-11-14T00:00:00Z'} for n in range(22)]
        self.events[0]['startDate'] = '2026-11-14'
        self.events[0]['legacyEventPaths'] = ['/event/fixture-old/']
        self.save('config/artists.json', self.artists)
        self.save('events.json', self.events)
        self.save('supplemental-events.json', [])
        self.save('config/permanent-state-pages.json', {'version':1,'states':['TX']})
        self.save('event-history.json', {'events':[]})
        (self.source/'CNAME').write_text('kingdomcircuit.com')
        (self.source/'app.js').write_text('function eventDetailUrl(event) {\nreturn "";\n}\nfunction artistProfileUrl(name) {\nreturn "";\n}\n')
        template = '<html><head><title>Fixture</title><meta name="description" content="Fixture"><meta name="robots" content="index,follow"></head><body><main><div class="event-grid" data-event-grid></div><div class="artist-grid" data-artist-grid></div></main></body></html>'
        for rel in ['index.html','shows/index.html','shows/this-month/index.html','festivals/index.html','new-shows/index.html','artists/index.html']:
            path=self.source/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(template)

    def save(self, relative, data):
        path=self.source/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data))

    def build(self, day='2026-11-14', cached=True):
        with patch.multiple(builder, REPO=self.source, OUT=self.source/'_site', TODAY=date.fromisoformat(day), VISIBILITY_CUTOFF=date.fromisoformat(day)), \
             patch.dict(os.environ, {'KC_BUILD_CACHE_DIR':str(self.cache) if cached else ''}), contextlib.redirect_stdout(io.StringIO()):
            builder.main()
        return {p.relative_to(self.source/'_site').as_posix():p.read_bytes() for p in (self.source/'_site').rglob('*')
                if p.is_file() and p.name!='seo-build-manifest.json'}

    def test_cold_warm_and_uncached_builds_are_byte_identical(self):
        uncached=self.build(cached=False)
        cold=self.build()
        with patch.object(builder,'render_event_pages',side_effect=AssertionError('event renderer ran')), \
             patch.object(builder,'render_artist_pages',side_effect=AssertionError('artist renderer ran')):
            warm=self.build()
        self.assertEqual(uncached,cold)
        self.assertEqual(cold,warm)
        self.assertNotIn('incremental-page-build.json',warm)
        report=json.loads((self.source/'incremental-page-build.json').read_text())['stages']['base-seo']
        self.assertEqual(422,report['hits'])
        self.assertEqual(0,report['misses'])

    def test_verification_metadata_reuses_events_artists_and_merged_targets(self):
        for event in self.events:
            event['lastVerified'] = '2026-11-13'
        alias = dict(self.events[0], id='fixture:merged', status='merged', mergedIntoId=self.events[0]['id'])
        self.save('events.json', self.events)
        self.save('supplemental-events.json', [alias])
        with patch.object(builder, 'render_event_pages', wraps=builder.render_event_pages) as renders:
            before = self.build()
        self.assertTrue(all(call.args[0]['lastVerified'] == '2026-11-13' for call in renders.call_args_list))
        for event in self.events:
            event['lastVerified'] = '2026-11-14'
        alias['lastVerified'] = '2026-11-14'
        self.save('events.json', self.events)
        self.save('supplemental-events.json', [alias])
        with patch.object(builder, 'render_event_pages', side_effect=AssertionError('metadata rendered an event')), \
             patch.object(builder, 'render_artist_pages', side_effect=AssertionError('metadata rendered an artist')):
            after = self.build()
        self.assertEqual({k:v for k,v in before.items() if k.endswith('.html')},
                         {k:v for k,v in after.items() if k.endswith('.html')})
        self.assertEqual(after, self.build(cached=False))
        self.assertEqual('2026-11-14', json.loads(after['events.json'])[0]['lastVerified'])
        self.assertEqual('2026-11-14', json.loads(after['supplemental-events.json'])[0]['lastVerified'])
        self.assertTrue(all(event['lastVerified'] == '2026-11-14' for event in self.events))

    def test_metadata_exclusion_is_narrow_and_preserves_anonymous_url_dependencies(self):
        original = dict(self.events[0], lastVerified='2026-11-13', unknownFutureFact='one')
        changed = dict(original, lastVerified='2026-11-14')
        self.assertEqual(builder.event_render_key(original), builder.event_render_key(changed))
        self.assertNotEqual(builder.event_render_key(original),
                            builder.event_render_key(dict(original, unknownFutureFact='two')))
        self.assertEqual('2026-11-13', original['lastVerified'])
        for identity in (None, '', 17):
            with self.subTest(identity=identity):
                before = dict(original, id=identity)
                after = dict(changed, id=identity)
                self.assertNotEqual(builder.event_render_key(before), builder.event_render_key(after))
                if not identity:
                    self.assertNotEqual(builder.event_path(before), builder.event_path(after))
                    self.assertNotEqual(builder.render_event_pages(before, self.artists),
                                        builder.render_event_pages(after, self.artists))

    def test_changed_event_rebuilds_its_page_and_artist_without_touching_other_renderers(self):
        before=self.build()
        self.events[0]['venue']='Updated reviewed hall'
        self.save('events.json',self.events)
        with patch.object(builder,'render_event_pages',wraps=builder.render_event_pages) as events, \
             patch.object(builder,'render_artist_pages',wraps=builder.render_artist_pages) as artists:
            after=self.build()
        self.assertEqual([self.events[0]], [call.args[0] for call in events.call_args_list])
        self.assertEqual([self.artists[0]], [call.args[0] for call in artists.call_args_list])
        other=builder.artist_path(self.artists[1]['name']).strip('/')+'/index.html'
        self.assertEqual(before[other],after[other])
        self.assertEqual(after,self.build(cached=False))

    def test_rollover_and_removals_do_not_resurrect_cached_paths(self):
        self.build()
        original_path=builder.event_path(self.events[0]).strip('/')+'/index.html'
        after=self.build('2026-11-15')
        self.assertNotIn(original_path,after)
        self.assertNotIn('event/fixture-old/index.html',after)
        profile=after[builder.artist_path(self.artists[0]['name']).strip('/')+'/index.html'].decode()
        self.assertIn('0 upcoming U.S. shows',profile)
        self.assertEqual(after,self.build('2026-11-15',cached=False))
        self.artists[-1]['enabled']=False
        self.save('config/artists.json',self.artists)
        after=self.build('2026-11-15')
        self.assertNotIn(builder.artist_path(self.artists[-1]['name']).strip('/')+'/index.html',after)

    def test_alias_resolution_and_merged_targets_are_preserved(self):
        artists=[{'name':'Canonical', 'aliases':['Guest']}, {'name':'Other','aliases':['Guest']}]
        event=dict(self.events[0], artists=['Guest'],advertisedBilling=['Guest'])
        selected=builder.relevant_artists([event],artists)
        self.assertEqual(builder.render_event_pages(event,artists),builder.render_event_pages(event,selected))
        merged=dict(event,id='alias',status='merged',mergedIntoId=self.events[1]['id'])
        pages=builder.render_event_pages(merged,selected,self.events[1])
        self.assertEqual({builder.event_path(merged)},set(pages))
        self.assertIn(builder.event_path(self.events[1]),next(iter(pages.values())))
        with self.assertRaisesRegex(ValueError,'no surviving page'):
            builder.render_event_pages(merged,selected)


if __name__=='__main__':
    unittest.main()
