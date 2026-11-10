"""Regression cases for final, immutable publication acceptance."""
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import publication_audit as audit


class FinalPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.site = Path(self.temp.name)

    def put(self, path, text):
        file = self.site / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)
        return file

    def page(self, path='/', robots='index,follow', extra=''):
        return ('<html><head><title>Concerts</title><meta name="robots" content="' + robots + '">'
                '<link rel="canonical" href="https://kingdomcircuit.com' + path + '"></head>'
                '<body><main><h1>Concerts</h1>' + extra + '</main></body></html>')

    def documents(self):
        return audit.audit_documents(self.site, {}, {'https://kingdomcircuit.com/'})

    def test_late_writer_noindex_or_canonical_change_blocks_sitemap_page(self):
        self.put('index.html', self.page())
        self.assertEqual(self.documents()['errors'], [])
        self.put('index.html', self.page(robots='noindex,follow'))
        self.assertIn('sitemap_nonindexable_or_noncanonical', [e['kind'] for e in self.documents()['errors']])
        self.put('index.html', self.page('/wrong/'))
        self.assertIn('canonical_mismatch', [e['kind'] for e in self.documents()['errors']])

    def test_malformed_schema_blocks_release_instead_of_being_ignored(self):
        self.put('index.html', self.page(extra='<script type="application/ld+json">{bad}</script>'))
        self.assertIn('invalid_jsonld_or_html_parse', [e['kind'] for e in self.documents()['errors']])

    def test_missing_internal_landing_page_blocks_acceptance(self):
        self.put('index.html', self.page(extra='<a href="/shows/missing-city/">Shows</a>'))
        self.assertIn('missing_internal_link_target', [e['kind'] for e in self.documents()['errors']])

    def test_missing_sitemap_entry_cannot_silently_hide_indexable_artist(self):
        self.put('index.html', self.page())
        self.put('artists/test/index.html', self.page('/artists/test/'))
        self.assertIn('indexable_page_missing_from_sitemap', [e['kind'] for e in self.documents()['errors']])

    def test_deleted_or_blocking_robots_cannot_be_accepted(self):
        self.assertTrue(audit.robots_errors(self.site, ['/']))
        self.put('robots.txt', 'User-agent: *\nAllow: /\nSitemap: https://kingdomcircuit.com/sitemap.xml\n')
        self.assertEqual(audit.robots_errors(self.site, ['/', '/artists/test/']), [])
        self.put('robots.txt', 'User-agent: *\nDisallow: /artists/\nSitemap: https://kingdomcircuit.com/sitemap.xml\n')
        errors = audit.robots_errors(self.site, ['/', '/artists/test/'])
        self.assertIn('robots_blocks_public_page', [e['kind'] for e in errors])

    def test_registry_image_paths_are_site_relative_not_config_relative(self):
        self.put('index.html', self.page())
        self.put('404.html', 'not found')
        self.put('config/artists.json', '[{"image":"assets/portrait.webp"}]')
        self.put('assets/portrait.webp', 'portrait bytes')
        manifest, errors = audit.build_manifest(self.site, 'release', '2026-11-09', {'/'})
        self.assertEqual(errors, [])
        self.assertIn('/assets/portrait.webp', manifest['files'])

    def test_private_booking_cannot_leak_event_schema(self):
        errors = audit.event_fact_errors('/event/private/', {'private': True}, [{'@type': 'MusicEvent'}])
        self.assertEqual(errors[0]['kind'], 'private_or_unconfirmed_event_schema')
        self.assertEqual(audit.event_fact_errors('/event/private/', {'private': True}, []), [])

    def test_final_private_canonical_is_checked_without_requiring_old_alias_copy(self):
        text = self.page('/event/private/', extra='<p class="kc-admission-restriction">Private / invite-only event</p>')
        self.assertEqual(audit.private_page_errors('/event/private/', text), [])
        leaked = text.replace('</main>', '<script type="application/ld+json">{"@type":"Offer","price":0}</script></main>')
        self.assertIn('private_public_schema_leak', [e['kind'] for e in audit.private_page_errors('/event/private/', leaked)])

    def test_failed_cli_removes_stale_acceptance_and_saves_failure_receipt(self):
        self.put('publication-manifest.json', '{"old":"accepted"}')
        report = self.site / 'failure.json'
        result = subprocess.run([sys.executable, str(Path(audit.__file__)), '--site', str(self.site),
                                 '--release-id', 'test', '--report', str(report),
                                 '--summary', str(self.site / 'summary.md')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(report.read_text())['status'], 'failed')
        self.assertFalse((self.site / 'publication-manifest.json').exists())

    def test_schema_cannot_invent_price_time_or_performers(self):
        record = dict(title='Concert', schemaStartDate='2027-02-26', schemaEndDate=None, offer=None,
                      venue='Hall', venueLocality='Calgary', state='AB', country='CA',
                      artists=['Artist A'], unconfirmedArtists=['Guest B'])
        schema = dict(name='Concert', url='https://kingdomcircuit.com/event/a/', startDate='2027-02-26',
            eventStatus='https://schema.org/EventScheduled',
            eventAttendanceMode='https://schema.org/OfflineEventAttendanceMode', location={'name': 'Hall', 'address': {
            'addressLocality': 'Calgary', 'addressRegion': 'AB', 'addressCountry': 'CA'}},
            performer=[{'name': 'Artist A'}])
        self.assertEqual(audit.event_fact_errors('/event/a/', record, [schema]), [])
        schema.update(startDate='2027-02-26T20:00:00-07:00', offers={'price': 0})
        schema['performer'].append({'name': 'Guest B'})
        errors = audit.event_fact_errors('/event/a/', record, [schema])
        self.assertEqual({e.get('field') for e in errors if e['kind'] == 'source_schema_fact_mismatch'}, {'startDate', 'offers'})
        self.assertIn('performer_membership_mismatch', [e['kind'] for e in errors])
        del schema['name']
        del schema['url']
        errors = audit.event_fact_errors('/event/a/', record, [schema])
        self.assertTrue({'name', 'url'} <= {e.get('field') for e in errors})
        schema.update(eventStatus='https://schema.org/EventCancelled',
                      eventAttendanceMode='https://schema.org/OnlineEventAttendanceMode')
        errors = audit.event_fact_errors('/event/a/', record, [schema])
        self.assertTrue({'eventStatus', 'eventAttendanceMode'} <= {e.get('field') for e in errors})

    def test_manifest_covers_runtime_status_and_webmanifest_icons(self):
        self.put('index.html', self.page(extra='<link rel="manifest" href="/manifest.webmanifest">'))
        self.put('404.html', 'not found')
        self.put('manifest.webmanifest', '{"icons":[{"src":"/assets/icon.png"}]}')
        self.put('assets/icon.png', 'icon bytes')
        self.put('run-status.json', '{"status":"ok"}')
        manifest, errors = audit.build_manifest(self.site, 'release', '2026-11-09', {'/'})
        self.assertEqual(errors, [])
        self.assertIn('/assets/icon.png', manifest['files'])
        self.assertIn('/run-status.json', manifest['files'])

    def test_manifest_covers_nested_resources_and_preserves_site_bytes(self):
        self.put('index.html', self.page(extra='<link rel="stylesheet" href="/assets/a.css"><img src="/assets/flyer.webp">'))
        self.put('assets/a.css', '@font-face{src:url("font.woff2")}')
        self.put('assets/font.woff2', 'font bytes')
        self.put('assets/flyer.webp', 'flyer bytes')
        self.put('404.html', '<h1>Not found</h1>')
        before = {p: p.read_bytes() for p in self.site.rglob('*') if p.is_file()}
        manifest, errors = audit.build_manifest(self.site, 'release-1', '2026-11-09', {'/'})
        self.assertEqual(errors, [])
        self.assertEqual(set(manifest['files']), {'/', '/404.html', '/__publication-audit-not-found__/',
                                                 '/assets/a.css', '/assets/font.woff2', '/assets/flyer.webp'})
        self.assertEqual(manifest['files']['/assets/flyer.webp']['sha256'], hashlib.sha256(b'flyer bytes').hexdigest())
        self.assertEqual(manifest['files']['/__publication-audit-not-found__/']['status'], 404)
        self.assertEqual(before, {p: p.read_bytes() for p in self.site.rglob('*') if p.is_file()})

    def test_missing_current_image_fails_but_external_archive_art_is_not_fetched(self):
        self.put('index.html', self.page(extra='<img src="/assets/missing.webp">'))
        self.put('404.html', 'not found')
        self.put('event/past/index.html', self.page('/event/past/', extra='<img src="https://expired.example/art.jpg">'))
        _, errors = audit.build_manifest(self.site, 'release', '2026-11-09', {'/'})
        self.assertIn('/assets/missing.webp', [e.get('resource') for e in errors])
        self.assertFalse(any('expired.example' in str(e) for e in errors))

    def test_manifest_never_exposes_source_registry_or_follows_outside_site(self):
        self.put('index.html', self.page(extra='<script src="/../secret.js"></script>'))
        self.put('404.html', 'not found')
        self.put('config/private-notes.json', '{"private":true}')
        manifest, _ = audit.build_manifest(self.site, 'release', '2026-11-09', {'/'})
        self.assertNotIn('/config/private-notes.json', manifest['files'])


if __name__ == '__main__':
    unittest.main()
