#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 docs/文件清单.md 与发布 zip。开发辅助脚本，不参与运行时。"""
import json
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_LIST = os.path.join(ROOT, "docs", "文件清单.md")
def _version():
    """版本号从 plugin.json 读取，避免包名与元数据不一致。"""
    with open(os.path.join(ROOT, ".codebuddy-plugin", "plugin.json"), encoding="utf-8") as fh:
        return json.load(fh)["version"]


ZIP_PATH = os.path.join(os.path.dirname(ROOT),
                        "czl-ashare-research-writer-v%s.zip" % _version())

EXTRA = {
    "docs/文件清单.md": "本文件：全量文件路径、行数、大小与职责",
    "docs/竞品对比.md": "竞品对比：10 个包的能力矩阵、6 项优势、10 项劣势、场景选择建议",
    "tools/build_package.py": "清单生成与 zip 打包，幂等可重跑",
}


def rel_of(full):
    return os.path.relpath(full, ROOT).replace(os.sep, "/")


def collect_purpose():
    """复用上一版清单里的职责描述；EXTRA 中的条目优先级更高，不被旧值覆盖。"""
    purpose = {}
    if os.path.exists(OUT_LIST):
        with open(OUT_LIST, encoding="utf-8") as fh:
            for m in re.finditer(r"\| \d+ \| `([^`]+)` \| \d+ \| \d+ \| (.*?) \|", fh.read()):
                if m.group(2).strip():
                    purpose[m.group(1)] = m.group(2)
    purpose.update(EXTRA)
    return purpose


def main():
    purpose = collect_purpose()
    rows, total_size, total_lines = [], 0, 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
        for f in sorted(filenames):
            if f.endswith(".pyc"):
                continue
            full = os.path.join(dirpath, f)
            rel = rel_of(full)
            size = os.path.getsize(full)
            try:
                with open(full, encoding="utf-8", errors="replace") as fh:
                    lines = sum(1 for _ in fh)
            except OSError:
                lines = 0
            total_size += size
            total_lines += lines
            rows.append((rel, lines, size, purpose.get(rel, "")))
    rows.sort()

    out = ["# 文件清单", "",
           "本清单由 `tools/build_package.py` 扫描实际目录生成，行数与字节数为真实值。",
           "",
           "总计 **%d** 个文件（含本清单），**%d** 行，**%.1f KB**。" % (
               len(rows), total_lines, total_size / 1024),
           "",
           "| # | 路径 | 行数 | 字节 | 职责 |",
           "|---|---|---|---|---|"]
    for i, (rel, lines, size, p) in enumerate(rows, 1):
        out.append("| %d | `%s` | %d | %d | %s |" % (i, rel, lines, size, p))
    out += ["", "## 目录职责对照", "", "| 目录 | 作用 |", "|---|---|",
            "| `.codebuddy-plugin/` | 平台识别与上架元数据 |",
            "| `agents/` | 主体提示词，定义角色、判断链与硬规矩 |",
            "| `rules/` | 跨工作流共用规则，alwaysApply |",
            "| `skills/` | 8 个工作流，每个含 SKILL.md 与必要脚本、参考 |",
            "| `avatars/` | 原创头像四个尺寸 |",
            "| `examples/` | 真实数据样本，可直接打开验证 |",
            "| `tools/` | 头像生成器、发布包自检与本脚本 |",
            "| `tests/` | 端到端测试与最近一次结果 |",
            "| `docs/` | 上架文案、开发记录、测试报告、风险清单 |",
            "", "## 未纳入包内的内容", "",
            "- 开发期中间产物（临时 draft、K 线缓存、试做后弃用的生成图）均已清理。",
            "- 无第三方依赖目录（`node_modules`、`site-packages` 等），脚本只用标准库。",
            "- 无生成模型产出的图片：初版头像因带平台水印已删除，最终头像由 `tools/make_avatar.py` 生成。",
            ""]
    with open(OUT_LIST, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    print("文件清单：%d 个文件 / %d 行 / %.1f KB" % (len(rows), total_lines, total_size / 1024))

    n = 0
    if os.path.exists(ZIP_PATH):
        os.remove(ZIP_PATH)
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel, _, _, _ in rows:
            z.write(os.path.join(ROOT, rel.replace("/", os.sep)), "czl-ashare-research-writer/" + rel)
            n += 1
    with zipfile.ZipFile(ZIP_PATH) as z:
        bad = z.testzip()
    print("发布包：%s（%d 个条目，%.1f KB，完整性 %s）" % (
        os.path.basename(ZIP_PATH), n, os.path.getsize(ZIP_PATH) / 1024,
        "OK" if bad is None else "损坏：" + bad))
    return 0 if bad is None else 1


if __name__ == "__main__":
    sys.exit(main())
