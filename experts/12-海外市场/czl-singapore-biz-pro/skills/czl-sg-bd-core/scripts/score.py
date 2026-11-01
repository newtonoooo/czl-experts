#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STRAIT 双层评分器 — Fit / Priority 分档、置信度、反证门禁。

用法:
    python score.py account.json
    python score.py account.json --explain
    python score.py account.json --json

输入 JSON 结构（字段名固定，缺少的维度视为 missing）:

{
  "account": "Example Pte Ltd",
  "fit": {
    "need_match":     {"level": "high", "evidence": "E1"},
    "scene_scale":    {"level": "mid"},
    "tech_adjacency": {"level": "low"},
    "budget_capacity":{"level": "mid"},
    "growth":         {"level": "high"}
  },
  "priority": {
    "signal_level":  {"value": 2},          # 1/2/3/4 级信号
    "accessibility": {"level": "high"},
    "decision_chain":{"level": "mid"},
    "cycle":         {"level": "high"},
    "vendor_lock":   {"level": "low"},
    "convert_12m":   {"level": "mid"}
  },
  "evidence_ids": ["E1", "E4"],
  "counter_evidence": [
    {"claim": "现有供应商已覆盖该场景", "answered": true},
    {"claim": "本地无预算主体", "answered": true},
    {"claim": "决策链跨集团", "answered": false}
  ]
}

输出只有档位，不输出小数分值；--explain 才显示内部加权值，并标注仅供内部比较。
"""

import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FIT_WEIGHTS = {
    "need_match": 0.30,
    "scene_scale": 0.20,
    "budget_capacity": 0.20,
    "tech_adjacency": 0.15,
    "growth": 0.15,
}

PRIORITY_WEIGHTS = {
    "signal_level": 0.25,
    "accessibility": 0.25,
    "vendor_lock": 0.15,
    "convert_12m": 0.15,
    "decision_chain": 0.10,
    "cycle": 0.10,
}

LEVEL_VALUE = {"high": 1.0, "mid": 0.6, "low": 0.3}
SIGNAL_VALUE = {1: 1.0, 2: 0.75, 3: 0.5, 4: 0.2}
SIGNAL_NAME = {1: "一级（直接采购信号）", 2: "二级（投资/项目信号）",
               3: "三级（组织能力信号）", 4: "四级（行业间接信号）"}

FIT_LABEL = {"need_match": "需求匹配", "scene_scale": "场景体量",
             "budget_capacity": "预算能力", "tech_adjacency": "技术邻接",
             "growth": "增长性"}
PRIORITY_LABEL = {"signal_level": "信号等级", "accessibility": "可进入性",
                  "vendor_lock": "供应商锁定", "convert_12m": "12个月转化",
                  "decision_chain": "决策链", "cycle": "周期"}


def band_of(value):
    if value >= 0.75:
        return "高"
    if value >= 0.50:
        return "中"
    return "低"


def read_dim(layer, key):
    """返回 (value, level_text, evidence, missing_reason)。"""
    node = layer.get(key)
    if not isinstance(node, dict):
        return None, None, None, "未提供"
    if key == "signal_level":
        raw = node.get("value", node.get("level"))
        try:
            n = int(raw)
        except (TypeError, ValueError):
            return None, None, node.get("evidence"), "信号等级非 1-4 整数"
        if n not in SIGNAL_VALUE:
            return None, None, node.get("evidence"), "信号等级超出 1-4"
        return SIGNAL_VALUE[n], SIGNAL_NAME[n], node.get("evidence"), None
    lv = node.get("level")
    if not isinstance(lv, str) or lv.lower() not in LEVEL_VALUE:
        return None, None, node.get("evidence"), "档位非 high/mid/low"
    return LEVEL_VALUE[lv.lower()], lv.lower(), node.get("evidence"), None


def score_layer(layer, weights, labels):
    present, missing, rows = [], [], []
    for key, w in weights.items():
        val, level, ev, why = read_dim(layer or {}, key)
        if val is None:
            missing.append((labels[key], why))
            rows.append((labels[key], "缺失", "-", 0.0))
        else:
            present.append((key, w, val))
            rows.append((labels[key], level, ev or "-", val))
    total_w = sum(w for _, w, _ in present)
    if total_w == 0:
        return None, rows, missing, 0.0
    value = sum(w * v for _, w, v in present) / total_w
    coverage = total_w / sum(weights.values())
    return value, rows, missing, coverage


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = argv[1]
    explain = "--explain" in argv
    as_json = "--json" in argv

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("错误: 找不到文件 %s" % path)
        return 2
    except json.JSONDecodeError as e:
        print("错误: JSON 解析失败 -> %s" % e)
        return 2

    account = data.get("account") or "（未命名账户）"
    fit_val, fit_rows, fit_missing, fit_cov = score_layer(data.get("fit"), FIT_WEIGHTS, FIT_LABEL)
    pri_val, pri_rows, pri_missing, pri_cov = score_layer(data.get("priority"), PRIORITY_WEIGHTS, PRIORITY_LABEL)

    fit_band = "信息不足" if fit_val is None or len(fit_missing) >= 3 else band_of(fit_val)
    pri_band = "信息不足" if pri_val is None or len(pri_missing) >= 3 else band_of(pri_val)

    evidence_ids = [e for e in (data.get("evidence_ids") or []) if isinstance(e, str) and e.strip()]
    counters = [c for c in (data.get("counter_evidence") or []) if isinstance(c, dict)]
    answered = [c for c in counters if c.get("answered") is True]

    present_dims = sum(1 for r in fit_rows + pri_rows if r[1] != "缺失")
    total_dims = len(fit_rows) + len(pri_rows)
    evidence_ratio = min(len(evidence_ids) / 4.0, 1.0)
    counter_ratio = min(len(answered) / 3.0, 1.0)
    confidence = 0.5 * (present_dims / total_dims) + 0.3 * evidence_ratio + 0.2 * counter_ratio

    blockers = []
    if len(evidence_ids) < 2:
        blockers.append("独立证据少于 2 条（当前 %d 条）" % len(evidence_ids))
    if len(counters) < 3:
        blockers.append("反证少于 3 条（当前 %d 条）" % len(counters))
    if len(counters) >= 3 and len(answered) < 3:
        blockers.append("反证未全部回应（已回应 %d/3）" % len(answered))
    if confidence < 0.5:
        blockers.append("置信度低于 0.5（%.2f）" % confidence)
    if pri_band == "信息不足":
        blockers.append("Priority 层信息不足，不得排序")

    gate = "PASS" if not blockers else "BLOCKED"

    if gate == "PASS" and pri_band == "高":
        accessibility = (data.get("priority", {}).get("accessibility") or {}).get("level", "")
        verdict = "A" if str(accessibility).lower() in ("high", "mid") else "B"
    elif gate == "PASS" and pri_band == "中":
        accessibility = (data.get("priority", {}).get("accessibility") or {}).get("level", "")
        verdict = "B" if str(accessibility).lower() == "high" else "C"
    elif pri_band == "低":
        verdict = "D"
    else:
        verdict = "资格待定（不得进前三）"

    if as_json:
        out = {
            "account": account,
            "fit_band": fit_band,
            "priority_band": pri_band,
            "confidence": round(confidence, 2),
            "gate": gate,
            "blockers": blockers,
            "verdict": verdict,
            "missing": {"fit": [m[0] for m in fit_missing], "priority": [m[0] for m in pri_missing]},
        }
        if explain:
            out["internal_fit"] = None if fit_val is None else round(fit_val, 3)
            out["internal_priority"] = None if pri_val is None else round(pri_val, 3)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if gate == "PASS" else 1

    print("账户: %s" % account)
    print("=" * 52)
    print("Fit（适配度）: %s" % fit_band)
    for label, level, ev, _ in fit_rows:
        print("  - %-6s %-6s 证据 %s" % (label, level, ev))
    print("Priority（开发优先级）: %s" % pri_band)
    for label, level, ev, _ in pri_rows:
        print("  - %-8s %-6s 证据 %s" % (label, level, ev))
    print("-" * 52)
    print("置信度: %.2f（维度覆盖 %.0f%%，独立证据 %d 条，反证已回应 %d/3）"
          % (confidence, 100 * present_dims / total_dims, len(evidence_ids), len(answered)))
    print("门禁: %s" % gate)
    for b in blockers:
        print("  ! %s" % b)
    print("分级: %s" % verdict)

    if fit_missing or pri_missing:
        print("-" * 52)
        print("缺失维度（需补证据，否则不得输出确定结论）:")
        for name, why in fit_missing + pri_missing:
            print("  - %s：%s" % (name, why))

    if explain:
        print("-" * 52)
        print("[内部参考] Fit 加权值 %.3f / Priority 加权值 %.3f — 仅用于内部比较，不得作为对外结论。"
              % (fit_val or 0.0, pri_val or 0.0))
    return 0 if gate == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
