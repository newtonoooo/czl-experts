#!/usr/bin/env python3
"""png_resize.py - crop / downscale / re-encode a PNG with the standard library only.

Why this exists: WorkBuddy requires expert avatars to be a square PNG, 512x512,
under 500 KB. Studio machines often have neither Pillow nor ImageMagick, and
`Add-Type` (System.Drawing) is blocked by policy on some of them. This script
does the whole job with zlib + struct, so it runs anywhere Python 3.8+ runs.

Supported input: 8-bit PNG, colour type 0 (grey), 2 (RGB), 4 (grey+alpha),
6 (RGBA), non-interlaced. That covers every avatar generator we have seen.

Usage
-----
    python png_resize.py in.png out.png --size 512
    python png_resize.py in.png out.png --size 512 --crop 40,0,900,900
    python png_resize.py in.png out.png --size 512 --probe      # report only

--crop takes left,top,width,height in source pixels and is applied before the
resize, which is how we trim generator watermarks out of a corner.

Exit codes: 0 ok, 2 bad input, 3 unsupported format.
"""

import argparse
import struct
import sys
import zlib

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _read_chunks(blob):
    if not blob.startswith(PNG_SIG):
        raise ValueError("not a PNG file")
    pos = len(PNG_SIG)
    while pos < len(blob):
        (length,) = struct.unpack(">I", blob[pos:pos + 4])
        ctype = blob[pos + 4:pos + 8]
        data = blob[pos + 8:pos + 8 + length]
        yield ctype, data
        pos += 12 + length


def read_png(path):
    """Return (width, height, channels, bytearray of raw samples)."""
    blob = open(path, "rb").read()
    ihdr = None
    idat = bytearray()
    for ctype, data in _read_chunks(blob):
        if ctype == b"IHDR":
            ihdr = data
        elif ctype == b"IDAT":
            idat += data
        elif ctype == b"IEND":
            break
    if ihdr is None:
        raise ValueError("no IHDR chunk")
    width, height, depth, colour, comp, filt, interlace = struct.unpack(">IIBBBBB", ihdr)
    if depth != 8:
        raise ValueError("only 8-bit PNG supported (got %d-bit)" % depth)
    if interlace != 0:
        raise ValueError("interlaced PNG not supported")
    channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(colour)
    if channels is None:
        raise ValueError("unsupported colour type %d" % colour)

    raw = zlib.decompress(bytes(idat))
    stride = width * channels
    out = bytearray(stride * height)
    prev = bytearray(stride)
    pos = 0
    for y in range(height):
        ftype = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if ftype == 1:      # Sub
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif ftype == 2:    # Up
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:    # Average
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:    # Paeth
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        elif ftype != 0:
            raise ValueError("bad filter type %d on row %d" % (ftype, y))
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return width, height, channels, out


def to_rgb(width, height, channels, buf):
    """Flatten to 3 bytes per pixel, compositing any alpha over white."""
    if channels == 3:
        return buf
    out = bytearray(width * height * 3)
    for i in range(width * height):
        if channels == 1:
            g = buf[i]
            out[3 * i:3 * i + 3] = bytes((g, g, g))
        elif channels == 2:
            g, a = buf[2 * i], buf[2 * i + 1]
            out[3 * i:3 * i + 3] = bytes(
                ((g * a + 255 * (255 - a)) // 255,) * 3)
        else:  # 4
            r, gg, b, a = buf[4 * i:4 * i + 4]
            out[3 * i] = (r * a + 255 * (255 - a)) // 255
            out[3 * i + 1] = (gg * a + 255 * (255 - a)) // 255
            out[3 * i + 2] = (b * a + 255 * (255 - a)) // 255
    return out


def crop_rgb(width, height, rgb, box):
    left, top, cw, ch = box
    if left < 0 or top < 0 or left + cw > width or top + ch > height:
        raise ValueError(
            "crop box %s does not fit inside %dx%d" % (str(box), width, height))
    out = bytearray(cw * ch * 3)
    for y in range(ch):
        src = ((top + y) * width + left) * 3
        out[y * cw * 3:(y + 1) * cw * 3] = rgb[src:src + cw * 3]
    return out, cw, ch


def area_resize(width, height, rgb, size):
    """Box-average downscale to size x size. Exact when size divides evenly."""
    out = bytearray(size * size * 3)
    for y in range(size):
        y0 = y * height // size
        y1 = max(y0 + 1, (y + 1) * height // size)
        for x in range(size):
            x0 = x * width // size
            x1 = max(x0 + 1, (x + 1) * width // size)
            r = g = b = n = 0
            for yy in range(y0, y1):
                base = (yy * width + x0) * 3
                for _ in range(x1 - x0):
                    r += rgb[base]
                    g += rgb[base + 1]
                    b += rgb[base + 2]
                    base += 3
                    n += 1
            o = (y * size + x) * 3
            out[o] = r // n
            out[o + 1] = g // n
            out[o + 2] = b // n
    return out


def _chunk(ctype, data):
    return (struct.pack(">I", len(data)) + ctype + data
            + struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF))


def write_png(path, size, rgb):
    stride = size * 3
    raw = bytearray()
    for y in range(size):
        raw.append(0)  # filter: None
        raw += rgb[y * stride:(y + 1) * stride]
    blob = (PNG_SIG
            + _chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + _chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(blob)
    return len(blob)


def _median_cut(hist, ncolors):
    """hist: {(r,g,b): count} -> list of (r,g,b) palette entries."""
    boxes = [list(hist.keys())]
    while len(boxes) < ncolors:
        # split the box with the largest weighted colour extent
        best, best_score = -1, -1
        for i, box in enumerate(boxes):
            if len(box) < 2:
                continue
            spans = [max(c[k] for c in box) - min(c[k] for c in box) for k in range(3)]
            score = max(spans) * len(box)
            if score > best_score:
                best, best_score = i, score
        if best < 0:
            break
        box = boxes.pop(best)
        spans = [max(c[k] for c in box) - min(c[k] for c in box) for k in range(3)]
        axis = spans.index(max(spans))
        box.sort(key=lambda c: c[axis])
        # cut at the weighted median so big flat areas keep their own entry
        total = sum(hist[c] for c in box)
        acc, cut = 0, len(box) // 2
        for idx, c in enumerate(box):
            acc += hist[c]
            if acc * 2 >= total:
                cut = min(max(idx, 1), len(box) - 1)
                break
        boxes.append(box[:cut])
        boxes.append(box[cut:])
    palette = []
    for box in boxes:
        total = sum(hist[c] for c in box) or 1
        palette.append(tuple(
            sum(c[k] * hist[c] for c in box) // total for k in range(3)))
    return palette


def quantize(size, rgb, ncolors=256):
    """Map RGB pixels onto an adaptive palette. Returns (palette, indices)."""
    npx = size * size
    hist = {}
    for i in range(npx):
        key = (rgb[3 * i], rgb[3 * i + 1], rgb[3 * i + 2])
        hist[key] = hist.get(key, 0) + 1
    if len(hist) <= ncolors:
        palette = sorted(hist)
    else:
        palette = _median_cut(hist, ncolors)
    # nearest palette entry, cached per distinct source colour
    lookup = {}
    for colour in hist:
        r, g, b = colour
        best, best_d = 0, 1 << 30
        for idx, (pr, pg, pb) in enumerate(palette):
            d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
            if d < best_d:
                best, best_d = idx, d
                if d == 0:
                    break
        lookup[colour] = best
    indices = bytearray(npx)
    for i in range(npx):
        indices[i] = lookup[(rgb[3 * i], rgb[3 * i + 1], rgb[3 * i + 2])]
    return palette, indices


def write_png_palette(path, size, palette, indices):
    stride = size
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        raw += indices[y * stride:(y + 1) * stride]
    plte = b"".join(struct.pack(">BBB", *c) for c in palette)
    blob = (PNG_SIG
            + _chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 3, 0, 0, 0))
            + _chunk(b"PLTE", plte)
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + _chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(blob)
    return len(blob)


def probe(path):
    blob = open(path, "rb").read()
    for ctype, data in _read_chunks(blob):
        if ctype == b"IHDR":
            w, h, depth, colour, _c, _f, il = struct.unpack(">IIBBBBB", data)
            return {"width": w, "height": h, "bit_depth": depth,
                    "colour_type": colour, "interlaced": il,
                    "bytes": len(blob)}
    raise ValueError("no IHDR chunk")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Crop and downscale a PNG to a square avatar.")
    ap.add_argument("src")
    ap.add_argument("dst", nargs="?")
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--crop", help="left,top,width,height in source pixels")
    ap.add_argument("--palette", type=int, default=0,
                    help="quantize to N colours (256 is plenty for flat art, "
                         "and is what gets a 512px avatar under the 500 KB cap)")
    ap.add_argument("--expand", action="store_true",
                    help="after quantising, re-expand to truecolour PNG so the "
                         "output stays colour type 2")
    ap.add_argument("--probe", action="store_true", help="only report source metadata")
    args = ap.parse_args(argv)

    try:
        info = probe(args.src)
    except (OSError, ValueError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2

    if args.probe or not args.dst:
        print("%s: %dx%d, %d-bit, colour type %d, interlaced=%d, %.0f KB"
              % (args.src, info["width"], info["height"], info["bit_depth"],
                 info["colour_type"], info["interlaced"], info["bytes"] / 1024))
        return 0

    try:
        w, h, ch, buf = read_png(args.src)
        rgb = to_rgb(w, h, ch, buf)
        if args.crop:
            box = tuple(int(v) for v in args.crop.split(","))
            if len(box) != 4:
                raise ValueError("--crop needs four integers")
            rgb, w, h = crop_rgb(w, h, rgb, box)
        if w < args.size or h < args.size:
            raise ValueError("source %dx%d is smaller than --size %d" % (w, h, args.size))
        small = area_resize(w, h, rgb, args.size)
        if args.palette:
            pal, idx = quantize(args.size, small, args.palette)
            if args.expand:
                # Quantise for compression, then write truecolour so no decoder
                # or server-side pipeline has to cope with an indexed PNG.
                expanded = bytearray(args.size * args.size * 3)
                for i, k in enumerate(idx):
                    r, g, b = pal[k]
                    expanded[3 * i] = r
                    expanded[3 * i + 1] = g
                    expanded[3 * i + 2] = b
                nbytes = write_png(args.dst, args.size, expanded)
            else:
                nbytes = write_png_palette(args.dst, args.size, pal, idx)
        else:
            nbytes = write_png(args.dst, args.size, small)
    except (OSError, ValueError, zlib.error) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 3

    print("wrote %s: %dx%d, %.0f KB" % (args.dst, args.size, args.size, nbytes / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
