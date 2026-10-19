import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from artist_thumbnail_framing import CROPS, frame_directory
from mobile_discovery import Document


class ArtistThumbnailTests(unittest.TestCase):
    def directory(self, asset=None):
        filename, width, height, *_ = CROPS['kaden-jordan']
        return ('<main><article data-artist-card data-name="Kaden Jordan">'
                '<a class="artist-visual" href="/artists/kaden-jordan/">'
                f'<img src="/assets/optimized/{asset or filename}" width="{width}" '
                f'height="{height}" alt="Kaden Jordan" sizes="270px" '
                'srcset="/photo-small.webp 320w, /photo-large.webp 1200w" '
                'style="object-position:center;filter:brightness(1.1)"></a>'
                '<h2>Kaden Jordan</h2><a href="/event/example/">Upcoming show</a>'
                '</article></main>')

    def test_directory_preserves_content_and_is_idempotent(self):
        before = self.directory()
        after = frame_directory(before)
        self.assertEqual(frame_directory(after), after)
        a = Document(before).one(lambda n: n.tag == 'img').attrs
        b = Document(after).one(lambda n: n.tag == 'img').attrs
        for key in a.keys() - {'sizes', 'style'}:
            self.assertEqual(a[key], b[key])
        self.assertIn('filter:brightness(1.1)', b['style'])
        self.assertGreater(int(b['sizes'].split(', ')[1].removesuffix('px')), 1000)
        img_a = Document(before).one(lambda n: n.tag == 'img')
        img_b = Document(after).one(lambda n: n.tag == 'img')
        self.assertEqual(before[:img_a.start] + before[img_a.end:],
                         after[:img_b.start] + after[img_b.end:])

    def test_replacement_photo_does_not_inherit_old_crop(self):
        source = self.directory('new-photo.webp')
        self.assertEqual(frame_directory(source), source)

    def test_reviewed_configuration_is_bounded(self):
        for slug, (asset, width, height, position, scale, origin) in CROPS.items():
            with self.subTest(slug=slug):
                self.assertEqual(Path(asset).name, asset)
                self.assertGreater(width, 0)
                self.assertGreater(height, 0)
                self.assertTrue(1 <= scale <= 2.5)


if __name__ == '__main__':
    unittest.main()
