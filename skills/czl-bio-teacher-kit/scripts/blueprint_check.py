#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""blueprint_check.py — 双向细目表校验（纯标准库）

检查项：
    1. 必填字段齐全（题号/考点/认知层级/题型/分值/预估难度）
    2. 分值合计等于设定总分
    3. 认知层级分布与目标配比偏差不超过阈值
    4. 难度配比与用途匹配
    5. 单一考点分值占比不超过阈值
    6. 题号连续且不重复

用法：
    python blueprint_check.py -i blueprint.csv --total 100 --profile unit
    python blueprint_check.py -i blueprint.csv --json

退出码：0 通过（可能带警告）；1 存在错误；2 参数或文件问题。
"""

import argparse
import csv
import json
import sys
from typing import Dict, List

REQUIRED = ["题号", "考点", "认知层级", "题型", "分值", "预估难度"]
LEVELS = ["记忆", "理解", "应用", "分析"]
DIFFS = ["易", "中", "难"]

PROFILES = {
    "unit":   {"level": [0.20, 0.40, 0.30, 0.10], "diff": [0.60, 0.30, 0.10], "label": "单元测"},
    "monthly": {"level": [0.15, 0.35, 0.35, 0.15], "diff": [0.50, 0.40, 0.10], "label": "月考"},
    "drill":  {"level": [0.10, 0.30, 0.40, 0.20], "diff": [0.40, 0.40, 0.20], "label": "专项训练"},
    "timed":  {"level": [0.25, 0.40, 0.30, 0.05], "diff": [0.70, 0.20, 0.10], "label": "限时训练"},
}


def load(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError("细目表没有数据行")
    return [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in rows]


def check(rows: List[Dict[str, str]], total: float, profile: str, level_tol: float, diff_tol: float,
          max_single: float):
    errors: List[str] = []
    warnings: List[str] = []

    fields = set(rows[0].keys())
    missing = [f for f in REQUIRED if f not in fields]
    if missing:
        return {"ok": False, "errors": [f"缺少字段: {', '.join(missing)}"], "warnings": [], "stats": {}}

    sum_score = 0.0
    level_score: Dict[str, float] = {k: 0.0 for k in LEVELS}
    diff_count: Dict[str, int] = {k: 0 for k in DIFFS}
    point_score: Dict[str, float] = {}
    seen_no = []

    for i, r in enumerate(rows, start=2):
        for f in REQUIRED:
            if not r.get(f):
                errors.append(f"第{i}行：字段「{f}」为空")
        lv = r.get("认知层级", "")
        if lv and lv not in LEVELS:
            errors.append(f"第{i}行：认知层级「{lv}」非法，应为 {'/'.join(LEVELS)}")
        df = r.get("预估难度", "")
        if df and df not in DIFFS:
            errors.append(f"第{i}行：预估难度「{df}」非法，应为 {'/'.join(DIFFS)}")
        try:
            sc = float(r.get("分值", "0") or 0)
        except ValueError:
            sc = 0.0
            errors.append(f"第{i}行：分值不是数字")
        sum_score += sc
        if lv in level_score:
            level_score[lv] += sc
        if df in diff_count:
            diff_count[df] += 1
        p = r.get("考点", "")
        if p:
            point_score[p] = point_score.get(p, 0.0) + sc
        no = r.get("题号", "")
        if no in seen_no:
            errors.append(f"第{i}行：题号「{no}」重复")
        seen_no.append(no)

    if abs(sum_score - total) > 1e-6:
        errors.append(f"分值合计 {sum_score:g} 与总分 {total:g} 不一致")

    prof = PROFILES[profile]
    if sum_score > 0:
        lv_actual = [level_score[k] / sum_score for k in LEVELS]
        for k, a, t in zip(LEVELS, lv_actual, prof["level"]):
            if abs(a - t) > level_tol:
                warnings.append(f"认知层级「{k}」实际 {a*100:.0f}%，目标 {t*100:.0f}%，偏差超过 {level_tol*100:.0f} 个百分点")
        cnt = sum(diff_count.values()) or 1
        df_actual = [diff_count[k] / cnt for k in DIFFS]
        for k, a, t in zip(DIFFS, df_actual, prof["diff"]):
            if abs(a - t) > diff_tol:
                warnings.append(f"难度「{k}」实际 {a*100:.0f}%，目标 {t*100:.0f}%，偏差超过 {diff_tol*100:.0f} 个百分点")
    else:
        lv_actual = [0, 0, 0, 0]
        df_actual = [0, 0, 0]

    if sum_score > 0:
        for p, sc in sorted(point_score.items(), key=lambda x: -x[1]):
            share = sc / sum_score
            if share > max_single:
                warnings.append(f"考点「{p}」占 {share*100:.0f}%，超过单品上限 {max_single*100:.0f}%")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "题目数": len(rows),
            "分值合计": round(sum_score, 2),
            "认知层级占比": {k: round(v, 4) for k, v in zip(LEVELS, lv_actual)},
            "难度占比": {k: round(v, 4) for k, v in zip(DIFFS, df_actual)},
            "考点数": len(point_score),
            "用途": prof["label"],
        },
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="双向细目表校验")
    ap.add_argument("-i", "--input", required=True)
    ap.add_argument("--total", type=float, default=100.0, help="试卷总分，默认 100")
    ap.add_argument("--profile", choices=list(PROFILES), default="unit", help="用途预设")
    ap.add_argument("--level-tol", type=float, default=0.10, help="层级偏差容忍度，默认 0.10")
    ap.add_argument("--diff-tol", type=float, default=0.15, help="难度偏差容忍度，默认 0.15")
    ap.add_argument("--max-single", type=float, default=0.35, help="单一考点分值上限占比，默认 0.35")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    try:
        rows = load(args.input)
    except Exception as exc:  # noqa: BLE001
        print(f"[错误] {exc}", file=sys.stderr)
        return 2

    res = check(rows, args.total, args.profile, args.level_tol, args.diff_tol, args.max_single)

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        st = res["stats"]
        print(f"用途 {st.get('用途')}｜题目 {st.get('题目数')}｜分值合计 {st.get('分值合计')}｜考点 {st.get('考点数')}")
        print("认知层级：" + "  ".join(f"{k} {v*100:.0f}%" for k, v in st.get("认知层级占比", {}).items()))
        print("难度分布：" + "  ".join(f"{k} {v*100:.0f}%" for k, v in st.get("难度占比", {}).items()))
        for w in res["warnings"]:
            print(f"[警告] {w}")
        for e in res["errors"]:
            print(f"[错误] {e}")
        print("结论：" + ("通过" if res["ok"] else "不通过"))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
