#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""报价价值测算：先把「不做的代价」算出来，再让价格出现。

脚本只做算术，不做假设。所有金额与口径都必须由你填，填不出的项会显式标为缺口，
不会被补成漂亮数字。默认不做折现，报告里会写明这一点。

输入 JSON：
{
  "client": "蜀通",
  "price": 480000,
  "period_months": 6,
  "annual_benefit": [
    {"item": "错发赔付下降", "basis": "去年 312 次 × 1800 元 × 降 70%", "amount": 393120}
  ],
  "cost_of_inaction": {"item": "维持现状的年损失", "basis": "去年同期口径", "amount": 560000},
  "options": [
    {"name": "够用版", "price": 380000, "scope_out": ["夜班排程优化"]},
    {"name": "推荐版", "price": 480000, "scope_out": []}
  ],
  "max_discount": 0.12
}

用法：
    python roi_model.py price.json
    python roi_model.py price.json --md 报价叙事.md
"""

import argparse
import json
import sys
from pathlib import Path


def load(p):
    path = Path(p)
    if not path.exists():
        raise SystemExit(f"文件不存在: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"JSON 解析失败（第 {e.lineno} 行）：{e.msg}")


def money(x):
    return f"{x:,.0f}"


def compute(doc):
    price = float(doc["price"])
    benefits = doc.get("annual_benefit") or []
    annual = sum(float(b.get("amount", 0)) for b in benefits)
    gaps = []
    for b in benefits:
        if not b.get("basis"):
            gaps.append(f"{b.get('item', '未命名')}：没有口径（basis），金额无法被追问")
        if not b.get("amount"):
            gaps.append(f"{b.get('item', '未命名')}：金额为 0")

    months = float(doc.get("period_months") or 0)
    payback = (price / (annual / 12)) if annual > 0 else None
    three_year_net = annual * 3 - price
    roi = (three_year_net / price * 100) if price else None
    ratio = (price / annual) if annual > 0 else None

    coi = doc.get("cost_of_inaction") or {}
    coi_amt = float(coi.get("amount", 0) or 0)
    if coi and not coi.get("basis"):
        gaps.append("不作为代价：没有口径（basis），不能当作论据使用")

    disc = float(doc.get("max_discount", 0.12))
    floor = price * (1 - disc)

    options = []
    for o in doc.get("options") or []:
        p = float(o.get("price", 0) or 0)
        options.append({
            "name": o.get("name", "未命名"),
            "price": p,
            "delta_vs_base": p - price,
            "scope_out": o.get("scope_out") or [],
            "note": o.get("note", ""),
        })

    return {
        "price": price, "annual_benefit": annual, "payback_months": payback,
        "three_year_net": three_year_net, "roi_percent": roi,
        "price_to_benefit": ratio, "cost_of_inaction": coi_amt,
        "floor_price": floor, "gaps": gaps, "options": options,
        "months": months,
    }


def to_md(doc, r):
    client = doc.get("client") or "客户"
    lines = [f"# 报价叙事：{client}", ""]

    lines.append("## 一、不做的代价（先算这个）")
    lines.append("")
    if r["cost_of_inaction"] > 0:
        coi = doc["cost_of_inaction"]
        lines.append(f"{client} 维持现状，一年要付 **{money(r['cost_of_inaction'])} 元** 的代价。")
        lines.append("")
        if coi.get("basis"):
            lines.append(f"口径：{coi['basis']}。")
        else:
            lines.append("口径：**缺口**。没有口径的数字不要写进标书，评委会问出处。")
    else:
        lines.append("未提供现状代价。**这一节不能空着**：哪怕只写一条可核的成本项，"
                     "也比只讲收益有说服力。")
    lines.append("")

    lines.append("## 二、收益与回本")
    lines.append("")
    if r["annual_benefit"] > 0:
        lines.append(f"年化可量化收益合计 **{money(r['annual_benefit'])} 元**。")
        lines.append("")
        lines.append("| 收益项 | 口径 | 年金额 |")
        lines.append("|---|---|---|")
        for b in doc.get("annual_benefit") or []:
            lines.append(f"| {b.get('item', '未命名')} | {b.get('basis') or '**缺口**'} | "
                         f"{money(float(b.get('amount', 0)))} |")
        lines.append("")
        lines.append(f"- 投入 {money(r['price'])} 元，回本期 **{r['payback_months']:.1f} 个月**")
        if r["roi_percent"] is not None:
            lines.append(f"- 三年净收益（未折现）**{money(r['three_year_net'])} 元**，"
                         f"投入产出比 {r['roi_percent']:.0f}%")
        if r["price_to_benefit"] is not None:
            lines.append(f"- 报价相当于年收益的 **{r['price_to_benefit']:.2f} 倍**"
                         + ("（大于 1 时，必须配不做的代价，否则客户只会看到贵）"
                            if r["price_to_benefit"] > 1 else ""))
    else:
        lines.append("未提供年化收益。此情形下**不要编 ROI**，把报价页改成三件事："
                     "范围写清、口径写清、验收写清。")
    lines.append("")
    lines.append("> 全表未折现，忽略资金时间价值与实施风险折价。"
                 "这是内部判断工具，不直接贴进标书；标书里只出现单条口径清楚的数字。")
    lines.append("")

    lines.append("## 三、三档配置")
    lines.append("")
    if r["options"]:
        lines.append("| 档位 | 价格 | 与推荐版差 | 这一档少了什么 |")
        lines.append("|---|---|---|---|")
        for o in r["options"]:
            out = "、".join(o["scope_out"]) or "—"
            lines.append(f"| {o['name']} | {money(o['price'])} | "
                         f"{'+' if o['delta_vs_base'] >= 0 else ''}{money(o['delta_vs_base'])} | {out} |")
        lines.append("")
        lines.append("三档的作用不是让客户砍价，是让客户在「少要点」和「多给点」之间选，"
                     "而不是在「买」和「不买」之间选。")
    else:
        lines.append("未提供档位。单档报价在预算紧张的项目里最容易被一刀切。")
    lines.append("")

    lines.append("## 四、让价边界")
    lines.append("")
    lines.append(f"- 按 {int(float(doc.get('max_discount', 0.12)) * 100)}% 让价上限测算，"
                 f"地板价约 **{money(r['floor_price'])} 元**（这个比例由你定，脚本不替你定）")
    lines.append("- 可让：交付节奏、培训场次、巡检频次、响应时段（这些让的是排期，不是核心能力）")
    lines.append("- 不可让：核心交付范围、验收口径、数据归属、责任边界")
    lines.append("- 让价必须换东西：每让 3% 换一条范围收缩或一个付款节点前置，"
                 "否则下一次还会被继续压")
    lines.append("")

    if r["gaps"]:
        lines.append("## 五、缺口清单（补不齐就不要用）")
        lines.append("")
        for g in r["gaps"]:
            lines.append(f"- {g}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="报价价值测算")
    ap.add_argument("input", help="price.json")
    ap.add_argument("--md", default=None, help="Markdown 输出路径")
    ap.add_argument("--json", default=None, help="JSON 输出路径")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    doc = load(args.input)
    r = compute(doc)
    md = to_md(doc, r)
    print(md)

    base = Path(args.input).parent
    if args.md:
        Path(args.md).write_text(md, encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.md and not args.json:
        (base / "报价叙事.md").write_text(md, encoding="utf-8")
        print(f"\n已写出：{base/'报价叙事.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
