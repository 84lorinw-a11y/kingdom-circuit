import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import finalize_fan_discovery as release


class ProductionIdentityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.site = Path(self.directory.name)
        (self.site / 'CNAME').write_text('kingdomcircuit.com\n')
        (self.site / 'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: https://kingdomcircuit.com/sitemap.xml\n')
        (self.site / 'index.html').write_text('<html><head><meta name="robots" content="index,follow"><link rel="canonical" href="https://kingdomcircuit.com/"><script>const id="G-N2KK9XF4TJ";</script></head><body></body></html>')

    def test_accepts_live_identity_and_keeps_intentional_noindex_on_other_pages(self):
        (self.site / 'private.html').write_text('<meta name="robots" content="noindex,follow">')
        release.production_identity(self.site)

    def test_rejects_sitewide_crawl_block(self):
        with (self.site / 'robots.txt').open('a') as out:
            out.write('Disallow: /\n')
        with self.assertRaisesRegex(AssertionError, 'blocked'):
            release.production_identity(self.site)

    def test_rejects_preview_analytics_or_links(self):
        for marker in release.FORBIDDEN:
            with self.subTest(marker=marker):
                (self.site / 'extra.js').write_text(marker)
                with self.assertRaisesRegex(AssertionError, 'Test leak'):
                    release.production_identity(self.site)

    def test_rejects_noindex_home(self):
        path = self.site / 'index.html'
        path.write_text(path.read_text().replace('index,follow', 'noindex,follow'))
        with self.assertRaises(AssertionError):
            release.production_identity(self.site)

    def test_only_two_new_pages_are_allowed(self):
        self.assertEqual({p for p in release.NEW_FILES if p.endswith('.html')},
                         {'about-us/index.html', 'shows/this-weekend/index.html'})


if __name__ == '__main__':
    unittest.main()
