# -*- coding: utf-8 -*-
"""三棱镜 · 口径层（Metric Contract）

为什么需要这一层：三个人并行看同一张表，最大的失败模式不是算错，
而是三个人用不同的分母、不同的时间粒度、不同的过滤条件，
最后合成一份自相矛盾的报告。

所以本层强制先冻结口径：每个指标写清字段、聚合方式、单位、分母、
时间粒度与过滤条件，并逐项对照体检结果做校验。校验不通过的分析一律作废。
"""

from __future__ import annotations

import json
import os

from triad_io import TableError, read_table

ALLOWED_AGG = ("sum", "mean", "count", "distinct", "max", "min")
ALLOWED_GRAIN = ("day", "week", "month", "quarter", "year")


class ContractError(Exception):
    pass


MONEY_PRIORITY = [
    ("销售额", 100), ("营收", 100), ("收入", 95), ("流水", 90), ("gmv", 90),
    ("金额", 85), ("营业额", 85), ("毛利", 80), ("利润", 78), ("回款", 70),
    ("成本", 60), ("费用", 55), ("支出", 50),
    ("revenue", 100), ("sales", 95), ("amount", 85), ("gmv", 90),
    ("profit", 78), ("cost", 60),
]


def rank_metric_candidates(profile):
    """给数值列排优先级：金额类指标优先，其次按波动性（更有信息量）排序。

    这一步是为了避免「表里第一列恰好是编号或订单数」时，报告围绕一个
    不重要的指标展开。排序只是默认建议，用户/主理人可随时改。
    """
    cols = {c["name"]: c for c in profile["columns"]}
    scored = []
    for i, name in enumerate(profile["metric_candidates"]):
        lower = name.lower()
        pri = 0
        for key, weight in MONEY_PRIORITY:
            if key in lower:
                pri = max(pri, weight)
        cv = (cols.get(name, {}).get("numeric") or {}).get("cv") or 0
        scored.append((pri, min(cv, 2.0), -i, name))
    scored.sort(reverse=True)
    return [s[3] for s in scored]


def draft_contract(profile, metrics=None, dimensions=None, grain=None):
    """从体检结果自动起草一份口径，供主理人改。"""
    metrics = metrics or rank_metric_candidates(profile)[:2]
    time_field = (profile.get("time_axis") or {}).get("column")
    grain = grain or (profile.get("time_axis") or {}).get("grain") or "month"
    dims = dimensions if dimensions is not None else profile["dimension_candidates"][:2]
    items = []
    for i, name in enumerate(metrics, 1):
        items.append({
            "id": f"M{i}",
            "name": name,
            "field": name,
            "agg": "sum",
            "unit": "元",
            "definition": f"按时间粒度对「{name}」求和",
        })
    return {
        "contract_version": 1,
        "table": profile["source"],
        "sheet": profile["sheet"],
        "grain": grain,
        "time_field": time_field,
        "metrics": items,
        "ratios": [],
        "dimensions": list(dims),
        "filters": [],
        "rules": [],
        "comparison": {"mode": "mom" if grain in ("day", "week", "month") else "yoy"},
        "notes": "由体检结果自动起草，使用前请确认指标定义与分母是否符合业务口径",
    }


def _find_col(table, name):
    for c in table.columns:
        if c.name == name:
            return c
    return None


def check_contract(contract, table):
    """逐项校验口径与真实表结构是否对得上。返回 (ok, errors, warnings)。"""
    errors, warnings = [], []
    if not isinstance(contract, dict):
        return False, ["口径文件不是合法的 JSON 对象"], []
    if contract.get("contract_version") != 1:
        warnings.append("contract_version 不是 1，可能是旧版本口径")

    grain = contract.get("grain")
    if grain not in ALLOWED_GRAIN:
        errors.append(f"时间粒度 grain={grain!r} 不在允许值 {ALLOWED_GRAIN} 内")

    tf = contract.get("time_field")
    if tf:
        col = _find_col(table, tf)
        if col is None:
            errors.append(f"时间字段「{tf}」在表中不存在")
        elif col.kind != "date":
            errors.append(f"时间字段「{tf}」的类型是 {col.kind}，不是可解析的日期")
    elif grain:
        warnings.append("未指定时间字段，趋势与同期对比将不可用")

    metrics = contract.get("metrics") or []
    if not metrics:
        errors.append("口径中没有任何指标，无法分析")
    seen = set()
    for m in metrics:
        mid = m.get("id")
        if not mid:
            errors.append(f"指标 {m.get('name')!r} 缺少 id")
        elif mid in seen:
            errors.append(f"指标 id 重复：{mid}")
        seen.add(mid)
        field = m.get("field")
        col = _find_col(table, field) if field else None
        if col is None:
            errors.append(f"指标「{m.get('name')}」引用的字段「{field}」不存在")
            continue
        agg = m.get("agg", "sum")
        if agg not in ALLOWED_AGG:
            errors.append(f"指标「{m.get('name')}」的聚合方式 {agg!r} 不支持")
        if agg in ("sum", "mean") and col.kind != "number":
            errors.append(f"指标「{m.get('name')}」要求数值列，但「{field}」是 {col.kind}")
        if not m.get("unit"):
            warnings.append(f"指标「{m.get('name')}」未写单位，报告将不带单位")

    for r in contract.get("ratios") or []:
        num, den = r.get("numerator"), r.get("denominator")
        for label, f in (("分子", num), ("分母", den)):
            col = _find_col(table, f) if f else None
            if col is None:
                errors.append(f"比率「{r.get('name')}」的{label}字段「{f}」不存在")
            elif col.kind != "number":
                errors.append(f"比率「{r.get('name')}」的{label}「{f}」不是数值列")
        if num and den and num == den:
            errors.append(f"比率「{r.get('name')}」分子分母相同，结果恒为 1")
        if den:
            col = _find_col(table, den)
            if col is not None and col.kind == "number" and col.values and sum(col.values) == 0:
                errors.append(f"比率「{r.get('name')}」的分母「{den}」合计为 0，比率无意义")

    for d in contract.get("dimensions") or []:
        col = _find_col(table, d)
        if col is None:
            errors.append(f"维度「{d}」在表中不存在")
        elif col.kind == "number":
            warnings.append(f"维度「{d}」是数值列，分组数可能过多")
        elif col.kind == "date":
            warnings.append(f"维度「{d}」是日期列，建议改用时间轴而不是当维度")

    for f in contract.get("filters") or []:
        col = _find_col(table, f.get("field", ""))
        if col is None:
            errors.append(f"过滤条件引用的字段「{f.get('field')}」不存在")

    for rule in contract.get("rules") or []:
        if rule.get("type") not in ("max_single", "min_single", "forbidden_value", "required_positive"):
            warnings.append(f"规则类型 {rule.get('type')!r} 未知，将被跳过")
        col = _find_col(table, rule.get("field", ""))
        if col is None:
            errors.append(f"规则「{rule.get('id')}」引用的字段「{rule.get('field')}」不存在")

    return (not errors), errors, warnings


def apply_filters(table, filters):
    """按口径过滤行，返回 (rows, applied) 便于在报告里声明过滤了什么。"""
    if not filters:
        return table.rows, []
    idx = {c.name: c.index for c in table.columns}
    rows = table.rows
    applied = []
    for f in filters:
        field = f.get("field")
        op = f.get("op", "eq")
        value = f.get("value")
        if field not in idx:
            raise ContractError(f"过滤字段不存在：{field}")
        i = idx[field]

        def keep(row):
            v = str(row[i]).strip() if i < len(row) else ""
            if op == "eq":
                return v == str(value)
            if op == "ne":
                return v != str(value)
            if op == "in":
                return v in {str(x) for x in (value or [])}
            if op == "not_in":
                return v not in {str(x) for x in (value or [])}
            if op == "contains":
                return str(value) in v
            raise ContractError(f"不支持的过滤操作 {op}")

        rows = [r for r in rows if keep(r)]
        applied.append({"field": field, "op": op, "value": value, "rows_left": len(rows)})
    return rows, applied


def load_contract(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="三棱镜 · 口径冻结")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draft", help="从体检结果起草口径")
    d.add_argument("--profile", required=True)
    d.add_argument("--out", required=True)
    d.add_argument("--metrics", nargs="*")
    d.add_argument("--dimensions", nargs="*")
    d.add_argument("--grain")
    c = sub.add_parser("check", help="校验口径与表结构")
    c.add_argument("--contract", required=True)
    c.add_argument("--path", required=True)
    c.add_argument("--sheet")
    args = ap.parse_args(argv)

    if args.cmd == "draft":
        with open(args.profile, "r", encoding="utf-8") as fh:
            prof = json.load(fh)
        contract = draft_contract(prof, args.metrics, args.dimensions, args.grain)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(contract, fh, ensure_ascii=False, indent=2)
        print(json.dumps({"ok": True, "contract": args.out}, ensure_ascii=False))
        return 0

    try:
        table = read_table(args.path, args.sheet)
        ok, errors, warnings = check_contract(load_contract(args.contract), table)
    except (TableError, ContractError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)], "warnings": []}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({"ok": ok, "errors": errors, "warnings": warnings}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
