#!/usr/bin/env python3
"""Tests for the zero-dependency PNG pipeline (bin/avatar_tool.py)."""

import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

import avatar_tool  # noqa: E402


def png_header(path: Path):
    with path.open("rb") as fh:
        head = fh.read(33)
    assert head[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    width, height = struct.unpack(">II", head[16:24])
    return width, height, head[24], head[25]


class TestDecode(unittest.TestCase):
    def test_roundtrip_of_shipped_avatar(self):
        w, h, pixels = avatar_tool.decode_png(ROOT / "avatars" / "expert.png")
        self.assertEqual((w, h), (512, 512))
        self.assertEqual(len(pixels), 512 * 512 * 4)

    def test_rejects_non_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "x.png"
            bad.write_bytes(b"not a png at all")
            with self.assertRaises(avatar_tool.PngError):
                avatar_tool.decode_png(bad)


class TestCrop(unittest.TestCase):
    def test_crop_dimensions_and_content(self):
        w, h, pixels = avatar_tool.decode_png(ROOT / "avatars" / "expert.png")
        cw, ch, cut = avatar_tool.crop(w, h, pixels, 56, 56, 400, 400)
        self.assertEqual((cw, ch), (400, 400))
        self.assertEqual(len(cut), 400 * 400 * 4)
        # first pixel of the crop must equal the source pixel at (56,56)
        src_i = (56 * w + 56) * 4
        self.assertEqual(cut[0:4], pixels[src_i:src_i + 4])

    def test_crop_clamps_to_bounds(self):
        w, h, pixels = avatar_tool.decode_png(ROOT / "avatars" / "expert.png")
        cw, ch, _ = avatar_tool.crop(w, h, pixels, 500, 500, 9999, 9999)
        self.assertEqual((cw, ch), (12, 12))


class TestEncode(unittest.TestCase):
    def test_flatten_emits_rgb(self):
        w, h, pixels = avatar_tool.decode_png(ROOT / "avatars" / "expert.png")
        rgb = avatar_tool.flatten_to_rgb(512, pixels, "17474A")
        payload = avatar_tool._encode_png_rgb(512, 512, rgb)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "rgb.png"
            out.write_bytes(payload)
            width, height, depth, color_type = png_header(out)
        self.assertEqual((width, height, depth), (512, 512, 8))
        self.assertEqual(color_type, 2, "flattened output must be colour type 2 (RGB)")

    def test_rounded_mask_makes_corners_transparent(self):
        w, h, pixels = avatar_tool.decode_png(ROOT / "avatars" / "expert.png")
        masked = avatar_tool.apply_rounded_alpha(512, pixels, 0.22)
        self.assertEqual(masked[3], 0, "top-left corner should be transparent")
        center = (256 * 512 + 256) * 4 + 3
        self.assertEqual(masked[center], 255, "centre should stay opaque")

    def test_flatten_rejects_bad_colour(self):
        with self.assertRaises(avatar_tool.PngError):
            avatar_tool.flatten_to_rgb(4, bytearray(4 * 4 * 4), "zzz")


class TestShippedAsset(unittest.TestCase):
    def test_avatar_meets_platform_rules(self):
        path = ROOT / "avatars" / "expert.png"
        width, height, depth, color_type = png_header(path)
        self.assertEqual(width, height)
        self.assertGreaterEqual(width, 512)
        self.assertEqual(depth, 8)
        self.assertIn(color_type, (2, 6))
        self.assertLess(path.stat().st_size / 1024, 500)

    def test_normalize_writes_requested_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "small.png"
            info = avatar_tool.normalize(ROOT / "avatars" / "expert.png", out, size=256)
            self.assertEqual(info["output_size"], "256x256")
            self.assertEqual(png_header(out)[:2], (256, 256))


if __name__ == "__main__":
    unittest.main(verbosity=2)
