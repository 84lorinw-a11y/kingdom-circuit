import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import permanent_state_pages as states
from build_seo_site import event_path
from finalize_seo_indexing_core import classify


class PermanentStateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "source"; self.source.mkdir()
        self.site = self.root / "site"; self.site.mkdir()
        (self.source / "config").mkdir()
        (self.source / states.REGISTRY).write_text(json.dumps({"version": 1, "states": ["PA", "PR"]}))
        (self.site / "shows").mkdir()
        (self.site / "shows/index.html").write_text('<html><head></head><body><main><h1>All Shows</h1></main></body></html>')
        (self.site / "config").mkdir()
        (self.site / "config/artists.json").write_text('[{"name":"KB"}]')

    def event(self, **kwargs):
        return dict(id="real-1", title="Confirmed concert", startDate="2026-09-01",
                    city="Pittsburgh", state="PA", artists=["KB"], confidence="high", **kwargs)

    def fixture(self, events=()):
        for code in ["PA", "PR"]:
            states.write_empty_page(self.site, code)
        for event in events:
            path = event_path(event)
            target = self.site / path.strip("/") / "index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f'<link rel="canonical" href="https://kingdomcircuit.com{path}"><h1>Past show</h1>')
        (self.site / "sitemap.xml").write_text("".join(
            f'<loc>https://kingdomcircuit.com{states.state_path(code)}</loc>' for code in ["PA", "PR"]))

    def test_registry_survives_empty_sources_and_repeated_rollover(self):
        (self.source / "events.json").write_text(json.dumps([dict(self.event(), state="WV")]))
        self.assertEqual(states.sync_registry(self.source), ["PA", "PR", "WV"])
        (self.source / "events.json").write_text("[]")
        self.assertEqual(states.sync_registry(self.source), ["PA", "PR", "WV"])
        first = (self.source / states.REGISTRY).read_bytes()
        states.sync_registry(self.source)
        self.assertEqual(first, (self.source / states.REGISTRY).read_bytes())

    def test_rejected_test_foreign_and_invalid_regions_do_not_create_pages(self):
        events = [dict(self.event(), id="bandsintown:108743066", state="AK"),
                  dict(self.event(), title="Test event", state="HI"),
                  dict(self.event(), country="CA", state="BC"),
                  dict(self.event(), state="../../unsafe"),
                  dict(self.event(), artists=["Propaganda"], state="VT")]
        (self.source / "events.json").write_text(json.dumps(events))
        self.assertEqual(states.discover_codes(self.source), ["PA", "PR"])

    def test_history_restores_established_state_even_without_upcoming(self):
        (self.source / "event-history.json").write_text(json.dumps({"events": [{"event": dict(self.event(), state="WI")}]}))
        self.assertEqual(states.discover_codes(self.source), ["PA", "PR", "WI"])

    def test_empty_message_canonical_links_and_full_archive_are_repeat_safe(self):
        events = [dict(self.event(), id=f"real-{i}", title=f"Confirmed concert {i}") for i in range(15)]
        self.fixture(events)
        stats = states.finalize(self.site, self.source, history=events)
        self.assertEqual(stats, {"statePages": 2, "archivedStateRows": 15})
        page = self.site / "shows/pennsylvania/index.html"
        text = page.read_text()
        self.assertIn("Stay tuned for more shows", text)
        self.assertIn("Check back for new Pennsylvania dates", text)
        self.assertIn('href="/shows/">Explore All Shows', text)
        self.assertIn("15 archived shows", text)
        self.assertEqual(text.count('class="past-show-row"'), 15)
        before = {p: p.read_bytes() for p in self.site.rglob("*.html")}
        states.finalize(self.site, self.source, history=events)
        states.finalize(self.site, self.source, history=events, check=True)
        self.assertTrue(all(p.read_bytes() == data for p, data in before.items()))
        self.assertEqual(states.state_path("PR"), "/shows/pr/")
        self.assertTrue(classify("/shows/pr/", "")[0])
        self.assertIn('href="/shows/pennsylvania/"', (self.site / "shows/index.html").read_text())

    def test_new_upcoming_shows_use_existing_url_without_empty_message(self):
        self.fixture()
        page = self.site / "shows/pennsylvania/index.html"
        text = page.read_text().replace(states.empty_calendar("PA"), '<article data-event-card="real-2">Upcoming concert</article>')
        page.write_text(text)
        states.finalize(self.site, self.source, history=[])
        self.assertNotIn('data-state-empty=', page.read_text())
        self.assertIn('https://kingdomcircuit.com/shows/pennsylvania/', page.read_text())

    def test_gate_rejects_missing_page_message_sitemap_and_stale_empty(self):
        self.fixture()
        page = self.site / "shows/pennsylvania/index.html"
        original = page.read_text()
        page.unlink()
        with self.assertRaisesRegex(ValueError, "page missing"):
            states.finalize(self.site, self.source, history=[])
        page.write_text(original.replace('data-state-empty="PA"', 'data-other="PA"'))
        with self.assertRaisesRegex(ValueError, "message missing"):
            states.finalize(self.site, self.source, history=[])
        page.write_text(original + '<article data-event-card>New show</article>')
        with self.assertRaisesRegex(ValueError, "remained with upcoming"):
            states.finalize(self.site, self.source, history=[])
        page.write_text(original)
        states.finalize(self.site, self.source, history=[])
        (self.site / "sitemap.xml").write_text("")
        with self.assertRaisesRegex(ValueError, "indexing metadata"):
            states.finalize(self.site, self.source, history=[], check=True)

    def test_workflow_survives_source_pruning_and_late_overlays(self):
        workflow = (ROOT / ".github/workflows/update-and-deploy.yml").read_text()
        self.assertLess(workflow.index("Remember permanent state pages"), workflow.index("Remove completed shows from source data"))
        self.assertLess(workflow.index("Apply approved mobile-first live redesign"), workflow.index("Preserve permanent state navigation"))
        self.assertLess(workflow.index("Preserve permanent state navigation"), workflow.index("Refresh final production indexing"))
        self.assertLess(workflow.index("Verify permanent state pages"), workflow.index("Upload Pages artifact"))
        self.assertIn("full-scan-candidates.json config/permanent-state-pages.json", workflow)


if __name__ == "__main__":
    unittest.main()
