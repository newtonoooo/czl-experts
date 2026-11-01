#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""metric_guard.py - statistical guardrails for product metric reviews.

Part of the Setpoint / 产品决策审校专家 package (czl-product-decision-audit).

Four jobs a metric review keeps getting wrong, done mechanically:

  card      validate metric definition cards - a number without a definition is
            not evidence
  baseline  separate real movement from noise using a robust band
            (median +/- k * 1.4826 * MAD), so a 3% wobble stops being a trend
  ab        two-proportion test with confidence interval and minimum
            detectable effect, so "512 vs 583 out of 10,000" gets a verdict
  simpson   compare aggregate effect against within-group effect, so a real
            segment reversal stops hiding behind a flat total

Pure standard library (math, csv, json, argparse). No network. No writes.

Examples
--------
    python metric_guard.py card fixtures/metric_cards.csv
    python metric_guard.py baseline 412,401,398,420,405,410,388 --k 2.5
    python metric_guard.py ab --control 10000 512 --treat 10000 583
    python metric_guard.py simpson fixtures/segments.csv

Exit codes
----------
    0  pass / no blocking problem
    1  blocking problem found
    2  usage or file problem
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys

Z_95 = 1.959963985
Z_80 = 0.8416212336


# ---------------------------------------------------------------- helpers


def phi(z: float) -> float:
    """Standard normal CDF."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def two_sided_p(z: float) -> float:
    return 2.0 * (1.0 - phi(abs(z)))


def wilson(k: int, n: int, z: float = Z_95):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, centre - half), min(1.0, centre + half))


def median(xs):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        raise ValueError("empty series")
    mid = n // 2
    if n % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def mad(xs, centre=None):
    c = median(xs) if centre is None else centre
    return median([abs(x - c) for x in xs])


def read_csv_dicts(path):
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        sample = fh.read(2048)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(fh, dialect=dialect)
        rows = [{(k or "").strip().lower(): (v or "").strip() for k, v in r.items()} for r in reader]
        fields = [f.strip().lower() for f in (reader.fieldnames or [])]
    return rows, fields


def as_float(value, default=None):
    try:
        return float(str(value).replace(",", "").replace("%", ""))
    except (TypeError, ValueError):
        return default


def as_int(value):
    f = as_float(value)
    return None if f is None else int(round(f))


# ---------------------------------------------------------------- card


CARD_REQUIRED = [
    "metric",
    "definition",
    "numerator",
    "denominator",
    "window",
    "system",
    "owner",
]

# Phrases that mean the definition has not actually been written down.
VAGUE_MARKERS = [
    "活跃用户",
    "有一定",
    "根据需要",
    "视情况",
    "待定",
    "TODO",
    "TBD",
    "同上",
    "默认",
    "全部都算",
]


def cmd_card(args):
    rows, fields = read_csv_dicts(args.path)
    problems = []
    warnings = []

    missing = [c for c in CARD_REQUIRED if c not in fields]
    if missing:
        print("口径卡缺少列: " + ", ".join(missing))
        return 2

    for i, row in enumerate(rows, start=1):
        name = row.get("metric") or f"row{i}"
        for col in CARD_REQUIRED:
            if not row.get(col):
                problems.append((name, "E_MISSING", f"字段 {col} 为空"))
        definition = row.get("definition", "")
        if definition and len(definition) < 12:
            problems.append(
                (name, "E_SHORT_DEF", f"定义过短（{len(definition)} 字），无法据以重算")
            )
        blob = " ".join(row.get(c, "") for c in ("definition", "numerator", "denominator"))
        hits = [m for m in VAGUE_MARKERS if m in blob]
        if hits:
            warnings.append((name, "W_VAGUE", "定义含含糊措辞: " + "、".join(hits)))
        if not row.get("dedupe"):
            warnings.append((name, "W_NO_DEDUPE", "未写去重规则（是否按用户/设备/订单去重）"))
        if not row.get("exclusions"):
            warnings.append((name, "W_NO_EXCL", "未写排除规则（退款、测试账号、内部账号）"))

    print(f"口径卡体检：{len(rows)} 张")
    print("=" * 40)
    if problems:
        print(f"错误 {len(problems)} 条：")
        for name, code, msg in problems:
            print(f"  [{name}] {code} {msg}")
    if warnings:
        print(f"提示 {len(warnings)} 条：")
        for name, code, msg in warnings:
            print(f"  [{name}] {code} {msg}")
    if not problems and not warnings:
        print("通过：口径可复算。")
    return 1 if problems else 0


# ---------------------------------------------------------------- baseline


def cmd_baseline(args):
    if args.values:
        raw = [v for chunk in args.values for v in chunk.split(",")]
        series = [as_float(v) for v in raw]
    else:
        rows, fields = read_csv_dicts(args.path)
        col = args.column
        if col not in fields:
            print(f"列 '{col}' 不存在，可用列: {', '.join(fields)}")
            return 2
        series = [as_float(r.get(col)) for r in rows]
    series = [s for s in series if s is not None]
    if len(series) < 5:
        print("数据点少于 5 个，无法估计波动带。")
        return 2

    centre = median(series)
    spread = mad(series, centre) * 1.4826
    mean = sum(series) / len(series)
    sd = math.sqrt(sum((x - mean) ** 2 for x in series) / (len(series) - 1))
    lo, hi = centre - args.k * spread, centre + args.k * spread

    latest = series[-1]
    prev = series[-2]
    dev = latest - centre
    z_like = dev / spread if spread else float("inf")
    outside = latest < lo or latest > hi

    cv = (sd / mean * 100.0) if mean else float("nan")

    print("指标波动体检")
    print("=" * 40)
    print(f"数据点: {len(series)}   中枢(中位数): {centre:.4g}")
    print(f"稳健波动(MAD 换算): {spread:.4g}   常规标准差: {sd:.4g}   变异系数: {cv:.1f}%")
    print(f"正常带({args.k}倍): [{lo:.4g}, {hi:.4g}]")
    print(f"最新值: {latest:.4g}（较上期 {latest - prev:+.4g}）")
    print(f"偏离中枢: {dev:+.4g}（{z_like:+.2f} 倍波动）")

    if outside:
        print("\n判定：超出正常带，可能是真实变化。")
        print("下一步：先确认口径未变（口径变了优先怀疑口径），再找同期事件。")
        code = 0
    else:
        print("\n判定：在正常带内，属于噪声，不要写成趋势。")
        print(f"要判断真实变化，至少需要连续 3 期同向超出 [{lo:.4g}, {hi:.4g}]。")
        code = 0

    if cv > 25:
        print(f"\n注意：变异系数 {cv:.1f}% 偏高，这个指标本身不稳定，适合看趋势带而不是单点。")
    return code


# ---------------------------------------------------------------- ab


def cmd_ab(args):
    n_c, k_c = args.control
    n_t, k_t = args.treat
    if n_c <= 0 or n_t <= 0:
        print("样本量必须为正数。")
        return 2
    if not (0 <= k_c <= n_c and 0 <= k_t <= n_t):
        print("转化数不能超过样本量。")
        return 2

    p_c, p_t = k_c / n_c, k_t / n_t
    diff = p_t - p_c
    pooled = (k_c + k_t) / (n_c + n_t)
    se_pool = math.sqrt(pooled * (1 - pooled) * (1 / n_c + 1 / n_t))
    z = diff / se_pool if se_pool else 0.0
    p_value = two_sided_p(z)

    se_unpool = math.sqrt(p_c * (1 - p_c) / n_c + p_t * (1 - p_t) / n_t)
    ci_lo, ci_hi = diff - Z_95 * se_unpool, diff + Z_95 * se_unpool
    mde = (Z_95 + Z_80) * se_unpool

    lo_c, hi_c = wilson(k_c, n_c)
    lo_t, hi_t = wilson(k_t, n_t)

    print("两组比例检验")
    print("=" * 40)
    print(f"对照组: {k_c}/{n_c} = {p_c:.4%}   95%区间 [{lo_c:.4%}, {hi_c:.4%}]")
    print(f"实验组: {k_t}/{n_t} = {p_t:.4%}   95%区间 [{lo_t:.4%}, {hi_t:.4%}]")
    print(f"差值: {diff:+.4%}   相对变化: {(diff / p_c if p_c else float('nan')):+.2%}")
    print(f"z = {z:.3f}   p = {p_value:.4g}")
    print(f"差值 95% 区间: [{ci_lo:+.4%}, {ci_hi:+.4%}]")
    print(f"本样本量可检出的最小效应(MDE, 80% 功效): {mde:.4%}")

    verdict_bits = []
    if p_value < 0.05:
        verdict_bits.append("差异在统计上显著")
    else:
        verdict_bits.append("差异未达统计显著")
    if ci_lo > 0 or ci_hi < 0:
        verdict_bits.append("区间不含 0")
    else:
        verdict_bits.append("区间跨过 0，方向不确定")
    if p_value >= 0.05:
        verdict_bits.append(f"差异 {abs(diff):.4%} 小于最小可检出效应 {mde:.4%}，样本不足以定论")

    print("\n判定：" + "；".join(verdict_bits) + "。")

    if p_value < 0.05 and ci_lo > 0:
        print("建议：结论方向可以采信。先问一句「这个提升在多少天后还能维持」，并写明回归监控窗口。")
        if mde > abs(diff):
            print(
                f"注意：本次样本量对这么小的效应处于功效边缘（MDE {mde:.4%} > 实测 {abs(diff):.4%}），"
                "建议延长一期再决定是否放大投入。"
            )
    elif p_value < 0.05 and ci_hi < 0:
        print("建议：实验组更差，不要上线；先查实验实现是否有 bug 再下结论。")
    else:
        need = 2 * (Z_95 + Z_80) ** 2 * pooled * (1 - pooled) / (abs(diff) ** 2 or 1e-12)
        print(f"建议：不要据此上线。若想检出 {abs(diff):.4%} 的差异，每组约需 {int(need):,} 个样本。")
    return 0


# ---------------------------------------------------------------- simpson


def cmd_simpson(args):
    rows, fields = read_csv_dicts(args.path)
    needed = ["group", "exp_n", "exp_k", "ctl_n", "ctl_k"]
    missing = [c for c in needed if c not in fields]
    if missing:
        print("缺少列: " + ", ".join(missing))
        return 2

    groups = []
    for row in rows:
        name = row.get("group") or "?"
        en, ek = as_int(row.get("exp_n")), as_int(row.get("exp_k"))
        cn, ck = as_int(row.get("ctl_n")), as_int(row.get("ctl_k"))
        if None in (en, ek, cn, ck) or en <= 0 or cn <= 0:
            continue
        groups.append(
            {
                "group": name,
                "exp_n": en,
                "exp_k": ek,
                "ctl_n": cn,
                "ctl_k": ck,
                "exp_rate": ek / en,
                "ctl_rate": ck / cn,
                "diff": ek / en - ck / cn,
                "weight": en + cn,
            }
        )

    if not groups:
        print("没有可用分组数据。")
        return 2

    tot_en = sum(g["exp_n"] for g in groups)
    tot_ek = sum(g["exp_k"] for g in groups)
    tot_cn = sum(g["ctl_n"] for g in groups)
    tot_ck = sum(g["ctl_k"] for g in groups)
    agg_diff = tot_ek / tot_en - tot_ck / tot_cn

    wsum = sum(g["weight"] for g in groups)
    within_diff = sum(g["diff"] * g["weight"] for g in groups) / wsum

    print("分组与合计对照（辛普森检查）")
    print("=" * 56)
    print(f"{'分组':<14}{'实验':>12}{'对照':>12}{'差值':>10}{'权重':>10}")
    for g in groups:
        print(
            f"{g['group']:<14}{g['exp_rate']:>11.2%}{g['ctl_rate']:>12.2%}"
            f"{g['diff']:>+10.2%}{g['weight']:>10}"
        )
    print("-" * 56)
    print(f"{'合计':<14}{tot_ek / tot_en:>11.2%}{tot_ck / tot_cn:>12.2%}{agg_diff:>+10.2%}{wsum:>10}")
    print(f"\n组内加权差值: {within_diff:+.2%}   合计差值: {agg_diff:+.2%}")

    same_sign = (within_diff >= 0) == (agg_diff >= 0)
    if same_sign:
        print("\n判定：方向一致，未发现辛普森反转。")
        return 0

    print("\n判定：**方向相反，存在辛普森反转。**")
    print("原因通常是分组样本比例差异极大：某一组在合计中占比过高，把整体方向带反了。")
    print("行动：结论只能按分组建模，禁止用合计数字对外汇报。")
    return 1


# ---------------------------------------------------------------- main


def build_parser():
    p = argparse.ArgumentParser(
        description="Setpoint metric guard: definition cards, noise bands, A/B tests, Simpson checks."
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("card", help="校验指标口径卡")
    pc.add_argument("path")
    pc.set_defaults(func=cmd_card)

    pb = sub.add_parser("baseline", help="用稳健波动带区分信号与噪声")
    pb.add_argument("values", nargs="*", help="逗号分隔的时间序列，如 412,401,398")
    pb.add_argument("--path", default="", help="或从 CSV 读取")
    pb.add_argument("--column", default="value", help="CSV 中的数值列名")
    pb.add_argument("--k", type=float, default=2.5, help="波动带倍数，默认 2.5")
    pb.set_defaults(func=cmd_baseline)

    pa = sub.add_parser("ab", help="两组比例检验")
    pa.add_argument("--control", nargs=2, type=int, metavar=("N", "K"), required=True)
    pa.add_argument("--treat", nargs=2, type=int, metavar=("N", "K"), required=True)
    pa.set_defaults(func=cmd_ab)

    ps = sub.add_parser("simpson", help="检查辛普森反转")
    ps.add_argument("path")
    ps.set_defaults(func=cmd_simpson)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print(f"错误：找不到文件 {exc}", file=sys.stderr)
        return 2
    except UnicodeDecodeError:
        print("错误：文件编码无法识别，请另存为 UTF-8", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
