#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""essay_score.py — 写作维度分折算、档次建议与一致性校验

用法：
    python essay_score.py --type app --content 4 --language 4 --structure 3 --cohesion 3
    python essay_score.py --type continuation --content 4 --language 3 --structure 3 --cohesion 3 --json

维度均按 0–5 分档打分（可给 0.5 步长）。
应用文满分 15：内容 6 / 语言 5 / 结构 2 / 得体 2
读后续写满分 25：情节 9 / 语言 8 / 连贯 4 / 细节收束 4

退出码：0 正常；2 参数错误。
"""
import argparse
import json
import sys

PROFILES = {
    "app": {
        "label": "应用文",
        "full": 15.0,
        "weights": {"content": 6.0, "language": 5.0, "structure": 2.0, "cohesion": 2.0},
        "names": {"content": "内容要点", "language": "语言准确", "structure": "篇章连贯", "cohesion": "语用得体"},
        "bands": [
            (13.0, 15.0, "第五档", "要点全覆盖，语言准确，格式得体"),
            (10.0, 12.99, "第四档", "要点基本覆盖，少量语言错误"),
            (7.0, 9.99, "第三档", "缺要点或错误较多，衔接生硬"),
            (4.0, 6.99, "第二档", "要点缺失明显，影响理解"),
            (0.0, 3.99, "第一档", "未传达要点，难以成篇"),
        ],
    },
    "continuation": {
        "label": "读后续写",
        "full": 25.0,
        "weights": {"content": 9.0, "language": 8.0, "structure": 4.0, "cohesion": 4.0},
        "names": {"content": "情节逻辑", "language": "语言表达", "structure": "衔接连贯", "cohesion": "细节收束"},
        "bands": [
            (21.0, 25.0, "第五档", "与前文高度协同，语言丰富，收束自然"),
            (16.0, 20.99, "第四档", "情节合理，语言基本准确"),
            (11.0, 15.99, "第三档", "情节能接上但有矛盾，句式单一"),
            (6.0, 10.99, "第二档", "情节脱节或套模板，错误多"),
            (0.0, 5.99, "第一档", "未形成完整情节"),
        ],
    },
}

DIM_KEYS = ["content", "language", "structure", "cohesion"]


def band_of(score, bands):
    for low, high, name, desc in bands:
        if low <= score <= high:
            return name, desc
    return bands[-1][2], bands[-1][3]


def evaluate(kind, dims):
    prof = PROFILES[kind]
    full = prof["full"]
    raw = 0.0
    detail = []
    for k in DIM_KEYS:
        v = float(dims[k])
        w = prof["weights"][k]
        got = v / 5.0 * w
        raw += got
        detail.append({"dim": k, "name": prof["names"][k], "level": v, "weight": w, "score": round(got, 2)})

    raw = round(raw, 2)
    rounded = round(raw * 2) / 2.0          # 按 0.5 分取整，贴近人工阅卷习惯
    rounded = min(full, max(0.0, rounded))
    name, desc = band_of(rounded, prof["bands"])

    flags = []
    c = float(dims["content"])
    l = float(dims["language"])
    vals = [float(dims[k]) for k in DIM_KEYS]
    if c <= 1 and rounded >= prof["bands"][3][0]:
        flags.append("内容维度极低但总分进入高档，需复核定档（内容通常决定档次上限）")
    if l <= 1 and rounded >= prof["bands"][3][0]:
        flags.append("语言维度极低但总分进入高档，需复核语言错误数")
    if max(vals) - min(vals) >= 4:
        flags.append("四个维度差距达到 4 档以上，建议再读一遍全文确认")
    if all(v == 5 for v in vals):
        flags.append("四维满分，需确认是否达到满分标准（满分通常要求无影响理解的错误且有亮点）")
    if kind == "continuation" and c <= 2:
        flags.append("情节档偏低：优先检查伏笔是否回收、人物是否与前文一致")

    return {
        "type": prof["label"],
        "dims": detail,
        "raw": raw,
        "suggested": rounded,
        "full": full,
        "band": name,
        "band_desc": desc,
        "flags": flags,
    }


def render(res):
    lines = [f"# {res['type']} 评分建议", ""]
    lines += ["| 维度 | 档位（0–5） | 权重 | 折算分 |", "|---|---|---|---|"]
    for d in res["dims"]:
        lines.append(f"| {d['name']} | {d['level']:g} | {d['weight']:g} | {d['score']:.2f} |")
    lines += ["", f"- 加权原始分：**{res['raw']:.2f} / {res['full']:g}**",
              f"- 建议得分（0.5 取整）：**{res['suggested']:g} / {res['full']:g}**",
              f"- 建议档次：**{res['band']}** — {res['band_desc']}", ""]
    if res["flags"]:
        lines += ["## 需复核", ""]
        for f in res["flags"]:
            lines.append(f"- ⚠️ {f}")
        lines.append("")
    else:
        lines += ["## 需复核", "", "- ✅ 未触发一致性告警。", ""]
    lines += ["> 最终分数与等第由教师确认，本结果仅为建议值。", ""]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="写作四维评分折算与档次建议")
    ap.add_argument("--type", required=True, choices=["app", "continuation"])
    for k in DIM_KEYS:
        ap.add_argument(f"--{k}", type=float, required=True, help="0–5 分档")
    ap.add_argument("--json", dest="json_out", help="输出 JSON 路径")
    args = ap.parse_args(argv)

    dims = {}
    for k in DIM_KEYS:
        v = getattr(args, k)
        if v < 0 or v > 5:
            print(f"[ERROR] --{k} 必须在 0–5 之间，收到 {v}", file=sys.stderr)
            return 2
        dims[k] = v

    res = evaluate(args.type, dims)
    print(render(res))
    if args.json_out:
        from pathlib import Path
        Path(args.json_out).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] JSON：{args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
