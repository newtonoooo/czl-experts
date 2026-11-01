#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""五维风险打分器（czl-uae-pa-toolkit）

按 references/05-risk-scoring-model.md 的模型计算阿联酋公共事务风险分。

用法:
    python risk_score.py --rule 3 --approval 4 --timing 2 --reputation 5 --enforcement 4
    python risk_score.py --rule 3 --approval 4 --timing 2 --reputation 5 --enforcement 4 --preset marketing
    python risk_score.py --rule "3-4" --approval 4 --timing 2 --reputation 5 --enforcement 4   # 区间分
    python risk_score.py --json '{"rule":3,"approval":4,"timing":2,"reputation":5,"enforcement":4}'

输出: 标准输出为人类可读报告; 加 --format json 输出机器可读结果。
退出码: 0 正常; 2 参数错误。
"""

import argparse
import json
import sys

DIMENSIONS = [
    ("rule", "规则确定性"),
    ("approval", "审批可控性"),
    ("timing", "时间不可控性"),
    ("reputation", "声誉外溢性"),
    ("enforcement", "执法严厉度"),
]

PRESETS = {
    "default":       {"rule": .25, "approval": .25, "timing": .15, "reputation": .20, "enforcement": .15},
    "gov-contract":  {"rule": .25, "approval": .30, "timing": .20, "reputation": .15, "enforcement": .10},
    "manufacturing": {"rule": .30, "approval": .25, "timing": .20, "reputation": .10, "enforcement": .15},
    "marketing":     {"rule": .20, "approval": .15, "timing": .10, "reputation": .35, "enforcement": .20},
    "finance":       {"rule": .30, "approval": .30, "timing": .10, "reputation": .15, "enforcement": .15},
    "cross-border":  {"rule": .30, "approval": .20, "timing": .20, "reputation": .15, "enforcement": .15},
}

LEVELS = [
    (0, 24, "低", "常规推进，保留文件"),
    (25, 44, "中", "推进 + 关键节点复核"),
    (45, 64, "中高", "先完成缓释动作再推进；需内部合规签字"),
    (65, 79, "高", "需本地持牌律师/顾问意见；设置停止条件"),
    (80, 100, "极高", "不建议推进；如必须推进须董事会级决策"),
]


def parse_score(raw):
    """接受 '3' 或 '3-4' 形式，返回 (low, high, is_range)。"""
    raw = str(raw).strip()
    if "-" in raw:
        lo, _, hi = raw.partition("-")
        lo, hi = float(lo), float(hi)
    else:
        lo = hi = float(raw)
    for v in (lo, hi):
        if v < 0 or v > 5:
            raise ValueError("维度分值必须在 0-5 之间，收到: %s" % raw)
    if lo > hi:
        lo, hi = hi, lo
    return lo, hi, lo != hi


def level_of(score):
    for lo, hi, name, action in LEVELS:
        if lo <= score <= hi:
            return name, action
    return "极高", LEVELS[-1][3]


def compute(scores, weights):
    total_w = sum(weights.values())
    if abs(total_w - 1.0) > 1e-6:
        # 归一化，避免用户传错权重导致分数失真
        weights = {k: v / total_w for k, v in weights.items()}
    low = sum(scores[k][0] * weights[k] for k, _ in DIMENSIONS) * 20
    high = sum(scores[k][1] * weights[k] for k, _ in DIMENSIONS) * 20
    return round(low, 1), round(high, 1)


def main(argv=None):
    ap = argparse.ArgumentParser(description="阿联酋公共事务五维风险打分器")
    for key, label in DIMENSIONS:
        ap.add_argument("--" + key, required=False, help="%s 0-5（可写区间如 3-4）" % label)
    ap.add_argument("--json", dest="json_in", help="以 JSON 传入五个维度分值")
    ap.add_argument("--preset", default="default", choices=sorted(PRESETS), help="行业权重预设")
    ap.add_argument("--weights", help="自定义权重，如 rule=.3,approval=.3,timing=.1,reputation=.15,enforcement=.15")
    ap.add_argument("--format", default="text", choices=["text", "json"], help="输出格式")
    args = ap.parse_args(argv)

    raw = {}
    if args.json_in:
        try:
            raw.update(json.loads(args.json_in))
        except json.JSONDecodeError as e:
            print("JSON 解析失败: %s" % e, file=sys.stderr)
            return 2
    for key, _ in DIMENSIONS:
        val = getattr(args, key)
        if val is not None:
            raw[key] = val

    missing = [k for k, _ in DIMENSIONS if k not in raw]
    if missing:
        print("缺少维度分值: %s" % ", ".join(missing), file=sys.stderr)
        return 2

    try:
        scores = {k: parse_score(raw[k]) for k, _ in DIMENSIONS}
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    weights = dict(PRESETS[args.preset])
    if args.weights:
        weights = {}
        for part in args.weights.split(","):
            k, _, v = part.partition("=")
            weights[k.strip()] = float(v)

    low, high = compute(scores, weights)
    level_low, action = level_of(low)
    level_high, _ = level_of(high)
    level = level_low if level_low == level_high else "%s~%s" % (level_low, level_high)

    # 主导维度：加权贡献最大者
    contrib = {k: scores[k][1] * weights.get(k, 0) * 20 for k, _ in DIMENSIONS}
    dominant = max(contrib, key=contrib.get)
    dominant_label = dict(DIMENSIONS)[dominant]
    is_range = any(v[2] for v in scores.values())

    result = {
        "score_low": low,
        "score_high": high,
        "level": level,
        "action": action,
        "dominant_dimension": dominant,
        "dominant_label": dominant_label,
        "preset": args.preset,
        "weights": {k: round(v, 3) for k, v in weights.items()},
        "confidence": "low" if is_range else "normal",
        "need_stop_conditions": high >= 65,
        "dimensions": {k: {"label": dict(DIMENSIONS)[k], "low": scores[k][0], "high": scores[k][1]} for k, _ in DIMENSIONS},
    }

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print("=" * 46)
    print("阿联酋公共事务风险评分")
    print("=" * 46)
    for key, label in DIMENSIONS:
        lo, hi, rng = scores[key]
        shown = ("%g-%g" % (lo, hi)) if rng else ("%g" % lo)
        print("  %s（%s）  权重 %.0f%%  分值 %s" % (label, key, weights[key] * 100, shown))
    print("-" * 46)
    print("  总分: %.1f%s" % (low, "" if low == high else " ~ %.1f" % high))
    print("  等级: %s" % level)
    print("  处置: %s" % action)
    print("  主导维度: %s (%s)" % (dominant_label, dominant))
    if is_range:
        print("  置信度: 低（存在区间分，需补依据）")
    if result["need_stop_conditions"]:
        print("  ⚠ 总分达到高风险阈值，交付物必须附【停止条件】与【升级路径】")
    print("=" * 46)
    return 0


if __name__ == "__main__":
    sys.exit(main())
