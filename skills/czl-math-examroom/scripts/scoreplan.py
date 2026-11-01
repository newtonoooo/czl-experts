#!/usr/bin/env python3
"""scoreplan.py - turn a target score into a section-by-section plan with a skip line.

Most "how do I get to 120" advice is a mood, not a plan. This turns the target
into four numbers you can check at the end of a mock: how many marks each
section has to carry, how many minutes each section gets, and the point at
which the student must walk away from a question.

Default paper: the 19-question new-curriculum structure used from 2024 -
8 single choice (5 each), 3 multiple choice (6 each), 3 fill-in (5 each),
5 written answers (13+15+15+17+17). Pass --paper old22 for the 22-question
structure if the region still uses it.

Usage
-----
    python scoreplan.py --target 120
    python scoreplan.py --target 120 --current "单选=30,多选=9,填空=7,解答=35"
    python scoreplan.py --target 135 --minutes 120 --json plan.json

Exit code: 0 ok, 2 bad input.
"""

import argparse
import json
import sys

PAPERS = {
    "new19": [
        # name, questions, marks each
        ("单选", 8, 5),
        ("多选", 3, 6),
        ("填空", 3, 5),
        ("解答", 5, None),   # uses the explicit list below
    ],
    "old22": [
        ("单选", 8, 5),
        ("多选", 4, 5),
        ("填空", 4, 5),
        ("解答", 6, None),
    ],
}
SOLVE_MARKS = {
    "new19": [13, 15, 15, 17, 17],
    "old22": [10, 12, 12, 12, 12, 12],
}
# relative time per mark - multiple choice costs more per mark than single,
# because it is read, re-read, and often partially guessed
TIME_WEIGHT = {"单选": 1.0, "多选": 1.25, "填空": 1.2, "解答": 0.95}
# hard ceilings per question, regardless of what the proportional split says:
# a multiple-choice item that eats 9 minutes has already cost you two other items
SKIP_CAP = {"单选": 4, "多选": 5, "填空": 6, "解答": 14}
DEFAULT_RATE = {"单选": 0.75, "多选": 0.50, "填空": 0.50, "解答": 0.45}


def build_sections(paper):
    sections = []
    for name, count, each in PAPERS[paper]:
        if each is None:
            marks = SOLVE_MARKS[paper]
            sections.append({"name": name, "count": len(marks),
                             "full": sum(marks), "each": marks})
        else:
            sections.append({"name": name, "count": count,
                             "full": count * each, "each": [each] * count})
    return sections


def parse_current(text):
    """'单选=30,多选=9' -> {'单选': 30.0, '多选': 9.0}"""
    out = {}
    if not text:
        return out
    for chunk in text.replace("，", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            raise ValueError("--current expects 名称=分数, got %r" % chunk)
        k, v = chunk.split("=", 1)
        out[k.strip()] = float(v)
    return out


def allocate(delta, sections, current):
    """Spread `delta` marks over sections in proportion to remaining headroom."""
    head = {s["name"]: max(0.0, s["full"] - current[s["name"]]) for s in sections}
    gain = {s["name"]: 0.0 for s in sections}
    left = delta
    for _ in range(6):                     # cap-and-redistribute, converges fast
        pool = sum(head.values())
        if left <= 1e-9 or pool <= 1e-9:
            break
        moved = 0.0
        for name in head:
            if head[name] <= 0:
                continue
            share = left * head[name] / pool
            take = min(share, head[name])
            gain[name] += take
            head[name] -= take
            moved += take
        left -= moved
        if moved <= 1e-9:
            break
    return gain, left


def time_boxes(sections, minutes, buffer_min=10):
    weights = {}
    for s in sections:
        weights[s["name"]] = s["full"] * TIME_WEIGHT[s["name"]]
    total = sum(weights.values())
    usable = max(30, minutes - buffer_min)
    boxes = {}
    for s in sections:
        raw = usable * weights[s["name"]] / total
        boxes[s["name"]] = max(3, int(round(raw)))
    # fix rounding drift on the largest section
    drift = usable - sum(boxes.values())
    biggest = max(boxes, key=lambda k: boxes[k])
    boxes[biggest] += drift
    return boxes, buffer_min


def skip_line(name, rate, boxes, count):
    per_q = boxes / max(1, count)
    cap = SKIP_CAP.get(name, 10)
    soft = min(cap, max(2, int(per_q * 1.5)))
    if rate >= 0.85:
        return "全做，不留空；卡住超过 %d 分钟先跳过，回头再补" % soft
    if rate >= 0.7:
        return "全做；单题超过 %d 分钟立刻跳过，保住后面的分" % soft
    if rate >= 0.5:
        return "只做前 %d 道（或只做一眼有路的），其余按 %d 分钟/题硬控" % (
            max(1, int(count * 0.7)), min(cap, max(2, int(per_q))))
    if name == "解答":
        return "只做第 (1) 问；第 (2) 问写出关键式子就给分，超过 %d 分钟停" % min(
            8, max(4, int(per_q)))
    if name == "多选":
        return "只选完全确定的选项，不猜第三个；每题上限 %d 分钟" % min(4, cap)
    return "先做会的，剩下的最后 5 分钟统一处理"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Turn a target score into an exam plan.")
    ap.add_argument("--target", type=float, required=True, help="目标总分，0-150")
    ap.add_argument("--current", help='当前各题型得分，如 "单选=30,多选=9,填空=7,解答=35"')
    ap.add_argument("--paper", choices=sorted(PAPERS), default="new19")
    ap.add_argument("--minutes", type=int, default=120)
    ap.add_argument("--json", help="also dump the plan as JSON")
    args = ap.parse_args(argv)

    sections = build_sections(args.paper)
    full_total = sum(s["full"] for s in sections)
    if not (0 < args.target <= full_total):
        print("ERROR: --target must be within 1..%d" % full_total, file=sys.stderr)
        return 2

    given = parse_current(args.current)
    current = {}
    for s in sections:
        val = given.get(s["name"])
        if val is None:
            val = s["full"] * DEFAULT_RATE[s["name"]]
        current[s["name"]] = min(max(val, 0.0), s["full"])

    cur_total = sum(current.values())
    delta = args.target - cur_total
    gain, shortfall = allocate(max(0.0, delta), sections, current)
    boxes, buffer_min = time_boxes(sections, args.minutes)

    print("# 考场得分计划（%s，满分 %d，%d 分钟）\n"
          % ({"new19": "新高考 19 题", "old22": "22 题旧结构"}[args.paper],
             full_total, args.minutes))
    print("- 目标：%s" % num(args.target))
    print("- 当前估计：%s（各题型按%s）"
          % (num(cur_total), "实测" if given else "默认得分率"))
    print("- 需要多拿：%s 分" % num(max(0.0, delta)))
    if delta <= 0:
        print("- 目标不高于当前水平：本轮不做加法，只做稳定性（限时整卷 + 书写规范）")
    if shortfall > 0.5:
        print("- **不可行**：即使各题型满分也只能到 %s，缺口 %s 分。"
              "先把目标降到 %s 再看计划。"
              % (num(full_total - shortfall), num(shortfall), num(cur_total + sum(gain.values()))))
    elif args.target / full_total >= 0.95:
        print("- **不现实**：这个目标要求每一块都接近满分（整体得分率 ≥ 95%%），"
              "任何一处失误都补不回来。建议先按 %s 分做计划，"
              "拿到一次模考实测再上调。" % num(min(full_total, cur_total + 0.6 * (full_total - cur_total))))
    elif delta > 0.6 * max(1.0, full_total - cur_total):
        print("- **偏激进**：需要多拿的分数超过当前剩余空间的一半，"
              "先把目标拆成两段（先到 %s，再谈 %s）。"
              % (num(cur_total + (args.target - cur_total) / 2), num(args.target)))
    print()

    print("| 题型 | 满分 | 当前 | 目标 | 需要多拿 | 建议用时 | 放弃线 |")
    print("|---|---|---|---|---|---|---|")
    for s in sections:
        tgt = current[s["name"]] + gain[s["name"]]
        rate = tgt / s["full"] if s["full"] else 0
        print("| %s（%d 题） | %s | %s | %s | %s | %d 分钟 | %s |"
              % (s["name"], s["count"], num(s["full"]), num(current[s["name"]]),
                 num(tgt), num(gain[s["name"]]), boxes[s["name"]],
                 skip_line(s["name"], rate, boxes[s["name"]], s["count"])))
    print("| 检查 | - | - | - | - | %d 分钟 | 只查三样：答题卡填涂、"
          "结果代回、单位与范围 |" % buffer_min)
    print()

    print("## 按题分配（每题上限）\n")
    for s in sections:
        per = boxes[s["name"]] / s["count"]
        print("- %s：%d 题共 %d 分钟，平均 %.1f 分钟/题；前 %d 题应快于均值，"
              "把时间让给最后两题" % (s["name"], s["count"], boxes[s["name"]], per,
                                max(1, s["count"] // 2)))
    print()

    print("## 三条硬规矩\n")
    print("1. 到点就走。单题超过上限立刻跳过并在题号上画圈，全部做完再回来。")
    print("2. 解答题写不完也要写。写出关键式子、设出未知量、写出所用定理，都有分。")
    print("3. 最后 %d 分钟不碰新题，只做三件事：填涂、代回、查范围。" % buffer_min)

    plan = {
        "paper": args.paper, "target": args.target, "current_total": cur_total,
        "delta": max(0.0, delta), "infeasible_gap": shortfall,
        "sections": [
            {"name": s["name"], "full": s["full"], "current": current[s["name"]],
             "target": current[s["name"]] + gain[s["name"]],
             "minutes": boxes[s["name"]]}
            for s in sections],
        "check_minutes": buffer_min,
    }
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(plan, fh, ensure_ascii=False, indent=2)
        print("\n[written] %s" % args.json, file=sys.stderr)
    return 0


def num(v):
    if abs(v - round(v)) < 0.05:
        return str(int(round(v)))
    return "%.1f" % v


if __name__ == "__main__":
    sys.exit(main())
