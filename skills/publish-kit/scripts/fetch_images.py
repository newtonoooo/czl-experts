#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_images.py — 下载配图到本地（朱笔 / publish-kit 技能）

公众号不接受外链图片，粘到后台必裂。所以流程是：
    下载到本地 → HTML 用相对路径引用（本地预览正常）→ 发布时在后台手动上传插入

这个脚本负责第一步：把图片下到本地，重命名成顺序号，读尺寸，记来源，并直接输出
可粘贴的 Markdown 图片标记。

用法:
    python fetch_images.py --urls https://a.jpg https://b.jpg --dir images
    python fetch_images.py --file urls.txt --dir images --prefix 01
    python fetch_images.py --file urls.txt --dir images --markdown

urls.txt 每行一个地址，可用 | 分隔说明：
    https://example.com/a.jpg | 初三教室全景
    https://example.com/b.jpg | 体育考试现场

输出:
    下载成功的文件路径、尺寸、体积
    可直接贴进 Markdown 的图片标记（--markdown）
    images/SOURCES.txt — 来源清单，用于版权追溯与发布前核对
"""

import argparse
import os
import re
import struct
import sys
import urllib.error
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (compatible; zhubi-publish-kit/1.0)"
MAX_BYTES = 12 * 1024 * 1024        # 单图硬上限，超过直接中断
MAGIC = {
    b"\x89PNG\r\n\x1a\n": ".png",
    b"\xff\xd8\xff": ".jpg",
    b"GIF87a": ".gif",
    b"GIF89a": ".gif",
}


def sniff_ext(head):
    for magic, ext in MAGIC.items():
        if head.startswith(magic):
            return ext
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    return None


def image_size(path):
    try:
        with open(path, "rb") as f:
            head = f.read(32)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                w, h = struct.unpack(">II", head[16:24])
                return w, h
            if head[:2] == b"\xff\xd8":
                f.seek(2)
                while True:
                    b = f.read(1)
                    if not b:
                        break
                    if b != b"\xff":
                        continue
                    marker = f.read(1)
                    while marker == b"\xff":
                        marker = f.read(1)
                    if marker in (b"\xc0", b"\xc1", b"\xc2", b"\xc3", b"\xc5",
                                  b"\xc6", b"\xc7", b"\xc9", b"\xca", b"\xcb",
                                  b"\xcd", b"\xce", b"\xcf"):
                        f.read(3)
                        h, w = struct.unpack(">HH", f.read(4))
                        return w, h
                    seg = f.read(2)
                    if len(seg) < 2:
                        break
                    f.seek(struct.unpack(">H", seg)[0] - 2, 1)
    except (OSError, struct.error):
        pass
    return None, None


def parse_lines(path):
    items = []
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" in line:
                url, desc = line.split("|", 1)
                items.append((url.strip(), desc.strip()))
            else:
                items.append((line, ""))
    return items


def download(url, dest_noext, timeout=30):
    """下载一张图，返回 (路径, 扩展名, 字节数) 或抛异常。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/*,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        ctype = r.headers.get("Content-Type", "")
        if "text/html" in ctype:
            raise ValueError(f"返回的是网页不是图片（Content-Type: {ctype}），可能是防盗链")
        data = r.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError(f"文件超过 {MAX_BYTES // 1024 // 1024} MB 上限")
    ext = sniff_ext(data[:16])
    if not ext:
        raise ValueError("不是可识别的图片格式（PNG/JPEG/GIF/WEBP）")
    path = dest_noext + ext
    with open(path, "wb") as f:
        f.write(data)
    return path, ext, len(data)


def main():
    ap = argparse.ArgumentParser(description="下载配图到本地并生成 Markdown 标记")
    ap.add_argument("--urls", nargs="*", default=[], help="图片地址，可多个")
    ap.add_argument("--file", default=None, help="地址清单文件，每行一个，可用 | 分隔说明")
    ap.add_argument("--dir", default="images", help="保存目录，默认 images")
    ap.add_argument("--prefix", default="01", help="文件名前缀，默认 01（生成 01_1.jpg 这种）")
    ap.add_argument("--markdown", action="store_true", help="输出可直接粘贴的 Markdown 图片标记")
    ap.add_argument("--timeout", type=int, default=30)
    args = ap.parse_args()

    items = [(u, "") for u in args.urls]
    if args.file:
        try:
            items += parse_lines(args.file)
        except OSError as e:
            print(f"读取地址清单失败：{e}", file=sys.stderr)
            sys.exit(2)

    if not items:
        print("没有图片地址。用法：--urls URL1 URL2 或 --file urls.txt", file=sys.stderr)
        sys.exit(2)

    try:
        os.makedirs(args.dir, exist_ok=True)
    except OSError as e:
        print(f"创建目录失败：{e}", file=sys.stderr)
        sys.exit(2)

    ok, fail = [], []
    for idx, (url, desc) in enumerate(items, 1):
        if not url.startswith(("http://", "https://")):
            fail.append((url, "不是 http/https 地址"))
            continue
        base = os.path.join(args.dir, f"{args.prefix}_{idx}")
        try:
            path, ext, nbytes = download(url, base, args.timeout)
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError) as e:
            fail.append((url, str(e)[:80]))
            continue
        w, h = image_size(path)
        ok.append({"path": path, "url": url, "desc": desc,
                   "w": w, "h": h, "kb": round(nbytes / 1024, 1)})
        print(f"✅ {path}  {w}×{h if h else '?'}  {nbytes/1024:.1f} KB")

    if fail:
        print("\n下载失败：")
        for url, why in fail:
            print(f"  ✗ {url}\n     {why}")

    if ok:
        # 来源清单，用于版权追溯
        src_path = os.path.join(args.dir, "SOURCES.txt")
        with open(src_path, "w", encoding="utf-8") as f:
            f.write("# 图片来源清单\n")
            f.write("# 发布前逐条确认授权：自制 / 明确可商用 / 已获授权\n")
            f.write("# 来源不明的图宁可不用\n\n")
            for i, im in enumerate(ok, 1):
                f.write(f"{i}. {im['path']}\n   来源：{im['url']}\n   说明：{im['desc'] or '（未填）'}\n\n")
        print(f"\n来源清单：{src_path}")

        if args.markdown:
            print("\n可粘贴的图片标记（按顺序插进正文）：")
            print()
            for im in ok:
                cap = im["desc"] or ""
                p = im["path"].replace("\\", "/")   # 统一正斜杠，Windows 下也能被 md 正确解析
                mark = f'![{cap}]({p} "{cap}")' if cap else f'![{cap}]({p})'
                print(mark)

        big = [im for im in ok if im["kb"] > 500]
        if big:
            print("\n⚠ 体积提醒（建议 < 500KB）：")
            for im in big:
                print(f"  · {im['path']} {im['kb']} KB")

        print("\n下一步：")
        print("  1. 把上面的图片标记插到 Markdown 对应位置")
        print("  2. python scripts/render_wechat.py 定稿.md  （会同时生成图片上传清单）")
        print("  3. 发布时按清单在公众号后台逐张上传插入")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
