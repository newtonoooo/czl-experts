#!/usr/bin/env python3
"""make_manifest.py - regenerate docs/文件清单.md with sizes and SHA-256.

A file list without hashes cannot answer "did the file I shipped match the file
I tested". Hashes can.

    python tools/make_manifest.py
    python tools/make_manifest.py --out docs/文件清单.md
"""

import argparse
import hashlib
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"__pycache__", ".git", "dist"}
GROUPS = [
    ("元数据与入口", [".codebuddy-plugin/plugin.json", "README.md", "CHANGELOG.md",
                     "LICENSE"]),
    ("主提示词", ["agents/"]),
    ("头像", ["avatars/"]),
    ("技能：拆题", ["skills/czl-math-decompose/"]),
    ("技能：诊断", ["skills/czl-math-diagnose/"]),
    ("技能：训练", ["skills/czl-math-drill/"]),
    ("技能：复盘", ["skills/czl-math-ledger/"]),
    ("技能：考场", ["skills/czl-math-examroom/"]),
    ("资料包", ["materials/"]),
    ("工具", ["tools/"]),
    ("文档", ["docs/"]),
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def collect():
    files = []
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in names:
            full = os.path.join(base, n)
            rel = os.path.relpath(full, ROOT).replace("\\", "/")
            files.append((rel, os.path.getsize(full), sha256(full)))
    return sorted(files, key=lambda x: x[0])


def main(argv=None):
    ap = argparse.ArgumentParser(description="Regenerate the file manifest.")
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "文件清单.md"))
    args = ap.parse_args(argv)

    files = collect()
    total = sum(f[1] for f in files)
    used = set()
    lines = []
    lines.append("# 文件清单")
    lines.append("")
    lines.append("自动生成，勿手改。重新生成：`python tools/make_manifest.py`")
    lines.append("")
    lines.append("- 生成时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("- 文件总数：%d（不含 dist/ 与 __pycache__）" % len(files))
    lines.append("- 总体积：%.1f KB" % (total / 1024))
    lines.append("")
    for title, prefixes in GROUPS:
        rows = [f for f in files if any(
            f[0] == p or f[0].startswith(p) for p in prefixes)
            and f[0] not in used]
        if not rows:
            continue
        used.update(f[0] for f in rows)
        lines.append("## %s（%d 个）" % (title, len(rows)))
        lines.append("")
        lines.append("| 文件 | 体积 | SHA-256（前 16 位） |")
        lines.append("|---|---|---|")
        for rel, size, digest in rows:
            lines.append("| `%s` | %.1f KB | `%s` |" % (rel, size / 1024, digest[:16]))
        lines.append("")

    rest = [f for f in files if f[0] not in used]
    if rest:
        lines.append("## 其他（%d 个）" % len(rest))
        lines.append("")
        lines.append("| 文件 | 体积 | SHA-256（前 16 位） |")
        lines.append("|---|---|---|")
        for rel, size, digest in rest:
            lines.append("| `%s` | %.1f KB | `%s` |" % (rel, size / 1024, digest[:16]))
        lines.append("")

    lines.append("## 校验方法")
    lines.append("")
    lines.append("```bash")
    lines.append("# 列出实际文件与哈希，和上表比对")
    lines.append("python - <<'PY'")
    lines.append("import hashlib, os")
    lines.append("for base, dirs, names in os.walk('.'):")
    lines.append("    dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git', 'dist')]")
    lines.append("    for n in names:")
    lines.append("        p = os.path.join(base, n)")
    lines.append("        print(hashlib.sha256(open(p,'rb').read()).hexdigest()[:16], p)")
    lines.append("PY")
    lines.append("```")
    lines.append("")
    lines.append("> `dist/` 不参与指纹：发布包每次打包的压缩流可能不同，哈希不稳定。")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("wrote %s (%d files, %.1f KB)" % (args.out, len(files), total / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
