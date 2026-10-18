import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import publish_chh_game as game


class GameReleaseTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / 'approved'
        source_game = self.source / 'test-overrides/chh-show-night'
        source_game.mkdir(parents=True)
        files = {'index.html': b'<title>Kingdom Circuit Test</title><meta name="robots" content="noindex,nofollow"><meta name="score-service" content="https://script.google.com/macros/s/test/exec"><meta http-equiv="Content-Security-Policy" content="connect-src https://script.googleusercontent.com"><script type="module" src="/play/game.mjs"></script><p>CHH SHOW NIGHT \xc2\xb7 TEST PREVIEW</p>',
                 'game.mjs': b"export const title='CHH SHOW NIGHT \xc2\xb7 TEST PREVIEW';", 'art.webp': b'approved-artwork'}
        for name, data in files.items():
            (source_game / name).write_bytes(data)
        manifest = json.dumps({name: hashlib.sha256(data).hexdigest() for name, data in files.items()}).encode()
        (self.source / 'test-overrides/chh-show-night-manifest.json').write_bytes(manifest)
        self.release = {'manifestSHA256': game.digest(manifest), 'fileCount': 3, 'sourceCommit': 'approved'}
        self.site = self.root / 'site'
        self.site.mkdir()
        (self.site / 'CNAME').write_text('kingdomcircuit.com')
        (self.site / 'index.html').write_text('<title>Existing live calendar</title>')
        (self.site / 'robots.txt').write_text('User-agent: *\nAllow: /\n')
        (self.site / 'sitemap.xml').write_text('<urlset/>')
        self.baseline = self.root / 'baseline.json'

    def build(self):
        return game.build(self.site, self.source, self.baseline, self.release)

    def test_live_release_changes_only_game_and_test_labels(self):
        before = game.inventory(self.site)
        self.build()
        self.assertEqual(game.inventory(self.site, exclude_game=True), before)
        self.assertNotIn('TEST PREVIEW', (self.site / 'play/index.html').read_text())
        self.assertEqual((self.site / 'play/art.webp').read_bytes(), b'approved-artwork')
        self.assertIn('noindex,nofollow', (self.site / 'play/index.html').read_text())

    def test_rejects_changed_approved_source_and_extra_files(self):
        path = self.source / 'test-overrides/chh-show-night/art.webp'
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(AssertionError, 'source mismatch'): self.build()
        path.write_bytes(b'approved-artwork')
        (path.parent / '.env').write_text('secret')
        with self.assertRaisesRegex(AssertionError, 'source files'): self.build()

    def test_rejects_missing_files_or_existing_page_changes(self):
        self.build()
        (self.site / 'index.html').write_text('Changed calendar')
        with self.assertRaisesRegex(AssertionError, 'existing live file changed'):
            game.verify(self.site, self.source, self.baseline, self.release)

    def test_rejects_overwrite_and_public_baseline(self):
        with self.assertRaisesRegex(AssertionError, 'outside'):
            game.build(self.site, self.source, self.site / 'private.json', self.release)
        self.build()
        with self.assertRaisesRegex(AssertionError, 'overwrite'): self.build()

    def test_workflow_pins_release_and_verifies_after_other_site_mutations(self):
        workflow = (game.ROOT / '.github/workflows/update-and-deploy.yml').read_text()
        self.assertIn('APPROVED_GAME_REF: ' + game.RELEASE['sourceCommit'], workflow)
        build = workflow.index('python scripts/publish_chh_game.py _site')
        self.assertGreater(build, workflow.index('python scripts/finalize_sold_out_artwork.py _site'))
        self.assertLess(build, workflow.index('uses: actions/upload-pages-artifact'))
        self.assertIn('node --test _game_source/tests/chh-game/*.test.mjs', workflow)


if __name__ == '__main__':
    unittest.main()
