#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the value case before any price is mentioned.

Usage:
    python value_case.py case.json [--md out.md]

Input JSON:
{
  "project": "某某医院机房改造",
  "years": 3,
  "annual_loss": 1200000,
  "investment": 800000,
  "annual_cost": 150000,
  "price_tiers": [
    {"name": "保底", "price": 700000, "scope": "满足全部硬性要求"},
    {"name": "推荐", "price": 860000, "scope": "保底 + 双活 + 两次演练"},
    {"name": "进取", "price": 1050000, "scope": "推荐 + 驻场半年 + 培训认证"}
  ]
}

Computes: cost of inaction, TCO, net benefit, ROI, payback (years).
Checks: at least 2 tiers, prices ascending, payback <= years, recommended tier is not the cheapest.
Exit: 0 ok, 2 invalid input.
"""
import json
import sys


def out(text=""):
    sys.stdout.write(text + "\n")


def fail(msg):
    out("ERROR: " + msg)
    sys.exit(2)


def num(data, key, required=True):
    v = data.get(key)
    if v is None:
        if required:
            fail("缺少字段 %s" % key)
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        fail("字段 %s 必须是数字" % key)


def money(x):
    if abs(x) >= 10000:
        return "%.1f 万" % (x / 10000.0)
    return "%.0f 元" % x


def main():
    argv = sys.argv[1:]
    if not argv:
        out(__doc__)
        sys.exit(2)
    try:
        data = json.load(open(argv[0], "r", encoding="utf-8"))
    except FileNotFoundError:
        fail("找不到输入文件: %s" % argv[0])
    except json.JSONDecodeError as e:
        fail("JSON 解析失败: %s" % e)

    years = num(data, "years")
    annual_loss = num(data, "annual_loss")
    investment = num(data, "investment")
    annual_cost = num(data, "annual_cost", required=False)
    tiers = data.get("price_tiers") or []
    if years <= 0:
        fail("years 必须大于 0")
    if annual_loss <= 0:
        fail("annual_loss 必须大于 0，否则没有价值可讲")

    inaction = annual_loss * years
    tco = investment + annual_cost * years
    net = inaction - tco
    roi = (net / tco * 100) if tco else 0.0
    yearly_gain = annual_loss - annual_cost
    payback = (investment / yearly_gain) if yearly_gain > 0 else None

    problems = []
    if len(tiers) < 2:
        problems.append("报价档位少于 2 档：客户只能比数字，不能比配置")
    prices = []
    for t in tiers:
        try:
            prices.append(float(t.get("price")))
        except (TypeError, ValueError):
            problems.append("档位「%s」价格不是数字" % t.get("name", "?"))
    if prices and prices != sorted(prices):
        problems.append("档位价格未按从低到高排列")
    if payback is None:
        problems.append("年度收益不为正，回本周期无法计算：先修 value case，再谈价")
    elif payback > years:
        problems.append("回本周期 %.1f 年 > 测算期 %.0f 年，客户会问「凭什么投」" % (payback, years))
    names = [t.get("name", "") for t in tiers]
    if "推荐" in names and prices:
        idx = names.index("推荐")
        if idx == 0:
            problems.append("推荐档是最低价：等于告诉客户我们没信心")

    L = ["# 价格叙事底稿", ""]
    L.append("项目：%s" % data.get("project", "（未填）"))
    L.append("")
    L.append("## 一、不做的代价（%d 年）" % years)
    L.append("")
    L.append("| 项 | 金额 |")
    L.append("|---|---|")
    L.append("| 年损失 | %s |" % money(annual_loss))
    L.append("| %d 年累计 | **%s** |" % (years, money(inaction)))
    L.append("")
    L.append("## 二、总拥有成本 TCO（%d 年）" % years)
    L.append("")
    L.append("| 项 | 金额 |")
    L.append("|---|---|")
    L.append("| 一次性投入 | %s |" % money(investment))
    L.append("| 年运营成本 ×%d | %s |" % (years, money(annual_cost * years)))
    L.append("| 合计 | **%s** |" % money(tco))
    L.append("")
    L.append("## 三、值不值")
    L.append("")
    L.append("- 净收益：%s" % money(net))
    L.append("- 投资回报率：%.0f%%" % roi)
    L.append("- 回本周期：%s" % ("%.1f 年" % payback if payback else "无法计算"))
    L.append("")
    if tiers:
        L.append("## 四、三档报价（先讲配置差，再讲价差）")
        L.append("")
        L.append("| 档位 | 价格 | 含什么 | 比上一档多什么 |")
        L.append("|---|---|---|---|")
        prev = None
        for t in tiers:
            p = t.get("price")
            diff = "-" if prev is None else "多 %s" % money(float(p) - prev)
            L.append("| %s | %s | %s | %s |" % (
                t.get("name", "-"), money(float(p)) if isinstance(p, (int, float)) else "-",
                t.get("scope", "-"), diff))
            if isinstance(p, (int, float)):
                prev = float(p)
        L.append("")
    L.append("## 五、检查结果")
    L.append("")
    if problems:
        for p in problems:
            L.append("- ⚠️ " + p)
    else:
        L.append("- 通过：档位、排序、回本周期均无形式问题。")
    L.append("")
    L.append("## 六、讲述顺序（照这个顺序念给客户听）")
    L.append("")
    L.append("1. 先问一句：这个问题现在每年花掉你多少钱？（把 annual_loss 的算法讲给客户，让他自己改数）")
    L.append("2. 再算 %d 年累计：%s。" % (years, money(inaction)))
    L.append("3. 然后说投入：%s，回本 %s。" % (money(tco), ("%.1f 年" % payback) if payback else "无法估算"))
    L.append("4. 最后才给三档，并说明每档少什么。")
    L.append("")
    L.append("> 所有金额口径由客户确认后才可写进标书。自行估算的损失必须标 E4。")

    report = "\n".join(L)
    out(report)
    if "--md" in argv:
        i = argv.index("--md")
        if i + 1 < len(argv):
            open(argv[i + 1], "w", encoding="utf-8").write(report + "\n")
            out("\n已写入: %s" % argv[i + 1])


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
