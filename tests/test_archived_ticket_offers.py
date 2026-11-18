import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import url_continuity as uc


class ArchivedTicketOfferTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.site = self.root / '_site'
        self.site.mkdir()
        self.path = '/event/recorded-concert/'
        self.event = {'id': 'manual:old', 'startDate': '2026-11-17',
                      'title': 'Recorded concert', 'city': 'Miami', 'state': 'FL'}
        self.state = uc.empty_state()
        self.state['events'][self.event['id']] = {'path': self.path, 'event': self.event}
        self.schema = {'@context': 'https://schema.org', '@graph': [
            {'@type': ['Event', 'MusicEvent'], 'name': 'Recorded concert',
             'startDate': '2026-11-17T19:00:00-05:00',
             'offers': {'@type': 'Offer', 'url': 'https://tickets.example/expired'}},
            {'@type': 'Organization', 'name': 'Promoter'}]}

    def page(self, schema=None, canonical=None):
        schema = self.schema if schema is None else schema
        text = ('<html><head><meta name="robots" content="index,follow">'
                f'<link rel="canonical" href="{uc.ORIGIN + (canonical or self.path)}">'
                '<script type="application/ld+json">' + json.dumps(schema) + '</script>'
                '</head><body><main><h1>Recorded concert</h1><p>Past show</p>'
                '<img src="/original.jpg" alt="Original poster">'
                '<a href="https://official.example/history">Official details</a>'
                '</main></body></html>')
        file = uc.target_file(self.site, self.path)
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)
        return file

    def test_expired_offer_removed_without_visible_or_historical_fact_changes(self):
        file = self.page()
        before = uc.PageFacts(file.read_text())
        saved_state = copy.deepcopy(self.state)
        report = uc.remove_expired_ticket_offers(self.site, self.state, {}, '2026-11-18')
        self.assertEqual({'changedPages': 1, 'expiredEventPaths': [self.path]}, report)
        after = uc.PageFacts(file.read_text())
        self.assertEqual(before.values, after.values)
        expected = copy.deepcopy(self.schema)
        del expected['@graph'][0]['offers']
        self.assertEqual([expected], after.schemas)
        self.assertEqual(saved_state, self.state)
        output = file.read_bytes()
        self.assertEqual(0, uc.remove_expired_ticket_offers(self.site, self.state, {}, '2026-11-18')['changedPages'])
        self.assertEqual(output, file.read_bytes())

    def test_current_catalog_and_noncanonical_pages_preserved(self):
        file = self.page()
        before = file.read_bytes()
        uc.save(self.site / 'assets/fan-show-catalog.json', {'shows': [{'path': self.path}]})
        self.assertEqual([], uc.remove_expired_ticket_offers(self.site, self.state, {}, '2026-11-18')['expiredEventPaths'])
        self.assertEqual(before, file.read_bytes())
        uc.save(self.site / 'assets/fan-show-catalog.json', {'shows': []})
        self.page(canonical='/event/current-canonical/')
        before = file.read_bytes()
        self.assertEqual(0, uc.remove_expired_ticket_offers(self.site, self.state, {}, '2026-11-18')['changedPages'])
        self.assertEqual(before, file.read_bytes())

    def test_authoritative_dates_multiday_unknown_and_pacific_end_boundary(self):
        for changes, removed in [
                ({'startDate': '2026-11-18'}, False),
                ({'startDate': '2026-11-17', 'endDate': '2026-11-19'}, False),
                ({'startDate': ''}, False),
                ({'startDate': '2026-11-17', 'endDate': '2026-11-18',
                  'endDateTime': '2026-11-18T01:00:00-05:00'}, True)]:
            with self.subTest(changes=changes):
                file = self.page()
                event = dict(self.event, **changes)
                before = file.read_bytes()
                result = uc.remove_expired_ticket_offers(self.site, self.state, {self.event['id']: event}, '2026-11-18')
                self.assertEqual(int(removed), result['changedPages'])
                if not removed:
                    self.assertEqual(before, file.read_bytes())

    def test_later_reintroduced_offer_is_rejected_by_verifier(self):
        file = self.page()
        uc.save(self.site / 'url-continuity-manifest.json', {'expiredEventPaths': [self.path]})
        with self.assertRaisesRegex(ValueError, 'Expired event retains ticket Offer'):
            uc.verify(self.site)
        uc.save(self.site / 'assets/fan-show-catalog.json', {'shows': [{'path': self.path}]})
        with self.assertRaisesRegex(ValueError, 'Current catalog page marked as expired'):
            uc.verify(self.site)

    def test_finalize_records_cleanup_before_content_fingerprint_and_survives_rebuild(self):
        file = self.page()
        uc.save(self.root / uc.STATE_FILE, self.state)
        uc.save(self.root / 'events.json', [])
        uc.save(self.root / 'supplemental-events.json', [])
        uc.save(self.root / 'config/artists.json', [])
        # Keep the fixture's canonical retained address, even though its generated
        # descriptive path differs. The current catalog deliberately has no rows.
        uc.save(self.site / 'assets/fan-show-catalog.json', {'shows': []})
        uc.finalize(self.root, self.site, today='2026-11-18')
        receipt = uc.load(self.site / 'url-continuity-manifest.json', {})
        self.assertIn(self.path, receipt['expiredEventPaths'])
        self.assertEqual(uc.PageFacts(file.read_text()).fingerprint(), receipt['pages'][self.path]['fingerprint'])
        self.assertNotIn('offers', uc.PageFacts(file.read_text()).schemas[0]['@graph'][0])
        snapshot = {str(p.relative_to(self.site)): p.read_bytes() for p in self.site.rglob('*.html')}
        uc.finalize(self.root, self.site, today='2026-11-18')
        self.assertEqual(snapshot, {str(p.relative_to(self.site)): p.read_bytes() for p in self.site.rglob('*.html')})


if __name__ == '__main__':
    unittest.main()
