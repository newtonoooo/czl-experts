#!/usr/bin/env python3
"""把 plugin.json 的 avatar 在「相对路径」与「内联 data URI」之间切换。

为什么需要这个开关
------------------
头像在界面上是 <img> 渲染的，加载失败就会回退成专家名首字（看起来像"图标没了，
变成一个汉字"）。触发加载失败的情况至少有三类：

  1. 通道把 avatar 当 CDN 相对路径拼接，本地包写成 avatars/expert.png 会 404；
  2. 文件不在插件根目录下、或超过 5 MB，解析阶段就返回空字符串；
  3. 自定义协议 URL 在部分渲染环境被 CSP 或权限拦掉。

data:image/... 不参与任何路径拼接，也不会被文件系统权限影响，因此是导入后
"先让图标显示出来"最稳的办法。上架官方市场时再切回相对路径（审核要求是路径）。

用法
    python apply_inline_avatar.py --apply      切到 data URI（默认 256px，约 30-60KB 文本）
    python apply_inline_avatar.py --revert     切回 avatars/expert.png
    python apply_inline_avatar.py --status     只看当前是什么

每次切换都会把旧值备份到 variants/ 下，可随时回滚。
仅依赖标准库。
"""

from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import shutil
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JSON = ROOT / ".codebuddy-plugin" / "plugin.json"
AVATAR = ROOT / "avatars" / "expert.png"
VARIANTS = ROOT / "variants"
RELATIVE = "avatars/expert.png"


def _load_avatar_prep():
    spec = importlib.util.spec_from_file_location("avatar_prep", ROOT / "tools" / "avatar_prep.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def make_data_uri(size: int) -> str:
    ap = _load_avatar_prep()
    img = ap.to_rgb(ap.read_png(AVATAR))
    if img.width != size:
        img = ap.box_resize(img, size)
    tmp = VARIANTS / "_inline_tmp.png"
    VARIANTS.mkdir(exist_ok=True)
    ap.write_png(img, tmp)
    uri = "data:image/png;base64," + base64.b64encode(tmp.read_bytes()).decode("ascii")
    tmp.unlink(missing_ok=True)
    return uri


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--apply", action="store_true")
    g.add_argument("--revert", action="store_true")
    g.add_argument("--status", action="store_true")
    ap.add_argument("--size", type=int, default=256)
    args = ap.parse_args()

    if not PLUGIN_JSON.exists():
        print("找不到 plugin.json：{}".format(PLUGIN_JSON))
        return 1

    manifest = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
    current = manifest.get("avatar", "")
    kind = "data URI（内联）" if current.startswith("data:") else current or "（空）"

    if args.status:
        print("当前 avatar：{}".format(kind))
        if current.startswith("data:"):
            print("长度：{:.1f} KB".format(len(current) / 1024))
        return 0

    VARIANTS.mkdir(exist_ok=True)
    backup = VARIANTS / "plugin.before-switch.json"
    shutil.copyfile(PLUGIN_JSON, backup)

    if args.apply:
        if not AVATAR.exists():
            print("找不到头像文件：{}".format(AVATAR))
            return 1
        uri = make_data_uri(args.size)
        manifest["avatar"] = uri
        PLUGIN_JSON.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        (VARIANTS / "plugin.relative-avatar.json").write_text(
            json.dumps({**manifest, "avatar": RELATIVE}, ensure_ascii=False, indent=2), encoding="utf-8")
        print("已切到内联头像：{}x{}，文本 {:.1f} KB".format(args.size, args.size, len(uri) / 1024))
        print("备份：{}".format(backup))
        print("上架官方市场前请执行 --revert 切回相对路径。")
    else:
        manifest["avatar"] = RELATIVE
        PLUGIN_JSON.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print("已切回相对路径：{}".format(RELATIVE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
