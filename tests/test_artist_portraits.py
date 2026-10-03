from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import artist_portraits as portraits
import optimize_public_images as optimizer
import sync_verified_artist_registry as sync


class ArtistPortraitTests(unittest.TestCase):
    def fixture(self, root):
        (root / 'config').mkdir()
        (root / 'assets/artists').mkdir(parents=True)
        (root / 'artists/kb').mkdir(parents=True)
        data = b'fixture image; codec validation is performed by the real release gate'
        (root / 'assets/artists/kb.jpg').write_bytes(data)
        records = {'KB': {'asset': 'assets/artists/kb.jpg', 'sha256': hashlib.sha256(data).hexdigest(),
                          'width': 640, 'height': 640, 'position': 'center'}}
        for path, value in [('config/artists.json', [{'name': 'KB', 'imageUrl': 'assets/artists/kb.jpg'}]),
                            (str(portraits.PORTRAITS), records),
                            (str(portraits.OVERRIDES), {'KB': 'assets/artists/kb.jpg'})]:
            (root / path).write_text(json.dumps(value))
        (root / 'artists/index.html').write_text('<a class="artist-visual"><img alt="KB" src="/assets/artists/kb.jpg"></a>')
        (root / 'artists/kb/index.html').write_text('<div class="kc-rd-profile-visual"><img alt="KB" src="/assets/artists/kb.jpg"></div>')
        return records

    def test_stale_refresh_preserves_saved_photo_and_other_artist_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            saved = portraits.load_portraits(root)
            rows = [{'name': 'KB', 'imageUrl': 'https://unavailable.example/photo.jpg',
                     'instagramProfile': 'https://instagram.com/kb_hga/', 'rosterOrder': 3}]
            portraits.apply_to_records(rows, saved)
            self.assertEqual(rows[0]['imageUrl'], 'assets/artists/kb.jpg')
            self.assertEqual(rows[0]['rosterOrder'], 3)
            self.assertEqual(rows[0]['instagramProfile'], 'https://instagram.com/kb_hga/')
            self.assertEqual(portraits.apply_to_records(rows, saved), 0)

    def test_missing_and_corrupt_saved_files_block_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            asset = root / 'assets/artists/kb.jpg'
            asset.write_bytes(b'broken')
            with self.assertRaisesRegex(ValueError, 'corrupt'):
                portraits.load_portraits(root)
            asset.unlink()
            with self.assertRaisesRegex(ValueError, 'missing'):
                portraits.load_portraits(root)

    def test_saved_portrait_persists_in_handoff_for_later_build_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = self.fixture(root)
            updates = root / 'config/verified-artist-registry-updates.json'
            updates.write_text(json.dumps([{'name': 'KB', 'rosterOrder': 1,
                                           'imageUrl': 'https://old.example/kb.jpg'}]))
            with (patch.object(sync, 'ROOT', root),
                  patch.object(sync, 'ARTISTS_FILE', root / 'config/artists.json'),
                  patch.object(sync, 'UPDATES_FILE', updates),
                  patch.object(sync, 'snapshot', return_value=[{'name': 'KB', 'verified': True}]),
                  patch.object(sync, 'order_records', side_effect=lambda rows: rows),
                  patch.object(sync, 'verify_records'),
                  patch.object(sync, 'apply_owner_roster'),
                  patch.object(sync, 'load_portraits', return_value=records)):
                sync.sync_config()
            self.assertEqual(json.loads(updates.read_text())[0]['imageUrl'], records['KB']['asset'])

    def test_catalog_remote_portrait_blocks_release_even_when_html_is_correct(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(portraits, 'decode_image', return_value=(640, 640)):
            root = Path(tmp)
            self.fixture(root)
            (root / 'config/artists.json').write_text(json.dumps([
                {'name': 'KB', 'imageUrl': 'https://old.example/kb.jpg'}]))
            with self.assertRaisesRegex(ValueError, 'saved locally'):
                portraits.verify_site(root, root)

    def test_directory_placeholder_and_profile_regressions_block_release(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(portraits, 'decode_image', return_value=(640, 640)):
            root = Path(tmp)
            self.fixture(root)
            self.assertEqual(portraits.verify_site(root, root)['portraitElements'], 2)
            page = root / 'artists/kb/index.html'
            page.write_text('<div class="kc-rd-profile-visual">KB</div>')
            with self.assertRaisesRegex(ValueError, 'disappeared'):
                portraits.verify_site(root, root)

    def test_remote_or_missing_srcset_cannot_hide_behind_valid_src(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(portraits, 'decode_image', return_value=(640, 640)):
            root = Path(tmp)
            self.fixture(root)
            page = root / 'artists/index.html'
            for src, message in [('https://outside.example/kb.jpg', 'saved locally'),
                                 ('/assets/optimized/missing.webp', 'missing')]:
                page.write_text(f'<a class="artist-visual"><img alt="KB" src="/assets/artists/kb.jpg" srcset="{src} 640w"></a>')
                with self.assertRaisesRegex(ValueError, message):
                    portraits.verify_site(root, root)

    def test_another_artists_valid_photo_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(portraits, 'decode_image', return_value=(640, 640)):
            root = Path(tmp)
            self.fixture(root)
            (root / 'assets/artists/wrong.jpg').write_bytes(b'other photo')
            (root / 'artists/index.html').write_text('<a class="artist-visual"><img alt="KB" src="/assets/artists/wrong.jpg"></a>')
            with self.assertRaisesRegex(ValueError, 'Wrong or placeholder'):
                portraits.verify_site(root, root)

    def test_inventory_above_old_256_limit_is_not_silently_skipped(self):
        # Exercise the optimizer's actual inventory/selection/manifest path;
        # image encoding is independent and already checked on the release.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'assets').mkdir()
            tags = []
            for i in range(300):
                (root / f'assets/{i}.jpg').write_bytes(b'same source bytes')
                tags.append(f'<img class="artist-photo" src="/assets/{i}.jpg">')
            (root / 'index.html').write_text(''.join(tags))
            def render(digest, data, dest, base, widths, quality, backend, deadline):
                name = digest[:24]+'-w640.webp'
                (dest / name).write_bytes(b'encoded fixture')
                return optimizer.OptimizedImage(digest[:24], 640, 640,
                    (optimizer.Variant(640, 640, name, '/assets/optimized/'+name),))
            with (patch.object(optimizer, 'choose_backend', return_value=SimpleNamespace(name='fixture')),
                  patch.object(optimizer, 'render_content', side_effect=render)):
                self.assertEqual(optimizer.main([str(root), '--max-images', '256']), 2)
                self.assertFalse((root / 'assets/optimized/manifest.json').exists())
                self.assertEqual(optimizer.main([str(root), '--offline']), 0)
                manifest = json.loads((root / 'assets/optimized/manifest.json').read_text())
                self.assertEqual(manifest['optimizedLocalSourceCount'], 300)
                self.assertEqual(manifest['failedSourceCount'], 0)


if __name__ == '__main__':
    unittest.main()
