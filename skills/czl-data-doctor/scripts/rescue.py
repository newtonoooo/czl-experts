#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rescue.py — 后台指标分级与 30 天救书表（纯标准库，离线）

补的是"数据诊断偏粗"这块：funnel.py 只算相邻章追读率，本脚本处理
整体指标（吸量、追读、完读、章均时长），给分级、归因、当周动作，
再排一张 30 天表。

用法：
    python rescue.py --metrics 吸量=300,追读=28,完读=12,章均完读=45,时长=75
    python rescue.py --metrics 吸量=300,追读=28 --track 都市 --plan 救书表.md
    python rescue.py --thresholds my.json --metrics ...

**口径说明**：这里的阈值是通用经验值，不是任何平台的官方红线。
平台规则会变，用到具体平台时必须自己核对当期公示；本脚本只做
"相对判断"（哪一项最拖后腿），不做"能不能上推荐"的预测。

作者：虫志龙 <47190078@qq.com>
许可：MIT
"""

import argparse
import json
import os
import sys

# 每项指标：单位、越高越好还是越低越好、三档线（S/A/B）、低于 B 判 D
DEFAULT = {
    "吸量": {"unit": "人/天", "higher": True, "tiers": [400, 200, 80],
             "why": "开书首周的曝光转化，决定能不能进下一层流量池"},
    "追读": {"unit": "%", "higher": True, "tiers": [35, 25, 15],
             "why": "相邻章留存，最直接反映读者还愿不愿意点下一章"},
    "完读": {"unit": "%", "higher": True, "tiers": [15, 10, 6],
             "why": "整本完读，决定长线推荐与完结收益"},
    "章均完读": {"unit": "%", "higher": True, "tiers": [55, 45, 35],
                 "why": "单章读完比例，暴露单章内部拖沓"},
    "时长": {"unit": "秒", "higher": True, "tiers": [90, 60, 40],
             "why": "单次阅读时长，太短说明跳读"},
}

# 指标 → 该先动哪一环
ACTION = {
    "吸量": ("书名/简介/封面三位一体", "czl-market-scout",
             "先改简介与书名，不动正文。三天换一版，看转化有没有起。"),
    "追读": ("开篇三章与每章章末", "czl-chapter-forge",
             "先算相邻章掉点（funnel.py），把掉得最狠那一章的结尾重写。"),
    "完读": ("中段压力与目标", "czl-chapter-forge",
             "查主角目标是否模糊、矛盾有没有升级；砍掉一条支线。"),
    "章均完读": ("单章节奏", "czl-voice-tune",
                 "跑 pace/voice 体检：段落是否过长、有没有大段设定说明。"),
    "时长": ("信息密度", "czl-voice-tune",
             "跳读多半因为对话与动作太少；把叙述改成场景。"),
}

GRADE_ORDER = ["S", "A", "B", "D"]


def grade(v, cfg):
    tiers = cfg["tiers"]
    higher = cfg.get("higher", True)
    if higher:
        if v >= tiers[0]:
            return "S"
        if v >= tiers[1]:
            return "A"
        if v >= tiers[2]:
            return "B"
        return "D"
    else:
        if v <= tiers[0]:
            return "S"
        if v <= tiers[1]:
            return "A"
        if v <= tiers[2]:
            return "B"
        return "D"


def parse_metrics(s):
    out = {}
    for part in s.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        try:
            out[k.strip()] = float(v.strip().rstrip("%"))
        except ValueError:
            continue
    return out


def plan_rows(drags, days=30):
    """30 天不是"每天改一点"，而是"改一次—看一次"的交替。改完必须留观察期，
    否则数据动了也分不清是哪一处改动带来的。"""
    checks = [(1, 3), (4, 6), (7, 9), (10, 12), (13, 15),
              (16, 18), (19, 21), (22, 24), (25, 27), (28, 30)]
    m1 = drags[0] if drags else None
    m2 = drags[1] if len(drags) > 1 else None
    stages = [
        ("先定位", "跑 funnel.py 找出掉得最狠的 3 章，不改稿" if m1 else "维持日更，攒够 10 章数据再看"),
        ("改第一处", ACTION[m1][0] if m1 else "按现有节奏写"),
        ("观察", "只记录数字，不改任何东西（改动效果要能归因）"),
        ("改第二处", ACTION[m2][0] if m2 else (ACTION[m1][0] if m1 else "维持")),
        ("观察", "同一时间窗对比，确认第一处改动是否有效"),
        ("改结构", "查主线目标与矛盾升级，砍一条支线" if m1 else "维持"),
        ("观察", "看追读曲线有没有抬头"),
        ("补钩子", "批量重写章末结尾（用 czl-chapter-forge 的钩子四型）" if m1 else "维持"),
        ("观察", "对比改前的相邻章追读率"),
        ("复盘", "只保留真的动了数的那一处，其余回滚"),
    ]
    rows = []
    for (d0, d1), (what, how) in zip(checks, stages):
        rows.append((d0, d1, what, how))
    return rows


def render(values, grades, drags, cfg, days):
    L = []
    L.append("=" * 66)
    worst = drags[0] if drags else None
    L.append("指标看板 ｜ %d 项 ｜ 最拖后腿：%s" % (len(values), worst or "无明显短板"))
    L.append("=" * 66)
    L.append("%-8s %-10s %-6s %-6s %s" % ("指标", "实测", "等级", "目标", "它决定什么"))
    for k, v in values.items():
        c = cfg.get(k)
        if not c:
            L.append("%-8s %-10s %-6s %-6s %s" % (k, v, "?", "—", "（未定义阈值，仅记录）"))
            continue
        L.append("%-8s %-10s %-6s %-6s %s"
                 % (k, "%g%s" % (v, c["unit"]), grades[k], c["tiers"][1], c["why"]))
    if drags:
        L.append("-" * 66)
        L.append("先动哪一环（按拖后腿程度排序）：")
        for m in drags:
            stage, skill, how = ACTION[m]
            L.append("  %s → 先动【%s】，交给 %s" % (m, stage, skill))
            L.append("     具体做法：%s" % how)
    L.append("-" * 66)
    L.append("%d 天表（每 3 天一个检查点，只改一项，改完再看数）" % days)
    L.append("%-9s %-10s %s" % ("第 X 天", "这一段做什么", "具体动作"))
    for d0, d1, what, how in plan_rows(drags, days):
        L.append("%-9s %-10s %s" % ("%d—%d" % (d0, d1), what, how))
    L.append("-" * 66)
    L.append("提醒：阈值是通用经验值，不是平台官方红线。换平台先核对当期公示，")
    L.append("      再改 thresholds JSON。本表只说明先后顺序，不预测结果。")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="指标分级与 30 天救书表")
    ap.add_argument("--metrics", required=True, help="如 吸量=300,追读=28,完读=12")
    ap.add_argument("--thresholds", default=None, help="自定义阈值 JSON")
    ap.add_argument("--track", default="", help="赛道名，仅写入报告抬头")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--plan", default=None, help="把 30 天表另存为 md")
    ap.add_argument("--json", dest="json_out", default=None)
    a = ap.parse_args()

    values = parse_metrics(a.metrics)
    if not values:
        print("没解析到指标。格式：吸量=300,追读=28,完读=12")
        return 2

    cfg = dict(DEFAULT)
    if a.thresholds:
        if not os.path.exists(a.thresholds):
            print("找不到阈值文件：%s" % a.thresholds)
            return 2
        with open(a.thresholds, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))

    grades = {}
    drags = []
    for k, v in values.items():
        c = cfg.get(k)
        if not c:
            grades[k] = "?"
            continue
        g = grade(v, c)
        grades[k] = g
        if g in ("B", "D"):
            drags.append(k)
    # 越靠后越优先（D 优先于 B）
    drags.sort(key=lambda k: -GRADE_ORDER.index(grades[k]))

    print(render(values, grades, drags, cfg, a.days))

    if a.plan:
        d = os.path.dirname(os.path.abspath(a.plan))
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        with open(a.plan, "w", encoding="utf-8") as f:
            f.write("# 救书表%s\n\n```\n" % ("（" + a.track + "）" if a.track else ""))
            f.write(render(values, grades, drags, cfg, a.days))
            f.write("\n```\n")
        print("已写入：%s" % a.plan)

    if a.json_out:
        d = os.path.dirname(os.path.abspath(a.json_out))
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        with open(a.json_out, "w", encoding="utf-8") as f:
            json.dump({"values": values, "grades": grades, "drags": drags},
                      f, ensure_ascii=False, indent=2)
        print("已写入：%s" % a.json_out)

    return 0 if not [k for k in drags if grades[k] == "D"] else 1


if __name__ == "__main__":
    sys.exit(main())
