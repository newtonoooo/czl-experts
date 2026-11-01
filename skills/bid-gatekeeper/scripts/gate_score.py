#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Go/No-Go weighted score for a bid opportunity.

Usage:
    python gate_score.py case.json [--md report.md]

Input JSON:
{
  "project": "某某医院机房改造",
  "criteria": [
    {"key": "资格匹配", "score": 4, "weight": 0.25, "note": "有同类资质"},
    {"key": "客户基础", "score": 2, "weight": 0.15},
    {"key": "方案差异", "score": 3, "weight": 0.25},
    {"key": "交付风险", "score": 3, "weight": 0.20},
    {"key": "商务空间", "score": 4, "weight": 0.15}
  ],
  "must_haves": [{"item": "近三年同类业绩", "owner": "销售", "due": "2026-11-02"}]
}

score: 0-5, weight: 0-1 and must sum to 1.0 (tolerance 0.01).
Verdict: >=70 go, 50-69 conditional, <50 no-bid or consortium.
Exit codes: 0 ok, 2 invalid input.
"""
import json
import sys

THRESHOLD_GO = 70.0
THRESHOLD_COND = 50.0


def out(text=""):
    sys.stdout.write(text + "\n")


def fail(msg):
    out("ERROR: " + msg)
    sys.exit(2)


def load(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        fail("找不到输入文件: %s" % path)
    except json.JSONDecodeError as e:
        fail("JSON 解析失败: %s" % e)


def validate(data):
    criteria = data.get("criteria") or []
    if not criteria:
        fail("criteria 为空，至少需要 1 个维度")
    total_w = 0.0
    for i, c in enumerate(criteria, 1):
        if "key" not in c:
            fail("第 %d 个维度缺少 key" % i)
        s = c.get("score")
        w = c.get("weight")
        if not isinstance(s, (int, float)) or not 0 <= s <= 5:
            fail("维度「%s」的 score 必须是 0-5 的数字" % c["key"])
        if not isinstance(w, (int, float)) or not 0 < w <= 1:
            fail("维度「%s」的 weight 必须是 0-1 之间的数字" % c["key"])
        total_w += w
    if abs(total_w - 1.0) > 0.01:
        fail("权重之和为 %.3f，必须等于 1.0（容差 0.01）" % total_w)
    return criteria


def verdict(total):
    if total >= THRESHOLD_GO:
        return "全力投", "各项条件基本成立，可锁资源并进入读标关。"
    if total >= THRESHOLD_COND:
        return "条件投", "存在明显短板，需先拿到必须项，否则退出。"
    return "不投或改联合体", "短板集中在少数维度，单打独斗性价比低。"


def render(data, criteria):
    rows = []
    total = 0.0
    for c in criteria:
        pts = c["score"] / 5.0 * c["weight"] * 100
        total += pts
        rows.append((c["key"], c["score"], c["weight"], pts, c.get("note", "")))

    label, reason = verdict(total)
    weakest = sorted(criteria, key=lambda c: c["score"] / 5.0 * c["weight"] * 100)[:2]
    musts = data.get("must_haves") or []

    lines = []
    lines.append("# 机会关评分记录")
    lines.append("")
    lines.append("项目：%s" % data.get("project", "（未填）"))
    lines.append("")
    lines.append("| 维度 | 得分(0-5) | 权重 | 折算分 | 备注 |")
    lines.append("|---|---|---|---|---|")
    for k, s, w, p, note in rows:
        lines.append("| %s | %s | %.0f%% | %.1f | %s |" % (k, s, w * 100, p, note))
    lines.append("")
    lines.append("**加权总分：%.1f / 100**" % total)
    lines.append("")
    lines.append("**结论：%s。** %s" % (label, reason))
    lines.append("")
    lines.append("拖分最多的两项：%s。" % "、".join(
        "%s（%s 分）" % (c["key"], c["score"]) for c in weakest))
    lines.append("")
    if musts:
        lines.append("进入下一关前必须拿到的事项（共 %d 项）：" % len(musts))
        for m in musts:
            lines.append("- %s｜责任人：%s｜期限：%s" % (
                m.get("item", "?"), m.get("owner", "待定"), m.get("due", "待定")))
    else:
        lines.append("未登记必须项：条件投的情况下，请先补一份必须项清单（事项/责任人/期限）。")
    lines.append("")
    lines.append("> 计分口径：折算分 = 得分/5 × 权重 × 100。分数由打分人主观给出，建议两人独立打分后取均值。")
    return "\n".join(lines)


def main():
    args = [a for a in sys.argv[1:]]
    if not args:
        out(__doc__)
        sys.exit(2)
    path = args[0]
    md_path = None
    if "--md" in args:
        i = args.index("--md")
        md_path = args[i + 1] if i + 1 < len(args) else None
    data = load(path)
    criteria = validate(data)
    report = render(data, criteria)
    out(report)
    if md_path:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(report + "\n")
        out("\n已写入: %s" % md_path)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
