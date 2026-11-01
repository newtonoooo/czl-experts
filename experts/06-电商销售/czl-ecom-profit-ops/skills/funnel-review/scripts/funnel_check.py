#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""funnel_check.py - GMV 变化拆解与归因排序（纯标准库）。

子命令
------
decompose  把两个周期的 GMV 变化拆成 流量 × 转化率 × 客单价 × (1-退款率) 四项贡献，
           用逐项替换法保证四项之和等于总变化。

口径说明：净成交额 = UV × 转化率 × 客单价 × (1 − 退款率)。
四项的贡献与替换顺序有关（交叉项被先替换的一项吃掉），所以输出里固定写明顺序。
做同比/环比前请先确认两期口径一致（埋点版本、活动错位、退款归属期）。

退出码：0 = 计算完成；2 = 输入错误。
"""

from __future__ import annotations

import argparse
import json
import sys

EPS = 1e-9

FIELDS = [
    ("uv", "流量 UV"),
    ("cvr", "转化率"),
    ("aov", "客单价"),
    ("refund", "退款率"),
]


def _num(x):
    return f"{x:,.0f}" if abs(x) >= 100 else f"{x:,.2f}"


def calc(p1, p2):
    v1 = p1["uv"] * p1["cvr"] * p1["aov"] * (1 - p1["refund"])
    v2 = p2["uv"] * p2["cvr"] * p2["aov"] * (1 - p2["refund"])
    total = v2 - v1

    steps = []
    cur = dict(p1)
    prev_val = v1
    for key, label in FIELDS:
        cur[key] = p2[key]
        val = cur["uv"] * cur["cvr"] * cur["aov"] * (1 - cur["refund"])
        effect = val - prev_val
        share = (effect / total) if abs(total) > EPS else None
        steps.append({
            "field": key,
            "label": label,
            "effect": round(effect, 2),
            "share": None if share is None else round(share, 4),
            "value_after": round(val, 2),
        })
        prev_val = val

    residual = (v2 - v1) - sum(s["effect"] for s in steps)
    ranked = sorted(steps, key=lambda s: abs(s["effect"]), reverse=True)
    return {
        "period1": {k: p1[k] for k, _ in FIELDS},
        "period2": {k: p2[k] for k, _ in FIELDS},
        "gmv1": round(v1, 2),
        "gmv2": round(v2, 2),
        "delta": round(total, 2),
        "delta_rate": round(total / v1, 4) if v1 > EPS else None,
        "steps": steps,
        "residual": round(residual, 2),
        "ranked": [s["label"] for s in ranked],
        "top_factor": ranked[0]["label"] if ranked else None,
        "direction": "上升" if total > EPS else ("下降" if total < -EPS else "持平"),
    }


def print_report(r):
    p1, p2 = r["period1"], r["period2"]
    print("## GMV 变化拆解")
    print(f"净成交额 = UV × 转化率 × 客单价 × (1 − 退款率)")
    print()
    print("| 指标 | 上期 | 本期 | 变化 |")
    print("|---|---:|---:|---:|")
    print(f"| 流量 UV | {_num(p1['uv'])} | {_num(p2['uv'])} | {_num(p2['uv'] - p1['uv'])} |")
    print(f"| 转化率 | {p1['cvr']*100:.2f}% | {p2['cvr']*100:.2f}% | {(p2['cvr']-p1['cvr'])*100:+.2f}pp |")
    print(f"| 客单价 | {_num(p1['aov'])} | {_num(p2['aov'])} | {_num(p2['aov'] - p1['aov'])} |")
    print(f"| 退款率 | {p1['refund']*100:.2f}% | {p2['refund']*100:.2f}% | {(p2['refund']-p1['refund'])*100:+.2f}pp |")
    print(f"| 净成交额 | {_num(r['gmv1'])} | {_num(r['gmv2'])} | {_num(r['delta'])} |")
    print()
    if r["delta_rate"] is not None:
        print(f"净成交额{r['direction']} {_num(abs(r['delta']))}，幅度 {r['delta_rate']*100:+.1f}%。")
    print()
    share_label = "占总降幅" if r["delta"] < -EPS else "占总增幅"
    print(f"| 拆解项 | 贡献额 | {share_label} | 替换后净成交额 |")
    print("|---|---:|---:|---:|")
    for s in r["steps"]:
        share = "—" if s["share"] is None else f"{s['share']*100:+.1f}%"
        print(f"| {s['label']} | {_num(s['effect'])} | {share} | {_num(s['value_after'])} |")
    print()
    print(f"四项合计 {_num(sum(s['effect'] for s in r['steps']))}，与总变化差额 {r['residual']}（应为 0.00）。")
    print(f"主因排序：{' > '.join(r['ranked'])}。")
    print()
    print("口径提醒：")
    print("1. 替换顺序为 UV → 转化率 → 客单价 → 退款率，交叉项归入先替换的一项；换顺序数字会变，结论方向通常不变。")
    print("2. 两期口径必须一致：埋点版本、活动错位、退款归属期、是否含运费，任一项变了要先断开趋势线。")


def main(argv=None):
    ap = argparse.ArgumentParser(description="GMV 变化拆解")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("decompose")
    for tag in ("p1", "p2"):
        p.add_argument(f"--{tag}-uv", dest=f"{tag}_uv", type=float, required=True)
        p.add_argument(f"--{tag}-cvr", dest=f"{tag}_cvr", type=float, required=True)
        p.add_argument(f"--{tag}-aov", dest=f"{tag}_aov", type=float, required=True)
        p.add_argument(f"--{tag}-refund", dest=f"{tag}_refund", type=float, default=0)
    p.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    data = {}
    for tag in ("p1", "p2"):
        d = {
            "uv": getattr(a, f"{tag}_uv"),
            "cvr": getattr(a, f"{tag}_cvr"),
            "aov": getattr(a, f"{tag}_aov"),
            "refund": getattr(a, f"{tag}_refund"),
        }
        if d["uv"] < 0 or d["cvr"] < 0 or d["aov"] < 0:
            print(f"输入错误：{tag} 的 UV / 转化率 / 客单价不能为负", file=sys.stderr)
            return 2
        if not (0 <= d["refund"] <= 1):
            print(f"输入错误：{tag} 的退款率应在 0–1 之间", file=sys.stderr)
            return 2
        if d["cvr"] > 1:
            print(f"输入错误：{tag} 的转化率是比例，不能大于 1", file=sys.stderr)
            return 2
        data[tag] = d

    r = calc(data["p1"], data["p2"])
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print_report(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
