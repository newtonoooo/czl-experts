#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q6 档位站：按七猫纯分成阶梯全勤表定位档位与缺口。纯标准库，离线运行。

数据来源：七猫中文网官方福利页（签约及分成模式 · 纯分成阶梯全勤奖，2025-02 版本）。
平台会调整，跑之前先核对官方页；本脚本只做查表与算差，不做预测。
"""

import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# (下限含, 上限不含, 千字单价, 日阅读UV门槛)
TABLE = {
    "normal": [
        (0, 6, 0, 0),
        (6, 10, 7, 0),
        (10, 15, 10, 0),
        (15, 20, 15, 500),
        (20, 25, 25, 500),
        (25, 30, 40, 500),
        (30, 35, 80, 1000),
        (35, 40, 100, 2000),
        (40, None, 200, 5000),
    ],
    "wuxia": [
        (0, 8, 0, 0),
        (8, 18, 15, 500),
        (18, None, 25, 500),
    ],
    "niandai": [
        (0, 10, 0, 0),
        (10, 18, 10, 500),
        (18, 28, 25, 500),
        (28, None, 50, 500),
    ],
}

LABEL = {
    "normal": "普通类型（男频通用 / 女频通用）",
    "wuxia": "特色类型 · 武侠仙侠（男频）",
    "niandai": "特色类型 · 年代重生（女频）",
}


def band(lo, hi):
    return "%.0f%% 以下" % hi if lo == 0 else \
           ("%.0f%% 以上" % lo if hi is None else "%.0f%%（含）~ %.0f%%" % (lo, hi))


def locate(kind, retention):
    tbl = TABLE[kind]
    for i, (lo, hi, rate, uv) in enumerate(tbl):
        if retention >= lo and (hi is None or retention < hi):
            return i, (lo, hi, rate, uv)
    return len(tbl) - 1, tbl[-1]


def main():
    ap = argparse.ArgumentParser(description="Q6 七猫留存档位定位")
    ap.add_argument("--retention", type=float, required=True, help="十万字处平均留存，百分比数值，如 9 表示 9%%")
    ap.add_argument("--uv", type=float, default=None, help="日阅读 UV，如 300")
    ap.add_argument("--type", default="normal", choices=["normal", "wuxia", "niandai"],
                    help="normal=普通，wuxia=武侠仙侠男频，niandai=年代重生女频")
    ap.add_argument("--months", type=int, default=99, help="签约后第几个月，用于前 2 个月规则")
    args = ap.parse_args()

    r = args.retention
    if r < 0 or r > 100:
        print("[错误] --retention 应为 0-100 的百分比数值。")
        return 2

    print("=" * 66)
    print("Q6 档位站 · 留存分档定位")
    print("=" * 66)
    print("类型：%s" % LABEL[args.type])
    print("输入：均留 %.1f%%，日阅读 UV %s" % (r, ("%.0f" % args.uv) if args.uv is not None else "未提供"))
    if args.months <= 2:
        print()
        print("[前 2 个月规则] 未出均留阶段，日更 >= 4000 字且无断更，按 6 元/千字计。")
        print("               这条只在头两个月成立，别拿它当长期收入算。")
    print()

    idx, cur = locate(args.type, r)
    lo, hi, rate, uv_req = cur

    print("-" * 66)
    print("当前档位")
    print("-" * 66)
    print("  档位：第 %d 档 / 共 %d 档" % (idx + 1, len(TABLE[args.type])))
    print("  区间：%s" % band(lo, hi))
    print("  千字单价：%s 元" % ("0（这一档没有全勤）" if rate == 0 else "%.0f" % rate))
    if uv_req:
        ok = (args.uv is not None and args.uv >= uv_req)
        if args.uv is None:
            print("  UV 门槛：>= %.0f（未验证：你没给 UV）" % uv_req)
        else:
            print("  UV 门槛：>= %.0f    你的 UV：%.0f    %s" % (uv_req, args.uv, "达标" if ok else "不达标"))
    else:
        print("  UV 门槛：本档无附加门槛")

    if rate > 0 and uv_req and args.uv is not None and args.uv < uv_req:
        print()
        print("  [注意] 均留进档了，但 UV 没到。这一档的单价拿不满——这是流量问题，不是正文问题，")
        print("         动正文没用，要把力气放在推荐位与站内曝光上。")

    # 下一档
    if idx + 1 < len(TABLE[args.type]):
        nlo, nhi, nrate, nuv = TABLE[args.type][idx + 1]
        gap = nlo - r
        print()
        print("-" * 66)
        print("下一档")
        print("-" * 66)
        print("  区间：%s" % band(nlo, nhi))
        print("  千字单价：%.0f 元（提升 %.0f 元/千字）" % (nrate, max(0, nrate - rate)))
        print("  均留缺口：%.1f 个百分点" % gap)
        if nuv:
            print("  还需同时满足：日阅读 UV >= %.0f" % nuv)
        print()
        print("[动作建议]")
        print("  1. 先定位掉点：把均留按卷拆开，找出掉得最狠的那一卷，再按章拆。")
        print("  2. 掉点通常只有四种原因：主线断了、反派太弱、感情线拖、更新不稳。")
        print("  3. 改完看 7 天，别看 1 天。单日波动不构成结论。")
    else:
        print()
        print("[说明] 已在最高档。守档比冲档重要：更新稳定 + 不灌水，比改稿更能守住单价。")

    print()
    print("-" * 66)
    print("达标天数规则（官方口径）")
    print("-" * 66)
    print("  连载状态下，当月同时满足平均留存与阅读 UV 的天数，需超过当月出该数据总天数的一半。")
    print("  例：当月出数据 31 天，一半是 15.5 天，则至少 16 天要同时达标。")
    print()
    print("[口径] 官方口径，以作者后台为准。本脚本按公开分档表查表，平台调整后需同步更新。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
