#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""机会雷达：政府数字化投标机会打分。

子命令：
    score    计算加权总分、档位、短板与下一步动作
    template 输出输入模板
    check    只做输入完整性检查

设计原则：
1. 资格不满足直接否决，不参与加权（避免高分掩盖废标）。
2. 权重固定且有据可查，不允许调用方随意改（要改就改这份文件并写进变更记录）。
3. 不给"中标概率"，没有历史数据支撑的概率是编的。
"""

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 维度权重：合计 1.00
WEIGHTS = {
    "funding": 0.18,
    "competition": 0.18,
    "relationship": 0.14,
    "case_match": 0.14,
    "policy_fit": 0.12,
    "differentiation": 0.12,
    "delivery": 0.12,
}

LABELS = {
    "funding": "资金与立项真实度",
    "competition": "竞争位势",
    "relationship": "客户关系基础",
    "case_match": "案例与业绩匹配",
    "policy_fit": "政策契合度",
    "differentiation": "方案差异化空间",
    "delivery": "交付资源可行性",
}

# 每条短板对应的补齐动作（可执行、有产出物）
ACTIONS = {
    "funding": "去要预算文号或年度采购意向公告；拿不到就按'待立项'处理，只做技术交流不做方案投入。",
    "competition": "列出对手已公开的同类案例与服务团队，找出他们没覆盖的业务处室，把交流资源压到那一条线上。",
    "relationship": "争取一次需求沟通或现场踏勘，至少约到信息中心技术负责人；约不到就别指望标书阶段翻盘。",
    "case_match": "找可核验的近似案例（同业务类型不同规模也可），补齐合同与验收报告；不够就评估联合体。",
    "policy_fit": "翻本级政府年度工作要点与部门专项规划，把项目挂到具体条目上；挂不上说明预算优先级低。",
    "differentiation": "找一件对手不愿做的脏活（历史数据清洗、多系统对接、驻场运维），把它做成方案主线。",
    "delivery": "先锁定交付负责人和本地驻场人选，再谈投标；人不到位，中标就是给自己挖坑。",
}

TIERS = ((70, "全力投入"), (55, "选择性参与"), (0, "建议放弃"))


def err(msg):
    print(f"[错误] {msg}", file=sys.stderr)


def load(path):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"找不到输入文件：{p}")
    return json.loads(p.read_text(encoding="utf-8"))


def validate(data, allow_missing=False):
    """返回 (gate, scores, missing, problems)。"""
    problems = []
    missing = []

    gate_raw = str(data.get("qualification_ok", "unknown")).lower()
    if gate_raw in ("true", "1", "yes", "是"):
        gate = "pass"
    elif gate_raw in ("false", "0", "no", "否"):
        gate = "fail"
    else:
        gate = "unknown"
        missing.append("qualification_ok（资格可满足性）")

    raw = data.get("scores") or {}
    scores = {}
    for key in WEIGHTS:
        val = raw.get(key)
        if isinstance(val, (int, float)) and 1 <= float(val) <= 5:
            scores[key] = float(val)
        elif val is None:
            missing.append(LABELS[key])
        else:
            problems.append(f"{LABELS[key]} 的分值 {val!r} 不在 1–5 区间，已忽略")

    for key in ("project", "client", "budget_wan", "bid_date"):
        if not data.get(key):
            missing.append(key)

    if not allow_missing and len(scores) < len(WEIGHTS):
        problems.append(
            f"七维里只给了 {len(scores)} 项，缺 {len(WEIGHTS) - len(scores)} 项，结论为待定"
        )
    return gate, scores, missing, problems


def compute(scores):
    """按已给维度归一化计算，避免缺项被当成 0 分。"""
    total_w = sum(WEIGHTS[k] for k in scores) or 1.0
    total = sum(scores[k] / 5.0 * WEIGHTS[k] for k in scores) / total_w * 100
    rows = []
    for k, v in scores.items():
        rows.append(
            {
                "key": k,
                "label": LABELS[k],
                "score": v,
                "weight": WEIGHTS[k],
                "contribution": round(v / 5.0 * WEIGHTS[k] / total_w * 100, 1),
                "gap": round((5 - v) * WEIGHTS[k] / total_w * 100, 1),
            }
        )
    rows.sort(key=lambda r: r["contribution"], reverse=True)
    weak = sorted(
        [r for r in rows if r["score"] <= 3],
        key=lambda r: r["gap"],
        reverse=True,
    )[:3]
    return round(total, 1), rows, weak


def tier_of(total, complete):
    if not complete:
        return "待定"
    for threshold, name in TIERS:
        if total >= threshold:
            return name
    return "建议放弃"


def render(data, gate, scores, rows, total, tier, weak, missing, problems):
    name = data.get("project") or "（未命名项目）"
    client = data.get("client") or "（客户待确认）"
    budget = data.get("budget_wan")
    budget_txt = f"{budget} 万元" if budget else "预算待确认"
    date = data.get("bid_date") or "开标时间待确认"

    out = []
    out.append(f"# 机会评估：{name}")
    out.append("")
    out.append(f"- 客户：{client}")
    out.append(f"- 规模：{budget_txt}")
    out.append(f"- 节点：{date}")
    out.append("")

    out.append("## 一、结论")
    out.append("")
    if gate == "fail":
        out.append("**不建议投标。** 资格条件不满足，属于无效投标，方案做得再好也不进入评分。")
        out.append("")
        out.append("可以做的：确认招标人是否接受联合体；或转为给符合资格的伙伴做技术支撑。")
    elif gate == "unknown":
        out.append("**待定。** 资格可满足性还没确认，先别投方案人力。")
        out.append("")
        out.append("先做一件事：把招标文件的资格性审查条款逐条对照我们的证照与案例，一天内能出结论。")
    else:
        out.append(f"**{tier}**（加权总分 {total} / 100）。")
        out.append("")
        if tier == "全力投入":
            out.append("下一步：立项报备、组投标小组、两周内完成需求共创与方案骨架。")
        elif tier == "选择性参与":
            out.append("下一步：只补下面第一条短板，两周后复审；补不上就转分包，别硬投。")
        else:
            out.append("下一步：不投主标。保留客户关系，争取做伙伴的分包或技术支撑，等下一轮。")
    out.append("")

    if rows:
        out.append("## 二、分数表")
        out.append("")
        out.append("| 维度 | 得分 | 权重 | 加权贡献 | 丢分 |")
        out.append("|---|---|---|---|---|")
        for r in rows:
            out.append(
                f"| {r['label']} | {r['score']:.0f} / 5 | {r['weight']:.2f} | "
                f"{r['contribution']} | {r['gap']} |"
            )
        out.append("")
        out.append("加权贡献合计即总分；缺项按已给维度归一化，不按 0 分处理。")
        out.append("")

    if weak:
        out.append("## 三、短板三条")
        out.append("")
        for i, r in enumerate(weak, 1):
            out.append(f"{i}. **{r['label']}（{r['score']:.0f}/5，丢 {r['gap']} 分）**")
            out.append(f"   - 补法：{ACTIONS[r['key']]}")
        out.append("")

    if missing:
        out.append("## 四、待确认信息")
        out.append("")
        for m in missing:
            out.append(f"- {m}")
        out.append("")
        out.append("以上信息补齐前，结论只能当参考，不能拿去立项。")
        out.append("")

    if problems:
        out.append("## 五、输入问题")
        out.append("")
        for p in problems:
            out.append(f"- {p}")
        out.append("")

    out.append("## 六、边界")
    out.append("")
    out.append("本分数不包含评委偏好、现场答辩、突发质疑等不可量化因素，也不输出中标概率。")
    return "\n".join(out)


def cmd_score(args):
    try:
        data = load(args.input)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        err(str(e))
        return 2

    gate, scores, missing, problems = validate(data, args.allow_missing)
    total, rows, weak = 0.0, [], []
    if scores:
        total, rows, weak = compute(scores)
    complete = gate == "pass" and len(scores) == len(WEIGHTS) and not any(
        "结论为待定" in p for p in problems
    )
    tier = tier_of(total, complete) if gate == "pass" else ("不建议投标" if gate == "fail" else "待定")
    if gate == "pass" and not complete:
        tier = "待定"

    if args.json:
        payload = {
            "project": data.get("project"),
            "gate": gate,
            "tier": tier,
            "total": total,
            "dims": rows,
            "weak": [
                {"key": w["key"], "label": w["label"], "gap": w["gap"], "action": ACTIONS[w["key"]]}
                for w in weak
            ],
            "missing": missing,
            "problems": problems,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(render(data, gate, scores, rows, total, tier, weak, missing, problems))
    return 0


TEMPLATE = {
    "project": "XX区一网通办升级改造",
    "client": "XX区行政审批局",
    "budget_wan": 860,
    "bid_date": "2026-12-10",
    "qualification_ok": True,
    "scores": {
        "funding": 4,
        "competition": 3,
        "relationship": 4,
        "case_match": 3,
        "policy_fit": 5,
        "differentiation": 4,
        "delivery": 3,
    },
    "notes": "对手为本地集成商，无同类案例；我方缺一个省级同规模案例",
}


def cmd_template(_args):
    print(json.dumps(TEMPLATE, ensure_ascii=False, indent=2))
    return 0


def cmd_check(args):
    try:
        data = load(args.input)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        err(str(e))
        return 2
    gate, scores, missing, problems = validate(data, allow_missing=True)
    print(f"资格一票否决项：{gate}")
    print(f"已给维度：{len(scores)}/{len(WEIGHTS)}")
    if missing:
        print("缺：")
        for m in missing:
            print(f"  - {m}")
    if problems:
        print("问题：")
        for p in problems:
            print(f"  - {p}")
    if not missing and not problems and gate == "pass":
        print("输入完整，可以算分。")
    return 0


def main():
    ap = argparse.ArgumentParser(description="政府数字化投标机会打分")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("score", help="计算分数与档位")
    p1.add_argument("--input", required=True)
    p1.add_argument("--json", action="store_true")
    p1.add_argument("--allow-missing", action="store_true", help="缺维度也出结论（归一化计算）")
    p1.set_defaults(func=cmd_score)

    p2 = sub.add_parser("template", help="输出输入模板")
    p2.add_argument("--json", action="store_true")
    p2.set_defaults(func=cmd_template)

    p3 = sub.add_parser("check", help="只检查输入完整性")
    p3.add_argument("--input", required=True)
    p3.set_defaults(func=cmd_check)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
