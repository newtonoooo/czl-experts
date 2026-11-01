#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q7 现金流站：七猫全勤与保底的月度现金流核算。纯标准库，离线运行。

规则口径：七猫中文网官方福利页（全勤奖 / 稿费结算，2025-02 版本）。
关键约束：日更 4000（含）~6000 一档、6000（含）以上一档；每月最多计 20 万字；
         每月允许请假 1 天，请假当天字数不计入；统计口径为当日发布且审核通过的新增连载正文。
"""

import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ATTEND_CAP = 200000  # 每月计入全勤的最高字数

TIER = {
    "normal": [(0, 6, 0, 0), (6, 10, 7, 0), (10, 15, 10, 0), (15, 20, 15, 500),
               (20, 25, 25, 500), (25, 30, 40, 500), (30, 35, 80, 1000),
               (35, 40, 100, 2000), (40, None, 200, 5000)],
    "wuxia": [(0, 8, 0, 0), (8, 18, 15, 500), (18, None, 25, 500)],
    "niandai": [(0, 10, 0, 0), (10, 18, 10, 500), (18, 28, 25, 500), (28, None, 50, 500)],
}

# 超级纯分成：当月千字收入 -> (全勤千字奖励, 月最高奖金)
CHAOJI = [(20, 60, 10, 2000), (60, 80, 30, 6000), (80, 100, 40, 8000),
          (100, 300, 50, 10000), (300, 600, 150, 30000), (600, 1000, 300, 60000),
          (1000, 2000, 500, 100000), (2000, None, 1000, 200000)]


def baodi_rate(daily):
    if daily >= 6000:
        return 7
    if daily >= 4000:
        return 5
    return 0


def tier_rate(kind, retention):
    if retention is None:
        return 0
    for lo, hi, rate, _uv in TIER[kind]:
        if retention >= lo and (hi is None or retention < hi):
            return rate
    return 0


def chaoji_rate(kincome, months):
    if months <= 2:
        return 10, None
    if kincome is None:
        return 0, None
    for lo, hi, rate, cap in CHAOJI:
        if kincome >= lo and (hi is None or kincome < hi):
            return rate, cap
    return 0, None


def money(x):
    return "%.0f" % round(x)


def month_calc(daily, days, mode, price, retention, kind, months, kincome, share):
    chars = daily * days
    base_chars = min(chars, ATTEND_CAP)
    if mode == "baodi":
        rate = baodi_rate(daily)
        cap = None
        guarantee = price * chars / 1000.0
    elif mode == "chunfencheng":
        rate = tier_rate(kind, retention)
        cap = None
        guarantee = 0.0
    else:
        rate, cap = chaoji_rate(kincome, months)
        guarantee = 0.0
    attend = rate * base_chars / 1000.0
    if cap is not None:
        attend = min(attend, cap)
    total = guarantee + attend + share
    return chars, base_chars, rate, guarantee, attend, total, cap


def main():
    ap = argparse.ArgumentParser(description="Q7 七猫全勤与保底现金流核算")
    ap.add_argument("--daily", type=int, required=True, help="每天稳定更新的字数")
    ap.add_argument("--days", type=int, default=30, help="当月更新天数，默认 30")
    ap.add_argument("--leave", type=int, default=0, help="当月请假天数，官方每月最多 1 天")
    ap.add_argument("--price", type=float, default=0, help="保底千字单价，如 20")
    ap.add_argument("--mode", default="baodi", choices=["baodi", "chunfencheng", "chaoji"],
                    help="baodi=保底+超保底分成，chunfencheng=纯分成，chaoji=超级纯分成")
    ap.add_argument("--retention", type=float, default=None, help="十万字均留，纯分成用于查档")
    ap.add_argument("--type", default="normal", choices=["normal", "wuxia", "niandai"])
    ap.add_argument("--months", type=int, default=99, help="签约后第几个月，超级纯分成前 2 个月特殊")
    ap.add_argument("--kincome", type=float, default=None,
                    help="超级纯分成第 3 个月起的当月千字收入")
    ap.add_argument("--share", type=float, default=0, help="广告分成等其他收入，元")
    ap.add_argument("--plan", type=int, default=0, help="计划总字数，用于估算完本周期")
    args = ap.parse_args()

    if args.daily <= 0:
        print("[错误] --daily 必须大于 0。")
        return 2
    if args.days > 31:
        print("[错误] --days 不能超过 31。")
        return 2

    print("=" * 70)
    print("Q7 现金流站 · 月度收入与产能核算")
    print("=" * 70)
    print("模式：%s    日更：%d 字    月更天数：%d    请假：%d 天"
          % ({"baodi": "保底+超保底分成", "chunfencheng": "纯分成", "chaoji": "超级纯分成"}[args.mode],
             args.daily, args.days, args.leave))
    if args.mode == "baodi":
        print("保底单价：%s 元/千字" % (("%.0f" % args.price) if args.price else "未提供"))
    if args.mode == "chunfencheng":
        print("均留：%s    类型：%s"
              % (("%.1f%%" % args.retention) if args.retention is not None else "未提供", args.type))
    print()

    chars, base_chars, rate, guarantee, attend, total, cap = month_calc(
        args.daily, args.days, args.mode, args.price, args.retention, args.type,
        args.months, args.kincome, args.share)

    print("-" * 70)
    print("本月账")
    print("-" * 70)
    print("  实际更新字数：%d 字" % chars)
    print("  计入全勤字数：%d 字（上限 20 万字/月）" % base_chars)
    if chars > ATTEND_CAP:
        print("  [注意] 超出 %d 字不计入全勤，只计入分成口径。" % (chars - ATTEND_CAP))
    print("  全勤单价：%s 元/千字" % money(rate))
    if guarantee:
        print("  保底稿费：%s 元（%.0f 元/千字 × %d 字）" % (money(guarantee), args.price, chars))
    print("  全勤金额：%s 元%s" % (money(attend), ("（已触顶 %s 元）" % money(cap)) if cap else ""))
    if args.share:
        print("  其他收入：%s 元" % money(args.share))
    print("  ----")
    print("  月收入（推算）：%s 元" % money(total))
    print()
    print("  [口径] 官方稿费按自然月统计，次月 8 日发放。以上不含税费、不含打赏分成。")

    print()
    print("-" * 70)
    print("四个日更档位对比")
    print("-" * 70)
    print("  %-8s %-10s %-10s %-10s %-12s" % ("日更", "月字数", "全勤单价", "全勤金额", "月收入推算"))
    for d in (4000, 5000, 6000, 8000):
        c, bc, rt, g, a, t, cp = month_calc(d, args.days, args.mode, args.price,
                                            args.retention, args.type, args.months,
                                            args.kincome, args.share)
        print("  %-8s %-10s %-10s %-10s %-12s"
              % ("%d 字" % d, "%d" % c, "%.0f 元" % rt, money(a), money(t)))

    print()
    print("-" * 70)
    print("风险检查")
    print("-" * 70)
    risks = []
    if args.daily < 4000:
        risks.append("日更 %d 字低于 4000，拿不到全勤——这一档只有分成。" % args.daily)
    if args.days < 28:
        risks.append("月更 %d 天，断更 %d 天。全勤看的是当月达标天数，断更会直接吃掉当月全勤。"
                     % (args.days, 30 - args.days))
    if args.leave > 1:
        risks.append("请假 %d 天，超过官方每月 1 天额度，超出部分视为断更。" % args.leave)
    if args.mode == "baodi" and args.price <= 0:
        risks.append("没填保底单价，保底稿费按 0 计，实际收入会高于本表。")
    if args.mode == "chunfencheng" and args.retention is None:
        risks.append("没填均留，全勤单价按 0 计——纯分成下没有均留就没有全勤。")
    if args.mode == "chaoji" and args.months > 2 and args.kincome is None:
        risks.append("超级纯分成第 3 个月起要按当月千字收入查档，缺这个数算不出全勤。")
    if args.daily >= 8000:
        risks.append("日更 8000 连续 30 天是 24 万字，产能压力大，先确认能扛三周再签。")
    if not risks:
        risks.append("当前参数下没有触发硬性风险，但产能风险要每周复查一次。")
    for r in risks:
        print("  - %s" % r)

    if args.plan:
        print()
        print("-" * 70)
        print("完本周期")
        print("-" * 70)
        monthly = chars
        months_needed = args.plan / monthly if monthly else 0
        print("  计划 %d 字，按月更 %d 字，约需 %.1f 个月（%.0f 天）。"
              % (args.plan, monthly, months_needed, months_needed * 30))
        if months_needed > 18:
            print("  [提示] 超过 18 个月，建议压低规划或提高日更，否则中途崩更概率高。")

    print()
    print("[声明] 以上为推算，不是承诺。签约价、推荐、留存都由平台与编辑决定。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
