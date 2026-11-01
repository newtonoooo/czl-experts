"""打发布包。

平台校验有两条硬规则，直接决定能打出几个包：

1. `avatar` 必须是**带扩展名的图片路径**（png/jpg/webp）。写 data URI 会被判"格式不支持：无扩展名"。
2. `defaultInitPrompt` 必须与 `quickPrompts[0]` 逐字一致（中英各一条）。

于是本工具输出两个包：

- `czl-stock-panorama-<ver>.zip`        平台提交版：avatar = avatars/expert.png，可过上架校验。
- `czl-stock-panorama-<ver>-local.zip`  本地分发版：avatar 内联 data URI，导入任意机器都能显示图标。

两个包除 plugin.json 的 avatar 字段外完全相同。打包过程不修改磁盘上的 plugin.json。

用法：
    python tools/build_dist.py            # 两个包都打
    python tools/build_dist.py --only market
    python tools/build_dist.py --only local
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = os.path.basename(ROOT)
SKIP_DIRS = {"dist", "__pycache__", ".git", ".idea"}
SKIP_FILES = {".DS_Store", "Thumbs.db", "avatar_data_uri.txt"}
SKIP_SUFFIX = (".pyc", ".pyo")
PLUGIN_REL = ".codebuddy-plugin/plugin.json"


def collect():
    items = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f in SKIP_FILES or f.endswith(SKIP_SUFFIX):
                continue
            p = os.path.join(base, f)
            rel = os.path.relpath(p, ROOT).replace("\\", "/")
            items.append((p, rel))
    return sorted(items, key=lambda x: x[1])


def manifest_bytes(mode: str):
    data = json.load(open(os.path.join(ROOT, PLUGIN_REL), encoding="utf-8"))
    if mode == "local":
        uri_file = os.path.join(ROOT, "avatars", "avatar_data_uri.txt")
        if not os.path.exists(uri_file):
            raise SystemExit("缺少 avatars/avatar_data_uri.txt，请先运行 tools/make_avatar.py")
        data["avatar"] = open(uri_file, encoding="utf-8").read().strip()
    else:
        data["avatar"] = "avatars/expert.png"
    # 两个包都必须满足"初始提示词 == 首条快捷词"，否则平台直接拒绝
    data["defaultInitPrompt"] = {"en": data["quickPrompts"][0]["en"],
                                  "zh": data["quickPrompts"][0]["zh"]}
    blob = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return blob, data


def build(mode: str) -> dict:
    blob, data = manifest_bytes(mode)
    version = data.get("version", "0.0.0")
    suffix = "" if mode == "market" else "-local"
    out = os.path.join(ROOT, "dist", f"{NAME}-{version}{suffix}.zip")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    items = collect()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for full, rel in items:
            if rel == PLUGIN_REL:
                zf.writestr(f"{NAME}/{rel}", blob)
            else:
                zf.write(full, f"{NAME}/{rel}")

    raw = open(out, "rb").read()
    sha = hashlib.sha256(raw).hexdigest()
    with open(out + ".sha256", "w", encoding="utf-8") as fh:
        fh.write(f"{sha}  {os.path.basename(out)}\n")
    return {"zip": out, "mode": mode, "avatar": data["avatar"][:34],
            "files": len(items), "bytes": len(raw), "sha256": sha}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["market", "local"])
    args = ap.parse_args()
    modes = ["market", "local"] if not args.only else [args.only]
    for m in modes:
        print(json.dumps(build(m), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
