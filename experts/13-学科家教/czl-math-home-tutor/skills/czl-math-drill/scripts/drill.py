#!/usr/bin/env python3
"""drill.py - lay out one practice session from a list of breakpoints.

The failure mode this prevents: a parent buys a workbook, the kid does 30
questions of the same shape, gets 28 right, and learns nothing that transfers.
Three tiers with different jobs fix that:

    同型 (same shape, new numbers)   - proves the routine is available at all
    换皮 (new context, same move)    - proves it is not tied to the wording
    换轴 (same knowledge, new ask)   - proves it transfers; this is the only
                                       tier that predicts exam performance

Usage
-----
    python drill.py --weak "导数单调性:M,解析几何弦长:M" --minutes 45
    python drill.py --weak "数列求和:A" --minutes 30 --tier-ratio 5:3:2
    python drill.py --weak "导数:M" --minutes 45 --json session.json

Each weak point may carry an error code (C/M/A/W/R) after a colon; the code
changes how much time goes to 同型 versus 换轴. No code = M.

Exit code: 0 ok, 2 bad input.
"""

import argparse
import json
import sys

TIER_MINUTES = {"同型": 5, "换皮": 7, "换轴": 10}
TIER_JOB = {
    "同型": "确认这套动作调得出来（换数字不换结构）",
    "换皮": "确认动作不绑在某种措辞上（换情境不换动作）",
    "换轴": "确认能迁移（同知识点换问法）——只有这一档能预测考场表现",
}
# C 类要先补定义，同型题的意义有限；A 类靠量，同型占比要高
CODE_RATIO = {
    "C": (2, 2, 1),
    "M": (2, 2, 2),
    "A": (5, 2, 1),
    "W": (3, 1, 1),
    "R": (3, 2, 1),
}
CODE_NAMES = {"C": "概念", "M": "方法", "A": "运算", "W": "书写", "R": "读题"}


def parse_weak(text):
    items = []
    for chunk in text.replace("，", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" in chunk:
            name, code = chunk.rsplit(":", 1)
            code = code.strip().upper()[:1]
        else:
            name, code = chunk, "M"
        if code not in CODE_NAMES:
            raise ValueError("unknown code %r on %r (use C/M/A/W/R)" % (code, name))
        items.append({"knowledge": name.strip(), "code": code})
    if not items:
        raise ValueError("no breakpoints given")
    return items


def parse_ratio(text):
    parts = [float(p) for p in text.replace("，", ":").split(":")]
    if len(parts) != 3 or sum(parts) <= 0:
        raise ValueError("--tier-ratio needs three positive numbers, e.g. 4:3:3")
    total = sum(parts)
    return [p / total for p in parts]


def fit_tiers(budget, weights, ratio):
    """Choose 同型/换皮/换轴 counts so the session never exceeds its budget.

    Greedy but ordered: 同型 first (it is the entry gate), then 换皮, then 换轴.
    A tier that cannot afford one question at the current budget is dropped
    rather than truncated - a 3-minute 换轴 question teaches nothing.
    """
    names = ("同型", "换皮", "换轴")
    wsum = sum(weights) or 1
    target = []
    for name, w, r in zip(names, weights, ratio):
        share = (w / wsum + r) / 2          # code preference blended with user ratio
        target.append(share)

    counts = [0, 0, 0]
    spent = 0
    # first pass: proportional floors, entry tier gets at least one
    for i, name in enumerate(names):
        want = target[i] * budget / TIER_MINUTES[name]
        c = int(want)
        if i == 0:
            c = max(1, c)
        elif want >= 0.5:
            c = max(1, c)
        counts[i] = c
        spent += c * TIER_MINUTES[name]

    # trim from the back until it fits
    while spent > budget:
        changed = False
        for i in (2, 1, 0):
            if counts[i] > (1 if i == 0 else 0):
                if i == 0 and counts[0] == 1:
                    continue
                counts[i] -= 1
                spent -= TIER_MINUTES[names[i]]
                changed = True
                break
        if not changed:
            break

    # spend leftovers on more 同型, which is the cheapest way to add reps
    while spent + TIER_MINUTES["同型"] <= budget:
        counts[0] += 1
        spent += TIER_MINUTES["同型"]

    return [{"tier": n, "count": c, "minutes": c * TIER_MINUTES[n], "job": TIER_JOB[n]}
            for n, c in zip(names, counts) if c > 0]


def plan(items, minutes, ratio, max_points=3):
    # a breakpoint needs at least ~12 minutes to be worth touching; below that
    # the session is better spent on one thing than on three
    max_points = max(1, min(max_points, minutes // 12))
    items = items[:max_points]
    # first breakpoint carries the session; later ones get a maintenance share
    shares = [1.0] if len(items) == 1 else [0.6] + [0.4 / (len(items) - 1)] * (len(items) - 1)
    budgets = [int(round(minutes * s)) for s in shares]
    # rounding must not push the total over what the user allotted
    drift = minutes - sum(budgets)
    if drift:
        heaviest = budgets.index(max(budgets))
        budgets[heaviest] += drift

    out = []
    for item, budget in zip(items, budgets):
        weights = CODE_RATIO[item["code"]]
        if len(items) > 1 and budget < minutes * 0.5:
            weights = (2, 1, 1)          # maintenance: keep the routine warm only
        tiers = fit_tiers(budget, weights, ratio)
        out.append({
            "knowledge": item["knowledge"], "code": item["code"],
            "budget": budget,
            "planned": sum(t["minutes"] for t in tiers),
            "tiers": tiers,
        })
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Lay out one practice session.")
    ap.add_argument("--weak", required=True,
                    help='断点列表，如 "导数单调性:M,解析几何弦长:M"')
    ap.add_argument("--minutes", type=int, default=45)
    ap.add_argument("--tier-ratio", default="4:3:3",
                    help="同型:换皮:换轴 的时间比，默认 4:3:3")
    ap.add_argument("--json", help="also dump the session as JSON")
    args = ap.parse_args(argv)

    try:
        items = parse_weak(args.weak)
        ratio = parse_ratio(args.tier_ratio)
    except ValueError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2

    sessions = plan(items, args.minutes, ratio)
    print("# 单次训练处方（%d 分钟上限）\n" % args.minutes)
    print("主码决定配比：概念类先补定义，运算类靠量，方法类三档均衡。\n")
    for s in sessions:
        print("## %s　主码 %s（%s）\n"
              % (s["knowledge"], s["code"], CODE_NAMES[s["code"]]))
        print("| 阶段 | 题量 | 用时 | 这一步在验什么 |")
        print("|---|---|---|---|")
        for t in s["tiers"]:
            print("| %s | %d 道 | %d 分钟 | %s |"
                  % (t["tier"], t["count"], t["minutes"], t["job"]))
        print("| 合计 | %d 道 | %d 分钟 | 预算 %d 分钟 |"
              % (sum(t["count"] for t in s["tiers"]), s["planned"], s["budget"]))
        print()

    print("## 出题要求（给我看的，不是给学生）\n")
    print("1. 每道题必须标：考点、改动点、答案。不给解析，解析等学生做完再讲。")
    print("2. 同型只换数字与符号，结构一字不动；换皮换情境（几何/应用/表格），"
          "动作不变；换轴换问法（求值↔求范围↔证存在），知识点不变。")
    print("3. 换轴题至少有一道要学生自己判断用哪条路，题干不提示。")
    print("4. 题量宁少不多。计划 4 道就出 4 道，多出来的下次用。")
    print()
    print("## 停止条件\n")
    print("- 同型连错 2 道：停，回到拆题，说明动作本身没建立。")
    print("- 换皮全对、换轴全错：说明会套不会用，下次把时间全给换轴。")
    print("- 到时间就停，不管做到第几道。做完比做多重要。")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"minutes": args.minutes, "sessions": sessions},
                      fh, ensure_ascii=False, indent=2)
        print("\n[written] %s" % args.json, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
