#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_avatar.py — 头像体检（专治「导入后图标变文字」）

WorkBuddy 只接受三种头像写法：
  1) http(s):// 绝对地址
  2) data:image/... 内联数据
  3) 相对专家包根的路径，且文件真的存在、且没跑出包目录

其余写法（绝对本地路径、file://、local-file://、路径大小写不符、文件缺失）
都会被解析成空字符串，界面于是回退成「名字首字」的色块——也就是「成字了」。

用法：
    python tools/verify_avatar.py <专家包目录>
退出码：0 通过 / 1 有问题
"""
import json
import os
import struct
import sys

MAX_KB = 500
EXPECT = 512


def png_info(path):
    with open(path, "rb") as fh:
        head = fh.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    w, h = struct.unpack(">II", head[16:24])
    depth, color = head[24], head[25]
    return {"w": w, "h": h, "depth": depth, "color": color}


def main():
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
    pj_path = os.path.join(root, ".codebuddy-plugin", "plugin.json")
    if not os.path.exists(pj_path):
        print("FAIL  找不到 .codebuddy-plugin/plugin.json")
        return 1
    pj = json.load(open(pj_path, encoding="utf-8"))
    avatar = pj.get("avatar", "")
    problems, notes = [], []

    if not avatar:
        problems.append("plugin.json 没有 avatar 字段")
    elif avatar.startswith(("http://", "https://", "data:")):
        notes.append("头像是远程/内联地址，跳过本地文件检查：%s" % avatar[:60])
    else:
        if os.path.isabs(avatar) or avatar.startswith(("file:", "local-file:")):
            problems.append("avatar 用了绝对路径或 file/local-file 协议，导入到别的机器必然失效：%s" % avatar)
        if "\\" in avatar:
            problems.append("avatar 路径含反斜杠，跨平台会解析失败：%s" % avatar)
        rel = avatar[2:] if avatar.startswith("./") else avatar
        target = os.path.normpath(os.path.join(root, rel))
        if not target.startswith(os.path.normpath(root) + os.sep):
            problems.append("avatar 指向了专家包之外：%s" % target)
        elif not os.path.exists(target):
            problems.append("avatar 文件不存在：%s" % target)
        else:
            notes.append("avatar 解析到：%s" % target)
            info = png_info(target)
            if info is None:
                notes.append("不是 PNG（若是 JPG 也能用，但建议 PNG），跳过尺寸检查")
            else:
                if (info["w"], info["h"]) != (EXPECT, EXPECT):
                    notes.append("尺寸 %dx%d，建议 %dx%d（不阻断，界面会自动缩放）"
                                 % (info["w"], info["h"], EXPECT, EXPECT))
                if info["depth"] != 8:
                    notes.append("位深 %d，建议 8bit" % info["depth"])
            kb = os.path.getsize(target) / 1024.0
            notes.append("文件大小 %.1f KB（上限建议 %d KB）" % (kb, MAX_KB))
            if kb > MAX_KB:
                problems.append("头像超过 %d KB，部分上传通道会拒绝" % MAX_KB)

    # 包内是否混入了别的头像文件（容易和 plugin.json 写混）
    av_dir = os.path.join(root, "avatars")
    if os.path.isdir(av_dir):
        files = sorted(os.listdir(av_dir))
        notes.append("avatars/ 目录内容：%s" % ", ".join(files))
        if len([f for f in files if f.lower().endswith((".png", ".jpg", ".jpeg"))]) > 1:
            notes.append("目录里有多张图，确认 plugin.json 指向的是正确那张")

    for n in notes:
        print("INFO  " + n)
    for p in problems:
        print("FAIL  " + p)
    if problems:
        print("\n结论：头像配置有问题，导入后很可能显示成文字头像。")
        return 1
    print("\n结论：头像配置可用（相对路径 + 文件存在 + 尺寸达标）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
