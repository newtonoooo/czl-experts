#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""filelist.py — 生成 docs/文件清单.md（真实扫描，不手写）

用法：python tools/filelist.py [--root .]

排除：dist/（产物）、src-assets/（设计过程稿）、__pycache__、系统垃圾文件。
本文自身不参与哈希（避免自指）。

作者：虫志龙 <47190078@qq.com>
许可：MIT
"""

import argparse
import hashlib
import json
import os
import sys

EXCLUDE_DIRS = {"dist", "src-assets", "__pycache__", ".git"}
EXCLUDE_FILES = {".DS_Store", "Thumbs.db"}

GROUPS = [
    ("元数据", [".codebuddy-plugin/"]),
    ("专家提示词", ["agents/"]),
    ("工作流（skill）", ["skills/"]),
    ("脚本", ["skills/czl-voice-tune/scripts/", "skills/czl-continuity-keeper/scripts/",
            "skills/czl-data-doctor/scripts/"]),
    ("头像", ["avatars/"]),
    ("文档", ["docs/"]),
    ("开发工具", ["tools/"]),
    ("根目录文件", ["README.md", "CHANGELOG.md", "LICENSE"]),
]


def sha8(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:8]


def collect(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            if fn in EXCLUDE_FILES:
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root).replace("\\", "/")
            out.append((rel, p))
    out.sort()
    return out


def group_of(rel):
    for name, prefixes in GROUPS:
        for pre in prefixes:
            if pre.endswith("/"):
                if rel.startswith(pre):
                    return name
            elif rel == pre:
                return name
    return "其他"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    root = os.path.abspath(a.root)

    files = collect(root)
    self_rel = "docs/\u6587\u4ef6\u6e05\u5355.md"

    buckets = {}
    for rel, p in files:
        buckets.setdefault(group_of(rel), []).append((rel, p))

    total_size = sum(os.path.getsize(p) for _, p in files)
    total_chars = 0
    for rel, p in files:
        if rel.endswith((".md", ".json", ".py")):
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                total_chars += len(f.read())

    L = []
    L.append("# 文件清单")
    L.append("")
    L.append("> 本文件由 `tools/filelist.py` 扫描真实目录生成，非手写。")
    with open(os.path.join(root, ".codebuddy-plugin", "plugin.json"), encoding="utf-8") as f:
        _ver = json.load(f).get("version", "")
    L.append("> 生成时间：2026-10-29 ｜ 版本：%s" % _ver)
    L.append("> 哈希为 SHA-256 前 8 位，用于核对文件未被改动。")
    L.append("")
    L.append("## 汇总")
    L.append("")
    L.append("| 项 | 值 |")
    L.append("|---|---|")
    L.append("| 包内文件数 | %d |" % len(files))
    L.append("| 总体积 | %.1f KB |" % (total_size / 1024.0))
    L.append("| 文本总量 | %d 字符 |" % total_chars)
    L.append("| 发布包 | `dist/czl-novel-director-1.0.0.zip`（由 `tools/build.py` 生成，不含 `dist/` 与 `src-assets/`） |")
    L.append("")
    L.append("## 目录结构")
    L.append("")
    L.append("```")
    L.append("czl-novel-director/")
    L.append("├── .codebuddy-plugin/plugin.json    专家清单（名称、作者、技能列表、头像路径）")
    L.append("├── agents/czl-novel-director.md     专家主提示词（七道工序与判断标准）")
    L.append("├── skills/                          七个工作流")
    L.append("│   ├── czl-market-scout/            侦察：赛道、卖点、书名")
    L.append("│   ├── czl-story-architect/         架构：规则表、人物卡、大纲、开篇")
    L.append("│   ├── czl-chapter-forge/           铸造：写作包与正文")
    L.append("│   ├── czl-voice-tune/              调音：14 项人味体检 + voice_scan.py")
    L.append("│   ├── czl-continuity-keeper/       台账：nproj.py + lint_project.py")
    L.append("│   ├── czl-data-doctor/             诊断：funnel.py + 演示数据")
    L.append("│   └── czl-delivery-pack/           交付：简介、导出、改编纲要")
    L.append("├── avatars/expert.png               虚拟人物头像 512×512")
    L.append("├── docs/                            研究、规格、文案、记录、测试、风险")
    L.append("├── tools/                           头像处理、打包、自检、清单生成")
    L.append("├── README.md                        使用说明")
    L.append("├── CHANGELOG.md                     版本日志")
    L.append("└── LICENSE                          MIT")
    L.append("```")
    L.append("")

    order = [g for g, _ in GROUPS] + ["其他"]
    for g in order:
        if g not in buckets:
            continue
        L.append("## %s" % g)
        L.append("")
        L.append("| 文件 | 体积 | SHA-256(前8) | 说明 |")
        L.append("|---|---|---|---|")
        for rel, p in sorted(buckets[g]):
            size = os.path.getsize(p)
            h = "—（本文）" if rel == self_rel else sha8(p)
            desc = DESCRIBE.get(rel, "")
            L.append("| `%s` | %s | `%s` | %s |" % (rel, fmt(size), h, desc))
        L.append("")

    L.append("## 未随包发布的文件")
    L.append("")
    L.append("| 路径 | 原因 |")
    L.append("|---|---|")
    L.append("| `src-assets/*.png` | 头像设计过程稿（AI 生成版，带平台水印），不进入发布包 |")
    L.append("| `dist/*.zip` | 打包产物本身 |")
    L.append("| `dist/selftest.json` | 自检结果，供核对，不入包 |")
    L.append("")

    out = os.path.join(root, "docs", "文件清单.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("已生成：%s（%d 个文件）" % (out, len(files)))
    return 0


def fmt(n):
    if n < 1024:
        return "%d B" % n
    if n < 1024 * 1024:
        return "%.1f KB" % (n / 1024.0)
    return "%.1f MB" % (n / 1048576.0)


DESCRIBE = {
    ".codebuddy-plugin/plugin.json": "专家清单，17 项必填",
    "agents/czl-novel-director.md": "主提示词：路由表、三条强制回边、判断标准九条",
    "README.md": "使用说明",
    "CHANGELOG.md": "版本与更新日志",
    "LICENSE": "MIT + 适用范围说明",
    "avatars/expert.png": "虚拟人物头像，生成后裁角标+降色，512×512",
    "skills/czl-market-scout/SKILL.md": "赛道三问、卖点命题、书名三路线",
    "skills/czl-story-architect/SKILL.md": "规则表、人物卡、卷章大纲、开篇三章",
    "skills/czl-story-architect/templates/bible.template.json": "设定档案模板",
    "skills/czl-chapter-forge/SKILL.md": "写作包、钩子四型、五问自检",
    "skills/czl-chapter-forge/templates/writing-packet.md": "七格写作包模板",
    "skills/czl-voice-tune/SKILL.md": "14 项体检的判定与改法",
    "skills/czl-voice-tune/scripts/voice_scan.py": "体检引擎，纯标准库",
    "skills/czl-voice-tune/samples/bad_sample.md": "负样本，应判 D/FAIL",
    "skills/czl-voice-tune/samples/good_sample.md": "正样本，应判 A/PASS",
    "skills/czl-continuity-keeper/SKILL.md": "建档、入档、伏笔、七项核查、旧稿接管",
    "skills/czl-continuity-keeper/scripts/nproj.py": "项目档案管理，六个子命令",
    "skills/czl-continuity-keeper/scripts/lint_project.py": "结构核查，七类问题",
    "skills/czl-data-doctor/SKILL.md": "漏斗诊断与改稿工单",
    "skills/czl-data-doctor/scripts/funnel.py": "追读率核算",
    "skills/czl-data-doctor/samples/funnel_demo.csv": "10 章演示数据",
    "skills/czl-delivery-pack/SKILL.md": "投稿自检、简介三版、导出",
    "skills/czl-delivery-pack/references/short-drama-outline.md": "短剧纲要模板",
    "docs/参考专家信息.md": "同类专家扫描与功能矩阵",
    "docs/产品规格.md": "需求、输入输出、质量要求",
    "docs/平台展示文案.md": "上架用文案与宣传红线",
    "docs/开发记录.md": "开发路径、图标问题排查、设计决策",
    "docs/测试报告.md": "14 项测试实测结果",
    "docs/商业发布风险清单.md": "版权、许可、平台要求、待决策事项",
    "tools/png_tool.py": "头像裁剪/缩放/降色，纯标准库",
    "tools/build.py": "打包脚本",
    "tools/selftest.py": "14 项自检",
    "tools/filelist.py": "生成本清单",
}


if __name__ == "__main__":
    sys.exit(main())
