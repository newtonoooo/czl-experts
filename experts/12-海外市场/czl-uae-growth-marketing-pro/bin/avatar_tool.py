#!/usr/bin/env python3
"""
avatar_tool.py - Zero-dependency PNG normalizer for WorkBuddy expert avatars.

Why this exists
---------------
WorkBuddy expects an expert avatar to be a square PNG, ideally 512x512 and
well under 500 KB. Many generation tools return 1024x1024 RGB images with a
white border baked in, which looks wrong inside a circular UI chip and can
exceed the size budget.

This module implements the minimum PNG codec needed for that job using only
the Python standard library (struct + zlib), so the published package has
ZERO third-party runtime dependencies. That keeps the commercial distribution
surface clean: no bundled library, no third-party license to audit.

Capabilities
------------
- Decode 8-bit PNG, color types 0 (gray), 2 (RGB), 3 (palette), 4 (gray+alpha),
  6 (RGBA), non-interlaced.
- High quality box-filter downscale (integer and non-integer ratios).
- Optional rounded-corner alpha mask (transparent outside the rounded square).
- Encode 8-bit RGBA PNG with zlib level 9.

Usage
-----
    python avatar_tool.py <input.png> <output.png> [--size 512] [--radius 0.22]

Exit codes: 0 success, 2 bad usage / unsupported input, 3 write failure.
"""

from __future__ import annotations

import argparse
import struct
import sys
import zlib
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class PngError(Exception):
    """Raised when the input file cannot be decoded by this minimal codec."""


def _read_chunks(raw: bytes):
    if not raw.startswith(PNG_SIGNATURE):
        raise PngError("not a PNG file (bad signature)")
    pos = len(PNG_SIGNATURE)
    while pos + 8 <= len(raw):
        (length,) = struct.unpack(">I", raw[pos:pos + 4])
        ctype = raw[pos + 4:pos + 8]
        data = raw[pos + 8:pos + 8 + length]
        yield ctype, data
        pos += 12 + length


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _unfilter(data: bytes, width: int, height: int, bpp: int) -> bytearray:
    stride = width * bpp
    out = bytearray(stride * height)
    prev = bytearray(stride)
    pos = 0
    for y in range(height):
        if pos >= len(data):
            raise PngError("truncated image data")
        ftype = data[pos]
        pos += 1
        line = bytearray(data[pos:pos + stride])
        if len(line) != stride:
            raise PngError("truncated scanline")
        pos += stride
        if ftype == 0:
            pass
        elif ftype == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ftype == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                upleft = prev[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + _paeth(left, prev[i], upleft)) & 0xFF
        else:
            raise PngError(f"unsupported filter type {ftype}")
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return out


def decode_png(path: Path):
    """Return (width, height, pixels) where pixels is a bytearray of RGBA."""
    raw = path.read_bytes()
    ihdr = None
    idat = bytearray()
    palette = b""
    trns = b""
    for ctype, data in _read_chunks(raw):
        if ctype == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", data)
        elif ctype == b"IDAT":
            idat += data
        elif ctype == b"PLTE":
            palette = data
        elif ctype == b"tRNS":
            trns = data
        elif ctype == b"IEND":
            break

    if ihdr is None:
        raise PngError("missing IHDR chunk")
    width, height, bit_depth, color_type, comp, filt, interlace = ihdr
    if bit_depth != 8:
        raise PngError(f"unsupported bit depth {bit_depth} (only 8-bit supported)")
    if interlace != 0:
        raise PngError("interlaced PNG is not supported")
    if comp != 0 or filt != 0:
        raise PngError("unsupported compression/filter method")

    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type)
    if channels is None:
        raise PngError(f"unsupported color type {color_type}")

    pixels = _unfilter(zlib.decompress(bytes(idat)), width, height, channels)

    rgba = bytearray(width * height * 4)
    if color_type == 6:
        rgba[:] = pixels
    elif color_type == 2:
        for i in range(width * height):
            r, g, b = pixels[i * 3:i * 3 + 3]
            rgba[i * 4:i * 4 + 4] = bytes((r, g, b, 255))
    elif color_type == 0:
        for i in range(width * height):
            v = pixels[i]
            rgba[i * 4:i * 4 + 4] = bytes((v, v, v, 255))
    elif color_type == 4:
        for i in range(width * height):
            v = pixels[i * 2]
            a = pixels[i * 2 + 1]
            rgba[i * 4:i * 4 + 4] = bytes((v, v, v, a))
    else:  # palette
        if not palette:
            raise PngError("palette image without PLTE chunk")
        for i in range(width * height):
            idx = pixels[i]
            base = idx * 3
            if base + 3 > len(palette):
                raise PngError("palette index out of range")
            r, g, b = palette[base:base + 3]
            a = trns[idx] if idx < len(trns) else 255
            rgba[i * 4:i * 4 + 4] = bytes((r, g, b, a))
    return width, height, rgba


def _encode_png(width: int, height: int, rgba: bytearray) -> bytes:
    """Encode RGBA with adaptive per-row filtering (lossless, much smaller output)."""
    stride = width * 4
    bpp = 4
    raw = bytearray()
    prev = bytearray(stride)
    for y in range(height):
        line = rgba[y * stride:(y + 1) * stride]
        # Try all five PNG row filters and keep the one with the smallest residual.
        candidates = []
        # 0: None
        candidates.append((0, bytes(line)))
        # 1: Sub
        sub = bytearray(stride)
        for i in range(stride):
            left = line[i - bpp] if i >= bpp else 0
            sub[i] = (line[i] - left) & 0xFF
        candidates.append((1, bytes(sub)))
        # 2: Up
        up = bytearray(stride)
        for i in range(stride):
            up[i] = (line[i] - prev[i]) & 0xFF
        candidates.append((2, bytes(up)))
        # 3: Average
        avg = bytearray(stride)
        for i in range(stride):
            left = line[i - bpp] if i >= bpp else 0
            avg[i] = (line[i] - ((left + prev[i]) >> 1)) & 0xFF
        candidates.append((3, bytes(avg)))
        # 4: Paeth
        pae = bytearray(stride)
        for i in range(stride):
            left = line[i - bpp] if i >= bpp else 0
            upleft = prev[i - bpp] if i >= bpp else 0
            pae[i] = (line[i] - _paeth(left, prev[i], upleft)) & 0xFF
        candidates.append((4, bytes(pae)))

        best_type, best_data = min(
            candidates,
            key=lambda c: sum(v if v < 128 else 256 - v for v in c[1]),
        )
        raw.append(best_type)
        raw += best_data
        prev = line

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (PNG_SIGNATURE
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def box_resize(src_w: int, src_h: int, rgba: bytearray, dst_w: int, dst_h: int) -> bytearray:
    """Area-average downscale. Also works for upscale (falls back to nearest-ish box)."""
    out = bytearray(dst_w * dst_h * 4)
    x_ratio = src_w / dst_w
    y_ratio = src_h / dst_h
    for dy in range(dst_h):
        y0 = int(dy * y_ratio)
        y1 = max(y0 + 1, int((dy + 1) * y_ratio))
        y1 = min(y1, src_h)
        for dx in range(dst_w):
            x0 = int(dx * x_ratio)
            x1 = max(x0 + 1, int((dx + 1) * x_ratio))
            x1 = min(x1, src_w)
            r = g = b = a = 0
            count = 0
            for sy in range(y0, y1):
                row = sy * src_w
                for sx in range(x0, x1):
                    i = (row + sx) * 4
                    r += rgba[i]
                    g += rgba[i + 1]
                    b += rgba[i + 2]
                    a += rgba[i + 3]
                    count += 1
            if count == 0:
                count = 1
            o = (dy * dst_w + dx) * 4
            out[o] = r // count
            out[o + 1] = g // count
            out[o + 2] = b // count
            out[o + 3] = a // count
    return out


def apply_rounded_alpha(size: int, rgba: bytearray, radius_ratio: float) -> bytearray:
    """Make everything outside a rounded square fully transparent (anti-aliased edge)."""
    if radius_ratio <= 0:
        return rgba
    radius = max(0.0, min(0.5, radius_ratio)) * size
    out = bytearray(rgba)
    for y in range(size):
        for x in range(size):
            cx = min(max(x + 0.5, radius), size - radius)
            cy = min(max(y + 0.5, radius), size - radius)
            dist = ((x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2) ** 0.5
            if dist <= radius - 0.5:
                continue
            if dist >= radius + 0.5:
                out[(y * size + x) * 4 + 3] = 0
            else:
                factor = 1.0 - (dist - (radius - 0.5))
                i = (y * size + x) * 4 + 3
                out[i] = int(out[i] * max(0.0, min(1.0, factor)))
    return out


def crop(src_w: int, src_h: int, rgba: bytearray, x: int, y: int, w: int, h: int) -> tuple[int, int, bytearray]:
    """Cut a rectangle out of the image. Coordinates are in source pixels."""
    x = max(0, min(x, src_w - 1))
    y = max(0, min(y, src_h - 1))
    w = max(1, min(w, src_w - x))
    h = max(1, min(h, src_h - y))
    out = bytearray(w * h * 4)
    for row in range(h):
        src_start = ((y + row) * src_w + x) * 4
        out[row * w * 4:(row + 1) * w * 4] = rgba[src_start:src_start + w * 4]
    return w, h, out


def flatten_to_rgb(size: int, rgba: bytearray, hex_color: str) -> bytearray:
    """Composite over an opaque colour and drop the alpha channel (PNG colour type 2).

    Some clients are pickier about RGBA avatars than about plain RGB, so an
    opaque RGB output is the most compatible option when the artwork already
    has a full-bleed background.
    """
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        raise PngError(f"bad --flatten colour: {hex_color}")
    br, bg, bb = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    out = bytearray(size * size * 3)
    for i in range(size * size):
        a = rgba[i * 4 + 3] / 255.0
        out[i * 3] = int(rgba[i * 4] * a + br * (1 - a))
        out[i * 3 + 1] = int(rgba[i * 4 + 1] * a + bg * (1 - a))
        out[i * 3 + 2] = int(rgba[i * 4 + 2] * a + bb * (1 - a))
    return out


def _encode_png_rgb(width: int, height: int, rgb: bytearray) -> bytes:
    """Same adaptive encoder as the RGBA path, but with 3 bytes per pixel."""
    stride = width * 3
    bpp = 3
    raw = bytearray()
    prev = bytearray(stride)
    for y in range(height):
        line = rgb[y * stride:(y + 1) * stride]
        candidates = [(0, bytes(line))]
        sub = bytearray(stride)
        for i in range(stride):
            left = line[i - bpp] if i >= bpp else 0
            sub[i] = (line[i] - left) & 0xFF
        candidates.append((1, bytes(sub)))
        up = bytearray(stride)
        for i in range(stride):
            up[i] = (line[i] - prev[i]) & 0xFF
        candidates.append((2, bytes(up)))
        avg = bytearray(stride)
        for i in range(stride):
            left = line[i - bpp] if i >= bpp else 0
            avg[i] = (line[i] - ((left + prev[i]) >> 1)) & 0xFF
        candidates.append((3, bytes(avg)))
        pae = bytearray(stride)
        for i in range(stride):
            left = line[i - bpp] if i >= bpp else 0
            upleft = prev[i - bpp] if i >= bpp else 0
            pae[i] = (line[i] - _paeth(left, prev[i], upleft)) & 0xFF
        candidates.append((4, bytes(pae)))
        best_type, best_data = min(
            candidates, key=lambda c: sum(v if v < 128 else 256 - v for v in c[1]))
        raw.append(best_type)
        raw += best_data
        prev = line

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (PNG_SIGNATURE
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def normalize(src: Path, dst: Path, size: int = 512, radius: float = 0.22,
              crop_box: tuple[int, int, int, int] | None = None,
              flatten: str | None = None) -> dict:
    w, h, rgba = decode_png(src)
    if crop_box:
        w, h, rgba = crop(w, h, rgba, *crop_box)
    if (w, h) != (size, size):
        rgba = box_resize(w, h, rgba, size, size)
    if flatten:
        rgb = flatten_to_rgb(size, rgba, flatten)
        payload = _encode_png_rgb(size, size, rgb)
        mode = "RGB"
    else:
        rgba = apply_rounded_alpha(size, rgba, radius)
        payload = _encode_png(size, size, rgba)
        mode = "RGBA"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(payload)
    return {
        "source": str(src),
        "source_size": f"{w}x{h}",
        "output": str(dst),
        "output_size": f"{size}x{size}",
        "mode": mode,
        "bytes": len(payload),
        "kb": round(len(payload) / 1024, 1),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Normalize a PNG avatar to a square RGBA file.")
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--radius", type=float, default=0.22,
                        help="corner radius as a fraction of size; 0 disables the mask")
    parser.add_argument("--crop", default=None,
                        help="crop box in source pixels before resizing, as X,Y,W,H")
    parser.add_argument("--flatten", default=None, metavar="HEX",
                        help="composite over this colour and emit opaque RGB (e.g. 0E3B43)")
    args = parser.parse_args(argv)

    crop_box = None
    if args.crop:
        try:
            parts = [int(v) for v in args.crop.split(",")]
            if len(parts) != 4:
                raise ValueError
            crop_box = tuple(parts)  # type: ignore[assignment]
        except ValueError:
            print("[FAIL] --crop must be X,Y,W,H", file=sys.stderr)
            return 2

    try:
        info = normalize(Path(args.input), Path(args.output), args.size, args.radius,
                         crop_box, args.flatten)
    except PngError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 3

    print(f"[OK] {info['source_size']} -> {info['output_size']} {info['mode']}, "
          f"{info['kb']} KB -> {info['output']}")
    if info["kb"] > 500:
        print("[WARN] file exceeds the 500 KB avatar budget", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
