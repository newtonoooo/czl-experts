#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""评审模拟与追分排序。

它不做两件事：不猜你的得分率，不预测名次。
它只做三件事：把逐项判断折成总分区间、找出最不确定的三项、按「每小时追回几分」排序。

输入 JSON 格式（items 里的 rate 必须由人填，脚本不代填）：

{
  "project": "蜀通前置仓 WMS 升级",
  "bid_total": 100,
  "reference_score": 84,          // 可选：历史入围线或已知对手分，不填则不做名次判断
  "items": [
    {"item": "技术方案", "max_score": 20, "rate": 0.72, "effort_hours": 12,
     "pess": 0.55, "opt": 0.85},   // pess/opt 可省略，省略时按 rate±0.12 处理并标注
    ...
  ]
}

用法：
    python score_sim.py assess.json
    python score_sim.py assess.json --md 评审模拟.md
"""

import argparse
import json
import sys
from pathlib import Path

SPREAD = 0.12  # 省略 pess/opt 时的默认振幅，报告中会明确标注


def load(p):
    path = Path(p)
    if not path.exists():
        raise SystemExit(f"文件不存在: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"JSON 解析失败（第 {e.lineno} 行）：{e.msg}")


def normalize(doc):
    items = doc.get("items")
    if not isinstance(items, list) or not items:
        raise SystemExit("缺少 items 数组")
    missing = [i.get("item", f"#{n}") for n, i in enumerate(items, 1) if "rate" not in i]
    if missing:
        raise SystemExit(
            "以下评分项没有填 rate（预计得分率 0-1），脚本不替你猜：\n  - "
            + "\n  - ".join(missing)
            + "\n请先逐项判断：这一项按现在的稿子，评委会给多少比例的分。"
        )
    out = []
    for i in items:
        rate = float(i["rate"])
        if not 0 <= rate <= 1.5:
            raise SystemExit(f"rate 超出合理范围：{i.get('item')} = {rate}")
        maxs = float(i.get("max_score", 0))
        if maxs <= 0:
            raise SystemExit(f"max_score 必须大于 0：{i.get('item')}")
        assumed = "pess" not in i or "opt" not in i
        pess = float(i.get("pess", max(0.0, rate - SPREAD)))
        opt = float(i.get("opt", min(1.0, rate + SPREAD)))
        out.append({
            "item": i.get("item", "未命名"),
            "max_score": maxs,
            "rate": rate,
            "pess": pess,
            "mid": rate,
            "opt": opt,
            "effort_hours": float(i.get("effort_hours", 0) or 0),
            "assumed_spread": assumed,
            "is_price": any(k in str(i.get("item", "")) for k in ("报价", "价格", "费率")),
        })
    return out


def simulate(items, bid_total, reference):
    for it in items:
        it["pess_score"] = it["max_score"] * it["pess"]
        it["mid_score"] = it["max_score"] * it["mid"]
        it["opt_score"] = it["max_score"] * it["opt"]
        # 追分空间：从中性到乐观能拿回多少分
        it["upside"] = it["opt_score"] - it["mid_score"]
        it["leverage"] = (it["upside"] / it["effort_hours"]) if it["effort_hours"] > 0 else 0.0

    total = {k: sum(i[f"{k}_score"] for i in items) for k in ("pess", "mid", "opt")}
    maxsum = sum(i["max_score"] for i in items)

    # 不确定性：悲观与乐观差距最大的三项
    for it in items:
        it["uncertainty"] = it["opt_score"] - it["pess_score"]
    uncertain = sorted(items, key=lambda x: -x["uncertainty"])[:3]

    # 追分排序：排掉报价类（那是决策项，不是写作项）与没有工时的项
    lever = sorted([i for i in items if i["effort_hours"] > 0 and not i["is_price"]],
                   key=lambda x: -x["leverage"])

    gap = None
    if reference:
        gap = float(reference) - total["mid"]
    return total, maxsum, uncertain, lever, gap


def to_md(doc, items, total, maxsum, uncertain, lever, gap, reference):
    name = doc.get("project") or "本次投标"
    lines = [f"# 评审模拟：{name}", ""]
    lines.append(f"**中性预估 {total['mid']:.1f} / {maxsum:g} 分**"
                 f"（悲观 {total['pess']:.1f}，乐观 {total['opt']:.1f}）")
    lines.append("")
    if gap is not None:
        verdict = ("中性预估已达参考线，重点转为守住与少扣分" if gap <= 0
                   else f"中性预估距参考线 {reference:g} 还差 **{gap:.1f} 分**")
        lines.append(f"- 参考线 {reference:g}：{verdict}")
        short = total["opt"] - total["mid"]
        if gap > 0:
            lines.append(f"- 全部追到乐观值可补 {short:.1f} 分"
                         + ("，够线但要每一项都到位" if short >= gap else
                            "，**即使全部拉满仍不够线**：需要动报价策略或换打法，不是改文字能解决的"))
    lines.append("- 参考线由你提供，脚本不做名次预测。")
    lines += ["", "## 逐项预估", "",
              "| 评分项 | 满分 | 悲观 | 中性 | 乐观 | 追分空间 | 工时 | 每小时追分 |",
              "|---|---|---|---|---|---|---|---|"]
    for it in items:
        lines.append(
            f"| {it['item']} | {it['max_score']:g} | {it['pess_score']:.1f} | "
            f"{it['mid_score']:.1f} | {it['opt_score']:.1f} | {it['upside']:.1f} | "
            f"{it['effort_hours']:g}h | {it['leverage']:.2f} |")
    lines.append("")
    if any(i["assumed_spread"] for i in items):
        lines.append(f"> 未填 pess/opt 的项按 rate±{SPREAD} 处理，属假设值，报告已标注。")

    lines += ["", "## 最不确定的三项（先把它们想清楚）", ""]
    for it in uncertain:
        lines.append(f"- **{it['item']}**：区间宽 {it['uncertainty']:.1f} 分"
                     f"（{it['pess_score']:.1f}–{it['opt_score']:.1f}）。"
                     "区间越宽，说明你的判断越没底，通常意味着评分口径没读透。")

    price_items = [i for i in items if i["is_price"]]
    if price_items:
        lines += ["", "## 不参与追分排序的项", ""]
        for it in price_items:
            lines.append(f"- **{it['item']}**（{it['max_score']:g} 分）：价格分由报价决策决定，"
                         "改文字追不回来。要动就动报价策略与配置分档，见报价叙事环节。")

    lines += ["", "## 追分优先级（每小时追回几分）", ""]
    if not lever:
        lines.append("没有填 effort_hours，无法排序。补上每项预计投入工时即可。")
    else:
        lines += ["| 顺序 | 评分项 | 可追分 | 工时 | 每小时 | 动作 |", "|---|---|---|---|---|---|"]
        for n, it in enumerate(lever[:8], 1):
            act = ("先补证据再润色" if it["upside"] >= 3 else
                   "补一段针对性内容即可" if it["upside"] >= 1.5 else
                   "性价比低，最后再说")
            lines.append(f"| {n} | {it['item']} | {it['upside']:.1f} | "
                         f"{it['effort_hours']:g}h | {it['leverage']:.2f} | {act} |")
        lines += ["", f"> 建议先做前 3 项：合计可追 "
                      f"{sum(i['upside'] for i in lever[:3]):.1f} 分，"
                      f"占全部可追分的 "
                      f"{(sum(i['upside'] for i in lever[:3]) / total['opt'] * 100) if total['opt'] else 0:.0f}%。"]

    lines += ["", "## 这份模拟不能证明什么", "",
              "- 不能证明你能中标。得分率是你的判断，不是评委会的判断。",
              "- 不能替代读招标文件。评分细则里没写进 items 的口径，这里都算不到。",
              "- 区间窄不代表判断准。三项以内的小样本，误差比区间大。"]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="评审模拟与追分排序")
    ap.add_argument("assess", help="assess.json")
    ap.add_argument("--md", default=None, help="Markdown 输出路径")
    ap.add_argument("--json", default=None, help="JSON 输出路径")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    doc = load(args.assess)
    items = normalize(doc)
    total, maxsum, uncertain, lever, gap = simulate(
        items, doc.get("bid_total"), doc.get("reference_score"))
    md = to_md(doc, items, total, maxsum, uncertain, lever, gap, doc.get("reference_score"))
    print(md)

    base = Path(args.assess).parent
    if args.md:
        Path(args.md).write_text(md, encoding="utf-8")
    if args.json:
        payload = {"total": total, "max_score": maxsum, "items": items,
                   "gap_to_reference": gap}
        Path(args.json).write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
    if not args.md and not args.json:
        (base / "评审模拟.md").write_text(md, encoding="utf-8")
        print(f"\n已写出：{base/'评审模拟.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
