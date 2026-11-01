#!/usr/bin/env python3
"""
avatar_check.py — 专家头像体检与规范化工具（纯标准库实现，无第三方依赖）

为什么需要它：
    WorkBuddy 客户端在解析专家头像时，若文件缺失或体积超限，会静默返回空字符串，
    前端随即退化为「首字文字头像」。这类问题不会报错，只会表现为「小图标不见了、变成字」。
    本脚本把这类隐性问题变成显式检查结果。

用法：
    python avatar_check.py check <专家目录>
    python avatar_check.py fix <输入图> <输出图> [--size 512] [--max-kb 480]

检查项：
    1. plugin.json 中 avatar 字段指向的文件是否存在
    2. 文件是否为合法 PNG / JPEG
    3. 尺寸是否为正方形、是否等于 512×512
    4. 体积是否 ≤ 500KB
"""

import json
import os
import struct
import sys
import zlib

MAX_BYTES = 500 * 1024
TARGET_SIZE = 512


# --------------------------------------------------------------------------- #
# 图片头解析
# --------------------------------------------------------------------------- #

def read_png_header(data):
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    width, height = struct.unpack('>II', data[16:24])
    bit_depth = data[24]
    color_type = data[25]
    return {
        'format': 'PNG',
        'width': width,
        'height': height,
        'bit_depth': bit_depth,
        'color_type': color_type,
        'channels': {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type, 0),
    }


def read_jpeg_header(data):
    if data[:2] != b'\xff\xd8':
        return None
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB):
            height, width = struct.unpack('>HH', data[i + 5:i + 9])
            return {'format': 'JPEG', 'width': width, 'height': height, 'bit_depth': 8, 'color_type': None, 'channels': 3}
        seg_len = struct.unpack('>H', data[i + 2:i + 4])[0]
        i += 2 + seg_len
    return None


def probe(path):
    with open(path, 'rb') as f:
        data = f.read()
    info = read_png_header(data) or read_jpeg_header(data)
    if info:
        info['bytes'] = len(data)
        info['path'] = path
    return info, data


# --------------------------------------------------------------------------- #
# PNG 解码 / 编码（8bit，支持灰度/RGB/调色板/带 Alpha）
# --------------------------------------------------------------------------- #

def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def decode_png(data):
    pos = 8
    width = height = bit_depth = color_type = None
    idat = bytearray()
    palette = b''
    trns = None
    while pos < len(data):
        length = struct.unpack('>I', data[pos:pos + 4])[0]
        ctype = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if ctype == b'IHDR':
            width, height, bit_depth, color_type = struct.unpack('>IIBB', chunk[:10])
        elif ctype == b'PLTE':
            palette = chunk
        elif ctype == b'tRNS':
            trns = chunk
        elif ctype == b'IDAT':
            idat.extend(chunk)
        elif ctype == b'IEND':
            break

    if bit_depth != 8:
        raise ValueError(f'仅支持 8bit PNG（当前 {bit_depth}bit），请用原图工具另存为 8bit')
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    raw = zlib.decompress(bytes(idat))
    stride = width * channels
    out = bytearray(width * height * 4)
    prev = bytearray(stride)
    offset = 0
    for y in range(height):
        ftype = raw[offset]
        offset += 1
        line = bytearray(raw[offset:offset + stride])
        offset += stride
        if ftype == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif ftype == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                upleft = prev[i - channels] if i >= channels else 0
                line[i] = (line[i] + _paeth(left, prev[i], upleft)) & 0xFF
        prev = line

        base = y * width * 4
        if color_type == 2:
            for x in range(width):
                s = x * 3
                d = base + x * 4
                out[d] = line[s]
                out[d + 1] = line[s + 1]
                out[d + 2] = line[s + 2]
                out[d + 3] = 255
        elif color_type == 6:
            out[base:base + width * 4] = line
        elif color_type == 0:
            for x in range(width):
                v = line[x]
                d = base + x * 4
                out[d] = out[d + 1] = out[d + 2] = v
                out[d + 3] = 255
        elif color_type == 4:
            for x in range(width):
                v = line[x * 2]
                d = base + x * 4
                out[d] = out[d + 1] = out[d + 2] = v
                out[d + 3] = line[x * 2 + 1]
        elif color_type == 3:
            for x in range(width):
                idx = line[x]
                d = base + x * 4
                out[d] = palette[idx * 3]
                out[d + 1] = palette[idx * 3 + 1]
                out[d + 2] = palette[idx * 3 + 2]
                out[d + 3] = trns[idx] if trns and idx < len(trns) else 255
    return width, height, bytes(out)


def _chunk(tag, payload):
    return struct.pack('>I', len(payload)) + tag + payload + struct.pack('>I', zlib.crc32(tag + payload) & 0xFFFFFFFF)


def encode_png(width, height, rgba, opaque=False):
    channels = 3 if opaque else 4
    stride = width * channels
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        if opaque:
            row = rgba[y * width * 4:(y + 1) * width * 4]
            for x in range(width):
                raw.extend(row[x * 4:x * 4 + 3])
        else:
            raw.extend(rgba[y * width * 4:(y + 1) * width * 4])
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 2 if opaque else 6, 0, 0, 0)
    body = zlib.compress(bytes(raw), 9)
    return b'\x89PNG\r\n\x1a\n' + _chunk(b'IHDR', ihdr) + _chunk(b'IDAT', body) + _chunk(b'IEND', b'')


def box_resize(src_w, src_h, rgba, dst_w, dst_h):
    out = bytearray(dst_w * dst_h * 4)
    x_ratio = src_w / dst_w
    y_ratio = src_h / dst_h
    for dy in range(dst_h):
        y0 = int(dy * y_ratio)
        y1 = max(y0 + 1, int((dy + 1) * y_ratio))
        for dx in range(dst_w):
            x0 = int(dx * x_ratio)
            x1 = max(x0 + 1, int((dx + 1) * x_ratio))
            r = g = b = a = 0
            n = 0
            for sy in range(y0, min(y1, src_h)):
                base = sy * src_w * 4
                for sx in range(x0, min(x1, src_w)):
                    p = base + sx * 4
                    r += rgba[p]
                    g += rgba[p + 1]
                    b += rgba[p + 2]
                    a += rgba[p + 3]
                    n += 1
            d = (dy * dst_w + dx) * 4
            out[d] = r // n
            out[d + 1] = g // n
            out[d + 2] = b // n
            out[d + 3] = a // n
    return bytes(out)


def is_opaque(rgba):
    return all(rgba[i] == 255 for i in range(3, len(rgba), 4))


# --------------------------------------------------------------------------- #
# 命令
# --------------------------------------------------------------------------- #

def cmd_check(expert_dir):
    plugin_json = os.path.join(expert_dir, '.codebuddy-plugin', 'plugin.json')
    if not os.path.exists(plugin_json):
        print(f'✖ 找不到 {plugin_json}')
        return 1

    with open(plugin_json, encoding='utf-8') as f:
        pj = json.load(f)

    avatar = pj.get('avatar', '')
    print(f'专家：{pj.get("name")}')
    print(f'配置：avatar = {avatar or "(空)"}')
    if not avatar:
        print('✖ avatar 字段为空，前端会直接退化为文字头像')
        return 1

    path = os.path.join(expert_dir, avatar.replace('/', os.sep))
    if not os.path.exists(path):
        print(f'✖ 头像文件不存在：{path}')
        print('  → 打包时未包含 avatars/ 目录，或 zip 顶层目录名与 name 字段不一致')
        return 1

    info, _ = probe(path)
    if not info:
        print('✖ 文件不是合法的 PNG / JPEG（扩展名与内容不符也会导致加载失败）')
        return 1

    problems = []
    print(f'文件：{info["format"]} {info["width"]}×{info["height"]}  {info["bytes"] / 1024:.1f} KB')

    ext = os.path.splitext(path)[1].lower()
    if ext in ('.png', '.jpg', '.jpeg'):
        expect = 'PNG' if ext == '.png' else 'JPEG'
        if info['format'] != expect:
            problems.append(f'扩展名是 {ext}，实际内容是 {info["format"]}（客户端按扩展名推断 MIME，会解码失败）')

    if info['width'] != info['height']:
        problems.append('不是正方形，列表展示会被裁切变形')
    if info['width'] != TARGET_SIZE or info['height'] != TARGET_SIZE:
        problems.append(f'尺寸不是 {TARGET_SIZE}×{TARGET_SIZE}（规范要求）')
    if info['bytes'] > MAX_BYTES:
        problems.append(f'体积 {info["bytes"] / 1024:.0f} KB 超过 500KB 上限')
    if info['format'] == 'JPEG':
        problems.append('使用 JPEG，建议改为 PNG（透明边缘与图标更清晰）')

    if problems:
        print('⚠ 发现以下问题：')
        for p in problems:
            print(f'   • {p}')
        print(f'\n修复：python avatar_check.py fix "{path}" "{path}" --size {TARGET_SIZE}')
        return 1

    print('✅ 头像符合规范（PNG / 512×512 / ≤500KB）')
    return 0


def cmd_fix(src, dst, size=TARGET_SIZE, max_kb=480):
    info, data = probe(src)
    if not info:
        print('✖ 不是合法的 PNG / JPEG')
        return 1
    if info['format'] != 'PNG':
        print('✖ 目前仅支持 PNG 输入，请先转存为 PNG')
        return 1

    w, h, rgba = decode_png(data)
    print(f'源图：{w}×{h}  {len(data) / 1024:.1f} KB')

    # 居中裁成正方形
    if w != h:
        side = min(w, h)
        ox = (w - side) // 2
        oy = (h - side) // 2
        cropped = bytearray(side * side * 4)
        for y in range(side):
            s = ((oy + y) * w + ox) * 4
            cropped[y * side * 4:(y + 1) * side * 4] = rgba[s:s + side * 4]
        w = h = side
        rgba = bytes(cropped)
        print(f'裁剪为正方形：{side}×{side}')

    opaque = is_opaque(rgba)
    budget = max_kb * 1024
    for target in (size, int(size * 0.875), int(size * 0.75), int(size * 0.625)):
        scaled = rgba if (w == target and h == target) else box_resize(w, h, rgba, target, target)
        out = encode_png(target, target, scaled, opaque)
        if len(out) <= budget or target == int(size * 0.625):
            with open(dst, 'wb') as f:
                f.write(out)
            print(f'✅ 输出：{dst}  {target}×{target}  {len(out) / 1024:.1f} KB  ({info["format"]}→PNG)')
            if len(out) > MAX_BYTES:
                print('⚠ 仍然超过 500KB，请进一步降低分辨率或减少细节')
                return 1
            return 0
        print(f'   {target}×{target} 压缩后 {len(out) / 1024:.1f} KB，继续降采样…')
    return 1


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    if cmd == 'check':
        return cmd_check(sys.argv[2])
    if cmd == 'fix':
        size = TARGET_SIZE
        max_kb = 480
        rest = sys.argv[4:]
        if '--size' in rest:
            size = int(rest[rest.index('--size') + 1])
        if '--max-kb' in rest:
            max_kb = int(rest[rest.index('--max-kb') + 1])
        return cmd_fix(sys.argv[2], sys.argv[3], size, max_kb)
    print(f'未知命令：{cmd}')
    return 1


if __name__ == '__main__':
    sys.exit(main())
