"""Publishing must not present a rebuild date as a page modification date."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import finalize_seo_indexing_core as indexing
from verify_live_redesign import verify_sitemap_dates

NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


class SitemapDateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.site = Path(temporary.name)

    def page(self, path, canonical=None, body=""):
        target = self.site / path.strip("/") / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            '<html><head><link rel="canonical" href="'
            + indexing.SITE_ORIGIN + (canonical or path)
            + '"></head><body>' + body + '</body></html>', encoding="utf-8"
        )

    def finalize(self):
        with contextlib.redirect_stdout(io.StringIO()):
            indexing.apply(self.site)
        return (self.site / "sitemap.xml").read_text(encoding="utf-8")

    def test_finalization_preserves_urls_without_build_dates_on_repeat_refresh(self):
        assets = self.site / "assets"
        assets.mkdir()
        (assets / "brand-live.css").write_text("/* test */")
        (assets / "logo-wordmark.svg").write_text("<svg/>")
        paths = {"/", "/shows/", "/artists/", "/festivals/", "/event/confirmed-show/"}
        paths.update(f"/artists/artist-{i}/" for i in range(350))
        for path in paths:
            self.page(path)
        self.page("/event/old-show/", canonical="/event/confirmed-show/")
        for excluded in ("/event/", "/artists/profile/", "/shows/empty-city/",
                         "/artists/artist-0/texas/"):
            self.page(excluded)
        (self.site / "sitemap.xml").write_text(
            '<urlset><url><loc>https://kingdomcircuit.com/</loc>'
            '<lastmod>2026-10-03</lastmod></url></urlset>'
        )

        first = self.finalize()
        root = ET.fromstring(first)
        urls = [node.text for node in root.findall("s:url/s:loc", NS)]
        self.assertEqual(sorted(indexing.SITE_ORIGIN + path for path in paths), urls)
        self.assertFalse(root.findall(".//s:lastmod", NS))
        verify_sitemap_dates(self.site)

        pages = {path: path.read_bytes() for path in self.site.rglob("*.html")}
        self.assertEqual(first, self.finalize())
        self.assertTrue(all(path.read_bytes() == data for path, data in pages.items()))

        # Later content additions must remain discoverable, still without an invented date.
        self.page("/event/new-confirmed-show/")
        refreshed = ET.fromstring(self.finalize())
        self.assertEqual(len(paths) + 1, len(refreshed.findall("s:url", NS)))
        self.assertIn(indexing.SITE_ORIGIN + "/event/new-confirmed-show/",
                      [node.text for node in refreshed.findall("s:url/s:loc", NS)])
        verify_sitemap_dates(self.site)

    def test_final_release_gate_rejects_reintroduced_dates(self):
        for namespace in ('', ' xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'):
            with self.subTest(namespace=namespace):
                (self.site / "sitemap.xml").write_text(
                    f'<urlset{namespace}><url><loc>https://kingdomcircuit.com/</loc>'
                    '<lastmod>2026-10-03</lastmod></url></urlset>'
                )
                with self.assertRaisesRegex(ValueError, "lastmod must be omitted"):
                    verify_sitemap_dates(self.site)


if __name__ == "__main__":
    unittest.main()
