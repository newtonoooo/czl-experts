#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
funnel_steps.py — 漏斗单步转化与短板定位。

两种用法：
  1) 直接给各步人数：
     python funnel_steps.py 访问=10000,加购=3200,下单=1500,支付=980 --aov 120
  2) 给事件表，按步骤去重人数：
     python funnel_steps.py --file 事件.csv --user 用户ID --step 步骤 \
         --order 访问,加购,下单,支付

有历史数据时用 --baseline 给上一期的各步人数，可算真正的「相对跌幅」：
     python funnel_steps.py 访问=10000,加购=3200,下单=1500,支付=980 \
         --baseline 访问=9800,加购=3600,下单=1700,支付=1050

输出：每步转化率、流失人数、相对短板（无基线时对比各步平均单步率），
      以及「这一步提升 1 个百分点值多少钱」。
"""

import argparse
import math
import sys

import czl_core as C


def parse_counts(spec: str):
    steps = []
    for part in spec.replace("，", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            C.die("步骤写法要像 访问=10000，收到：%s" % part)
        name, val = part.split("=", 1)
        n = C.to_number(val)
        if n is None:
            C.die("步骤「%s」的人数不是数字：%s" % (name, val))
        steps.append((name.strip(), float(n)))
    if len(steps) < 2:
        C.die("至少要有两个步骤才能算漏斗")
    return steps


def from_events(path, user_col, step_col, order):
    header, rows, _ = C.read_table(path)
    ui = C.col_index(header, user_col)
    si = C.col_index(header, step_col)
    want = [s.strip() for s in order.replace("，", ",").split(",") if s.strip()]
    if not want:
        C.die("--order 不能为空，要按业务真实顺序写出步骤名")
    seen = {s: set() for s in want}
    unknown = set()
    for r in rows:
        st = (r[si] or "").strip()
        u = (r[ui] or "").strip()
        if not u or not st:
            continue
        if st in seen:
            seen[st].add(u)
        else:
            unknown.add(st)
    if unknown:
        C.warn("事件表里出现未在 --order 中列出的步骤，已忽略：%s" % "、".join(sorted(unknown)[:5]))
    empty = [s for s in want if not seen[s]]
    if empty:
        C.die("这些步骤在数据里一个人都没有，请核对步骤名：%s" % "、".join(empty))
    return [(s, float(len(seen[s]))) for s in want]


def main():
    ap = argparse.ArgumentParser(description="数证台 · 漏斗单步转化与短板定位")
    ap.add_argument("counts", nargs="?", help="各步人数，如 访问=10000,加购=3200,下单=1500,支付=980")
    ap.add_argument("--file", help="事件表 CSV")
    ap.add_argument("--user", help="事件表里的用户列")
    ap.add_argument("--step", help="事件表里的步骤列")
    ap.add_argument("--order", help="步骤的先后顺序，逗号分隔")
    ap.add_argument("--baseline", help="上一期各步人数，格式同 counts；给出后按基期算相对跌幅")
    ap.add_argument("--aov", type=float, help="客单价（元），用于把提升换算成钱")
    ap.add_argument("--out", help="输出 Markdown 路径")
    args = ap.parse_args()

    if args.file:
        if not (args.user and args.step and args.order):
            C.die("用 --file 时必须同时给 --user、--step、--order")
        steps = from_events(args.file, args.user, args.step, args.order)
        src = "`%s`（按用户去重）" % args.file
    else:
        if not args.counts:
            C.die("请给出各步人数，或改用 --file 指定事件表。示例：funnel_steps.py 访问=10000,加购=3200,下单=1500,支付=980")
        steps = parse_counts(args.counts)
        src = "手工输入"

    base_steps = None
    if args.baseline:
        base_steps = parse_counts(args.baseline)
        if len(base_steps) != len(steps):
            C.die("--baseline 的步骤数（%d）与本期（%d）不一致" % (len(base_steps), len(steps)))
        for (n1, _), (n2, _) in zip(steps, base_steps):
            if n1 != n2:
                C.die("--baseline 的步骤名与本期对不上：本期「%s」vs 基期「%s」" % (n1, n2))

    # 人数必须单调不增
    for i in range(1, len(steps)):
        if steps[i][1] > steps[i - 1][1] * 1.001:
            C.warn("第 %d 步「%s」人数（%s）大于上一步（%s）。通常是存在旁路或定义重叠，请核查"
                   % (i + 1, steps[i][0], C.num(steps[i][1], 0), C.num(steps[i - 1][1], 0)))

    # 各步单步率与几何平均（无基线时的参照系）
    step_rates = []
    for i in range(1, len(steps)):
        prev = steps[i - 1][1]
        step_rates.append(steps[i][1] / prev if prev else float("nan"))
    avg_rate = (math.exp(sum(math.log(r) for r in step_rates) / len(step_rates))
                if all(r > 0 for r in step_rates) else float("nan"))

    rows = []
    base_all = steps[0][1]
    for i, (name, n) in enumerate(steps):
        if i == 0:
            rows.append([1, name, C.num(n, 0), "—", "—", "—", "—"])
            continue
        rate_all = n / base_all if base_all else float("nan")
        sr = step_rates[i - 1]
        drop = steps[i - 1][1] - n
        vs_avg = (sr / avg_rate - 1) if avg_rate and avg_rate == avg_rate else None
        rows.append([i + 1, name, C.num(n, 0), C.pct(rate_all), C.pct(sr),
                     C.num(drop, 0),
                     (C.signed_pct(vs_avg) if vs_avg is not None else "—")])
    head = ["#", "步骤", "人数", "总体转化率", "单步转化率", "流失人数",
            "单步率相对各步均值"]

    # ---- 定位
    L = []
    L.append("# 漏斗分析\n")
    L.append("数据来源：%s　｜　首步人数：%s\n" % (src, C.num(base_all, 0)))

    if base_steps:
        # 真正的相对跌幅：本期单步率 vs 基期单步率
        L.append("## 与基期对比\n")
        b_rows = []
        worst_i, worst = None, 0.0
        for i in range(1, len(steps)):
            bsr = base_steps[i][1] / base_steps[i - 1][1] if base_steps[i - 1][1] else float("nan")
            csr = step_rates[i - 1]
            rel = (csr - bsr) / bsr if bsr == bsr and bsr else float("nan")
            b_rows.append([i + 1, steps[i][0], C.pct(bsr), C.pct(csr),
                           C.signed_pct(rel) if rel == rel else "—"])
            if rel == rel and rel < worst:
                worst, worst_i = rel, i
        L.append(C.md_table(["#", "步骤", "基期单步率", "本期单步率", "相对变化"], b_rows))
        L.append("")
        L.append(C.md_table(
            ["#", "步骤", "人数", "总体转化率", "单步转化率", "流失人数", "单步率相对各步均值"],
            rows))
        L.append("")
        L.append("## 定位\n")
        if worst_i is None:
            L.append("- 各步单步率相对基期均未下滑，流失结构没有恶化。")
        else:
            w = steps[worst_i]
            pre = steps[worst_i - 1]
            L.append("- 相对基期跌幅最大的一步是**「%s」→「%s」**，单步转化率从 %s 降到 %s，相对下跌 %s。" % (
                pre[0], w[0], C.pct(base_steps[worst_i][1] / base_steps[worst_i - 1][1]),
                C.pct(step_rates[worst_i - 1]), C.pct(abs(worst))))
            L.append("- 这一步本期流失 %s 人。" % C.num(pre[1] - w[1], 0))
    else:
        L.append(C.md_table(head, rows))
        L.append("")
        L.append("## 定位\n")
        cand = [(i, step_rates[i - 1]) for i in range(1, len(steps))]
        cand = [(i, r) for i, r in cand if r == r]
        if cand:
            wi, wr = min(cand, key=lambda x: x[1])
            pre = steps[wi - 1]
            w = steps[wi]
            L.append("- 单步转化率最低的是**「%s」→「%s」**，只有 %s，不到各步均值（%s）的 %.0f%%。" % (
                pre[0], w[0], C.pct(wr), C.pct(avg_rate), (wr / avg_rate * 100) if avg_rate else 0))
            L.append("- 这一步流失 %s 人。修它的收益最大，但**要先查原因**，别直接改页面。" % C.num(pre[1] - w[1], 0))
        L.append("")
        L.append("> 没有基期数据时，只能用「各步平均单步率」当参照系，这不是真实的跌幅。")
        L.append("> 想判断「这步是不是变差了」，用 `--baseline` 给上一期各步人数，或看 `period_compare.py` 的结果。")

    # ---- 钱
    L.append("")
    L.append("## 换算成钱\n")
    if not args.aov:
        L.append("- 加 `--aov 客单价` 可把每步的提升换算成金额。当前只给人数口径。")
    else:
        for i in range(1, len(steps)):
            pre = steps[i - 1]
            gain1 = 0.01 * pre[1]
            L.append("- 「%s」→「%s」：单步转化率 +1 个百分点，约多 %.0f 人 × %s = **%s**。" % (
                pre[0], steps[i][0], gain1, C.num(args.aov), C.money(gain1 * args.aov)))

    L.append("")
    L.append("## 结论边界\n")
    L.append("- 漏斗只说明**在哪一步流失**，不说明**为什么流失**。要原因，去看该步的页面、流程、人群差异。")
    L.append("- 若步骤之间存在旁路（用户可跳过某步），单步率会失真，需按真实路径重新定义步骤。")
    L.append("- 单步率高低不能跨业务比较，不同漏斗的「正常水平」不一样。")
    L.append("")
    L.append("## 复现\n")
    L.append("```bash")
    if args.file:
        L.append("python funnel_steps.py --file %s --user %s --step %s --order %s%s%s" % (
            args.file, args.user, args.step, args.order,
            (" --baseline " + args.baseline) if args.baseline else "",
            (" --aov %s" % args.aov) if args.aov else ""))
    else:
        L.append("python funnel_steps.py %s%s%s" % (
            args.counts,
            (" --baseline " + args.baseline) if args.baseline else "",
            (" --aov %s" % args.aov) if args.aov else ""))
    L.append("```")
    L.append("")
    L.append("---\n*由 czl-evidence-playbook / funnel_steps.py 生成*")

    C.write_out("\n".join(L), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
