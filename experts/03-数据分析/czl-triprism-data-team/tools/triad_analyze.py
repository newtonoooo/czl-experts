# -*- coding: utf-8 -*-
"""三棱镜 · 三路分析引擎

三条互不重叠的分析线，各自产出结构化结论（JSON），每条结论都带一个
可被重新计算的 recheck 规格，供校验官复算。模型只负责叙述，数字全部由本模块算出。

lane = course      走势：时间序列、拐点、季节性、外推
lane = composition 拆解：占比、集中度、结构位移、交叉
lane = integrity   验伤：离群、缺失、重复、规则违背
"""

from __future__ import annotations

import datetime as _dt
import math
import statistics as st

from triad_contract import apply_filters, ContractError

SEVERITY_ORDER = {"CRITICAL": 0, "WARN": 1, "INFO": 2}
GROUP_DEVIATION_THRESHOLD = 0.40   # 组内数值偏离中位数超过 40% 即标记为关注


# ---------------------------------------------------------------- 通用

def bucket_key(d, grain):
    if grain == "day":
        return d.strftime("%Y-%m-%d")
    if grain == "week":
        iso = d.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    if grain == "month":
        return d.strftime("%Y-%m")
    if grain == "quarter":
        return f"{d.year}-Q{(d.month - 1) // 3 + 1}"
    return d.strftime("%Y")


def _r(x, digits=4):
    if x is None:
        return None
    try:
        return round(float(x), digits)
    except (TypeError, ValueError):
        return None


def _pct(new, old):
    if old in (None, 0):
        return None
    return (new - old) / abs(old) * 100.0


def num_txt(v):
    """叙述用数字格式：大数不显示无意义小数，小数保留两位。"""
    if v is None:
        return "—"
    a = abs(v)
    if a >= 1000:
        return f"{v:,.0f}"
    if a >= 100:
        return f"{v:,.1f}"
    return f"{v:,.2f}"


def ols(y):
    """最小二乘直线拟合，返回 (slope, intercept, r2)。"""
    n = len(y)
    if n < 2:
        return 0.0, (y[0] if y else 0.0), 0.0
    xs = list(range(n))
    mx, my = st.fmean(xs), st.fmean(y)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return 0.0, my, 0.0
    sxy = sum((xs[i] - mx) * (y[i] - my) for i in range(n))
    slope = sxy / sxx
    intercept = my - slope * mx
    ss_tot = sum((v - my) ** 2 for v in y)
    ss_res = sum((y[i] - (intercept + slope * xs[i])) ** 2 for i in range(n))
    r2 = 0.0 if ss_tot == 0 else max(0.0, 1 - ss_res / ss_tot)
    return slope, intercept, r2


def smooth(y, window=3):
    if len(y) < window:
        return list(y)
    out = []
    half = window // 2
    for i in range(len(y)):
        lo = max(0, i - half)
        hi = min(len(y), i + half + 1)
        out.append(st.fmean(y[lo:hi]))
    return out


def next_period_label(label, grain):
    try:
        if grain == "month":
            y, m = label.split("-")
            y, m = int(y), int(m) + 1
            if m > 12:
                y, m = y + 1, 1
            return f"{y}-{m:02d}"
        if grain == "year":
            return str(int(label) + 1)
        if grain == "quarter":
            y, q = label.split("-Q")
            y, q = int(y), int(q) + 1
            if q > 4:
                y, q = y + 1, 1
            return f"{y}-Q{q}"
        if grain == "day":
            d = _dt.datetime.strptime(label, "%Y-%m-%d") + _dt.timedelta(days=1)
            return d.strftime("%Y-%m-%d")
        if grain == "week":
            y, w = label.split("-W")
            w = int(w) + 1
            if w > 52:
                y, w = int(y) + 1, 1
            return f"{int(y)}-W{w:02d}"
    except (ValueError, IndexError):
        pass
    return f"{label}+1"


def build_series(rows, table, time_field, field, agg, grain, filters=None):
    """按时间粒度聚合，返回 [(label, value)] 且已按时间排序。"""
    t_idx = {c.name: c.index for c in table.columns}[time_field]
    f_idx = {c.name: c.index for c in table.columns}[field]
    from triad_io import _to_number, parse_date
    buckets = {}
    for r in rows:
        if t_idx >= len(r) or f_idx >= len(r):
            continue
        d = parse_date(r[t_idx])
        if d is None:
            continue
        key = bucket_key(d, grain)
        if agg in ("count", "distinct"):
            buckets.setdefault(key, []).append(str(r[f_idx]).strip())
            continue
        v = _to_number(r[f_idx])
        if v is None:
            continue
        buckets.setdefault(key, []).append(v)
    out = []
    for key in sorted(buckets):
        vals = buckets[key]
        if agg == "sum":
            out.append((key, sum(vals)))
        elif agg == "mean":
            out.append((key, st.fmean(vals)))
        elif agg == "max":
            out.append((key, max(vals)))
        elif agg == "min":
            out.append((key, min(vals)))
        elif agg == "count":
            out.append((key, float(len(vals))))
        elif agg == "distinct":
            out.append((key, float(len(set(vals)))))
    return out


# ---------------------------------------------------------------- 走势线

def analyze_course(table, contract, metric, filters=None):
    grain = contract.get("grain") or "month"
    time_field = contract.get("time_field")
    rows, applied = apply_filters(table, filters or contract.get("filters"))
    if not time_field:
        return {"lane": "course", "available": False,
                "reason": "口径未指定时间字段，无法做走势分析",
                "findings": [], "caveats": ["未识别到时间轴"]}

    series = build_series(rows, table, time_field, metric["field"], metric.get("agg", "sum"), grain)
    if len(series) < 2:
        return {"lane": "course", "available": False,
                "reason": f"按 {grain} 聚合后只有 {len(series)} 个时点，无法判断走势",
                "findings": [], "caveats": ["时间点不足"]}

    labels = [s[0] for s in series]
    values = [s[1] for s in series]
    slope, intercept, r2 = ols(values)
    first, last = values[0], values[-1]
    change_pct = _pct(last, first)
    diffs = [values[i + 1] - values[i] for i in range(len(values) - 1)]
    mean_v = st.fmean(values)
    cv = (st.pstdev(values) / mean_v) if mean_v else None

    direction = "平稳"
    if slope > 0 and abs(change_pct or 0) >= 5:
        direction = "上行"
    elif slope < 0 and abs(change_pct or 0) >= 5:
        direction = "下行"
    elif abs(change_pct or 0) < 5:
        direction = "基本持平"

    grade = "A" if (len(values) >= 12 and r2 >= 0.5) else "B" if len(values) >= 6 else "C" if len(values) >= 3 else "D"

    # 拐点：在平滑序列上找斜率变化最大的位置（前后各留足样本，避免把首尾噪声当拐点）
    inflections = []
    if len(values) >= 7:
        sm = smooth(values, 3)
        d1 = [sm[i + 1] - sm[i] for i in range(len(sm) - 1)]
        d2 = [d1[i + 1] - d1[i] for i in range(len(d1) - 1)]
        thresh = (st.pstdev(d2) if len(d2) > 1 else 0) * 0.8
        cands = [(abs(d2[i]), i) for i in range(len(d2))
                 if abs(d2[i]) >= thresh and thresh > 0 and 2 <= i <= len(d2) - 3]
        cands.sort(reverse=True)
        for _, i in cands[:2]:
            before = st.fmean(d1[max(0, i - 2): i + 1])
            after = st.fmean(d1[i + 1: min(len(d1), i + 4)])
            inflections.append({
                "period": labels[i + 1],
                "before_slope": _r(before),
                "after_slope": _r(after),
                "delta": _r(after - before),
                "note": "由升转降" if after < before else "由降转升",
            })

    # 环比 / 同比
    mom = None
    if len(values) >= 2:
        mom = {"period": labels[-1], "value": _r(last),
               "prev_period": labels[-2], "prev_value": _r(values[-2]),
               "change_pct": _r(_pct(last, values[-2]))}
    yoy = None
    if grain == "month" and len(values) >= 13:
        yoy = {"period": labels[-1], "value": _r(last),
               "base_period": labels[-13], "base_value": _r(values[-13]),
               "change_pct": _r(_pct(last, values[-13]))}

    # 季节性：至少两年月度数据
    seasonality = {"available": False}
    if grain == "month" and len(values) >= 24:
        by_month = {}
        for label, v in series:
            m = label.split("-")[1]
            by_month.setdefault(m, []).append(v)
        overall = st.fmean(values) or 1
        idx = [{"month": m, "index": _r(st.fmean(vs) / overall)} for m, vs in sorted(by_month.items())]
        seasonality = {"available": True, "method": "月份均值比整体均值", "index": idx}

    # 外推：线性 + 残差带，明确标注置信度
    forecast = {"available": False}
    if len(values) >= 4:
        resid = [values[i] - (intercept + slope * i) for i in range(len(values))]
        se = st.pstdev(resid) if len(resid) > 1 else 0.0
        horizon = 3
        pts = []
        label = labels[-1]
        for h in range(1, horizon + 1):
            label = next_period_label(label, grain)
            v = intercept + slope * (len(values) - 1 + h)
            pts.append({"period": label, "value": _r(v),
                        "low": _r(v - 1.96 * se), "high": _r(v + 1.96 * se)})
        forecast = {"available": True, "method": "最小二乘直线外推，区间为 ±1.96×残差标准差",
                    "confidence": "中" if r2 >= 0.5 else "低", "r2": _r(r2), "points": pts}

    findings = [{
        "id": "C1",
        "claim": f"{metric['name']}从 {labels[0]} 的 {num_txt(first)} 变到 {labels[-1]} 的 {num_txt(last)}，整体{direction}"
                 + (f"，累计{'增长' if (change_pct or 0) >= 0 else '下降'} {abs(change_pct):.2f}%" if change_pct is not None else ""),
        "value": _r(change_pct, 2),
        "unit": "%",
        "grade": grade,
        "recheck": {"op": "delta_pct", "field": metric["field"], "agg": metric.get("agg", "sum"),
                    "grain": grain, "time_field": time_field, "filters": applied},
    }]
    if mom and mom["change_pct"] is not None:
        findings.append({
            "id": "C2",
            "claim": f"最近一期（{mom['period']}）环比{'上升' if mom['change_pct'] >= 0 else '下降'} {abs(mom['change_pct']):.2f}%",
            "value": _r(mom["change_pct"], 2), "unit": "%", "grade": grade,
            "recheck": {"op": "mom_pct", "field": metric["field"], "agg": metric.get("agg", "sum"),
                        "grain": grain, "time_field": time_field, "filters": applied},
        })
    for k, inf in enumerate(inflections, 1):
        findings.append({
            "id": f"C{k+2}",
            "claim": f"{inf['period']} 出现走势转折（{inf['note']}），前后斜率由 {num_txt(inf['before_slope'])} 变为 {num_txt(inf['after_slope'])}",
            "value": inf["delta"], "unit": "单位/期", "grade": "B" if len(values) >= 8 else "C",
            "recheck": {"op": "inflection_delta", "field": metric["field"], "agg": metric.get("agg", "sum"),
                        "grain": grain, "time_field": time_field, "period": inf["period"], "filters": applied},
        })

    caveats = []
    if len(values) < 6:
        caveats.append(f"只有 {len(values)} 个时点，斜率与拐点仅供参考，不能作为趋势定论")
    if r2 < 0.3 and len(values) >= 6:
        caveats.append(f"线性拟合 R²={r2:.2f}，走势更像波动而非稳定趋势")
    if forecast.get("available") and forecast["confidence"] == "低":
        caveats.append("外推置信度低，区间仅用于量级参考")

    return {
        "lane": "course",
        "available": True,
        "metric": {"id": metric["id"], "name": metric["name"], "unit": metric.get("unit")},
        "time_field": time_field,
        "grain": grain,
        "series": [{"period": p, "value": _r(v)} for p, v in series],
        "stats": {"first": _r(first), "last": _r(last), "change_pct": _r(change_pct, 2),
                  "slope_per_period": _r(slope), "r2": _r(r2), "cv": _r(cv),
                  "mean": _r(mean_v), "points": len(values), "direction": direction},
        "mom": mom, "yoy": yoy,
        "inflections": inflections,
        "seasonality": seasonality,
        "forecast": forecast,
        "findings": findings,
        "caveats": caveats,
        "filters_applied": applied,
    }


# ---------------------------------------------------------------- 拆解线

def analyze_composition(table, contract, metric, dimension, filters=None, top_n=6):
    rows, applied = apply_filters(table, filters or contract.get("filters"))
    idx = {c.name: c.index for c in table.columns}
    if dimension not in idx:
        return {"lane": "composition", "available": False,
                "reason": f"维度「{dimension}」不在表中", "findings": [], "caveats": []}
    from triad_io import _to_number
    d_i, f_i = idx[dimension], idx[metric["field"]]
    agg = metric.get("agg", "sum")
    groups = {}
    for r in rows:
        if d_i >= len(r) or f_i >= len(r):
            continue
        key = str(r[d_i]).strip() or "(空)"
        if agg in ("count", "distinct"):
            groups.setdefault(key, []).append(str(r[f_i]).strip())
            continue
        v = _to_number(r[f_i])
        if v is None:
            continue
        groups.setdefault(key, []).append(v)

    def combine(vals):
        if agg == "sum":
            return sum(vals)
        if agg == "mean":
            return st.fmean(vals)
        if agg == "max":
            return max(vals)
        if agg == "min":
            return min(vals)
        if agg == "count":
            return float(len(vals))
        return float(len(set(vals)))

    items = [(k, combine(v)) for k, v in groups.items() if v]
    total = sum(v for _, v in items)
    if not items or total == 0:
        return {"lane": "composition", "available": False,
                "reason": "该维度下没有有效数值可拆解", "findings": [], "caveats": []}
    items.sort(key=lambda kv: -kv[1])
    shares = [(k, v, v / total) for k, v in items]
    cum = 0.0
    rows_out = []
    for k, v, s in shares:
        cum += s
        rows_out.append({"name": k, "value": _r(v), "share": _r(s * 100, 2), "cum_share": _r(cum * 100, 2)})

    hhi = sum(s * s for _, _, s in shares) * 10000
    top2 = sum(s for _, _, s in shares[:2]) * 100
    pareto_n = next((i + 1 for i, r in enumerate(rows_out) if (r["cum_share"] or 0) >= 80), len(rows_out))
    if hhi >= 2500:
        level = "高度集中"
    elif hhi >= 1500:
        level = "中度集中"
    elif hhi >= 1000:
        level = "轻度集中"
    else:
        level = "较为分散"

    # 结构位移：首期 vs 末期
    shift = []
    time_field = contract.get("time_field")
    if time_field and time_field in idx:
        from triad_io import parse_date
        grain = contract.get("grain") or "month"
        t_i = idx[time_field]
        buckets = {}
        for r in rows:
            d = parse_date(r[t_i]) if t_i < len(r) else None
            if d is None:
                continue
            buckets.setdefault(bucket_key(d, grain), []).append(r)
        if len(buckets) >= 2:
            keys = sorted(buckets)
            def shares_of(rs):
                g = {}
                for r in rs:
                    if d_i >= len(r):
                        continue
                    k = str(r[d_i]).strip() or "(空)"
                    v = _to_number(r[f_i]) if f_i < len(r) else None
                    if v is None:
                        continue
                    g[k] = g.get(k, 0.0) + v
                t = sum(g.values()) or 1
                return {k: v / t for k, v in g.items()}
            s0, s1 = shares_of(buckets[keys[0]]), shares_of(buckets[keys[-1]])
            for k in {**s0, **s1}:
                delta = (s1.get(k, 0) - s0.get(k, 0)) * 100
                if abs(delta) >= 1:
                    shift.append({"name": k, "share_first": _r(s0.get(k, 0) * 100, 2),
                                  "share_last": _r(s1.get(k, 0) * 100, 2), "delta_pp": _r(delta, 2)})
            shift.sort(key=lambda x: -abs(x["delta_pp"]))
            shift = shift[:5]

    grade = "A" if len(items) >= 3 and len(rows) >= 30 else "B" if len(items) >= 2 else "C"
    findings = [{
        "id": "S1",
        "claim": f"按「{dimension}」拆解，{rows_out[0]['name']}占 {rows_out[0]['share']}%"
                 + (f"，前两名合计 {top2:.2f}%，结构{level}" if len(rows_out) >= 2 else ""),
        "value": rows_out[0]["share"], "unit": "%", "grade": grade,
        "recheck": {"op": "share", "field": metric["field"], "agg": agg,
                    "dimension": dimension, "name": rows_out[0]["name"], "filters": applied},
    }]
    findings.append({
        "id": "S2",
        "claim": f"该维度的集中度 HHI 为 {hhi:.0f}（{level}），达到 80% 累计占比需要 {pareto_n} 个分组",
        "value": _r(hhi, 0), "unit": "HHI", "grade": grade,
        "recheck": {"op": "hhi", "field": metric["field"], "agg": agg,
                    "dimension": dimension, "filters": applied},
    })
    if shift:
        top = shift[0]
        findings.append({
            "id": "S3",
            "claim": f"结构位移最大的是「{top['name']}」，占比从 {top['share_first']}% 变为 {top['share_last']}%（{top['delta_pp']:+.2f} 个百分点）",
            "value": top["delta_pp"], "unit": "pp", "grade": "B",
            "recheck": {"op": "share_shift", "field": metric["field"], "agg": agg,
                        "dimension": dimension, "name": top["name"], "grain": contract.get("grain"),
                        "time_field": time_field, "filters": applied},
        })

    caveats = []
    if len(items) > 12:
        caveats.append(f"该维度有 {len(items)} 个分组，只展示前 {top_n} 项，其余归入「其他」")
    if len(rows) < 30:
        caveats.append("样本行数偏少，占比结构的稳定性有限")

    return {
        "lane": "composition",
        "available": True,
        "metric": {"id": metric["id"], "name": metric["name"], "unit": metric.get("unit")},
        "dimension": dimension,
        "groups": len(items),
        "total": _r(total),
        "rows": rows_out[:top_n] + ([{"name": "其他", "value": _r(total - sum(r["value"] for r in rows_out[:top_n])),
                                      "share": _r((1 - sum(r["share"] for r in rows_out[:top_n]) / 100) * 100, 2),
                                      "cum_share": 100.0}]
                                    if len(rows_out) > top_n else []),
        "top2_share": _r(top2, 2),
        "hhi": _r(hhi, 0),
        "hhi_level": level,
        "pareto_n": pareto_n,
        "shift": shift,
        "findings": findings,
        "caveats": caveats,
        "filters_applied": applied,
    }


# ---------------------------------------------------------------- 验伤线

def _modified_z(values):
    med = st.median(values)
    mad = st.median([abs(v - med) for v in values])
    if mad == 0:
        sd = st.pstdev(values) if len(values) > 1 else 0
        return [0.0] * len(values), med, (sd or 1)
    return [0.6745 * (v - med) / mad for v in values], med, mad


def analyze_integrity(table, contract, filters=None, max_critical=5):
    rows, applied = apply_filters(table, filters or contract.get("filters"))
    idx = {c.name: c.index for c in table.columns}
    items = []
    metrics = [m for m in (contract.get("metrics") or []) if m.get("field") in idx]

    for m in metrics:
        field = m["field"]
        col = table.column(field)
        if col.kind != "number":
            continue
        i = idx[field]
        vals, pos = [], []
        for r_i, r in enumerate(rows):
            if i >= len(r):
                continue
            from triad_io import _to_number
            v = _to_number(r[i])
            if v is not None:
                vals.append(v)
                pos.append(r_i)
        if len(vals) < 8:
            items.append({"severity": "INFO", "code": "small_sample", "column": field, "row": None,
                          "value": None, "expected": "≥8 个有效数值",
                          "message": f"「{field}」有效数值仅 {len(vals)} 个，离群检测不可靠",
                          "action": "补充数据或改用人工核对"})
            continue

        zs, med, mad = _modified_z(vals)
        q1 = st.quantiles(vals, n=4)[0] if len(vals) >= 4 else min(vals)
        q3 = st.quantiles(vals, n=4)[2] if len(vals) >= 4 else max(vals)
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        for k, v in enumerate(vals):
            z = abs(zs[k])
            if z >= 3.5:
                sev = "CRITICAL" if z >= 6 or v < 0 else "WARN"
                items.append({"severity": sev, "code": "robust_outlier", "column": field,
                              "row": pos[k] + 2, "value": _r(v),
                              "expected": f"中位数 {med:,.2f}，稳健 z={z:.2f}",
                              "message": f"「{field}」第 {pos[k]+2} 行数值 {v:,.2f} 明显偏离常态（稳健 z={z:.1f}）",
                              "action": "核对该行原始凭证，确认是录入错误还是真实业务事件"})
            elif v < lo or v > hi:
                items.append({"severity": "INFO", "code": "iqr_outlier", "column": field,
                              "row": pos[k] + 2, "value": _r(v),
                              "expected": f"IQR 正常区间 [{lo:,.2f}, {hi:,.2f}]",
                              "message": f"「{field}」第 {pos[k]+2} 行落在 1.5×IQR 之外，仅作记录",
                              "action": "无需处理，观察是否连续出现"})
        neg = [v for v in vals if v < 0]
        if neg:
            items.append({"severity": "CRITICAL", "code": "negative_value", "column": field,
                          "row": None, "value": _r(min(neg)),
                          "expected": "非负金额",
                          "message": f"「{field}」出现 {len(neg)} 个负值，最小 {min(neg):,.2f}",
                          "action": "确认是否为退款/冲销，若是应单列口径而不是混在正向金额里"})

    # 分组内离群：整体分布会被大分组掩盖，必须按维度（含维度交叉）再看一遍
    from triad_io import _to_number as _num
    dims = [d for d in (contract.get("dimensions") or []) if d in idx][:2]
    group_plans = []
    if dims:
        group_plans.append((dims, " × ".join(dims)))
    for plan_dims, plan_label in group_plans:
        groups = {}
        for r_i, r in enumerate(rows):
            key_parts = []
            ok = True
            for d in plan_dims:
                di = idx[d]
                if di >= len(r):
                    ok = False
                    break
                key_parts.append(str(r[di]).strip() or "(空)")
            if ok:
                groups.setdefault(" / ".join(key_parts), []).append(r_i)
        for m in metrics:
            if m["field"] not in idx:
                continue
            f_i = idx[m["field"]]
            for gname, row_ids in groups.items():
                if len(row_ids) < 6:
                    continue
                gvals = [(ri, _num(rows[ri][f_i])) for ri in row_ids
                         if f_i < len(rows[ri]) and _num(rows[ri][f_i]) is not None]
                if len(gvals) < 6:
                    continue
                vs = [v for _, v in gvals]
                zs, gmed, _ = _modified_z(vs)
                flagged = set()
                hits = [(k, abs(zs[k])) for k in range(len(vs)) if abs(zs[k]) >= 3.5]
                hits.sort(key=lambda kv: -kv[1])
                for k, z in hits[:2]:
                    ri, v = gvals[k]
                    flagged.add(k)
                    items.append({
                        "severity": "WARN", "code": "group_outlier", "column": m["field"],
                        "row": ri + 2, "value": _r(v),
                        "expected": f"「{plan_label}={gname}」组内中位数 {gmed:,.2f}",
                        "message": f"「{m['field']}」第 {ri+2} 行在「{gname}」分组内明显偏离（稳健 z={z:.1f}）",
                        "action": "与同组其他记录对比，确认该行是否为压价、退货或录入错误",
                    })
                # 稳健 z 对「同组季节性波动大」的场景偏保守，再补一条相对中位数的偏离规则
                if gmed:
                    ratios = [(k, v / gmed) for k, (_, v) in enumerate(gvals)
                              if k not in flagged and abs(v / gmed - 1) >= GROUP_DEVIATION_THRESHOLD]
                    ratios.sort(key=lambda kv: -abs(kv[1] - 1))
                    for k, ratio in ratios[:2]:
                        ri, v = gvals[k]
                        items.append({
                            "severity": "WARN", "code": "group_deviation", "column": m["field"],
                            "row": ri + 2, "value": _r(v),
                            "expected": f"「{plan_label}={gname}」组内中位数 {gmed:,.2f}",
                            "message": f"「{m['field']}」第 {ri+2} 行为同组中位数的 {ratio*100:.0f}%（{v:,.0f} vs {gmed:,.0f}）",
                            "action": "确认是真实业务事件（降价/退货/一次性冲销）还是录入错误，并在报告中注明",
                        })

    # 缺失
    for c in table.columns:
        if c.kind == "empty":
            continue
        rate = c.nulls / len(rows) if rows else 0
        if rate >= 0.05:
            items.append({"severity": "WARN" if rate >= 0.2 else "INFO", "code": "missing",
                          "column": c.name, "row": None, "value": _r(rate * 100, 2),
                          "expected": "缺失率 <5%",
                          "message": f"「{c.name}」缺失 {c.nulls} 个（{rate*100:.1f}%）",
                          "action": "确认缺失是未填写还是业务上不存在"})

    # 重复
    seen, dups = {}, 0
    for r_i, r in enumerate(rows):
        key = tuple(str(x).strip() for x in r)
        if key in seen:
            dups += 1
            if dups <= 3:
                items.append({"severity": "WARN", "code": "duplicate_row", "column": None,
                              "row": r_i + 2, "value": None,
                              "expected": "与第 %d 行不重复" % (seen[key] + 2),
                              "message": f"第 {r_i+2} 行与第 {seen[key]+2} 行完全相同",
                              "action": "确认是否重复导入，重复行会让合计虚高"})
        else:
            seen[key] = r_i

    # 未来日期
    from triad_io import parse_date
    now = _dt.datetime.now()
    for c in table.date_columns():
        i = c.index
        fut = [(r_i + 2, parse_date(r[i])) for r_i, r in enumerate(rows)
               if i < len(r) and parse_date(r[i]) and parse_date(r[i]) > now]
        if fut:
            items.append({"severity": "WARN", "code": "future_date", "column": c.name,
                          "row": fut[0][0], "value": fut[0][1].strftime("%Y-%m-%d"),
                          "expected": "不晚于今天",
                          "message": f"「{c.name}」有 {len(fut)} 个未来日期，首例在第 {fut[0][0]} 行",
                          "action": "确认是否为计划值；计划值与实绩混算会让趋势失真"})

    # 业务规则
    from triad_io import _to_number
    for rule in contract.get("rules") or []:
        field = rule.get("field")
        if field not in idx:
            continue
        i = idx[field]
        rtype = rule.get("type")
        thr = rule.get("threshold")
        hits = []
        for r_i, r in enumerate(rows):
            if i >= len(r):
                continue
            v = _to_number(r[i])
            if v is None:
                continue
            if rtype == "max_single" and thr is not None and v > thr:
                hits.append((r_i + 2, v))
            elif rtype == "min_single" and thr is not None and v < thr:
                hits.append((r_i + 2, v))
            elif rtype == "required_positive" and v <= 0:
                hits.append((r_i + 2, v))
        for row_no, v in hits[:3]:
            items.append({"severity": "CRITICAL", "code": "rule_violation", "column": field,
                          "row": row_no, "value": _r(v), "expected": f"规则：{rule.get('message') or rtype}",
                          "message": f"第 {row_no} 行「{field}」= {v:,.2f}，违背规则「{rule.get('message') or rtype}」",
                          "action": "按内控流程复核该笔记录"})

    items.sort(key=lambda x: (SEVERITY_ORDER.get(x["severity"], 9), x["column"] or "", x["row"] or 0))
    counts = {"CRITICAL": 0, "WARN": 0, "INFO": 0}
    for it in items:
        counts[it["severity"]] += 1
    crit_items = [i for i in items if i["severity"] == "CRITICAL"][:max_critical]
    kept = crit_items + [i for i in items if i["severity"] != "CRITICAL"][:20]

    findings = []
    if counts["CRITICAL"]:
        top = crit_items[0]
        findings.append({
            "id": "A1",
            "claim": f"发现 {counts['CRITICAL']} 处高危异常，最严重的是第 {top['row']} 行「{top['column']}」= {num_txt(top['value'])}",
            "value": top["value"], "unit": "元", "grade": "A",
            "recheck": {"op": "value_at", "column": top["column"], "row": top["row"],
                        "filters": applied},
        })
    if dups:
        findings.append({"id": "A2", "claim": f"存在 {dups} 行完全重复的记录，合计会被重复计算",
                         "value": dups, "unit": "行", "grade": "A",
                         "recheck": {"op": "duplicate_rows", "filters": applied}})
    findings.append({"id": "A3", "claim": f"本次共扫描 {len(rows)} 行，标记 {len(items)} 条问题"
                                          f"（高危 {counts['CRITICAL']} / 关注 {counts['WARN']} / 提示 {counts['INFO']}）",
                     "value": len(rows), "unit": "行", "grade": "A",
                     "recheck": {"op": "row_count", "filters": applied}})

    return {
        "lane": "integrity",
        "available": True,
        "scanned_rows": len(rows),
        "counts": counts,
        "items": kept,
        "findings": findings,
        "caveats": (["样本不足 30 行，离群判定以稳健 z 为主，IQR 仅作提示"] if len(rows) < 30 else []),
        "filters_applied": applied,
    }


# ---------------------------------------------------------------- 编排

def run_lanes(table, contract, lanes=None, metrics=None, dimensions=None):
    lanes = lanes or ["course", "composition", "integrity"]
    out = {"contract": contract, "lanes": {}}
    ms = [m for m in (contract.get("metrics") or [])]
    if metrics:
        ms = [m for m in ms if m.get("id") in metrics or m.get("name") in metrics] or ms
    primary = ms[0] if ms else None
    dims = dimensions or contract.get("dimensions") or []
    try:
        if "course" in lanes and primary:
            out["lanes"]["course"] = analyze_course(table, contract, primary)
        if "composition" in lanes and primary and dims:
            out["lanes"]["composition"] = analyze_composition(table, contract, primary, dims[0])
        if "integrity" in lanes:
            out["lanes"]["integrity"] = analyze_integrity(table, contract)
    except ContractError as exc:
        out["error"] = str(exc)
    return out
