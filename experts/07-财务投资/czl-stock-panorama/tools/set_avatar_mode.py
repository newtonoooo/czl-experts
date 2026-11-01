"""切换头像的引用方式。

背景（这是本产品要解决的一个真实坑）：
WorkBuddy 渲染专家头像时，会把 plugin.json 里的相对路径拼到官方 CDN 前缀上
（例如 avatar = "avatars/expert.png" -> https://.../workbuddy/expert-marketplace/avatars/expert.png）。
本地开发/自建分发的包没有把图传到那个 CDN，请求 404，头像组件就退化成渲染名字首字，
看起来像“图标没了，变成一个字”。本地文件不会被读取。

所以：
- 自建分发、要保证任何机器导入后都能显示 -> 用内联 data URI（默认）；
- 提交官方市场上架（图会随包上传到 CDN）-> 用相对路径，体积也更小。

用法：
    python tools/set_avatar_mode.py --mode data-uri
    python tools/set_avatar_mode.py --mode path
    python tools/set_avatar_mode.py --mode data-uri --check     # 只检查当前模式
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, ".codebuddy-plugin", "plugin.json")
URI_FILE = os.path.join(ROOT, "avatars", "avatar_data_uri.txt")
PNG = os.path.join(ROOT, "avatars", "expert.png")


def load():
    with open(PLUGIN, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save(data):
    with open(PLUGIN, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["data-uri", "path"], help="目标模式")
    ap.add_argument("--check", action="store_true", help="只报告当前模式，不修改")
    args = ap.parse_args()

    data = load()
    cur = data.get("avatar") or ""
    mode = "data-uri" if cur.startswith("data:image/") else ("path" if cur else "empty")

    if args.check or not args.mode:
        print(json.dumps({"mode": mode, "avatar_head": cur[:60], "len": len(cur)}, ensure_ascii=False))
        return 0

    if args.mode == "data-uri":
        if not os.path.exists(URI_FILE):
            print("缺少 avatars/avatar_data_uri.txt，请先运行 tools/make_avatar.py", file=sys.stderr)
            return 2
        uri = open(URI_FILE, "r", encoding="utf-8").read().strip()
        if not uri.startswith("data:image/png;base64,"):
            print("data URI 文件格式不对", file=sys.stderr)
            return 2
        data["avatar"] = uri
    else:
        if not os.path.exists(PNG):
            print("缺少 avatars/expert.png", file=sys.stderr)
            return 2
        data["avatar"] = "avatars/expert.png"

    save(data)
    print(json.dumps({"ok": True, "mode": args.mode, "len": len(data["avatar"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
