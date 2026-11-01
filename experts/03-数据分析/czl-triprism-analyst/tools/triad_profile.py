# -*- coding: utf-8 -*-
"""三棱镜 · 体检层（Triage）

在任何分析开始之前，先把表摸清楚：每列是什么、缺多少、有没有重复、
能不能做时间序列、可信度评级（A/B/C/D）与是否放行（pass/warn/block）。

这一层是整条流水线的闸门：体检不通过就不许往下跑，
避免三位分析官在垃圾数据上各算一套、最后合成一份看着很专业但错的报告。
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import statistics as st

from triad_io import TableError, read_table

GRADE_ORDER = {"A": 4, "B": 3, "C": 2, "D": 1}


def _pct(x, digits=2):
    return round(float(x) * 100, digits)


def _safe_div(a, b):
    return (a / b) if b else None


def _percentile(sorted_vals, q):
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = (len(sorted_vals) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def numeric_stats(values):
    if not values:
        return None
    s = sorted(values)
    mean = st.fmean(s)
    sd = st.pstdev(s) if len(s) > 1 else 0.0
    return {
        "count": len(s),
        "min": round(s[0], 6),
        "max": round(s[-1], 6),
        "mean": round(mean, 6),
        "median": round(_percentile(s, 0.5), 6),
        "p05": round(_percentile(s, 0.05), 6),
        "p95": round(_percentile(s, 0.95), 6),
        "std": round(sd, 6),
        "cv": round(sd / mean, 6) if mean else None,
        "zeros": sum(1 for v in s if v == 0),
        "negatives": sum(1 for v in s if v < 0),
        "sum": round(sum(s), 6),
    }


def text_stats(values, top_n=5):
    if not values:
        return None
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0])))[:top_n]
    total = len(values)
    return {
        "cardinality": len(counts),
        "top": [{"value": k, "count": c, "share": _pct(c / total)} for k, c in ranked],
    }


def date_stats(values):
    if not values:
        return None
    s = sorted(values)
    gaps = [(s[i + 1] - s[i]).days for i in range(len(s) - 1)]
    gaps = [g for g in gaps if g > 0]
    median_gap = st.median(gaps) if gaps else 0
    return {
        "min": s[0].strftime("%Y-%m-%d"),
        "max": s[-1].strftime("%Y-%m-%d"),
        "distinct_dates": len(set(v.date() for v in s)),
        "span_days": (s[-1] - s[0]).days,
        "median_gap_days": median_gap,
        "grain": guess_grain(median_gap),
        "future_dates": sum(1 for v in s if v > _dt.datetime.now()),
    }


def guess_grain(median_gap_days):
    if median_gap_days <= 0:
        return "single"
    if median_gap_days <= 1.5:
        return "day"
    if median_gap_days <= 8:
        return "week"
    if median_gap_days <= 32:
        return "month"
    if median_gap_days <= 95:
        return "quarter"
    return "year"


def profile_table(path, sheet=None):
    table = read_table(path, sheet)
    cols = []
    issues = []
    for c in table.columns:
        item = {
            "name": c.name,
            "kind": c.kind,
            "non_null": len(c.values),
            "null": c.nulls,
            "null_rate": _pct(c.nulls / table.n_rows) if table.n_rows else 0.0,
        }
        if c.kind == "number":
            item["numeric"] = numeric_stats(c.values)
            item["distinct"] = len(set(c.values))
        elif c.kind == "date":
            item["date"] = date_stats(c.values)
            item["distinct"] = len(set(c.values))
        elif c.kind == "text":
            item["text"] = text_stats(c.values)
            item["distinct"] = item["text"]["cardinality"] if item["text"] else 0
        else:
            item["distinct"] = 0
        cols.append(item)

        if c.kind == "empty":
            issues.append({"level": "warn", "code": "empty_column",
                           "column": c.name, "message": f"列「{c.name}」全空，已忽略"})
        elif item["null_rate"] >= 30:
            issues.append({"level": "warn", "code": "high_null",
                           "column": c.name,
                           "message": f"列「{c.name}」缺失率 {item['null_rate']}%，结论需谨慎"})
        if c.kind == "date" and item["date"]["future_dates"]:
            issues.append({"level": "info", "code": "future_dates", "column": c.name,
                           "message": f"列「{c.name}」有 {item['date']['future_dates']} 个未来日期，可能是计划值而非实绩"})

    # 整行重复
    seen = set()
    dup = 0
    for r in table.rows:
        key = tuple(str(x).strip() for x in r)
        if key in seen:
            dup += 1
        else:
            seen.add(key)
    dup_rate = _pct(dup / table.n_rows) if table.n_rows else 0.0
    if dup_rate >= 2:
        issues.append({"level": "warn", "code": "duplicate_rows", "column": None,
                       "message": f"整行完全重复 {dup} 行（{dup_rate}%），可能重复导入"})

    nums = table.numeric_columns()
    dates = table.date_columns()
    texts = table.text_columns()

    time_axis = None
    if dates:
        best = max(dates, key=lambda c: len(set(v.date() for v in c.values)))
        stats = date_stats(best.values)
        time_axis = {"column": best.name, "grain": stats["grain"],
                     "from": stats["min"], "to": stats["max"],
                     "points": stats["distinct_dates"]}
        if stats["distinct_dates"] < 3:
            issues.append({"level": "warn", "code": "thin_time_axis", "column": best.name,
                           "message": "时间轴上的不同时点少于 3 个，趋势分析只能给方向不能给斜率"})

    if not nums:
        issues.append({"level": "block", "code": "no_numeric", "column": None,
                       "message": "没有任何可识别的数值列，无法做量化分析"})
    if table.n_rows < 10:
        issues.append({"level": "block", "code": "too_few_rows", "column": None,
                       "message": f"有效数据仅 {table.n_rows} 行，不足以支撑任何统计结论"})
    elif table.n_rows < 30:
        issues.append({"level": "warn", "code": "small_sample", "column": None,
                       "message": f"有效数据 {table.n_rows} 行，离群检测与显著性判断可靠性下降"})
    if table.n_cols <= 1:
        issues.append({"level": "block", "code": "single_column", "column": None,
                       "message": "只有一列数据，没有维度也没有度量，无法分析"})

    score = 100
    for it in issues:
        if it["code"] in ("high_null", "duplicate_rows"):
            score -= 10
        elif it["code"] == "small_sample":
            score -= 20
        elif it["code"] == "thin_time_axis":
            score -= 5
        elif it["code"] == "future_dates":
            score -= 2
        elif it["level"] == "block":
            score -= 40
    score = max(0, min(100, score))
    grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 55 else "D"
    gate = "block" if any(i["level"] == "block" for i in issues) else (
        "warn" if grade in ("C", "D") else "pass")

    return {
        "tool": "triad_profile",
        "version": 1,
        "source": os.path.basename(path),
        "path": os.path.abspath(path),
        "sheet": table.sheet,
        "rows": table.n_rows,
        "cols": table.n_cols,
        "headers": list(table.headers),
        "columns": cols,
        "duplicates": {"full_row_duplicates": dup, "rate": dup_rate},
        "time_axis": time_axis,
        "metric_candidates": [c.name for c in nums],
        "dimension_candidates": [c.name for c in texts if 1 < (len(set(c.values)) or 0) <= max(60, table.n_rows // 2)],
        "quality": {"score": score, "grade": grade, "gate": gate, "issues": issues},
        "notes": table.notes,
    }


def summarize_for_prompt(profile):
    """把 profile 压成一段给模型看的摘要，避免整表塞进上下文。"""
    lines = [f"表：{profile['source']} / 工作表 {profile['sheet']} / {profile['rows']} 行 × {profile['cols']} 列",
             f"可信度：{profile['quality']['grade']}（{profile['quality']['score']} 分），闸门 {profile['quality']['gate']}"]
    if profile.get("time_axis"):
        ta = profile["time_axis"]
        lines.append(f"时间轴：{ta['column']}（{ta['grain']}，{ta['from']} → {ta['to']}，{ta['points']} 个时点）")
    else:
        lines.append("时间轴：未识别到可用日期列")
    lines.append("数值列：" + "、".join(profile["metric_candidates"]))
    if profile["dimension_candidates"]:
        lines.append("维度列：" + "、".join(profile["dimension_candidates"][:8]))
    if profile["quality"]["issues"]:
        lines.append("体检发现：")
        for it in profile["quality"]["issues"][:8]:
            lines.append(f"  - [{it['level']}] {it['message']}")
    return "\n".join(lines)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="三棱镜 · 表格体检")
    ap.add_argument("path")
    ap.add_argument("--sheet", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--brief", action="store_true", help="只打印给模型看的摘要")
    args = ap.parse_args(argv)
    try:
        prof = profile_table(args.path, args.sheet)
    except TableError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(prof, fh, ensure_ascii=False, indent=2)
    if args.brief:
        print(summarize_for_prompt(prof))
    else:
        print(json.dumps(prof, ensure_ascii=False, indent=2))
    return 0 if prof["quality"]["gate"] != "block" else 3


if __name__ == "__main__":
    raise SystemExit(main())
