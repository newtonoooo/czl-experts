#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lint_project.py — 项目档案结构核查（纯标准库，离线）

检查七类问题：
    L1 缺章            章节号不连续
    L2 字数越界        单章低于下限 80% 或高于上限 125%
    L3 体检缺失/未过    没有 qc 报告，或报告判定为 FAIL
    L4 伏笔逾期        到期章已过仍未回收
    L5 称号漂移        同一章里同一人物用了两种以上称法
    L6 档案待复核      上一章问题未清还要往前写
    L7 文件不一致      state 里登记的章与磁盘上的文件对不上

用法：
    python lint_project.py --dir <作品目录> [--json 输出] [--max-chapter 87]

退出码：0 无阻断项；1 有阻断项。阻断项 = L1 / L3 / L4（核心）/ L6 / L7。

作者：虫志龙 <47190078@qq.com>
许可：随本专家包发布的原创代码，MIT。
"""

import argparse
import json
import os
import re
import sys

HANZI = re.compile(r"[\u4e00-\u9fff]")
ALNUM = re.compile(r"[A-Za-z0-9]")
HEADING = re.compile(r"^\s*#")

BLOCKING = {"L1", "L3", "L6", "L7"}


def count_chars(text):
    n = 0
    for line in text.splitlines():
        if HEADING.match(line):
            continue
        n += len(HANZI.findall(line)) + len(ALNUM.findall(line))
    return n


def read_json(p, default=None):
    if not os.path.exists(p):
        return default
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def lint(root, max_chapter=None):
    root = os.path.abspath(root)
    state_path = os.path.join(root, ".nproj", "state.json")
    st = read_json(state_path)
    if st is None:
        return {"ok": False, "error": "缺少 .nproj/state.json，先跑 nproj.py init"}

    bible = read_json(os.path.join(root, ".nproj", "bible.json"), {}) or {}
    chs = sorted(st.get("chapters", []), key=lambda c: c["n"])
    nums = [c["n"] for c in chs]
    last = max(nums) if nums else 0
    if max_chapter:
        last = max(last, int(max_chapter))
    lo, hi = st.get("chapter_range", [2400, 3750])

    issues = []

    def add(code, level, msg, where=None):
        issues.append({"code": code, "level": level, "msg": msg, "where": where or ""})

    # L1 缺章
    gaps = [i for i in range(1, last + 1) if i not in nums]
    if gaps:
        add("L1", "block", "缺章：%s" % "、".join(str(g) for g in gaps[:15]),
            "chapters/ 下没有对应文件")

    # L2 字数越界
    thin = [c for c in chs if c["chars"] < int(lo * 0.8)]
    fat = [c for c in chs if c["chars"] > int(hi * 1.25)]
    for c in thin:
        add("L2", "warn", "第 %d 章仅 %d 字（下限 %d）" % (c["n"], c["chars"], lo), c["file"])
    for c in fat:
        add("L2", "warn", "第 %d 章 %d 字（上限 %d）" % (c["n"], c["chars"], hi), c["file"])

    # L3 体检
    for c in chs:
        if c.get("qc") in (None, "missing"):
            add("L3", "block", "第 %d 章没有体检报告" % c["n"], "qc/ch-%03d.report.json" % c["n"])
        elif c.get("qc") != "pass":
            add("L3", "block", "第 %d 章体检未过（%s）" % (c["n"], c.get("qc")), "")

    # L4 伏笔逾期
    for t in st.get("threads", []):
        if t.get("status") != "open":
            continue
        due = t.get("due_chapter") or 0
        if due and due <= last:
            add("L4", "block", "伏笔到期未收：%s（应于第 %d 章回收，现值第 %d 章）"
                % (t.get("content", t["id"])[:24], due, last), t["id"])
        elif due and 0 < due - last <= 3:
            add("L4", "warn", "伏笔将到期：%s（第 %d 章）" % (t.get("content", t["id"])[:24], due), t["id"])

    # L5 称号漂移
    chars = bible.get("characters", []) if isinstance(bible, dict) else []
    texts = {}
    for c in chs:
        p = os.path.join(root, c["file"])
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                texts[c["n"]] = f.read()
    for ch in chars:
        designations = []
        if ch.get("title"):
            designations.append(ch["title"])
        for a in ch.get("aliases", []) or []:
            if a:
                designations.append(a)
        if len(designations) < 2:
            continue
        for n, txt in texts.items():
            used = [d for d in designations if d in txt]
            if len(used) >= 2:
                add("L5", "warn",
                    "第 %d 章里「%s」出现 %d 种称法：%s"
                    % (n, ch.get("name", ch.get("id")), len(used), "、".join(used)),
                    "chapters/ch-%03d.md" % n)

    # L6 待复核
    if st.get("stale"):
        add("L6", "block", "档案待复核：%s" % st.get("stale_reason", "未说明原因"),
            ".nproj/state.json")

    # L7 文件一致性
    for c in chs:
        p = os.path.join(root, c["file"])
        if not os.path.exists(p):
            add("L7", "block", "第 %d 章登记了但文件不存在：%s" % (c["n"], c["file"]), c["file"])
            continue
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            real = count_chars(f.read())
        if abs(real - c["chars"]) > 5:
            add("L7", "warn", "第 %d 章字数与登记不符：登记 %d，实际 %d"
                % (c["n"], c["chars"], real), c["file"])

    blocks = [i for i in issues if i["level"] == "block"]
    warns = [i for i in issues if i["level"] == "warn"]
    return {
        "ok": True,
        "title": st.get("title", ""),
        "chapters": len(chs),
        "last_chapter": last,
        "chars": sum(c["chars"] for c in chs),
        "blocks": blocks,
        "warns": warns,
        "verdict": "PASS" if not blocks else "FAIL",
    }


def render(r):
    if not r.get("ok"):
        return "核查失败：" + r.get("error", "")
    L = []
    L.append("=" * 58)
    L.append("档案核查  判定 %s ｜ %d 章 ｜ %d 字 ｜ 阻断 %d ｜ 提示 %d"
             % (r["verdict"], r["chapters"], r["chars"], len(r["blocks"]), len(r["warns"])))
    L.append("=" * 58)
    if not r["blocks"] and not r["warns"]:
        L.append("无问题。")
    for i in r["blocks"]:
        L.append("✗ [%s] %s" % (i["code"], i["msg"]))
    for i in r["warns"]:
        L.append("! [%s] %s" % (i["code"], i["msg"]))
    if r["blocks"]:
        L.append("-" * 58)
        L.append("有阻断项：先修完再写下一章。")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="项目档案结构核查")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--json", dest="json_out", default=None)
    ap.add_argument("--max-chapter", type=int, default=None,
                    help="把已有章节数之外的进度也算进来（例如用户说写到第 87 章）")
    a = ap.parse_args()

    r = lint(a.dir, a.max_chapter)
    print(render(r))
    if a.json_out:
        d = os.path.dirname(os.path.abspath(a.json_out))
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        with open(a.json_out, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
        print("已写入：%s" % a.json_out)
    return 0 if r.get("ok") and r.get("verdict") == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
