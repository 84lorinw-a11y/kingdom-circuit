from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import optimize_public_images as optimizer


class PortraitResponsiveVariantTests(unittest.TestCase):
    def test_only_pinned_opt_in_gets_extra_variant_without_upscaling_or_source_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'assets').mkdir()
            sources = {}
            for name, size, color in [('selected', (1400, 1000), '#876543'),
                                      ('unchanged', (2000, 1500), '#234567')]:
                path = root / f'assets/{name}.jpg'
                Image.new('RGB', size, color).save(path)
                sources[name] = path.read_bytes()
            digest = hashlib.sha256(sources['selected']).hexdigest()
            config = root / 'framing.json'
            config.write_text(json.dumps({'selected': {
                'responsiveCrop': True, 'responsiveWidths': [1800], 'imageSha256': digest}}))
            (root / 'index.html').write_text(''.join(
                f'<img class="artist-photo" src="/assets/{name}.jpg" alt="{name}">'
                for name in sources))
            with patch.object(optimizer, 'PORTRAIT_FRAMING_PATH', config):
                self.assertEqual(optimizer.main([str(root), '--offline']), 0)
            manifest = json.loads((root / 'assets/optimized/manifest.json').read_text())
            self.assertEqual(manifest['requestedWidths'], list(optimizer.DEFAULT_WIDTHS))
            images = {item['id']: item for item in manifest['images']}
            for name, original in sources.items():
                content_id = hashlib.sha256(original).hexdigest()[:24]
                widths = [variant['width'] for variant in images[content_id]['variants']]
                expected = [320, 640, 960, 1280, 1400] if name == 'selected' else [320, 640, 960, 1280]
                self.assertEqual(widths, expected)
                self.assertEqual((root / f'assets/{name}.jpg').read_bytes(), original)
                for variant in images[content_id]['variants']:
                    with Image.open(root / variant['file']) as image:
                        self.assertEqual(image.size, (variant['width'], variant['height']))
            html = (root / 'index.html').read_text()
            self.assertIn(f'{digest[:24]}-w1400.webp 1400w', html)
            self.assertNotIn('1800w', html)

    def test_invalid_opt_ins_fail_before_any_output_is_replaced(self):
        valid = {'responsiveCrop': True, 'responsiveWidths': [1600], 'imageSha256': 'a' * 64}
        invalid = [
            {'responsiveCrop': False}, {'responsiveCrop': 'true'},
            {'imageSha256': 'not-a-checksum'}, {'imageSha256': None},
            {'responsiveWidths': []}, {'responsiveWidths': [True]},
            {'responsiveWidths': [1600.0]}, {'responsiveWidths': [float('inf')]},
            {'responsiveWidths': [0]}, {'responsiveWidths': [2049]},
            {'responsiveWidths': '1600'},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / 'framing.json'
            (root / 'index.html').write_text('original page')
            for replacement in invalid:
                with self.subTest(replacement=replacement):
                    config.write_text(json.dumps({'portrait': valid | replacement}))
                    with self.assertRaisesRegex(ValueError, 'Invalid responsive portrait widths'):
                        optimizer.portrait_responsive_widths(config)
            config.write_text(json.dumps({'portrait': valid | {'responsiveWidths': [4096]}}))
            with patch.object(optimizer, 'PORTRAIT_FRAMING_PATH', config):
                self.assertEqual(optimizer.main([str(root), '--offline']), 2)
            self.assertEqual((root / 'index.html').read_text(), 'original page')
            self.assertFalse((root / 'assets/optimized').exists())

    def test_unconfigured_profiles_do_not_change_widths_and_shared_hashes_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / 'framing.json'
            config.write_text(json.dumps({
                'existing': {'responsiveCrop': True, 'imageSha256': 'b' * 64},
                'first': {'responsiveCrop': True, 'responsiveWidths': [1600], 'imageSha256': 'a' * 64},
                'second': {'responsiveCrop': True, 'responsiveWidths': [1800, 1600], 'imageSha256': 'a' * 64},
            }))
            self.assertEqual(optimizer.portrait_responsive_widths(config), {'a' * 64: (1600, 1800)})


if __name__ == '__main__':
    unittest.main()
