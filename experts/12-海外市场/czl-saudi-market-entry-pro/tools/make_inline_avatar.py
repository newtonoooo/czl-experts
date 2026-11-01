#!/usr/bin/env python3
"""把头像转成 data URI，用于规避官方市场通道的相对路径解析问题。

背景：官方市场通道会把 plugin.json 里的 avatar 当成 CDN 相对路径拼接，
本地包写 avatars/expert.png 会 404，界面回退成文字。data URI 不参与拼接。

用法：
    python make_inline_avatar.py --avatar ../avatars/expert.png --size 256
    python make_inline_avatar.py --avatar ../avatars/expert.png --size 256 --apply

--apply 会直接改写 plugin.json（先备份为 plugin.json.bak）。

仅依赖标准库。
"""

import argparse
import base64
import json
import shutil
import struct
import sys
import zlib
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def decode_png(path):
    data = Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit("不是 PNG 文件；JPG 请先转换")
    pos = 8
    width = height = colortype = None
    idat = bytearray()
    palette = None
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctype = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        if ctype == b"IHDR":
            width, height, bitdepth, colortype, _, _, interlace = struct.unpack(">IIBBBBB", body)
            if bitdepth != 8 or interlace != 0:
                raise SystemExit("仅支持 8 位非隔行 PNG")
        elif ctype == b"PLTE":
            palette = body
        elif ctype == b"IDAT":
            idat += body
        elif ctype == b"IEND":
            break
        pos += 12 + length

    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[colortype]
    raw = zlib.decompress(bytes(idat))
    stride = width * channels
    out = bytearray(height * stride)
    prev = bytearray(stride)
    p = 0
    for y in range(height):
        f = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if f == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif f == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif f == 4:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        out[y * stride:(y + 1) * stride] = line
        prev = line

    rgb = bytearray(width * height * 3)
    if colortype == 2:
        rgb[:] = out
    elif colortype == 6:
        for i in range(width * height):
            rgb[i * 3:i * 3 + 3] = out[i * 4:i * 4 + 3]
    elif colortype == 0:
        for i in range(width * height):
            v = out[i]
            rgb[i * 3:i * 3 + 3] = bytes((v, v, v))
    elif colortype == 3:
        for i in range(width * height):
            idx = out[i]
            rgb[i * 3:i * 3 + 3] = palette[idx * 3:idx * 3 + 3]
    else:
        raise SystemExit("不支持的 PNG 颜色类型")
    return width, height, rgb


def resize_square(width, height, rgb, size):
    """最近邻 + 块平均的简化缩放，够用且无需第三方库。"""
    out = bytearray(size * size * 3)
    for y in range(size):
        y0 = y * height // size
        y1 = max(y0 + 1, (y + 1) * height // size)
        for x in range(size):
            x0 = x * width // size
            x1 = max(x0 + 1, (x + 1) * width // size)
            r = g = b = 0
            n = 0
            for yy in range(y0, y1):
                base = (yy * width + x0) * 3
                for xx in range(x0, x1):
                    o = base + (xx - x0) * 3
                    r += rgb[o]
                    g += rgb[o + 1]
                    b += rgb[o + 2]
                    n += 1
            o = (y * size + x) * 3
            out[o] = r // n
            out[o + 1] = g // n
            out[o + 2] = b // n
    return out


def encode_png(width, height, rgb):
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]

    def chunk(tag, body):
        return (struct.pack(">I", len(body)) + tag + body
                + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def main():
    ap = argparse.ArgumentParser(description="生成 data URI 头像")
    ap.add_argument("--avatar", required=True, help="头像 PNG 路径")
    ap.add_argument("--size", type=int, default=256, help="内联尺寸，建议 256")
    ap.add_argument("--apply", action="store_true", help="直接改写同级 plugin.json")
    args = ap.parse_args()

    w, h, rgb = decode_png(args.avatar)
    if w != h:
        raise SystemExit(f"头像应为正方形，当前 {w}x{h}")
    pixels = resize_square(w, h, rgb, args.size)
    png = encode_png(args.size, args.size, pixels)
    b64 = base64.b64encode(png).decode("ascii")
    data_uri = "data:image/png;base64," + b64

    print(f"原图 {w}x{h} → 内联 {args.size}x{args.size}，PNG {len(png)/1024:.1f} KB，"
          f"data URI {len(data_uri)/1024:.1f} KB 文本")

    if args.apply:
        pj = Path(args.avatar).resolve().parent.parent / ".codebuddy-plugin" / "plugin.json"
        if not pj.exists():
            raise SystemExit(f"未找到 plugin.json：{pj}")
        shutil.copyfile(pj, str(pj) + ".bak")
        payload = json.loads(pj.read_text(encoding="utf-8"))
        payload["avatar"] = data_uri
        pj.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已写入 {pj}（备份 plugin.json.bak）")
        print("提醒：上架官方市场前请改回相对路径 avatars/expert.png")
    else:
        print("\n把下面这段替换 plugin.json 中 avatar 字段的值：\n")
        print(json.dumps({"avatar": data_uri}, ensure_ascii=False)[:200] + " ...（已省略）")
        out = Path("avatar-inline.json")
        out.write_text(json.dumps({"avatar": data_uri}, ensure_ascii=False), encoding="utf-8")
        print(f"\n完整内容已写入 {out.resolve()}")


if __name__ == "__main__":
    main()
