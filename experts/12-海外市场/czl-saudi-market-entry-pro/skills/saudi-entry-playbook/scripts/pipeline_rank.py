#!/usr/bin/env python3
"""G4 商机优先级排序。

不看合同额排名，而是把金额、毛利、胜率、时间、可及性、匹配度、竞争强度
折算成一个可比分数，再分档。所有输入必须显式提供。

用法：
    python pipeline_rank.py --input pipeline.json
    python pipeline_rank.py --input pipeline.json --format md
"""

import argparse
import json
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

TIER_RULES = [(0.70, "A"), (0.40, "B"), (0.0, "C")]
TIER_ACTION = {
    "A": "投入资源：组建投标小组，锁定资格与伙伴",
    "B": "保持跟踪：补齐资格缺口，观察竞争动向",
    "C": "明确放弃：写明原因，释放资源",
}


def _clamp(val, lo, hi, field, name):
    try:
        num = float(val)
    except (TypeError, ValueError):
        raise ValueError(f"{name}: 字段 {field} 必须为数字")
    if num < lo or num > hi:
        raise ValueError(f"{name}: 字段 {field} 应在 {lo}-{hi} 区间，收到 {num}")
    return num


def score_one(opp):
    name = opp.get("name", "unnamed")
    value = _clamp(opp.get("value_sar", 0), 0, 1e13, "value_sar", name)
    margin = _clamp(opp.get("gross_margin_pct", 0.2), 0, 1, "gross_margin_pct", name)
    win = _clamp(opp.get("win_probability", 0.2), 0, 1, "win_probability", name)
    months = _clamp(opp.get("months_to_award", 6), 0, 120, "months_to_award", name)
    access = _clamp(opp.get("accessibility", 3), 1, 5, "accessibility", name)
    fit = _clamp(opp.get("fit", 3), 1, 5, "fit", name)
    comp = _clamp(opp.get("competition", 3), 1, 5, "competition", name)

    expected_margin = value * margin * win
    time_discount = 1.0 / (1.0 + months / 12.0)
    quality = (access * fit) / comp
    raw = expected_margin * time_discount * quality

    return {
        "name": name,
        "expected_margin_sar": round(expected_margin, 2),
        "time_discount": round(time_discount, 4),
        "quality_factor": round(quality, 3),
        "raw_score": raw,
        "inputs": {
            "value_sar": value,
            "gross_margin_pct": margin,
            "win_probability": win,
            "months_to_award": months,
            "accessibility": access,
            "fit": fit,
            "competition": comp,
        },
    }


def analyze(payload):
    opps = payload.get("opportunities") or []
    if not opps:
        raise ValueError("opportunities 不能为空")

    scored = [score_one(o) for o in opps]
    peak = max(s["raw_score"] for s in scored) or 1.0

    for s in scored:
        s["index"] = round(s["raw_score"] / peak * 100, 1)
        s["tier"] = next(letter for threshold, letter in TIER_RULES if s["index"] >= threshold * 100)
        s["action"] = TIER_ACTION[s["tier"]]

    scored.sort(key=lambda s: s["index"], reverse=True)
    for i, s in enumerate(scored, 1):
        s["rank"] = i

    return {
        "count": len(scored),
        "ranking": scored,
        "tiers": {
            letter: [s["name"] for s in scored if s["tier"] == letter] for letter in ("A", "B", "C")
        },
        "note": "分档基于同一批机会的相对位置，不是绝对收益预测。",
    }


def to_markdown(result):
    lines = [
        "## 商机优先级",
        "",
        "| 排名 | 商机 | 指数 | 档位 | 期望毛利 | 时间折现 | 处置 |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in result["ranking"]:
        lines.append(
            f"| {s['rank']} | {s['name']} | {s['index']:.1f} | {s['tier']} | "
            f"{s['expected_margin_sar']:,.0f} | {s['time_discount']:.2f} | {s['action']} |"
        )
    lines += ["", f"> {result['note']}"]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="G4 商机优先级排序")
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
