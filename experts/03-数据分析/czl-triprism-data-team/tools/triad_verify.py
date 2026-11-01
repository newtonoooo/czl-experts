# -*- coding: utf-8 -*-
"""三棱镜 · 校验层（Evidence Recheck）

这是本产品与「让模型写一段分析」最根本的区别：
每一条结论都附带一个 recheck 规格，校验官用同一份源数据重算一遍，
算不出来的、对不上的，一律降级或剔除，不进入最终报告。

状态：
  PASS  复算一致（相对误差 ≤ 0.5% 或绝对误差 ≤ 0.01）
  FAIL  复算不一致
  SKIP  规格不足以复算（例如缺字段），报告中标注为「未复算」
"""

from __future__ import annotations

import json

from triad_contract import apply_filters
from triad_io import TableError, _to_number, parse_date, read_table
from triad_analyze import (analyze_composition, analyze_course, analyze_integrity,
                           build_series, bucket_key)

REL_TOL = 0.005
ABS_TOL = 0.01


def _series_of(table, spec, rows):
    return build_series(rows, table, spec["time_field"], spec["field"],
                        spec.get("agg", "sum"), spec.get("grain", "month"))


def _groups(table, rows, field, agg, dimension):
    idx = {c.name: c.index for c in table.columns}
    d_i, f_i = idx[dimension], idx[field]
    g = {}
    for r in rows:
        if d_i >= len(r) or f_i >= len(r):
            continue
        key = str(r[d_i]).strip() or "(空)"
        if agg in ("count", "distinct"):
            g.setdefault(key, []).append(str(r[f_i]).strip())
        else:
            v = _to_number(r[f_i])
            if v is not None:
                g.setdefault(key, []).append(v)
    out = {}
    for k, vals in g.items():
        if not vals:
            continue
        if agg == "sum":
            out[k] = sum(vals)
        elif agg == "mean":
            out[k] = sum(vals) / len(vals)
        elif agg == "max":
            out[k] = max(vals)
        elif agg == "min":
            out[k] = min(vals)
        elif agg == "count":
            out[k] = float(len(vals))
        else:
            out[k] = float(len(set(vals)))
    return out


def recompute(table, spec):
    """按 recheck 规格重算一个标量。返回 (value, note)。"""
    rows, _ = apply_filters(table, spec.get("filters"))
    op = spec.get("op")

    if op == "delta_pct":
        s = _series_of(table, spec, rows)
        if len(s) < 2 or s[0][1] == 0:
            return None, "时点不足或首期为 0"
        return (s[-1][1] - s[0][1]) / abs(s[0][1]) * 100, f"{s[0][0]}→{s[-1][0]}"

    if op == "mom_pct":
        s = _series_of(table, spec, rows)
        if len(s) < 2 or s[-2][1] == 0:
            return None, "时点不足或上期为 0"
        return (s[-1][1] - s[-2][1]) / abs(s[-2][1]) * 100, f"{s[-2][0]}→{s[-1][0]}"

    if op == "inflection_delta":
        res = analyze_course(table, {"grain": spec.get("grain"), "time_field": spec["time_field"],
                                     "metrics": [{"id": "X", "name": spec["field"], "field": spec["field"],
                                                  "agg": spec.get("agg", "sum")}]},
                             {"id": "X", "name": spec["field"], "field": spec["field"],
                              "agg": spec.get("agg", "sum")},
                             filters=spec.get("filters"))
        for inf in res.get("inflections", []):
            if inf["period"] == spec.get("period"):
                return inf["delta"], f"拐点 {inf['period']}"
        return None, "该期未复现拐点"

    if op == "share":
        g = _groups(table, rows, spec["field"], spec.get("agg", "sum"), spec["dimension"])
        total = sum(g.values())
        if not total or spec.get("name") not in g:
            return None, "分组不存在或合计为 0"
        return g[spec["name"]] / total * 100, spec["name"]

    if op == "hhi":
        g = _groups(table, rows, spec["field"], spec.get("agg", "sum"), spec["dimension"])
        total = sum(g.values())
        if not total:
            return None, "合计为 0"
        return sum((v / total) ** 2 for v in g.values()) * 10000, f"{len(g)} 个分组"

    if op == "share_shift":
        idx = {c.name: c.index for c in table.columns}
        t_i = idx[spec["time_field"]]
        grain = spec.get("grain") or "month"
        buckets = {}
        for r in rows:
            d = parse_date(r[t_i]) if t_i < len(r) else None
            if d:
                buckets.setdefault(bucket_key(d, grain), []).append(r)
        if len(buckets) < 2:
            return None, "时点不足"
        keys = sorted(buckets)
        def share_of(rs):
            g = _groups(table, rs, spec["field"], spec.get("agg", "sum"), spec["dimension"])
            t = sum(g.values()) or 1
            return g.get(spec["name"], 0) / t * 100
        return share_of(buckets[keys[-1]]) - share_of(buckets[keys[0]]), f"{keys[0]}→{keys[-1]}"

    if op == "value_at":
        idx = {c.name: c.index for c in table.columns}
        col = idx.get(spec["column"])
        row_no = spec.get("row")
        if col is None or not isinstance(row_no, int):
            return None, "缺少行号或列名"
        data_i = row_no - 2          # 文件行号 = 表头 1 行 + 数据从第 2 行起
        if not (0 <= data_i < len(rows)):
            return None, "行号超出范围"
        return _to_number(rows[data_i][col]), f"第 {row_no} 行"

    if op == "duplicate_rows":
        seen, dup = set(), 0
        for r in rows:
            key = tuple(str(x).strip() for x in r)
            if key in seen:
                dup += 1
            else:
                seen.add(key)
        return float(dup), "整行重复计数"

    if op == "row_count":
        return float(len(rows)), "过滤后行数"

    if op == "count_where":
        idx = {c.name: c.index for c in table.columns}
        col = idx.get(spec.get("field"))
        if col is None:
            return None, "字段不存在"
        cmp_ = spec.get("cmp", "!=")
        target = spec.get("value")
        n = 0
        for r in rows:
            if col >= len(r):
                continue
            v = _to_number(r[col])
            if v is None:
                continue
            if cmp_ == "!=" and target is None:
                n += 1
            elif cmp_ == "<" and v < target:
                n += 1
            elif cmp_ == ">" and v > target:
                n += 1
            elif cmp_ == "==" and abs(v - target) < 1e-9:
                n += 1
        return float(n), "条件计数"

    return None, f"未知复算操作 {op}"


def close_enough(a, b):
    if a is None or b is None:
        return False
    if abs(a - b) <= ABS_TOL:
        return True
    denom = max(abs(a), abs(b), 1e-12)
    return abs(a - b) / denom <= REL_TOL


def verify_findings(table, bundle):
    """bundle 为 analyze 输出（含 lanes）。返回校验报告。"""
    results = []
    for lane, data in (bundle.get("lanes") or {}).items():
        if not isinstance(data, dict):
            continue
        for f in data.get("findings") or []:
            spec = f.get("recheck")
            if not spec:
                results.append({"lane": lane, "id": f.get("id"), "status": "SKIP",
                                "claim_value": f.get("value"), "recomputed": None,
                                "note": "该结论未附复算规格", "claim": f.get("claim")})
                continue
            try:
                val, note = recompute(table, spec)
            except (TableError, KeyError, ValueError, ZeroDivisionError) as exc:
                val, note = None, f"复算异常：{exc}"
            if val is None:
                status = "SKIP"
            elif close_enough(val, f.get("value")):
                status = "PASS"
            else:
                status = "FAIL"
            results.append({"lane": lane, "id": f.get("id"), "status": status,
                            "claim_value": f.get("value"), "recomputed": None if val is None else round(val, 4),
                            "note": note, "claim": f.get("claim"), "op": spec.get("op")})

    checked = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    skipped = sum(1 for r in results if r["status"] == "SKIP")
    if failed == 0 and passed > 0:
        overall = "PASS"
    elif failed == 0:
        overall = "SKIP"
    else:
        overall = "FAIL"
    return {"overall": overall, "checked": checked, "passed": passed,
            "failed": failed, "skipped": skipped, "results": results,
            "note": "FAIL 的结论必须从报告中删除或改写；SKIP 的结论必须在报告中标注「未复算」"}


def demote(bundle, report):
    """把 FAIL 的结论降级为 C/D 并在 claims 上打标记，供渲染层过滤。"""
    bad = {(r["lane"], r["id"]) for r in report["results"] if r["status"] == "FAIL"}
    skip = {(r["lane"], r["id"]) for r in report["results"] if r["status"] == "SKIP"}
    for lane, data in (bundle.get("lanes") or {}).items():
        if not isinstance(data, dict):
            continue
        for f in data.get("findings") or []:
            key = (lane, f.get("id"))
            if key in bad:
                f["grade"] = "D"
                f["verified"] = False
                f["flag"] = "复算不一致，已作废"
            elif key in skip:
                f["verified"] = None
                f["flag"] = "未复算"
            else:
                f["verified"] = True
    return bundle


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="三棱镜 · 结论复算校验")
    ap.add_argument("--path", required=True)
    ap.add_argument("--sheet", default=None)
    ap.add_argument("--bundle", required=True, help="analyze 输出的 JSON")
    ap.add_argument("--out", default=None)
    ap.add_argument("--demote-out", default=None, help="写出降级后的 bundle")
    args = ap.parse_args(argv)
    try:
        table = read_table(args.path, args.sheet)
    except TableError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    with open(args.bundle, "r", encoding="utf-8") as fh:
        bundle = json.load(fh)
    report = verify_findings(table, bundle)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
    if args.demote_out:
        with open(args.demote_out, "w", encoding="utf-8") as fh:
            json.dump(demote(bundle, report), fh, ensure_ascii=False, indent=2)
    print(json.dumps({"overall": report["overall"], "checked": report["checked"],
                      "passed": report["passed"], "failed": report["failed"],
                      "skipped": report["skipped"]}, ensure_ascii=False))
    return 0 if report["overall"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
