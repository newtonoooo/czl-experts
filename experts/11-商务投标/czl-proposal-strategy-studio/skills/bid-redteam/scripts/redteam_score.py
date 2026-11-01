#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Red-team scoring: score our draft against the scoring table, then against rivals.

Usage:
    python redteam_score.py review.json [--md out.md]

Input JSON:
{
  "project": "某某医院机房改造",
  "items": [
    {"item": "技术方案", "score": 30, "self": 24,
     "rivals": {"低价型": 27, "关系型": 25, "技术型": 28}},
    {"item": "实施计划", "score": 15, "self": 13, "rivals": {"低价型": 13}},
    {"item": "服务承诺", "score": 10, "self": 6, "rivals": {"关系型": 9}}
  ],
  "checks": [
    {"item": "资格文件齐全", "done": true},
    {"item": "签字盖章", "done": false}
  ]
}

Outputs: our total and score rate, per-rival totals, biggest three losses,
recoverable points, disqualification checklist status, verdict.
Exit: 0 ok, 2 invalid input.
"""
import json
import sys


def out(text=""):
    sys.stdout.write(text + "\n")


def fail(msg):
    out("ERROR: " + msg)
    sys.exit(2)


def pct(a, b):
    return (a / b * 100) if b else 0.0


def main():
    argv = sys.argv[1:]
    if not argv:
        out(__doc__)
        sys.exit(2)
    try:
        data = json.load(open(argv[0], "r", encoding="utf-8"))
    except FileNotFoundError:
        fail("找不到输入文件: %s" % argv[0])
    except json.JSONDecodeError as e:
        fail("JSON 解析失败: %s" % e)

    items = data.get("items") or []
    if not items:
        fail("items 为空")
    checks = data.get("checks") or []

    total_w = 0.0
    our = 0.0
    rival_totals = {}
    rows = []
    for it in items:
        name = it.get("item", "?")
        try:
            w = float(it.get("score"))
            s = float(it.get("self"))
        except (TypeError, ValueError):
            fail("条目「%s」的 score/self 必须是数字" % name)
        if s > w:
            fail("条目「%s」自评分 %.1f 超过满分 %.1f" % (name, s, w))
        total_w += w
        our += s
        rivals = it.get("rivals") or {}
        for rn, rv in rivals.items():
            try:
                rival_totals[rn] = rival_totals.get(rn, 0.0) + float(rv)
            except (TypeError, ValueError):
                fail("条目「%s」对手「%s」分数不是数字" % (name, rn))
        rows.append((name, w, s, w - s))

    rows_by_loss = sorted(rows, key=lambda r: -r[3])
    recoverable = sorted([r for r in rows if r[1] and r[2] / r[1] < 0.8],
                         key=lambda r: -(r[1] - r[2]))
    missing = [c.get("item", "?") for c in checks if not c.get("done")]

    L = ["# 红队评审记录", ""]
    L.append("项目：%s" % data.get("project", "（未填）"))
    L.append("")
    L.append("## 一、按评分表自评")
    L.append("")
    L.append("| 得分点 | 满分 | 自评 | 丢分 |")
    L.append("|---|---|---|---|")
    for name, w, s, loss in rows:
        L.append("| %s | %.1f | %.1f | %.1f |" % (name, w, s, loss))
    L.append("| **合计** | **%.1f** | **%.1f** | **%.1f** |" % (total_w, our, total_w - our))
    L.append("")
    L.append("自评得分率：**%.1f%%**" % pct(our, total_w))
    L.append("")

    if rival_totals:
        L.append("## 二、对手视角（假设分）")
        L.append("")
        L.append("| 对手类型 | 预估总分 | 与我方差 |")
        L.append("|---|---|---|")
        for rn, rv in sorted(rival_totals.items(), key=lambda x: -x[1]):
            L.append("| %s | %.1f | %+.1f |" % (rn, rv, our - rv))
        L.append("")
        top_rival = max(rival_totals.values())
        gap = our - top_rival
        if gap > 0:
            verdict = "领先 %.1f 分，重点是别丢低级分：格式、盖章、响应偏离表。" % gap
        elif gap > -5:
            verdict = "胶着，落后 %.1f 分，需要在一到两个高分项上做出可验证的增量。" % abs(gap)
        else:
            verdict = "落后 %.1f 分，先确认是否值得投；若投，必须换打法或找联合体。" % abs(gap)
        L.append("**判断：%s**" % verdict)
        L.append("")
    else:
        L.append("## 二、对手视角")
        L.append("")
        L.append("未提供对手假设分。建议至少设三类：低价型、关系型、技术型，各填一版再比。")
        L.append("")

    L.append("## 三、丢分最多的三项")
    L.append("")
    for name, w, s, loss in rows_by_loss[:3]:
        L.append("- **%s**：丢 %.1f 分（自评 %.1f / 满分 %.1f）" % (name, loss, s, w))
    L.append("")

    if recoverable:
        L.append("## 四、还能捞回来的分（自评得分率 <80% 的项，按可得分数排序）")
        L.append("")
        for name, w, s, loss in recoverable[:5]:
            L.append("- %s：可捞 %.1f 分，做法是补证据或补承诺的具体数字" % (name, w - s))
        L.append("")
    else:
        L.append("## 四、还能捞回来的分")
        L.append("")
        L.append("各项自评得分率均 ≥80%，说明要么写得确实好，要么自评太宽松。建议换人复评。")
        L.append("")

    L.append("## 五、交标核查")
    L.append("")
    if not checks:
        L.append("未提供核查项。交标前至少核对：资格文件、签字盖章、份数、密封、命名、上传时间。")
    else:
        L.append("已确认 %d / %d 项。" % (len(checks) - len(missing), len(checks)))
        if missing:
            L.append("")
            L.append("**未完成：%s**" % "、".join(missing))
            L.append("")
            L.append("任何一项未确认，都不算可交。")
        else:
            L.append("")
            L.append("全部确认。建议再做一次「换人复核」：由没参与写作的人按清单点一遍。")
    L.append("")
    L.append("> 自评分是主观的。同一份稿子让两个人独立打分，差距超过 10% 时，先讨论标准，不要讨论分数。")

    report = "\n".join(L)
    out(report)
    if "--md" in argv:
        i = argv.index("--md")
        if i + 1 < len(argv):
            open(argv[i + 1], "w", encoding="utf-8").write(report + "\n")
            out("\n已写入: %s" % argv[i + 1])


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
