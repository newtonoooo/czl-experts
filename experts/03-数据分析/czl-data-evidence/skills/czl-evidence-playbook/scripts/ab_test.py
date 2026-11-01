#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ab_test.py — 实验/对比检验：两比例或两均值。

用法：
    # 两比例（转化人数 / 样本量）
    python ab_test.py --control 512/10000 --treat 583/10000

    # 明细表：0/1 列按比例处理，连续列按均值处理
    python ab_test.py --file ab.csv --group 组别 --metric 是否转化
    python ab_test.py --file ab.csv --group 组别 --metric 客单价

输出：绝对值、相对值、检验统计量、p 值、95% 区间、以及一句可直接抄进报告的结论。
"""

import argparse
import math
import sys

import czl_core as C


def parse_fraction(s: str):
    if "/" not in s:
        C.die("比例要写成 成功数/总数，例如 512/10000，收到：%s" % s)
    a, b = s.split("/", 1)
    x, n = C.to_number(a), C.to_number(b)
    if x is None or n is None or n <= 0:
        C.die("比例里的数字不合法：%s" % s)
    if x > n:
        C.die("成功数大于总数：%s" % s)
    return x, n


def t_ppf(p: float, df: float) -> float:
    """t 分布分位数：对双侧尾概率做二分。"""
    lo, hi = 0.0, 100.0
    for _ in range(200):
        mid = (lo + hi) / 2
        sf = C.t_sf_two_sided(mid, df)
        if sf > 1 - p:      # 需要更大的 t
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def two_prop(x1, n1, x2, n2):
    p1, p2 = x1 / n1, x2 / n2
    pool = (x1 + x2) / (n1 + n2)
    se_pool = math.sqrt(pool * (1 - pool) * (1 / n1 + 1 / n2)) if 0 < pool < 1 else 0.0
    diff = p2 - p1
    z = diff / se_pool if se_pool else float("nan")
    p = C.t_sf_two_sided(z, 1e7) if se_pool else float("nan")   # 大样本近似正态
    se_un = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    zc = C.norm_ppf(0.975)
    lo, hi = diff - zc * se_un, diff + zc * se_un
    return p1, p2, diff, z, p, (lo, hi)


def welch(a, b):
    m1, m2 = C.mean(a), C.mean(b)
    v1, v2 = C.variance(a), C.variance(b)
    n1, n2 = len(a), len(b)
    se = math.sqrt(v1 / n1 + v2 / n2)
    diff = m2 - m1
    t = diff / se if se else float("nan")
    df = (v1 / n1 + v2 / n2) ** 2 / ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1)) \
        if n1 > 1 and n2 > 1 else float("nan")
    p = C.t_sf_two_sided(t, df) if df == df else float("nan")
    if df == df:
        tc = t_ppf(0.95, df)
        lo, hi = diff - tc * se, diff + tc * se
    else:
        lo, hi = float("nan"), float("nan")
    return m1, m2, diff, t, p, (lo, hi), df


def main():
    ap = argparse.ArgumentParser(description="数证台 · 实验/对比检验")
    ap.add_argument("--control", help="对照组 成功数/总数")
    ap.add_argument("--treat", help="实验组 成功数/总数")
    ap.add_argument("--file", help="明细表 CSV（与 --group/--metric 一起用）")
    ap.add_argument("--group", help="分组列名，取值含 control/对照 与 treat/实验")
    ap.add_argument("--metric", help="指标列名；0/1 视为比例，其余视为连续值")
    ap.add_argument("--out", help="输出 Markdown 路径")
    args = ap.parse_args()

    L = []
    if args.control and args.treat:
        x1, n1 = parse_fraction(args.control)
        x2, n2 = parse_fraction(args.treat)
        p1, p2, diff, stat, p, ci = two_prop(x1, n1, x2, n2)
        L.append("# 两比例检验\n")
        L.append(C.md_table(
            ["组", "成功数", "样本量", "比例"],
            [["对照组", C.num(x1, 0), C.num(n1, 0), C.pct(p1, 2)],
             ["实验组", C.num(x2, 0), C.num(n2, 0), C.pct(p2, 2)]]))
        L.append("")
        L.append(C.md_table(
            ["指标", "值"],
            [["绝对差", "%+.2f 个百分点" % (diff * 100)],
             ["相对差", C.signed_pct(diff / p1, 1) if p1 else "—"],
             ["检验方法", "两比例 z 检验（合并方差）"],
             ["z 值", C.num(stat, 3)],
             ["双侧 p 值", "%.4f" % p if p == p else "—"],
             ["95% 区间（绝对差）", "[%+.2f, %+.2f] 个百分点" % (ci[0] * 100, ci[1] * 100)]]))
        L.append("")
        L.append("## 结论\n")
        if p == p and p < 0.05 and not (ci[0] < 0 < ci[1]):
            L.append("- **差异显著**：p=%.4f，95%% 区间不含 0。可以说「实验组比对照组高 %+.2f 个百分点」。" % (p, diff * 100))
            if ci[0] <= 0.001:
                L.append("- 但区间下限接近 0（%+.3f 个百分点），建议延长观测或扩大样本后再定投放规模。" % (ci[0] * 100))
        elif ci[0] < 0 < ci[1]:
            L.append("- **未测出显著差异**：95%% 区间 [%+.2f, %+.2f] 个百分点，跨 0。" % (ci[0] * 100, ci[1] * 100))
            L.append("- 注意表述：这**不等于**「两组一样」，只能说这份样本不足以证明有差异。")
        else:
            L.append("- 未达显著（p=%.4f），区间 [%+.2f, %+.2f] 个百分点。" % (p, ci[0] * 100, ci[1] * 100))
        sig = (p == p and p < 0.05 and not (ci[0] < 0 < ci[1]))
        n_avg = (n1 + n2) / 2
        if not sig:
            mde = math.sqrt(16 * p1 * (1 - p1) / n_avg) * 100 if p1 and n_avg else float("nan")
            L.append("- 检验力参考：这个样本量能稳定检出的最小差异约 %.2f 个百分点（α=0.05，power=80%%）。"
                     "小于它的差异，这份数据分辨不出来，需要加样本。" % mde)
        else:
            L.append("- 想把区间收窄一半（判断幅度更准），每组样本约需现在的 4 倍（约 %s 人/组）。" % C.num(n_avg * 4, 0))
        L.append("")
        L.append("## 复现\n")
        L.append("```bash\npython ab_test.py --control %s --treat %s\n```" % (args.control, args.treat))

    elif args.file:
        if not (args.group and args.metric):
            C.die("用 --file 时必须同时给 --group 与 --metric")
        header, rows, _ = C.read_table(args.file)
        gi = C.col_index(header, args.group)
        mi = C.col_index(header, args.metric)

        groups = {}
        for r in rows:
            g = (r[gi] or "").strip()
            v = C.to_number(r[mi])
            if v is None or not g:
                continue
            groups.setdefault(g, []).append(v)
        if len(groups) < 2:
            C.die("分组列只有 %d 个取值，无法对比：%s" % (len(groups), "、".join(groups)))

        keys = list(groups)
        ctrl = next((k for k in keys if any(w in k for w in ("control", "对照", "基准", "A"))), keys[0])
        trt = next((k for k in keys if k != ctrl and any(w in k for w in ("treat", "实验", "测试", "B"))), None)
        if trt is None:
            trt = [k for k in keys if k != ctrl][0]
        a, b = groups[ctrl], groups[trt]

        is_binary = all(v in (0.0, 1.0) for v in a + b)
        L.append("# 明细表对比检验（%s）\n" % ("比例" if is_binary else "均值"))
        if is_binary:
            x1, n1 = sum(a), len(a)
            x2, n2 = sum(b), len(b)
            p1, p2, diff, stat, p, ci = two_prop(x1, n1, x2, n2)
            L.append(C.md_table(["组", "成功数", "样本量", "比例"],
                                [[ctrl, C.num(x1, 0), C.num(n1, 0), C.pct(p1, 2)],
                                 [trt, C.num(x2, 0), C.num(n2, 0), C.pct(p2, 2)]]))
            unit = "个百分点"
            scale = 100
        else:
            m1, m2, diff, stat, p, ci, df = welch(a, b)
            L.append(C.md_table(["组", "样本量", "均值", "中位数", "标准差"],
                                [[ctrl, len(a), C.num(m1), C.num(C.median(a)), C.num(C.stdev(a))],
                                 [trt, len(b), C.num(m2), C.num(C.median(b)), C.num(C.stdev(b))]]))
            L.append("\n检验方法：Welch t 检验（不等方差），自由度 %.1f。" % df)
            unit, scale = "单位", 1

        L.append("")
        L.append(C.md_table(["指标", "值"], [
            ["绝对差（%s−%s）" % (trt, ctrl), "%+.3f %s" % (diff * scale, unit)],
            ["相对差", C.signed_pct(diff / (p1 if is_binary else m1), 1) if (p1 if is_binary else m1) else "—"],
            ["统计量", C.num(stat, 3)],
            ["双侧 p 值", "%.4f" % p if p == p else "—"],
            ["95% 区间", "[%+.3f, %+.3f] %s" % (ci[0] * scale, ci[1] * scale, unit)],
        ]))
        L.append("")
        L.append("## 结论\n")
        if p == p and p < 0.05 and not (ci[0] < 0 < ci[1]):
            L.append("- **差异显著**（p=%.4f，区间不含 0）。" % p)
        else:
            L.append("- **未测出显著差异**（p=%.4f，区间跨 0）。不要写成「两组一样」。" % p if p == p else "- 样本不足，无法完成检验。")
        if is_binary:
            L.append("- 注意：这是观察性对比，若分组不是随机分流，差异不能归因于改动本身。")
        L.append("")
        L.append("## 复现\n")
        L.append("```bash\npython ab_test.py --file %s --group %s --metric %s\n```" % (
            args.file, args.group, args.metric))
    else:
        C.die("请用 --control/--treat 给两组比例，或用 --file/--group/--metric 给明细表")

    L.append("")
    L.append("---\n*由 czl-evidence-playbook / ab_test.py 生成。p 值与区间不构成因果结论，因果需随机分流或准实验设计。*")

    C.write_out("\n".join(L), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
