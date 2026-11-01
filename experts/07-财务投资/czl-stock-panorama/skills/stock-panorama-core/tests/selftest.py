"""离线自测：不联网、不依赖任何 MCP，纯本地断言。

运行：
    cd skills/stock-panorama-core/scripts
    python ../tests/selftest.py

覆盖的内容：
- 指标计算与手算结果对得上；
- 单位归一化（0.241 -> 24.1%）按预期生效；
- 全量样本能出分、缺失样本不给假分；
- 亏损样本的 PE 不被当成“便宜”；
- 关键价位满足 支撑 < 现价 < 压力；
- 报告不缺章节、不出现 None 字样；
- CLI 正常退出码与错误退出码；
- 同一输入两次运行结果完全一致。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, SCRIPTS)

from panorama import indicators, scorecard, schema, qa, levels, report  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ok   " if cond else "  FAIL ") + name + (f"  -- {detail}" if detail and not cond else ""))


def build_series(n=260, start=100.0, step=0.35, amp=1.2):
    closes, highs, lows, vols = [], [], [], []
    px = start
    for i in range(n):
        px = px + step + (amp if i % 7 == 0 else (-amp * 0.6 if i % 11 == 0 else 0.05))
        closes.append(round(px, 2))
        highs.append(round(px * 1.012, 2))
        lows.append(round(px * 0.988, 2))
        vols.append(round(1_000_000 * (1 + (0.2 if i % 5 == 0 else 0)), 0))
    return closes, highs, lows, vols


def full_payload():
    c, h, l, v = build_series()
    return {
        "meta": {"code": "600000", "name": "测试样本", "market": "SH", "industry": "示例行业",
                  "as_of": "2026-10-27", "adjust": "前复权", "report_period": "2026-06-30"},
        "valuation": {"pe_ttm": 18.5, "pb": 2.6, "peg": 1.1, "pe_percentile_5y": 28,
                       "industry_pe_median": 24.0, "dividend_yield": 2.8},
        "profitability": {"roe_ttm": 0.171, "gross_margin": 42.0, "net_margin": 15.2, "roic": 12.5,
                           "asset_turnover": 0.72},
        "growth": {"rev_yoy": 12.5, "np_yoy": 18.0, "rev_cagr_3y": 9.5, "np_cagr_3y": 14.0, "q_np_yoy": 21.0},
        "health": {"debt_ratio": 38.0, "current_ratio": 2.1, "ocf_to_np": 1.08,
                    "interest_coverage": 12.0, "goodwill_to_equity": 4.0, "fcf_positive_years": 5},
        "capital": {"main_net_inflow_20d": 2.4e8, "main_net_inflow_20d_pct": 0.9,
                     "north_hold_change_20d": 0.35, "margin_balance_change_20d": 3.0,
                     "holder_count_change": -6.0},
        "governance": {"pledge_ratio": 0.0, "audit_opinion": "标准无保留意见"},
        "events": [
            {"date": "2026-08-25", "type": "业绩", "summary": "中报净利同比 +18%", "tone": "正面", "confidence": "高"},
            {"date": "2026-09-10", "type": "增减持", "summary": "高管小幅减持", "tone": "负面", "confidence": "中"},
        ],
        "peers": [
            {"name": "同业甲", "pe_ttm": 22.0, "roe_ttm": 14.0, "np_yoy": 11.0},
            {"name": "同业乙", "pe_ttm": 16.0, "roe_ttm": 19.0, "np_yoy": 22.0},
        ],
        "technical": {"close": c[-1], "turnover": 0.8},
        "series": {"closes": c, "highs": h, "lows": l, "volumes": v},
    }


def thin_payload():
    return {"meta": {"code": "000001", "name": "稀疏样本", "as_of": "2026-10-27"},
            "valuation": {"pe_ttm": 12.0},
            "profitability": {"roe_ttm": 11.0}}


def loss_payload():
    p = full_payload()
    p["meta"]["code"] = "300999"
    p["meta"]["name"] = "亏损样本"
    p["valuation"].update({"pe_ttm": -30.0, "pb": 5.5, "pe_percentile_5y": 88})
    p["profitability"].update({"net_margin": -12.0, "roe_ttm": -8.0})
    p["growth"].update({"np_yoy": -45.0, "rev_yoy": -20.0})
    p["health"].update({"debt_ratio": 72.0, "ocf_to_np": -0.4})
    p["events"] = [{"date": "2026-09-01", "type": "诉讼", "summary": "被提起诉讼", "tone": "负面", "confidence": "高"}]
    return p


def test_indicators():
    print("[1] 指标计算")
    closes = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    check("SMA5 = 8.0", indicators.sma(closes, 5) == 8.0, indicators.sma(closes, 5))
    check("数据不足返回 None", indicators.sma(closes, 20) is None)
    check("常数序列 EMA 等于常数", indicators.ema([5] * 30, 10) == 5.0, indicators.ema([5] * 30, 10))
    up = list(range(1, 40))
    check("单边上涨 RSI 接近 100", indicators.rsi(up, 14) > 95, indicators.rsi(up, 14))
    check("RSI 数据不足返回 None", indicators.rsi([1, 2, 3], 14) is None)
    b = indicators.boll([10] * 25, 20)
    check("常数序列布林带三轨相等", b[0] == b[1] == b[2] == 10.0, b)
    d = indicators.derive_technical({"closes": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]})
    check("推导结果不含 None 键", all(v is not None for v in d.values()))


def test_normalize():
    print("[2] 输入规范化")
    data, nr = schema.normalize(full_payload())
    check("ROE 0.171 -> 17.1", data["business"]["profitability"]["roe_ttm"] == 17.1,
          data["business"]["profitability"]["roe_ttm"])
    check("归一化留下记录", any("roe_ttm" in x for x in nr["normalized"]))
    check("无致命错误", nr["errors"] == [])
    check("技术指标由序列补齐", data["technical"].get("ma20") is not None)
    check("非法输入被拦截", schema.normalize("不是对象")[1]["errors"] != [])
    check("缺 code 报错", schema.normalize({"meta": {}})[1]["errors"] != [])
    # 0.9% 的资金占比不能被当成 90%
    check("资金占比 0.9 不被放大", data["business"]["capital"]["main_net_inflow_20d_pct"] == 0.9,
          data["business"]["capital"]["main_net_inflow_20d_pct"])
    check("歧义值给出提示", any("小于 1.5" in w for w in nr["warnings"]), nr["warnings"])
    forced, _ = schema.normalize(dict(full_payload(), meta=dict(full_payload()["meta"], units={"percent_format": "decimal"})))
    check("meta.units 可强制小数口径", forced["business"]["capital"]["north_hold_change_20d"] == 35.0,
          forced["business"]["capital"]["north_hold_change_20d"])


def test_scoring():
    print("[3] 评分")
    data, nr = schema.normalize(full_payload())
    r = scorecard.evaluate(data)
    check("全量样本有总分", isinstance(r["overall"], (int, float)), r["overall"])
    check("总分落在 0-100", 0 <= (r["overall"] or -1) <= 100, r["overall"])
    check("六个维度齐全", len(r["dimensions"]) == 6)
    check("权重合计为 1", abs(sum(d["weight"] for d in r["dimensions"]) - 1.0) < 1e-9)
    check("有最强/最弱维度", r["strongest"] and r["weakest"])
    check("多头证据非空", len(scorecard.bull_case(r)) > 0)
    check("空头证据非空", len(scorecard.bear_case(r)) > 0)

    cap = next(x for x in r["dimensions"] if x["key"] == "capital")
    audit_factor = next(f for f in cap["factors"] if f["key"] == "audit")
    check("“标准无保留意见”判为正面", (audit_factor["score"] or 0) >= 80, audit_factor["score"])
    worst = next(x for x in r["dimensions"] if x["key"] == "capital")
    flow_factor = next(f for f in worst["factors"] if f["key"] == "main_flow")
    check("资金占比 0.9% 走中档而非满分", 40 <= (flow_factor["score"] or 0) <= 60, flow_factor["score"])

    d2, _ = schema.normalize(thin_payload())
    r2 = scorecard.evaluate(d2)
    check("稀疏样本不给总分", r2["overall"] is None, r2["overall"])
    check("稀疏样本档位为 N/A", r2["grade"] == "N/A")

    d3, _ = schema.normalize(loss_payload())
    r3 = scorecard.evaluate(d3)
    val = next(x for x in r3["dimensions"] if x["key"] == "valuation")
    pe_factor = next(f for f in val["factors"] if f["key"] == "pe_ttm")
    check("负 PE 不给高分", (pe_factor["score"] or 0) <= 5, pe_factor["score"])
    loss = next(x for x in r3["dimensions"] if x["key"] == "profitability")
    nm = next(f for f in loss["factors"] if f["key"] == "net_margin")
    check("负净利率给低分", (nm["score"] or 100) <= 10, nm["score"])
    check("亏损样本总分低于全量样本", (r3["overall"] or 0) < (r["overall"] or 0),
          f"{r3['overall']} vs {r['overall']}")


def test_levels():
    print("[4] 关键价位")
    data, _ = schema.normalize(full_payload())
    lv = levels.compute_levels(data["technical"])
    check("价位可用", lv["available"])
    check("支撑 < 现价", lv["support"] is None or lv["support"] < lv["close"], lv)
    check("压力 > 现价", lv["resistance"] is None or lv["resistance"] > lv["close"], lv)
    check("风险位低于现价", lv["risk_line"] is None or lv["risk_line"] < lv["close"])
    check("空数据不崩", levels.compute_levels({})["available"] is False)


def test_audit():
    print("[5] 数据体检")
    data, nr = schema.normalize(full_payload())
    r = scorecard.evaluate(data)
    a = qa.audit(data, r, nr)
    check("置信度在 高中低 内", a["confidence"] in ("高", "中", "低"), a["confidence"])
    check("有时效判定", a["freshness"]["status"] in ("fresh", "acceptable", "stale", "unknown", "invalid"))
    stale = full_payload()
    stale["meta"]["report_period"] = "2024-06-30"
    d, n2 = schema.normalize(stale)
    a2 = qa.audit(d, scorecard.evaluate(d), n2)
    check("过期财报被标记", any("过期" in w for w in a2["warnings"]), a2["warnings"])
    check("过期拉低置信度", a2["confidence"] in ("中", "低"), a2["confidence"])


def test_report():
    print("[6] 报告渲染")
    out = report.run(full_payload())
    md = out["report_markdown"]
    for kw in ("结论摘要", "六维评分", "关键价位", "同业对标", "多空证据", "数据体检", "不构成投资建议"):
        check(f"报告含「{kw}」", kw in md)
    check("报告无 None 字样", "None" not in md)
    check("报告无未替换占位符", "{dim" not in md and "{{" not in md)
    check("覆盖率写进报告", "数据覆盖率" in md)


def test_cli():
    print("[7] 命令行")
    tmp = tempfile.mkdtemp(prefix="panorama_selftest_")
    p_in = os.path.join(tmp, "in.json")
    p_md = os.path.join(tmp, "out.md")
    with open(p_in, "w", encoding="utf-8") as fh:
        json.dump(full_payload(), fh, ensure_ascii=False)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r1 = subprocess.run([sys.executable, "-m", "panorama.cli", "report", "--input", p_in, "--out", p_md],
                        cwd=SCRIPTS, capture_output=True, text=True, encoding="utf-8", env=env)
    check("report 退出码 0", r1.returncode == 0, r1.stderr[-300:])
    check("报告文件已生成", os.path.exists(p_md) and os.path.getsize(p_md) > 800)

    r2 = subprocess.run([sys.executable, "-m", "panorama.cli", "check", "--input", p_in],
                        cwd=SCRIPTS, capture_output=True, text=True, encoding="utf-8", env=env)
    check("check 退出码 0", r2.returncode == 0, r2.stderr[-300:])

    bad = os.path.join(tmp, "bad.json")
    with open(bad, "w", encoding="utf-8") as fh:
        fh.write('{"meta": {}}')
    r3 = subprocess.run([sys.executable, "-m", "panorama.cli", "score", "--input", bad],
                        cwd=SCRIPTS, capture_output=True, text=True, encoding="utf-8", env=env)
    check("非法输入退出码 2", r3.returncode == 2, r3.returncode)


def test_determinism():
    print("[8] 结果稳定性")
    a = report.run(full_payload())["report_markdown"]
    b = report.run(full_payload())["report_markdown"]
    check("同一输入两次渲染一致", a == b)


def main():
    print(f"panorama 自测开始（Python {sys.version.split()[0]}）")
    for fn in (test_indicators, test_normalize, test_scoring, test_levels,
               test_audit, test_report, test_cli, test_determinism):
        fn()
    print("-" * 52)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        print("失败项：" + "、".join(FAIL))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
