"""Separate retained artwork capacity from image delivery requirements."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import optimize_public_images as optimizer
import verify_public_performance as performance


class PublicArtifactCapacityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.site = Path(self.temp.name).resolve() / 'site'
        self.site.mkdir()

    def sized_file(self, name, size):
        path = self.site / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('wb') as handle:
            handle.truncate(size)
        return path

    def optimized_site(self):
        from PIL import Image
        Image.new('RGB', (80, 60), 'red').save(self.site / 'photo.png')
        (self.site / 'index.html').write_text(
            '<div class="profile-visual"><img class="artist-photo" src="/photo.png"></div>')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, optimizer.main([str(self.site), '--offline', '--widths', '16,32,64']))
        # The social tags normally come from the production image repair pass.
        text = (self.site / 'index.html').read_text()
        parser = performance.ImageParser(self.site / 'index.html')
        parser.feed(text)
        url = performance.DEFAULT_ORIGIN + parser.images[0].source
        (self.site / 'index.html').write_text(
            f'<meta property="og:image" content="{url}">'
            f'<meta name="twitter:image" content="{url}">' + text)

    def verify(self, library_limit=None):
        return performance.verify(self.site, '/', performance.DEFAULT_ORIGIN,
                                  False, 0, None, 2 * 1024 * 1024, library_limit)

    def test_retained_library_can_grow_without_altering_image_guards(self):
        self.optimized_site()
        # Valid WebP bytes with an ignored RIFF metadata chunk. Hard links keep
        # the test small on disk while exercising the actual logical byte count.
        sample = next((self.site / 'assets/optimized').glob('*.webp'))
        data = sample.read_bytes()
        padding = 1024 * 1024 - len(data) - 8
        data += b'JUNK' + padding.to_bytes(4, 'little') + bytes(padding)
        data = data[:4] + (len(data) - 8).to_bytes(4, 'little') + data[8:]
        retained = self.site / 'assets/optimized/retained-0.webp'
        retained.write_bytes(data)
        for number in range(1, 151):
            (retained.parent / f'retained-{number}.webp').hardlink_to(retained)
        errors, warnings, summary = self.verify()
        self.assertEqual([], errors)
        self.assertEqual([], warnings)
        self.assertGreater(summary['optimizedWebPBytes'], 149 * 1024 * 1024)
        self.assertEqual('healthy', summary['artifactCapacity']['status'])
        self.assertEqual(data, retained.read_bytes())
        self.assertEqual(2 * 1024 * 1024, performance.arguments([str(self.site)]).max_variant_bytes)
        self.assertIsNone(performance.arguments([str(self.site)]).max_total_optimized_bytes)

        errors, _, _ = self.verify(149 * 1024 * 1024)
        self.assertTrue(any('total WebP bytes' in error for error in errors))

        oversized = self.sized_file('assets/optimized/oversized.webp', 2 * 1024 * 1024 + 1)
        errors, _, _ = self.verify()
        self.assertTrue(any('per-variant limit' in error for error in errors))
        oversized.unlink()
        page = self.site / 'index.html'
        page.write_text(page.read_text().replace('loading="eager"', 'loading="lazy"'))
        errors, _, _ = self.verify()
        self.assertTrue(any('hero must use loading=eager' in error for error in errors))

    def test_whole_artifact_includes_originals_archives_and_game(self):
        self.sized_file('assets/original.jpg', 150)
        self.sized_file('archive/show/flyer.jpg', 200)
        self.sized_file('play/media.mp4', 300)
        result = performance.audit_artifact_capacity(self.site, 600, 1000)
        self.assertEqual((650, 3), (result['bytes'], result['files']))
        self.assertEqual('warning', result['status'])
        self.assertEqual([], result['errors'])
        self.assertEqual(1, len(result['warnings']))
        self.sized_file('play/second.mp4', 351)
        result = performance.audit_artifact_capacity(self.site, 600, 1000)
        self.assertEqual('failed', result['status'])
        self.assertIn('1001 bytes', result['errors'][0])

    def test_default_hosting_capacity_keeps_headroom_below_one_gigabyte(self):
        self.assertEqual(750_000_000, performance.ARTIFACT_WARNING_BYTES)
        self.assertEqual(900_000_000, performance.MAX_ARTIFACT_BYTES)
        self.assertLess(performance.MAX_ARTIFACT_BYTES, 1_000_000_000)
        self.sized_file('retained.bin', performance.MAX_ARTIFACT_BYTES + 1)
        self.assertEqual('failed', performance.audit_artifact_capacity(self.site)['status'])

    def test_symbolic_links_fail_without_counting_or_following_targets(self):
        outside = Path(self.temp.name) / 'outside'
        outside.mkdir()
        (outside / 'secret').write_bytes(b'not an artifact file')
        (self.site / 'linked-directory').symlink_to(outside, target_is_directory=True)
        (self.site / 'linked-file').symlink_to(outside / 'secret')
        result = performance.audit_artifact_capacity(self.site)
        self.assertEqual((0, 0), (result['bytes'], result['files']))
        self.assertEqual('failed', result['status'])
        self.assertEqual(2, len(result['errors']))


if __name__ == '__main__':
    unittest.main()
