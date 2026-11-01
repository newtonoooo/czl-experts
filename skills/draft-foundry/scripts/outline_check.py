#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
outline_check.py — 骨架（大纲）承重检查（朱笔 / draft-foundry 技能）

骨架的标准只有一条：每个节点都要能回答"这一段读者会得到什么"。
回答不出来的节点，写出来就是水段。这个脚本就查这一件事，外加几条结构常识。

约定的大纲格式:
    ## 01 节点名
    读者得到：一句话
    （可选）素材：……
    （可选）字数：600

    ## 02 节点名
    ...

用法:
    python outline_check.py outline.md
    python outline_check.py outline.md --json

退出码:
    0  通过
    1  有需要修的节点
    2  输入错误
"""

import argparse
import json
import re
import sys

HEAD_RE = re.compile(r"^(#{2,4})\s*(.+?)\s*$")
GET_RE = re.compile(r"^\s*(?:[-*>]\s*)?(?:\*\*)?读者得到(?:\*\*)?\s*[:：]\s*(.*)$")
WORD_RE = re.compile(r"^\s*(?:[-*>]\s*)?(?:\*\*)?字数(?:\*\*)?\s*[:：]\s*(\d+)")
BUDGET_RE = re.compile(r"字数预算\s*[:：]\s*(\d+)")


def parse(text):
    lines = text.splitlines()
    budget = None
    for ln in lines:
        m = BUDGET_RE.search(ln)
        if m:
            budget = int(m.group(1))
            break

    nodes = []
    cur = None
    for ln in lines:
        m = HEAD_RE.match(ln)
        if m:
            if cur:
                nodes.append(cur)
            cur = {"title": m.group(2).strip(), "get": "", "words": None, "line": 0}
            continue
        if cur is None:
            continue
        g = GET_RE.match(ln)
        if g and not cur["get"]:
            cur["get"] = g.group(1).strip()
            continue
        w = WORD_RE.match(ln)
        if w and cur["words"] is None:
            cur["words"] = int(w.group(1))
    if cur:
        nodes.append(cur)
    return nodes, budget


def check(nodes, budget):
    issues = []
    warns = []

    if not nodes:
        issues.append("没有识别到任何节点。节点请用「## 标题」格式书写。")
        return issues, warns

    for i, n in enumerate(nodes, 1):
        if not n["get"]:
            issues.append(f"节点 {i}「{n['title']}」没写「读者得到：」。写不出这句，说明这个节点不该存在。")
        elif len(n["get"]) < 4:
            issues.append(f"节点 {i}「{n['title']}」的「读者得到」太短，等于没写（'{n['get']}'）。")

    if len(nodes) < 5:
        warns.append(f"只有 {len(nodes)} 个节点，公众号长文一般 5—9 个。太少的骨架容易一段写干。")
    if len(nodes) > 9:
        warns.append(f"有 {len(nodes)} 个节点，超过 9 个。检查是否有两个节点在说同一件事。")

    # 节点名重复或高度相似
    seen = {}
    for i, n in enumerate(nodes, 1):
        key = re.sub(r"[\s\W]+", "", n["title"])[:6]
        if key and key in seen:
            warns.append(f"节点 {i} 与节点 {seen[key]} 标题开头相同（「{n['title']}」），可能重复。")
        else:
            seen[key] = i

    # 字数分配
    if budget:
        assigned = sum(n["words"] for n in nodes if n["words"])
        if assigned and abs(assigned - budget) > budget * 0.15:
            warns.append(f"节点字数合计 {assigned}，与预算 {budget} 相差超过 15%。")
        if not assigned:
            avg = budget // len(nodes)
            warns.append(f"节点未标字数，按预算均分每节约 {avg} 字（可以此填进骨架）。")
        else:
            heavy = [f"节点{i}({n['words']}字)" for i, n in enumerate(nodes, 1)
                     if n["words"] and n["words"] > budget * 0.4]
            if heavy:
                warns.append("单个节点占比过高：" + "、".join(heavy) + "。检查是否该拆。")

    # 结尾节点常见病：总结升华
    last = nodes[-1]["title"]
    if any(w in last for w in ("总结", "小结", "综上", "结语", "升华", "感悟")):
        warns.append(f"最后一个节点叫「{last}」。公众号结尾写总结会劝退，改成动作、场景或一句没说完的话。")

    return issues, warns


def main():
    ap = argparse.ArgumentParser(description="骨架承重检查")
    ap.add_argument("path", help="大纲文件（.md）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        with open(args.path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"读取失败：{e}", file=sys.stderr)
        sys.exit(2)

    nodes, budget = parse(text)
    issues, warns = check(nodes, budget)

    if args.json:
        print(json.dumps({
            "nodes": nodes,
            "budget": budget,
            "issues": issues,
            "warnings": warns,
            "ok": not issues,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"节点数：{len(nodes)}" + (f"｜字数预算：{budget}" if budget else ""))
        print("-" * 50)
        for i, n in enumerate(nodes, 1):
            mark = "✓" if n["get"] and len(n["get"]) >= 4 else "✗"
            print(f"{mark} {i:02d} {n['title']}")
            if n["get"]:
                print(f"     得到：{n['get']}")
            if n["words"]:
                print(f"     字数：{n['words']}")
        if issues:
            print("-" * 50)
            print("必须修：")
            for x in issues:
                print(f"  ✗ {x}")
        if warns:
            print("-" * 50)
            print("建议检查：")
            for x in warns:
                print(f"  → {x}")
        if not issues:
            print("-" * 50)
            print("骨架通过：每个节点都说得清读者能拿走什么。可以开写。")

    sys.exit(0 if not issues else 1)


if __name__ == "__main__":
    main()
