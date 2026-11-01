#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
period_compare.py — 两期对比 + 量价结构三因子分解。

用法：
    python period_compare.py 订单.csv --date 支付日期 --value 金额 --period 2026-05:2026-06
    python period_compare.py 订单.csv --date 支付日期 --value 金额 --qty 件数 \
        --period 2026-05:2026-06 --by 渠道 --out 对比.md

分解口径：
    总变化 = Σ(Δ量 × 基期价) + Σ(基期量 × Δ价) + Σ(Δ量 × Δ价)
            └─ 量的贡献 ─┘   └─ 价的贡献 ─┘   └─ 交互/结构项 ─┘
"""

import argparse
import sys

import czl_core as C


def main():
    ap = argparse.ArgumentParser(description="数证台 · 两期对比与量价结构分解")
    ap.add_argument("path", help="CSV/TSV 文件")
    ap.add_argument("--date", required=True, help="日期列名")
    ap.add_argument("--value", required=True, help="金额列名")
    ap.add_argument("--qty", help="数量列名；不给则用行数当量")
    ap.add_argument("--period", required=True, help="基期:对比期，如 2026-05:2026-06 或 2026-05-01..2026-05-31:2026-06-01..2026-06-30")
    ap.add_argument("--by", help="拆分维度列名，如 渠道")
    ap.add_argument("--out", help="输出 Markdown 路径")
    args = ap.parse_args()

    if ":" not in args.period:
        C.die("--period 要写成 基期:对比期，例如 2026-05:2026-06")
    base_span, test_span = args.period.split(":", 1)
    b0, b1 = C.parse_range(base_span)
    t0, t1 = C.parse_range(test_span)

    header, rows, _ = C.read_table(args.path)
    di = C.col_index(header, args.date)
    vi = C.col_index(header, args.value)
    qi = C.col_index(header, args.qty) if args.qty else None
    gi = C.col_index(header, args.by) if args.by else None

    base, test, bad_date, bad_val = [], [], 0, 0
    for r in rows:
        d = C.to_date(r[di])
        v = C.to_number(r[vi])
        if d is None:
            bad_date += 1
            continue
        if v is None:
            bad_val += 1
            continue
        if b0 <= d <= b1:
            base.append((r, v))
        elif t0 <= d <= t1:
            test.append((r, v))

    if bad_date:
        C.warn("有 %d 行日期无法解析，已跳过" % bad_date)
    if bad_val:
        C.warn("有 %d 行金额无法解析，已跳过" % bad_val)
    if not base or not test:
        C.die("基期或对比期没有数据（基期 %d 行，对比期 %d 行）。请检查 --date 与 --period 是否对得上" % (len(base), len(test)))

    def qty_of(pairs):
        if qi is None:
            return float(len(pairs))
        s = 0.0
        miss = 0
        for r, _ in pairs:
            q = C.to_number(r[qi])
            if q is None:
                miss += 1
            else:
                s += q
        if miss:
            C.warn("数量列有 %d 行为空或非数字，按 0 计" % miss)
        return s

    v0 = sum(v for _, v in base)
    v1 = sum(v for _, v in test)
    q0 = qty_of(base)
    q1 = qty_of(test)
    if q0 == 0:
        C.die("基期数量为 0，无法计算单价。请检查 --qty 列是否正确")
    p0, p1 = v0 / q0, v1 / q1 if q1 else float("nan")

    dq, dp = q1 - q0, p1 - p0
    c_qty, c_price, c_mix = dq * p0, q0 * dp, dq * dp
    dv = v1 - v0

    L = []
    L.append("# 两期对比与分解\n")
    L.append("| 项 | 基期 %s | 对比期 %s | 变化 |" % (base_span, test_span))
    L.append("|---|---|---|---|")
    L.append("| 金额 | %s | %s | %s（%s） |" % (
        C.money(v0), C.money(v1), C.money(dv),
        C.signed_pct(dv / v0) if v0 else "—"))
    L.append("| %s | %s | %s | %s（%s） |" % (
        args.qty or "行数", C.num(q0, 0), C.num(q1, 0), C.num(dq, 0),
        C.signed_pct(dq / q0) if q0 else "—"))
    L.append("| 单价 | %s | %s | %s（%s） |" % (
        C.num(p0), C.num(p1), C.num(dp), C.signed_pct(dp / p0) if p0 else "—"))
    L.append("")

    L.append("## 三因子分解（金额口径）\n")
    denom = abs(c_qty) + abs(c_price) + abs(c_mix)
    L.append(C.md_table(
        ["因子", "金额贡献", "占变化绝对值", "读法"],
        [["量的贡献", C.money(c_qty), C.pct(abs(c_qty) / denom) if denom else "—",
          "客流/订单量变化带来的增减"],
         ["价的贡献", C.money(c_price), C.pct(abs(c_price) / denom) if denom else "—",
          "单价、折扣结构变化带来的增减"],
         ["交互/结构项", C.money(c_mix), C.pct(abs(c_mix) / denom) if denom else "—",
          "量价同时变化、或高低价品占比改变"]]))
    L.append("")
    L.append("校验：三项之和 %s，与实际变化 %s 的差额 %s。\n" % (
        C.money(c_qty + c_price + c_mix), C.money(dv),
        C.money(abs(c_qty + c_price + c_mix - dv))))

    # ---- 按维度拆
    if gi is not None:
        bmap, tmap = {}, {}
        for r, v in base:
            k = (r[gi] or "（空）").strip()
            bv, bq = bmap.get(k, (0.0, 0.0))
            q = C.to_number(r[qi]) if qi is not None else 1.0
            bmap[k] = (bv + v, bq + (q or 0.0))
        for r, v in test:
            k = (r[gi] or "（空）").strip()
            tv, tq = tmap.get(k, (0.0, 0.0))
            q = C.to_number(r[qi]) if qi is not None else 1.0
            tmap[k] = (tv + v, tq + (q or 0.0))

        keys = sorted(set(bmap) | set(tmap))
        detail = []
        for k in keys:
            bv, bq = bmap.get(k, (0.0, 0.0))
            tv, tq = tmap.get(k, (0.0, 0.0))
            bp = bv / bq if bq else 0.0
            tp = tv / tq if tq else 0.0
            d_v = tv - bv
            d_q = tq - bq
            k_qty = d_q * bp
            k_price = bq * (tp - bp)
            k_mix = d_q * (tp - bp)
            detail.append({"组": k, "基期": bv, "对比期": tv, "变化": d_v,
                           "量贡献": k_qty, "价贡献": k_price,
                           "基期量": bq, "对比期量": tq,
                           "基期价": bp, "对比期价": tp})

        detail.sort(key=lambda x: -abs(x["变化"]))
        sum_abs = sum(abs(d["变化"]) for d in detail) or 1.0
        rows_out = []
        for d in detail[:10]:
            rows_out.append([d["组"], C.money(d["基期"]), C.money(d["对比期"]),
                             C.money(d["变化"]),
                             C.pct(abs(d["变化"]) / sum_abs),
                             C.money(d["量贡献"]), C.money(d["价贡献"])])
        L.append("## 按「%s」拆解（按变化绝对值排序，前 10）\n" % args.by)
        L.append(C.md_table(["组", "基期", "对比期", "变化", "占变化绝对值", "其中量", "其中价"], rows_out))
        L.append("")

        sum_d = sum(d["变化"] for d in detail)
        resid = abs(sum_d - dv)
        L.append("分组校验：各组变化合计 %s，整体变化 %s，差额 %s（占整体 %.2f%%）。" % (
            C.money(sum_d), C.money(dv), C.money(resid),
            (resid / abs(dv) * 100) if dv else 0))
        if dv and resid / abs(dv) > 0.01:
            L.append("\n> 差额超过 1%，说明还有未拆到的维度，或数据存在重复行。建议回 W2 复核。")
        L.append("")

        drops = [d for d in detail if d["变化"] < 0]
        ups = [d for d in detail if d["变化"] > 0]
        L.append("## 读法\n")
        if drops:
            d0 = drops[0]
            driver = "量" if abs(d0["量贡献"]) >= abs(d0["价贡献"]) else "价"
            L.append("- 最大拖累：「%s」%s，其中主要是**%s**在起作用（量贡献 %s，价贡献 %s）。" % (
                d0["组"], C.money(d0["变化"]), driver,
                C.money(d0["量贡献"]), C.money(d0["价贡献"])))
        if ups:
            u0 = ups[0]
            L.append("- 最大支撑：「%s」%s，抵消了部分下滑。" % (u0["组"], C.money(u0["变化"])))
        if c_mix and dv and abs(c_mix / dv) > 0.3:
            L.append("- 交互项占比超过 30%，说明高低价品结构在变，整体结论必须按组讲，不能只给总数。")
    else:
        L.append("## 未指定拆分维度\n")
        L.append("只能给整体三因子，无法定位到具体组。建议补 `--by 渠道/地区/品类` 再跑一次。\n")

    L.append("## 复现\n")
    L.append("```bash")
    L.append("python period_compare.py %s --date %s --value %s%s --period %s%s" % (
        args.path, args.date, args.value,
        (" --qty " + args.qty) if args.qty else "",
        args.period, (" --by " + args.by) if args.by else ""))
    L.append("```")
    L.append("")
    L.append("---\n*由 czl-evidence-playbook / period_compare.py 生成*")

    C.write_out("\n".join(L), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
