from __future__ import annotations

import json
import pathlib
import struct
import unittest
import zlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def decode_rgba(path: pathlib.Path) -> tuple[int, int, list[bytes]]:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise AssertionError(f"Not a PNG: {path}")
    offset = len(PNG_SIGNATURE)
    width = height = 0
    payload = bytearray()
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        chunk = data[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if kind == b"IHDR":
            width, height, depth, color_type, _, _, interlace = struct.unpack(
                ">IIBBBBB", chunk
            )
            if (depth, color_type, interlace) != (8, 6, 0):
                raise AssertionError(f"Expected non-interlaced RGBA PNG: {path}")
        elif kind == b"IDAT":
            payload.extend(chunk)
        elif kind == b"IEND":
            break

    raw = zlib.decompress(bytes(payload))
    stride = width * 4
    rows: list[bytes] = []
    previous = bytearray(stride)
    cursor = 0
    for _ in range(height):
        filter_type = raw[cursor]
        source = raw[cursor + 1 : cursor + 1 + stride]
        cursor += stride + 1
        row = bytearray(stride)
        for index, value in enumerate(source):
            left = row[index - 4] if index >= 4 else 0
            above = previous[index]
            upper_left = previous[index - 4] if index >= 4 else 0
            if filter_type == 0:
                decoded = value
            elif filter_type == 1:
                decoded = value + left
            elif filter_type == 2:
                decoded = value + above
            elif filter_type == 3:
                decoded = value + ((left + above) // 2)
            elif filter_type == 4:
                estimate = left + above - upper_left
                distances = (
                    abs(estimate - left),
                    abs(estimate - above),
                    abs(estimate - upper_left),
                )
                predictor = (left, above, upper_left)[distances.index(min(distances))]
                decoded = value + predictor
            else:
                raise AssertionError(f"Unsupported PNG filter {filter_type}: {path}")
            row[index] = decoded & 0xFF
        rows.append(bytes(row))
        previous = row
    return width, height, rows


class ProductionFaviconTests(unittest.TestCase):
    def test_favicon_package_has_expected_dimensions_and_transparency(self) -> None:
        expected = {
            "favicon-kc-stacked-v2-48.png": 48,
            "favicon-kc-stacked-v2-96.png": 96,
            "favicon-kc-stacked-v2-180.png": 180,
            "favicon-kc-stacked-v2-192.png": 192,
            "favicon-kc-stacked-v2-512.png": 512,
            "favicon-kc-stacked-v2-maskable-512.png": 512,
        }
        for filename, size in expected.items():
            width, height, rows = decode_rgba(ROOT / "assets" / filename)
            self.assertEqual((width, height), (size, size))
            self.assertEqual(rows[0][3], 0, filename)
            center_alpha = rows[size // 2][(size // 2) * 4 + 3]
            self.assertEqual(center_alpha, 255, filename)

    def test_manifest_uses_the_new_icons(self) -> None:
        manifest = json.loads((ROOT / "manifest.webmanifest").read_text(encoding="utf-8"))
        sources = {icon["src"] for icon in manifest["icons"]}
        self.assertEqual(
            sources,
            {
                "/assets/favicon-kc-stacked-v2-192.png",
                "/assets/favicon-kc-stacked-v2-512.png",
                "/assets/favicon-kc-stacked-v2-maskable-512.png",
            },
        )

    def test_source_pages_and_generators_use_the_new_favicon(self) -> None:
        sources = (
            ROOT / "index.html",
            ROOT / "404.html",
            ROOT / "shows/index.html",
            ROOT / "shows/this-month/index.html",
            ROOT / "festivals/index.html",
            ROOT / "new-shows/index.html",
            ROOT / "artists/index.html",
            ROOT / "artists/profile/index.html",
            ROOT / "event/index.html",
            ROOT / "submit/index.html",
            ROOT / "scripts/build_site.py",
            ROOT / "scripts/build_seo_site.py",
            ROOT / "scripts/add_past_show_archives.py",
        )
        for path in sources:
            text = path.read_text(encoding="utf-8")
            self.assertIn("/assets/favicon-kc-stacked-v2-48.png", text, path)
            self.assertIn("/manifest.webmanifest", text, path)
            self.assertNotIn("/assets/favicon.svg", text, path)


if __name__ == "__main__":
    unittest.main()
