#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
segment_abc.py — 分层分析：ABC 集中度，或 RFM 三档。

用法：
    python segment_abc.py 订单.csv --key 客户ID --value 金额
    python segment_abc.py 订单.csv --key 客户ID --value 金额 --rfm --date 支付日期

ABC 口径：按金额降序累计，累计占比 ≤70% 为 A，70–90% 为 B，其余为 C。
RFM 口径：R（最近一次距今）、F（出现次数）、M（金额）各按五分位打 1–5 分，给出分群。
"""

import argparse
import sys
from datetime import date

import czl_core as C


def quintile_scores(values):
    """把一个数值列映射成 1–5 分，5 代表最优（用于 R 时需反向）。"""
    if not values:
        return {}
    s = sorted(values)
    cuts = [C.quantile(s, q) for q in (0.2, 0.4, 0.6, 0.8)]

    def score(v):
        for i, c in enumerate(cuts):
            if v <= c:
                return i + 1
        return 5

    return score


def main():
    ap = argparse.ArgumentParser(description="数证台 · 分层分析（ABC / RFM）")
    ap.add_argument("path", help="CSV/TSV 文件")
    ap.add_argument("--key", required=True, help="主体列名，如 客户ID")
    ap.add_argument("--value", required=True, help="金额列名")
    ap.add_argument("--date", help="日期列名（RFM 需要）")
    ap.add_argument("--rfm", action="store_true", help="输出 RFM 分群")
    ap.add_argument("--top", type=int, default=20, help="明细表列出前多少名，默认 20")
    ap.add_argument("--out", help="输出 Markdown 路径")
    args = ap.parse_args()

    if args.rfm and not args.date:
        C.die("用 --rfm 时必须给 --date")

    header, rows, _ = C.read_table(args.path)
    ki = C.col_index(header, args.key)
    vi = C.col_index(header, args.value)
    di = C.col_index(header, args.date) if args.date else None

    agg = {}
    dates = {}
    for r in rows:
        k = (r[ki] or "").strip()
        v = C.to_number(r[vi])
        if not k or v is None:
            continue
        a = agg.setdefault(k, {"sum": 0.0, "n": 0})
        a["sum"] += v
        a["n"] += 1
        if di is not None:
            d = C.to_date(r[di])
            if d:
                dates[k] = max(dates.get(k, date.min), d)

    if not agg:
        C.die("没有解析出任何有效的「%s + %s」组合，请检查列名" % (args.key, args.value))

    total = sum(a["sum"] for a in agg.values())
    items = sorted(agg.items(), key=lambda kv: -kv[1]["sum"])

    # ---- ABC
    cum, abc = 0.0, []
    for k, a in items:
        cum += a["sum"]
        share = cum / total if total else 0
        grade = "A" if share <= 0.70 else "B" if share <= 0.90 else "C"
        abc.append((k, a["sum"], a["n"], share, grade))

    cnt = {"A": 0, "B": 0, "C": 0}
    val = {"A": 0.0, "B": 0.0, "C": 0.0}
    for _, s, _, _, g in abc:
        cnt[g] += 1
        val[g] += s

    n_total = len(abc)
    top10 = max(1, int(round(n_total * 0.1)))
    top10_share = sum(x[1] for x in abc[:top10]) / total if total else 0

    L = []
    L.append("# 分层分析（ABC）\n")
    L.append("主体：`%s`　｜　口径：按 %s 汇总　｜　有效主体：%d 个　｜　总额：%s\n" % (
        args.key, args.value, n_total, C.money(total)))

    L.append(C.md_table(
        ["层级", "主体数", "主体占比", "金额", "金额占比", "判定口径"],
        [["A", cnt["A"], C.pct(cnt["A"] / n_total), C.money(val["A"]),
          C.pct(val["A"] / total) if total else "—", "累计金额前 70%"],
         ["B", cnt["B"], C.pct(cnt["B"] / n_total), C.money(val["B"]),
          C.pct(val["B"] / total) if total else "—", "累计 70%–90%"],
         ["C", cnt["C"], C.pct(cnt["C"] / n_total), C.money(val["C"]),
          C.pct(val["C"] / total) if total else "—", "累计 90% 之后"]]))
    L.append("")
    L.append("- 前 10%% 的主体（%d 个）贡献 %s 的金额。" % (top10, C.pct(top10_share)))
    L.append("- 集中度判断：%s" % (
        "高度集中，少数主体波动会直接改写整体数字，分析必须按主体分层" if top10_share >= 0.7
        else "较为集中，建议对 A 层单独成表" if top10_share >= 0.5
        else "相对分散，整体结论较稳"))
    L.append("")

    L.append("## 明细（前 %d）\n" % args.top)
    body = []
    for i, (k, s, n, share, g) in enumerate(abc[: args.top], 1):
        body.append([i, k, C.money(s), n, C.money(s / n) if n else "—", C.pct(share), g])
    L.append(C.md_table(["#", "主体", "金额", "次数", "均价", "累计占比", "层级"], body))
    L.append("")

    # ---- RFM
    if args.rfm:
        today = max(dates.values()) if dates else date.today()
        recency, freq, mon = {}, {}, {}
        for k, a in agg.items():
            mon[k] = a["sum"]
            freq[k] = a["n"]
            recency[k] = (today - dates[k]).days if k in dates else 999
        r_score = quintile_scores(list(recency.values()))
        f_score = quintile_scores(list(freq.values()))
        m_score = quintile_scores(list(mon.values()))

        seg = {}
        for k in agg:
            # R 越小越好，分数反向
            r = 6 - r_score(recency[k])
            f = f_score(freq[k])
            m = m_score(mon[k])
            key = (r, f, m)
            seg.setdefault(key, []).append(k)

        L.append("## RFM 分群\n")
        L.append("基准日取数据里的最大日期：%s。R 越近分越高，F/M 越大分越高。\n" % today)
        rows2 = []
        for key in sorted(seg, key=lambda t: (-(t[0] + t[1] + t[2]), -len(seg[t]))):
            users = seg[key]
            label = label_of(*key)
            rows2.append(["%d-%d-%d" % key, label, len(users),
                          C.pct(len(users) / n_total),
                          C.money(sum(mon[u] for u in users))])
        L.append(C.md_table(["R-F-M", "类型", "人数", "人数占比", "金额"], rows2))
        L.append("")
        L.append("> 分档含义：R 高=最近买过；F 高=买得频；M 高=花得多。具体阈值按五分位，跨期比较时需固定同一套阈值。")
        L.append("")

    L.append("## 结论边界\n")
    L.append("- ABC 只说明金额分布，不说明谁更值得投入；要判断价值，得结合毛利与获取成本。")
    L.append("- 主体数少于 30 个时，分层结果不稳定，只能当参考。")
    L.append("- 只有一次购买记录的主体，F 恒为 1，RFM 对它没有区分力。")
    L.append("")
    L.append("## 复现\n")
    L.append("```bash")
    L.append("python segment_abc.py %s --key %s --value %s%s" % (
        args.path, args.key, args.value,
        (" --rfm --date " + args.date) if args.rfm else ""))
    L.append("```")
    L.append("")
    L.append("---\n*由 czl-evidence-playbook / segment_abc.py 生成*")

    C.write_out("\n".join(L), args.out)
    return 0


def label_of(r, f, m):
    total = r + f + m
    if r >= 4 and f >= 4 and m >= 4:
        return "核心高价值"
    if r <= 2 and f >= 4:
        return "高价值流失预警"
    if r >= 4 and f <= 2:
        return "新近尝鲜"
    if total >= 12:
        return "稳定贡献"
    if total <= 6:
        return "低活跃"
    return "常规"


if __name__ == "__main__":
    sys.exit(main())
