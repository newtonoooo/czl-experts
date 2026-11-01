#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cohort_retention.py — 同期群留存矩阵。

用法：
    python cohort_retention.py 事件.csv --user 用户ID --date 日期 --period month
    python cohort_retention.py 订单.csv --user 客户ID --date 支付日期 --period week --value 金额

口径：
    每个用户归属到「首次出现的周期」，第 N 期是否出现决定是否留存。
    留存率 = 该群在第 N 期仍出现的用户数 / 该群总用户数。
    数据末尾之后的期数标「—」（观测不到），不按 0 计。
    给了 --value 时，另出一张「金额留存」：该期人均贡献 / 首期人均贡献。
"""

import argparse
import sys

import czl_core as C

KIND_CN = {"day": "日", "week": "周", "month": "月", "quarter": "季"}


def main():
    ap = argparse.ArgumentParser(description="数证台 · 同期群留存矩阵")
    ap.add_argument("path", help="CSV/TSV 文件")
    ap.add_argument("--user", required=True, help="用户/客户列名")
    ap.add_argument("--date", required=True, help="日期列名")
    ap.add_argument("--period", default="month", choices=["day", "week", "month", "quarter"],
                    help="同期群周期，默认 month")
    ap.add_argument("--value", help="金额列名；给出则额外输出金额留存")
    ap.add_argument("--max-offset", type=int, default=12, help="最多看几期，默认 12")
    ap.add_argument("--out", help="输出 Markdown 路径")
    args = ap.parse_args()

    header, rows, _ = C.read_table(args.path)
    ui = C.col_index(header, args.user)
    di = C.col_index(header, args.date)
    vi = C.col_index(header, args.value) if args.value else None

    user_periods = {}
    user_value = {}
    bad_date = bad_user = 0
    for r in rows:
        d = C.to_date(r[di])
        u = (r[ui] or "").strip()
        if not u:
            bad_user += 1
            continue
        if d is None:
            bad_date += 1
            continue
        k = C.period_key(d, args.period)
        user_periods.setdefault(u, set()).add(k)
        if vi is not None:
            v = C.to_number(r[vi])
            if v is not None:
                user_value[(u, k)] = user_value.get((u, k), 0.0) + v

    if not user_periods:
        C.die("没有解析出任何用户与日期的组合，请检查 --user 与 --date 列名")
    if bad_date:
        C.warn("%d 行日期无法解析，已跳过" % bad_date)
    if bad_user:
        C.warn("%d 行用户为空，已跳过" % bad_user)

    first = {u: min(ps, key=lambda k: C.period_index(k, args.period))
             for u, ps in user_periods.items()}
    cohort_size = {}
    for u, f in first.items():
        cohort_size[f] = cohort_size.get(f, 0) + 1

    last_idx = max(C.period_index(k, args.period) for ps in user_periods.values() for k in ps)
    cohorts = sorted(cohort_size, key=lambda k: C.period_index(k, args.period))

    # 只展示「至少有一个群能观测到」的期数，避免整列都是 —
    max_obs = 0
    for c in cohorts:
        max_obs = max(max_obs, last_idx - C.period_index(c, args.period))
    max_off = min(args.max_offset, max_obs)
    offsets = list(range(0, max_off + 1))

    retained = {}
    val_sum = {}
    for u, ps in user_periods.items():
        f = first[u]
        fi = C.period_index(f, args.period)
        for k in ps:
            off = C.period_index(k, args.period) - fi
            if 0 <= off <= max_off:
                retained[(f, off)] = retained.get((f, off), 0) + 1
                if vi is not None:
                    val_sum[(f, off)] = val_sum.get((f, off), 0.0) + user_value.get((u, k), 0.0)

    def observable(c, o):
        return C.period_index(c, args.period) + o <= last_idx

    L = []
    L.append("# 同期群留存矩阵（按%s）\n" % KIND_CN[args.period])
    L.append("用户数：%d　｜　同期群数：%d　｜　可观测期数：%d　｜　首期计入 offset 0\n"
             % (len(user_periods), len(cohorts), max_off + 1))

    head = ["首期", "人数"] + ["第%d期" % o for o in offsets[1:]]
    body = []
    for c in cohorts:
        n = cohort_size[c]
        row = [c, str(n)]
        for o in offsets[1:]:
            if not observable(c, o):
                row.append("—")
            else:
                row.append("%.1f%%" % (retained.get((c, o), 0) / n * 100))
        body.append(row)
    L.append(C.md_table(head, body))
    L.append("")

    # ---- 读法
    valid1 = [c for c in cohorts if cohort_size[c] and observable(c, 1)]
    L.append("## 读法\n")
    if len(valid1) >= 2:
        rates = [retained.get((c, 1), 0) / cohort_size[c] for c in valid1]
        L.append("- 第 2 期留存（%d 个可观测同期群）：平均 %.1f%%，区间 %.1f%%–%.1f%%。"
                 % (len(valid1), sum(rates) / len(rates) * 100, min(rates) * 100, max(rates) * 100))
    elif len(valid1) == 1:
        c = valid1[0]
        L.append("- 只有一个同期群可观测到第 2 期（%s），留存 %.1f%%，无法做群间比较。"
                 % (c, retained.get((c, 1), 0) / cohort_size[c] * 100))
    else:
        L.append("- 没有同期群能观测到第 2 期，数据时间跨度不足，补一个月数据再看。")

    if len(valid1) >= 6:
        first3, last3 = valid1[:3], valid1[-3:]
        a = sum(retained.get((c, 1), 0) / cohort_size[c] for c in first3) / 3
        b = sum(retained.get((c, 1), 0) / cohort_size[c] for c in last3) / 3
        L.append("- 最早 3 个群 %.1f%%，最近 3 个群 %.1f%%，差 %s。" % (
            a * 100, b * 100, C.signed_pct((b - a) / a) if a else "—"))
    if len(valid1) >= 2:
        L.append("- 横看（同一列不同群）差异大 → 获客质量或渠道结构变了。")
        L.append("- 纵看（同一行不同列）衰减变陡 → 产品或体验问题。")
        L.append("- 两者常同时发生，要分开说，别混成一句「留存变差」。")
    L.append("")

    # ---- 金额留存
    if vi is not None:
        L.append("## 金额留存（该期人均贡献 / 首期人均贡献）\n")
        body2, has_data = [], False
        for c in cohorts:
            n = cohort_size[c]
            base_avg = val_sum.get((c, 0), 0.0) / n if n else 0
            row = [c]
            for o in offsets[1:]:
                if not observable(c, o) or not base_avg:
                    row.append("—")
                    continue
                cnt = retained.get((c, o), 0)
                avg = val_sum.get((c, o), 0.0) / cnt if cnt else 0
                row.append("%.0f%%" % (avg / base_avg * 100))
                has_data = True
            body2.append(row)
        L.append(C.md_table(["首期"] + ["第%d期" % o for o in offsets[1:]], body2))
        L.append("")
        if not has_data:
            L.append("> 可观测期数为 1，暂无金额留存可比。\n")

    L.append("## 结论边界\n")
    L.append("- 群内人数少于 50 的，百分比波动很大，别单独下结论。")
    L.append("- 首期定义变了（如从注册改为首单），历史群会失真，需重算。")
    L.append("- 留存下降不等于体验变差，也可能是新客占比上升带来的稀释，要结合分群看。")
    L.append("- 「—」表示数据截止到这个时点还观测不到，不是留存为 0。")
    L.append("")
    L.append("## 复现\n")
    L.append("```bash")
    L.append("python cohort_retention.py %s --user %s --date %s --period %s%s" % (
        args.path, args.user, args.date, args.period,
        (" --value " + args.value) if args.value else ""))
    L.append("```")
    L.append("")
    L.append("---\n*由 czl-evidence-playbook / cohort_retention.py 生成*")

    C.write_out("\n".join(L), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
