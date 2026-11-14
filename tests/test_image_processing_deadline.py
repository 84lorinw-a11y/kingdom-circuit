"""Keep the required local image inventory within a bounded processing budget."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import finalize_public_experience as pipeline
import optimize_public_images as optimizer
import verify_public_performance as performance


class ImageProcessingDeadlineTests(unittest.TestCase):
    def test_budget_counts_unique_local_rasters_and_preserves_time_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'photo.jpg').write_bytes(b'local image')
            (root / 'alias.jpg').hardlink_to(root / 'photo.jpg')
            (root / 'logo.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>')
            (root / 'index.html').write_text(''.join(
                f'<img class="artist-photo" src="{source}">'
                for source in ['/photo.jpg', '/photo.jpg', '/alias.jpg', '/logo.svg', 'https://example.test/remote.jpg']))
            budget = pipeline.image_processing_budget(root, True)
            self.assertEqual(2, budget['localSourceCount'])
            self.assertEqual(2 * len(b'local image'), budget['localInputBytes'])
            self.assertEqual(361 * 1024 * 1024, budget['totalInputBytes'])
            self.assertEqual(360, pipeline.image_processing_budget(root, True)['wallTimeSeconds'])
            self.assertEqual(180, pipeline.image_processing_budget(root, False)['wallTimeSeconds'])
            local = optimizer.SourceRef('local:photo.jpg', '/photo.jpg', local_path=root / 'photo.jpg')
            for count, remote, expected in [(695, True, 755), (695, False, 695), (1000, True, 900)]:
                inventory = {str(i): (0, local) for i in range(count)}
                with self.subTest(count=count, remote=remote), patch.object(
                        optimizer, 'collect_inventory', return_value=({}, {}, inventory)):
                    result = pipeline.image_processing_budget(root, remote)
                    self.assertEqual(expected, result['wallTimeSeconds'])
                    self.assertLessEqual(result['wallTimeSeconds'], 900)

    def test_measured_input_allowance_grows_with_local_work_but_has_a_hard_ceiling(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / 'large.jpg'
            with image.open('wb') as handle:
                handle.truncate(12 * 1024 * 1024)
            source = optimizer.SourceRef('local:large.jpg', '/large.jpg', local_path=image)
            for count, remote, expected_mib in [(35, True, 484), (35, False, 420), (80, True, 1024)]:
                inventory = {str(i): (0, source) for i in range(count)}
                with self.subTest(count=count, remote=remote), patch.object(
                        optimizer, 'collect_inventory', return_value=({}, {}, inventory)):
                    result = pipeline.image_processing_budget(root, remote)
                    self.assertEqual(expected_mib * 1024 * 1024, result['totalInputBytes'])
            with patch.object(optimizer, 'collect_inventory', return_value=(
                    {}, {}, {str(i): (0, source) for i in range(81)})):
                with self.assertRaisesRegex(RuntimeError, '1 GiB'):
                    pipeline.image_processing_budget(root, True)

    def run_codec_with_budget(self, seconds):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tags = []
            for index, color in enumerate(['red', 'green', 'blue']):
                Image.new('RGB', (32, 32), color).save(root / f'{index}.png')
                tags.append(f'<img class="artist-photo" src="/{index}.png">')
            original = {path.name: path.read_bytes() for path in root.glob('*.png')}
            (root / 'index.html').write_text(''.join(tags))
            backend = optimizer.PillowBackend()
            clock = [0.0]
            real_open, real_read = backend._open, optimizer.read_source
            readers = threading.Barrier(3)

            def read(*args):
                data = real_read(*args)
                readers.wait(timeout=5)
                return data

            def open_image(data):
                # Deterministic codec work, using the real renderer and its
                # deadline check. The three input files are already read.
                clock[0] += 1.0
                return real_open(data)

            budget = pipeline.image_processing_budget(root, False)['wallTimeSeconds'] if seconds is None else seconds
            output = io.StringIO()
            with patch.object(optimizer, 'choose_backend', return_value=backend), \
                 patch.object(optimizer, 'read_source', side_effect=read), \
                 patch.object(backend, '_open', side_effect=open_image), \
                 patch.object(optimizer.time, 'monotonic', side_effect=lambda: clock[0]), \
                 contextlib.redirect_stdout(output):
                self.assertEqual(0, optimizer.main([str(root), '--offline', '--workers', '3', '--wall-time', str(budget)]))
            self.assertEqual(original, {path.name: path.read_bytes() for path in root.glob('*.png')})
            self.assertEqual(sum(map(len, original.values())), json.loads(output.getvalue())['bytesRead'])
            errors, _, _ = performance.verify(root, '/', 'https://kingdomcircuit.com', False, 0, None, 5 * 1024 * 1024, 192 * 1024 * 1024)
            floor_errors = [error for error in errors if 'every local source must be optimized' in error]
            self.assertEqual(bool(seconds), bool(floor_errors))
            return json.loads((root / 'assets/optimized/manifest.json').read_text())

    def test_real_codec_deadline_reproduces_missing_tail_with_all_input_bytes_read(self):
        manifest = self.run_codec_with_budget(4)
        self.assertEqual(3, manifest['localSourceCount'])
        self.assertEqual(1, manifest['optimizedLocalSourceCount'])
        self.assertEqual(['wall-time-limit', 'wall-time-limit'],
                         sorted(failure['code'] for failure in manifest['failures']))

    def test_allocated_budget_finishes_the_same_images_without_replacing_sources(self):
        manifest = self.run_codec_with_budget(None)
        self.assertEqual(3, manifest['optimizedLocalSourceCount'])
        self.assertEqual(0, manifest['failedSourceCount'])
        self.assertEqual(3, manifest['uniqueOptimizedImageCount'])


if __name__ == '__main__':
    unittest.main()
