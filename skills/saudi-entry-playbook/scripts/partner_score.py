#!/usr/bin/env python3
"""G3 伙伴八维评分。

固定权重、固定红旗项，保证不同候选之间可比。
红旗项一票否决：不论总分多高，等级直接降为 D。

用法：
    python partner_score.py --input candidates.json
    python partner_score.py --input candidates.json --format md
"""

import argparse
import json
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DIMENSIONS = [
    ("category_fit", "品类匹配", 0.20),
    ("customer_coverage", "客户覆盖", 0.18),
    ("technical_capability", "技术能力", 0.15),
    ("financial_strength", "财务稳健", 0.12),
    ("compliance_record", "合规记录", 0.12),
    ("channel_depth", "渠道深度", 0.10),
    ("commitment", "投入意愿", 0.08),
    ("governance", "治理透明度", 0.05),
]

RED_FLAGS = {
    "exclusive_no_commitment": "要求无边界独家且拒绝业绩承诺",
    "refuse_disclosure": "拒绝提供 CR / 税务 / 股权信息",
    "direct_competitor": "与自有产品直接竞争且无隔离安排",
    "litigation": "存在未决重大诉讼或失信记录",
    "informal_settlement": "要求非正规结算方式",
    "nominee_arrangement": "提出挂名、代持或虚假本地化",
}

GRADES = [(80, "A"), (65, "B"), (50, "C"), (0, "D")]
GRADE_ACTION = {
    "A": "可签，进入条款谈判",
    "B": "有条件可签，列明条件与观察期",
    "C": "观察，先做小单试合作",
    "D": "不可签，写明原因",
}


def grade_of(score):
    for threshold, letter in GRADES:
        if score >= threshold:
            return letter
    return "D"


def score_candidate(cand):
    name = cand.get("name", "unnamed")
    scores = cand.get("scores") or {}
    missing = [key for key, _, _ in DIMENSIONS if key not in scores]

    breakdown = []
    total = 0.0
    for key, label, weight in DIMENSIONS:
        raw = scores.get(key)
        if raw is None:
            breakdown.append(
                {"key": key, "label": label, "weight": weight, "score": None, "weighted": None}
            )
            continue
        try:
            val = float(raw)
        except (TypeError, ValueError):
            raise ValueError(f"{name}: 维度 {key} 必须为 1-5 的数字")
        if val < 1 or val > 5:
            raise ValueError(f"{name}: 维度 {key} 超出 1-5 区间")
        weighted = val * weight * 20  # 折算到 100 分制
        total += weighted
        breakdown.append(
            {
                "key": key,
                "label": label,
                "weight": weight,
                "score": val,
                "weighted": round(weighted, 2),
            }
        )

    flags = [f for f in (cand.get("red_flags") or []) if f]
    unknown = [f for f in flags if f not in RED_FLAGS]
    if unknown:
        raise ValueError(f"{name}: 未知红旗代码 {unknown}")

    score = round(total, 2)
    grade = grade_of(score)
    overridden = False
    if flags:
        grade = "D"
        overridden = True

    return {
        "name": name,
        "score": score,
        "grade": grade,
        "grade_overridden_by_red_flag": overridden,
        "action": GRADE_ACTION[grade],
        "missing_dimensions": missing,
        "complete": not missing,
        "breakdown": breakdown,
        "red_flags": [{"code": f, "label": RED_FLAGS[f]} for f in flags],
        "notes": cand.get("notes", ""),
    }


def analyze(payload):
    candidates = payload.get("candidates") or []
    if not candidates:
        raise ValueError("candidates 不能为空")
    results = [score_candidate(c) for c in candidates]
    results.sort(key=lambda r: (r["grade"] != "D", r["score"]), reverse=True)
    for i, r in enumerate(results, 1):
        r["rank"] = i
    return {
        "count": len(results),
        "ranking": results,
        "warning": "只有一家候选时不构成比选：请先扩充长名单（建议 ≥3 家）再做评分。"
        if len(results) < 3
        else "",
    }


def to_markdown(result):
    lines = [
        "## 伙伴评分",
        "",
        "| 排名 | 候选 | 总分 | 等级 | 红旗 | 处置 |",
        "|---|---|---|---|---|---|",
    ]
    for r in result["ranking"]:
        flags = "、".join(f["label"] for f in r["red_flags"]) or "无"
        lines.append(
            f"| {r['rank']} | {r['name']} | {r['score']:.1f} | {r['grade']} | {flags} | {r['action']} |"
        )
    if result["warning"]:
        lines += ["", f"> {result['warning']}"]
    blocked = [r for r in result["ranking"] if r["grade"] == "D"]
    actionable = [r for r in result["ranking"] if r["grade"] != "D"]
    if blocked and actionable:
        top_blocked = max(blocked, key=lambda r: r["score"])
        low_ok = min(actionable, key=lambda r: r["score"])
        if top_blocked["score"] > low_ok["score"]:
            lines += [
                "",
                f"> 注意：{top_blocked['name']} 总分 {top_blocked['score']:.1f}，高于 "
                f"{low_ok['name']} 的 {low_ok['score']:.1f}，但触发红旗项，按规则排在可签候选之后。"
                "分数不能覆盖否决条件。",
            ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="G3 伙伴八维评分")
    ap.add_argument("--input", required=True)
    ap.add_argument("--format", choices=["json", "md"], default="json")
    args = ap.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        result = analyze(payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1

    if args.format == "md":
        print(to_markdown(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
