"""报告渲染：把结构化结果写成 Markdown。

原则：
- 报告里出现的每个数字都必须来自输入或本地计算，模板不做任何补白；
- 缺失项统一写“未取到”，不用“约为/大致”掩饰；
- 固定保留“反方证据”与“待确认项”两节，避免输出单向叙事。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import levels as levels_mod
from . import qa as qa_mod
from . import scorecard

DIM_ICON = {
    "valuation": "①", "profitability": "②", "growth": "③",
    "health": "④", "technical": "⑤", "capital": "⑥",
}


def _fmt(v, unit: str = "") -> str:
    if v is None:
        return "未取到"
    if isinstance(v, bool):
        return "是" if v else "否"
    if isinstance(v, (int, float)):
        if abs(v) >= 1e8:
            return f"{round(v / 1e8, 2)} 亿{unit}"
        if isinstance(v, float) and not v.is_integer():
            return f"{round(v, 2)}{unit}"
        return f"{v}{unit}"
    return str(v)


def _price(v) -> str:
    return "未取到" if v is None else f"{round(float(v), 2)}"


def _table(headers: List[str], rows: List[List[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def _dim_rows(result: Dict[str, Any]) -> List[List[str]]:
    rows = []
    for d in result.get("dimensions") or []:
        rows.append([
            DIM_ICON.get(d["key"], "·"),
            d["label"],
            _fmt(d["score"]),
            f"{int(round(d['coverage'] * 100))}%",
            f"{int(round(d['weight'] * 100))}%",
            d["verdict"],
        ])
    return rows


def _factor_rows(dim: Dict[str, Any]) -> List[List[str]]:
    rows = []
    for f in dim.get("factors") or []:
        caveat = f.get("caveat") or ""
        rows.append([
            f["label"],
            f.get("evidence") or "未取到",
            _fmt(f.get("score")),
            f"{int(round(f['weight'] * 100))}%",
            caveat,
        ])
    return rows


def _peer_block(peer: Dict[str, Any]) -> str:
    if not peer.get("available"):
        return f"> 同业对标未执行：{peer.get('reason')}\n"
    headers = ["公司", "PE(TTM)", "ROE", "净利同比"]
    rows = []
    for r in peer["rows"]:
        rows.append([
            r.get("name") or "-",
            _fmt(r.get("pe_ttm")),
            _fmt(r.get("roe_ttm"), "%"),
            _fmt(r.get("np_yoy"), "%"),
        ])
    return _table(headers, rows) + "\n\n> 分位需样本≥3 家才具参考性；样本过少时只看绝对值，不做排名结论。\n"


def render_markdown(data: Dict[str, Any], result: Dict[str, Any], audit: Dict[str, Any]) -> str:
    meta = data.get("meta") or {}
    lv = levels_mod.compute_levels(data.get("technical") or {})
    peer = scorecard.peer_matrix(data)
    bull, bear = scorecard.bull_case(result), scorecard.bear_case(result)

    title = f"# 个股全景诊断报告：{meta.get('name') or '未命名标的'}（{meta.get('code') or '-'}）"
    head = [
        title,
        "",
        _table(
            ["项目", "内容"],
            [
                ["所属行业", meta.get("industry") or "未标注"],
                ["数据截止", meta.get("as_of") or "未标注"],
                ["财务报告期", meta.get("report_period") or "未标注"],
                ["技术面复权方式", meta.get("adjust") or "未声明"],
                ["结论置信度", audit.get("confidence") or "-"],
                ["数据覆盖率", f"{int(round((result.get('total_coverage') or 0) * 100))}%"],
                ["综合评分", f"{_fmt(result.get('overall'))} / 100（{result.get('grade')}）"],
            ],
        ),
    ]

    strongest = next((d for d in result["dimensions"] if d["key"] == result.get("strongest")), None)
    weakest = next((d for d in result["dimensions"] if d["key"] == result.get("weakest")), None)
    summary = [
        "",
        "## 一、结论摘要",
        "",
        f"- 综合评分 **{_fmt(result.get('overall'))}**，档位 **{result.get('grade')}**：{result.get('grade_desc')}。",
    ]
    if strongest and weakest and strongest["key"] != weakest["key"]:
        summary.append(
            f"- 六维里最强的是**{strongest['label']}**（{strongest['score']} 分），最弱的是**{weakest['label']}**（{weakest['score']} 分）。"
        )
    if result.get("total_coverage", 0) < 0.6:
        summary.append("- 数据覆盖率不足 60%，本报告只作线索整理，不构成评级结论。")
    summary.append("- 评分来自固定规则（见 references/scoring_rules.md），换一套阈值结论会变，这是方法本身的局限。")

    sec_dims = ["", "## 二、六维评分", "", _table(["", "维度", "得分", "覆盖率", "权重", "判定"], _dim_rows(result))]
    for d in result.get("dimensions") or []:
        sec_dims += [
            "",
            f"### {DIM_ICON.get(d['key'], '·')} {d['label']}（{_fmt(d['score'])} 分 / 覆盖率 {int(round(d['coverage']*100))}%）",
            "",
            _table(["分项", "取到的数", "得分", "权重", "口径提示"], _factor_rows(d)),
        ]

    sec_levels = ["", "## 三、关键价位", ""]
    if lv.get("available"):
        sec_levels += [
            _table(
                ["参照", "价格", "依据"],
                [
                    ["现价", _price(lv.get("close")), "最新收盘"],
                    ["第一支撑", _price(lv.get("support")), lv.get("support_basis") or "均线/低点"],
                    ["第一压力", _price(lv.get("resistance")), lv.get("resistance_basis") or "均线/高点"],
                    ["两倍 ATR 风险位", _price(lv.get("risk_line")), "收盘 - 2×ATR"],
                ],
            ),
            "",
        ]
        for n in lv.get("notes") or []:
            sec_levels.append(f"- {n}")
        sec_levels += ["", f"> {lv.get('disclaimer')}"]
    else:
        sec_levels.append(f"> 未能计算关键价位：{lv.get('reason')}")

    sec_peer = ["", "## 四、同业对标", "", _peer_block(peer)]

    sec_case = ["", "## 五、多空证据（由评分反推，非主观判断）", "", "**支持看多的分项**", ""]
    sec_case += [f"- {x}" for x in bull] or ["- 无明显高分项"]
    sec_case += ["", "**支持看空的分项**", ""]
    sec_case += [f"- {x}" for x in bear] or ["- 无明显低分项"]

    events = data.get("events") or []
    sec_ev = ["", "## 六、事件与治理", ""]
    if events:
        sec_ev.append(_table(["日期", "类型", "摘要", "倾向", "佐证强度"],
                             [[e.get("date") or "-", e.get("type") or "-", e.get("summary") or "-",
                               e.get("tone") or "未判定", e.get("confidence") or "中"] for e in events]))
    else:
        sec_ev.append("> 未录入事件：业绩、增减持、重组、质押等均未纳入评分。")

    sec_qa = ["", "## 七、数据体检", ""]
    cov_lines = [f"- {k}：{v['got']}/{v['total']}（{int(round(v['ratio']*100))}%）" for k, v in (audit.get("coverage", {}).get("per_block") or {}).items()]
    sec_qa += cov_lines
    if audit.get("freshness"):
        sec_qa.append(f"- 数据时效：{audit['freshness'].get('hint')}（{audit['freshness'].get('status')}）")
    if audit.get("normalized"):
        sec_qa += ["", "**已自动归一化的字段**", ""] + [f"- {x}" for x in audit["normalized"]]
    if audit.get("warnings"):
        sec_qa += ["", "**风险提示**", ""] + [f"- {x}" for x in audit["warnings"]]
    if audit.get("must_verify"):
        sec_qa += ["", "**待人工确认**", ""] + [f"- [ ] {x}" for x in audit["must_verify"]]

    tail = [
        "",
        "---",
        "",
        "> 本报告由本地规则引擎生成：取数来自所用数据源，评分与价位为机械推导，未做主观加权。",
        "> 内容仅供研究参考，不构成投资建议，不承诺任何收益。市场有风险，决策需自负。",
    ]
    return "\n".join(head + summary + sec_dims + sec_levels + sec_peer + sec_case + sec_ev + sec_qa + tail) + "\n"


def run(payload: Any, with_report: bool = True) -> Dict[str, Any]:
    """一站式：规范化 -> 评分 -> 体检 ->（可选）渲染 markdown。"""
    from . import schema

    data, norm_report = schema.normalize(payload)
    if norm_report["errors"]:
        return {"ok": False, "errors": norm_report["errors"], "audit": {"errors": norm_report["errors"]}}
    result = scorecard.evaluate(data)
    audit = qa_mod.audit(data, result, norm_report)
    out: Dict[str, Any] = {
        "ok": True,
        "meta": data["meta"],
        "score": {
            "overall": result["overall"],
            "grade": result["grade"],
            "total_coverage": result["total_coverage"],
            "dimensions": [
                {"key": d["key"], "label": d["label"], "score": d["score"],
                 "coverage": d["coverage"], "verdict": d["verdict"]}
                for d in result["dimensions"]
            ],
            "strongest": result.get("strongest"),
            "weakest": result.get("weakest"),
        },
        "levels": levels_mod.compute_levels(data.get("technical") or {}),
        "audit": audit,
        "bull": scorecard.bull_case(result),
        "bear": scorecard.bear_case(result),
    }
    if with_report:
        out["report_markdown"] = render_markdown(data, result, audit)
    return out
