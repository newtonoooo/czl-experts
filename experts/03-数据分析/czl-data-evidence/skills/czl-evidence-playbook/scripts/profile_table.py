#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
profile_table.py — 表格体检：出质量账与可用性评级。

用法：
    python profile_table.py 订单.csv
    python profile_table.py 订单.csv --out 质量账.md --by 渠道 --key 订单号

评级口径见 SKILL.md 与 references/07-数据质量判定标准.md。
"""

import argparse
import sys

import czl_core as C


def infer_type(values):
    """返回 (类型, 非空数, 数值可解析数, 日期可解析数)。"""
    nonempty = [v for v in values if str(v).strip() != ""]
    n = len(nonempty)
    if n == 0:
        return "空列", 0, 0, 0
    num_ok = sum(1 for v in nonempty if C.to_number(v) is not None)
    date_ok = sum(1 for v in nonempty if C.to_date(v) is not None)
    sample = nonempty[:50]
    num_ratio = sum(1 for v in sample if C.to_number(v) is not None) / len(sample)
    date_ratio = sum(1 for v in sample if C.to_date(v) is not None) / len(sample)
    if rate_ok(date_ratio, num_ratio):
        return "日期", n, num_ok, date_ok
    if rate_ok(num_ratio, date_ratio):
        return "数值", n, num_ok, date_ok
    # 同列类型混杂的判定：既有数字又有文字，且各占一定比例
    mixed = 0.15 < num_ratio < 0.85
    return ("文本(混杂)" if mixed else "文本"), n, num_ok, date_ok


def rate_ok(a, b):
    return a >= 0.9 and a > b


def grade(v, a, b, c, reverse=False):
    """按阈值打 A–D。reverse=True 时数值越小越好。"""
    if reverse:
        return "A" if v <= a else "B" if v <= b else "C" if v <= c else "D"
    return "A" if v >= a else "B" if v >= b else "C" if v >= c else "D"


def worst(*grades):
    order = {"A": 0, "B": 1, "C": 2, "D": 3}
    return max(grades, key=lambda g: order[g])


def main():
    ap = argparse.ArgumentParser(description="数证台 · 表格体检（质量账）")
    ap.add_argument("path", help="CSV/TSV 文件")
    ap.add_argument("--out", help="输出 Markdown 路径（默认打印到屏幕）")
    ap.add_argument("--by", help="分组维度列名，用于判断分组样本量是否充足")
    ap.add_argument("--key", help="主体列名（订单号/客户ID），用于重复主体检查")
    args = ap.parse_args()

    header, rows, enc = C.read_table(args.path)
    nrow, ncol = len(rows), len(header)
    C.warn("已读取 %d 行 × %d 列，编码 %s" % (nrow, ncol, enc))

    # ---- 逐列体检
    col_stats = []
    for i, name in enumerate(header):
        vals = [r[i] for r in rows]
        typ, nonempty, num_ok, date_ok = infer_type(vals)
        missing = 1 - nonempty / nrow if nrow else 0
        uniq = len({(v or "").strip() for v in vals if str(v).strip() != ""})
        st = {"名称": name, "类型": typ, "缺失率": missing, "唯一值": uniq,
              "非空": nonempty}
        if typ == "数值" and nonempty:
            nums = sorted(C.numbers(rows, i))
            if nums:
                q1 = C.quantile(nums, 0.25)
                q3 = C.quantile(nums, 0.75)
                iqr = q3 - q1
                outliers = sum(1 for v in nums if v > q3 + 3 * iqr or v < q1 - 3 * iqr) if iqr else 0
                st.update({"min": nums[0], "p50": C.quantile(nums, .5),
                           "p90": C.quantile(nums, .9), "max": nums[-1],
                           "mean": C.mean(nums), "离群": outliers})
        if typ == "日期" and nonempty:
            ds = sorted(d for d in (C.to_date(v) for v in vals) if d)
            if ds:
                span = (ds[-1] - ds[0]).days + 1
                st.update({"起": ds[0], "止": ds[-1], "跨度天": span,
                           "有数据天数": len(set(ds)),
                           "断档天": max(0, span - len(set(ds)))})
        col_stats.append(st)

    # ---- 重复行
    seen, dup_rows = set(), 0
    for r in rows:
        k = tuple((c or "").strip() for c in r)
        if k in seen:
            dup_rows += 1
        else:
            seen.add(k)
    dup_ratio = dup_rows / nrow if nrow else 0

    dup_key = None
    if args.key:
        ki = C.col_index(header, args.key)
        keys = [(r[ki] or "").strip() for r in rows if (r[ki] or "").strip()]
        if keys:
            dup_key = len(keys) - len(set(keys))
            dup_key = (dup_key, dup_key / len(keys))

    # ---- 分组样本量
    min_group = None
    if args.by:
        bi = C.col_index(header, args.by)
        g = C.groups(rows, bi)
        if g:
            smallest = min(g.items(), key=lambda kv: len(kv[1]))
            min_group = (smallest[0], len(smallest[1]), len(g))

    # ---- 五维评级
    worst_missing_col = max(col_stats, key=lambda s: s["缺失率"])
    completeness = 1 - worst_missing_col["缺失率"]
    g_complete = grade(completeness, 0.99, 0.95, 0.80, reverse=False)

    g_cont = "—"
    gap_note = ""
    date_cols = [s for s in col_stats if s["类型"] == "日期"]
    if date_cols:
        dc = max(date_cols, key=lambda s: s.get("有数据天数", 0))
        gaps = dc.get("断档天", 0)
        g_cont = grade(gaps, 0, 2, 7, reverse=True)
        gap_note = "%s 断档 %d 天" % (dc["名称"], gaps)

    g_dup = grade(dup_ratio, 0.0, 0.005, 0.03, reverse=True)

    mixed_cols = [s["名称"] for s in col_stats if s["类型"] == "文本(混杂)"]
    g_cons = ("A" if not mixed_cols else "B" if len(mixed_cols) == 1
              else "C" if len(mixed_cols) == 2 else "D")

    if min_group:
        g_samp = grade(min_group[1], 200, 100, 30)
        samp_note = "最小分组「%s」%d 行（共 %d 组）" % (min_group[0], min_group[1], min_group[2])
    else:
        g_samp = grade(nrow, 1000, 300, 100)
        samp_note = "按总行数近似（未指定 --by，实际分组样本量可能更小）"

    overall = worst(g_complete, g_cont if g_cont != "—" else "A", g_dup, g_cons, g_samp)

    # ---- 三条影响提示（规则生成，需人工确认）
    hints = []
    if completeness < 0.99:
        hints.append(("列「%s」缺失 %.1f%%" % (worst_missing_col["名称"], worst_missing_col["缺失率"] * 100),
                      "若缺失集中在特定类型样本，合计值会被系统性低估或高估",
                      "按该列是否为空分别统计，或改用可得子集并在报告标注"))
    if dup_ratio > 0:
        hints.append(("疑似重复行 %d 行（%.2f%%）" % (dup_rows, dup_ratio * 100),
                      "所有合计值会被等比放大，比例类指标影响较小",
                      "按业务主键去重后再算，去重前后各出一版对比"))
    if dup_key and dup_key[0] > 0:
        hints.append(("主体「%s」有 %d 条重复（%.2f%%）" % (args.key, dup_key[0], dup_key[1] * 100),
                      "按主体计数会虚高；按主体求和的指标不受影响",
                      "明确是按人还是按单统计，报告里写清粒度"))
    if g_cont not in ("A", "—") and gap_note:
        hints.append((gap_note,
                      "趋势图上会出现假跳变，把断档前后连成一条线会误导",
                      "按日/周补零或打断点，报告里注明断档"))
    for mc in mixed_cols[:1]:
        hints.append(("列「%s」类型混杂（数字与文字并存）" % mc,
                      "求和时会静默跳过非数字行，导致合计偏低",
                      "清洗规则写进留痕，被跳过的样本贴出来核对"))
    if min_group and min_group[1] < 100:
        hints.append(("最小分组「%s」仅 %d 行" % (min_group[0], min_group[1]),
                      "该组差异大概率是噪声，不能据此下结论",
                      "合并到「其他」或明确标注样本不足"))
    while len(hints) < 3:
        hints.append(("未发现显著质量问题",
                      "当前数据在五个维度上均无明显缺陷",
                      "仍建议抽样核对 20 行原始记录，确认导出未错列"))

    # ---- 输出
    L = []
    L.append("# 质量账（自动生成）\n")
    L.append("| 项 | 值 |\n|---|---|")
    L.append("| 文件 | `%s` |" % args.path)
    L.append("| 行数 × 列数 | %d × %d |" % (nrow, ncol))
    L.append("| 编码 | %s |" % enc)
    L.append("| 整体评级 | **%s** |" % overall)
    L.append("")
    L.append("> 评级取五维中最低项。评级含义：A 可直接支撑决策 / B 可支撑但需注明限制 / C 只能描述 / D 不产出业务结论。\n")

    L.append("## 一、五维评级\n")
    L.append(C.md_table(
        ["维度", "评级", "依据"],
        [["完整性", g_complete,
          ("所有列无缺失" if worst_missing_col["缺失率"] == 0 else
           "缺失率最高的有效列「%s」缺失 %.2f%%" % (worst_missing_col["名称"], worst_missing_col["缺失率"] * 100))],
         ["连续性", g_cont, gap_note or "未识别到日期列"],
         ["唯一性", g_dup, "整行重复 %d 行（%.2f%%）" % (dup_rows, dup_ratio * 100)],
         ["一致性", g_cons, ("同列类型混杂的列：" + "、".join(mixed_cols)) if mixed_cols else "未发现同列类型混杂"],
         ["充分性", g_samp, samp_note]]))
    L.append("")

    L.append("## 二、逐列体检\n")
    rows_out = []
    for s in col_stats:
        extra = ""
        if s["类型"] == "数值" and "p50" in s:
            extra = "中位 %s / P90 %s / 极值 %s–%s／离群 %d" % (
                C.num(s["p50"]), C.num(s["p90"]), C.num(s["min"]), C.num(s["max"]), s["离群"])
        elif s["类型"] == "日期" and "起" in s:
            extra = "%s → %s，有数据 %d 天" % (s["起"], s["止"], s["有数据天数"])
        rows_out.append([s["名称"], s["类型"], "%.2f%%" % (s["缺失率"] * 100), s["唯一值"], extra])
    L.append(C.md_table(["列名", "推断类型", "缺失率", "唯一值", "备注"], rows_out))
    L.append("")

    L.append("## 三、三条影响提示\n")
    L.append("> 以下三条由脚本规则生成，只说明「可能怎么偏」，实际方向需人工确认。\n")
    L.append(C.md_table(["#", "发现的问题", "会让结论偏成什么样", "处理办法"],
                        [[i + 1, h[0], h[1], h[2]] for i, h in enumerate(hints[:3])]))
    L.append("")

    L.append("## 四、本数据能做什么\n")
    can = { "A": "可支撑归因与决策建议（仍需过五验）",
            "B": "可支撑归因，结论须注明限制",
            "C": "只能做描述，不能做归因",
            "D": "不能产出业务结论，先修数据" }[overall]
    L.append("- 能：%s" % can)
    if overall in ("C", "D"):
        L.append("- 不能：做因果判断、给预算级动作建议")
    L.append("- 复现命令：`python profile_table.py %s%s%s`" % (
        args.path,
        (" --by " + args.by) if args.by else "",
        (" --key " + args.key) if args.key else ""))
    L.append("")
    L.append("---\n*由 czl-evidence-playbook / profile_table.py 生成，口径与判级标准见同目录上级 references/07-数据质量判定标准.md*")

    C.write_out("\n".join(L), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
