#!/usr/bin/env python3
"""G3 选址加权打分与权重敏感性。

做两件事
    1. 按权重把多个候选落点排序；
    2. 把每个维度权重分别上下调 step，看排名是否翻转（翻转 = 该选择对权重太敏感）。

用法
    python site_score.py input.json
    python site_score.py --demo

input.json 结构
    {
      "criteria": [
        {"key": "logistics", "label": "物流与港口", "weight": 0.30},
        {"key": "utilities", "label": "公用工程",   "weight": 0.20},
        {"key": "land",      "label": "土地与交付", "weight": 0.15},
        {"key": "labor",     "label": "劳动力",     "weight": 0.15},
        {"key": "policy",    "label": "政策与税",   "weight": 0.10},
        {"key": "supply",    "label": "供应链配套", "weight": 0.10}
      ],
      "sites": [
        {"name": "SCZone", "scores": {"logistics": 5, "utilities": 3, "land": 3,
                                      "labor": 2, "policy": 5, "supply": 3}},
        ...
      ],
      "sensitivity_step": 0.10
    }

评分为 1-5，5 最好。权重会自动归一化。
仅依赖标准库。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


DEMO = {
    "criteria": [
        {"key": "logistics", "label": "物流与港口", "weight": 0.30},
        {"key": "utilities", "label": "公用工程", "weight": 0.20},
        {"key": "land", "label": "土地与交付", "weight": 0.15},
        {"key": "labor", "label": "劳动力", "weight": 0.15},
        {"key": "policy", "label": "政策与税", "weight": 0.10},
        {"key": "supply", "label": "供应链配套", "weight": 0.10},
    ],
    "sites": [
        {"name": "SCZone", "scores": {"logistics": 5, "utilities": 3, "land": 3, "labor": 2, "policy": 5, "supply": 3}},
        {"name": "大开罗工业带", "scores": {"logistics": 4, "utilities": 4, "land": 4, "labor": 4, "policy": 3, "supply": 5}},
        {"name": "亚历山大-Borg El Arab", "scores": {"logistics": 5, "utilities": 3, "land": 3, "labor": 3, "policy": 3, "supply": 4}},
        {"name": "上埃及", "scores": {"logistics": 2, "utilities": 2, "land": 5, "labor": 3, "policy": 4, "supply": 2}},
    ],
    "sensitivity_step": 0.10,
}


def _rank(criteria, sites):
    total_w = sum(c["weight"] for c in criteria) or 1.0
    rows = []
    for s in sites:
        score = sum(c["weight"] * s["scores"].get(c["key"], 0) for c in criteria) / total_w
        rows.append({"name": s["name"], "weighted": round(score / 5 * 100, 2)})
    rows.sort(key=lambda r: r["weighted"], reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def compute(payload: dict) -> dict:
    criteria = payload["criteria"]
    sites = payload["sites"]
    step = float(payload.get("sensitivity_step", 0.10))

    base = _rank(criteria, sites)
    base_top = base[0]["name"]

    flips = []
    for i, c in enumerate(criteria):
        for direction in (1 + step, 1 - step):
            alt = [dict(x) for x in criteria]
            alt[i]["weight"] = max(0.0, c["weight"] * direction)
            alt_rank = _rank(alt, sites)
            if alt_rank[0]["name"] != base_top:
                flips.append({
                    "criterion": c.get("label", c["key"]),
                    "adjust": "{:+.0f}%".format((direction - 1) * 100),
                    "new_top": alt_rank[0]["name"],
                })

    gap = base[0]["weighted"] - base[1]["weighted"] if len(base) > 1 else 99
    if gap < 5 and gap >= 0:
        verdict = "TIE"
        note = "前两名分差 {:.2f}，视为并列，需补一条定性理由（交付时间/电力排队/社区关系）".format(gap)
    elif gap > 15:
        verdict = "CLEAR"
        note = "前两名分差 {:.2f}，可给单一推荐，但需写明备选反超条件".format(gap)
    else:
        verdict = "LEAN"
        note = "前两名分差 {:.2f}，有倾向但不绝对，建议补敏感性说明".format(gap)

    return {
        "ranking": base,
        "top": base[0]["name"],
        "runner_up": base[1]["name"] if len(base) > 1 else None,
        "gap": round(gap, 2),
        "verdict": verdict,
        "note": note,
        "sensitivity_flips": flips,
        "sensitivity_step": step,
    }


def render(result: dict, criteria: list) -> str:
    head = "排名  落点                    加权分"
    lines = [head, "-" * len(head)]
    for r in result["ranking"]:
        lines.append("{:<5} {:<22} {:>6.2f}".format(r["rank"], r["name"], r["weighted"]))
    lines.append("")
    lines.append("权重：" + "，".join("{}={:.0%}".format(c.get("label", c["key"]), c["weight"]) for c in criteria))
    lines.append("判定：{} — {}".format(result["verdict"], result["note"]))
    if result["sensitivity_flips"]:
        lines.append("敏感性：以下调整会让第一名翻转")
        for f in result["sensitivity_flips"]:
            lines.append("  - {} {} -> 第一名为 {}".format(f["criterion"], f["adjust"], f["new_top"]))
    else:
        lines.append("敏感性：±{:.0%} 权重扰动下第一名稳定".format(result["sensitivity_step"]))
    return "\n".join(lines)


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    payload = DEMO if args[0] == "--demo" else json.loads(Path(args[0]).read_text(encoding="utf-8"))
    result = compute(payload)
    print(render(result, payload["criteria"]))
    if "--json" in args:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
