#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selfcheck.py - package integrity check for the czl-resume-gate expert.

Verifies: plugin.json fields, agent frontmatter, skill layout, script syntax,
avatar format/size, doc presence, and absence of TODO placeholders.

Usage:
    python scripts/selfcheck.py [--root <expert-dir>]
Exit code 0 = all checks passed, 1 = at least one failure.
"""

import argparse
import json
import py_compile
import re
import struct
import sys
import tempfile
from pathlib import Path

REQUIRED_DOCS = [
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "docs/产品规格.md",
    "docs/开发记录.md",
    "docs/文件清单.md",
    "docs/测试报告.md",
    "docs/商业发布风险清单.md",
    "docs/平台展示文案.md",
    "docs/使用说明.md",
]

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    return ok


def png_size(path):
    data = path.read_bytes()[:33]
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    w, h = struct.unpack(">II", data[16:24])
    return w, h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    root = Path(ap.parse_args().root).resolve()

    # plugin.json
    pj_path = root / ".codebuddy-plugin" / "plugin.json"
    pj = {}
    if check("plugin.json 存在且可解析", pj_path.exists()):
        try:
            pj = json.loads(pj_path.read_text(encoding="utf-8"))
            check("plugin.json 是合法 JSON", True)
        except json.JSONDecodeError as e:
            check("plugin.json 是合法 JSON", False, str(e))

    name = pj.get("name", "")
    check("name 以 czl- 开头且 kebab-case", bool(re.match(r"^czl-[a-z0-9\-]+$", name)), name)
    check("plugin == name", pj.get("plugin") == name)
    check("version 为语义化版本", bool(re.match(r"^\d+\.\d+\.\d+$", pj.get("version", ""))), pj.get("version"))
    check("author 为虫志龙 / 47190078@qq.com",
          pj.get("author", {}).get("name") == "虫志龙"
          and pj.get("author", {}).get("email") == "47190078@qq.com")
    check("expertType == agent", pj.get("expertType") == "agent")
    check("categoryId 合法", pj.get("categoryId") == "09-OperationsHR", pj.get("categoryId"))

    for f in ("displayName", "profession", "displayDescription", "defaultInitPrompt"):
        v = pj.get(f, {})
        check("字段 %s 中英双语" % f, bool(v.get("en")) and bool(v.get("zh")))

    dd_zh = pj.get("displayDescription", {}).get("zh", "")
    check("displayDescription.zh 长度 40-50", 40 <= len(dd_zh) <= 50, "%d 字" % len(dd_zh))

    tags = pj.get("tags", [])
    qp = pj.get("quickPrompts", [])
    check("tags 恰好 3 个", len(tags) == 3, str(len(tags)))
    check("quickPrompts 恰好 3 个", len(qp) == 3, str(len(qp)))
    check("defaultInitPrompt == quickPrompts[0]",
          bool(qp) and pj.get("defaultInitPrompt", {}).get("zh") == qp[0].get("zh"))

    # agent md
    agent_name = pj.get("agentName", "")
    md = root / "agents" / ("%s.md" % agent_name)
    if check("agents/%s.md 存在" % agent_name, md.exists()):
        text = md.read_text(encoding="utf-8")
        fm = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        check("Agent MD 有 frontmatter", bool(fm))
        if fm:
            check("frontmatter name == 文件名", ("name: %s" % agent_name) in fm.group(1))
            check("frontmatter 无 tools 字段", "tools:" not in fm.group(1))
        check("Agent MD 无 TODO 占位", "[TODO" not in text)
        check("Agent MD 含三闸门定义", "闸门 A" in text and "闸门 B" in text and "闸门 C" in text)

    # skills
    for sp in pj.get("skills", []):
        d = root / sp.lstrip("./")
        ok = check("技能目录 %s 含 SKILL.md" % d.name, (d / "SKILL.md").exists())
        if ok:
            sk = (d / "SKILL.md").read_text(encoding="utf-8")
            check("技能 %s 无 TODO 占位" % d.name, "[TODO" not in sk)
        for py in sorted(d.glob("scripts/*.py")):
            try:
                with tempfile.TemporaryDirectory() as td:
                    py_compile.compile(str(py), cfile=str(Path(td) / "x.pyc"), doraise=True)
                check("脚本 %s 通过语法编译" % py.name, True)
            except py_compile.PyCompileError as e:
                check("脚本 %s 通过语法编译" % py.name, False, str(e)[:120])

    # avatar
    av = root / pj.get("avatar", "")
    if check("头像文件存在", av.exists(), pj.get("avatar", "")):
        size = png_size(av)
        check("头像为 PNG", size is not None)
        if size:
            check("头像 512x512", size == (512, 512), "%dx%d" % size)
        kb = av.stat().st_size / 1024
        check("头像 ≤500KB", kb <= 500, "%.1f KB" % kb)

    # docs
    for doc in REQUIRED_DOCS:
        check("文档 %s 存在" % doc, (root / doc).exists())

    # forbidden
    for bad in ("hooks", "commands", ".lsp.json"):
        check("无禁用项 %s" % bad, not (root / bad).exists())

    # global TODO scan
    todo_files = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix in (".md", ".json", ".py") and p.name != "selfcheck.py":
            if "[TODO" in p.read_text(encoding="utf-8", errors="ignore"):
                todo_files.append(str(p.relative_to(root)))
    check("全包无 TODO 占位", not todo_files, ", ".join(todo_files))

    fails = [r for r in results if not r[1]]
    for n, ok, detail in results:
        print("%s %s%s" % ("PASS" if ok else "FAIL", n, ("  -> " + detail) if detail else ""))
    print("\n%d checks, %d failed" % (len(results), len(fails)))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
