#!/usr/bin/env python3
"""端到端自检：函数级断言 + CLI 子进程调用。

运行：
    python selftest.py            # 全部测试
    python selftest.py -v         # 显示每条断言

退出码：0 = 全部通过，1 = 存在失败
"""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import entry_gate  # noqa: E402
import partner_score  # noqa: E402
import pipeline_rank  # noqa: E402
import route_cost  # noqa: E402

VERBOSE = "-v" in sys.argv
RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))
    if VERBOSE:
        mark = "PASS" if condition else "FAIL"
        print(f"[{mark}] {name}" + (f" :: {detail}" if detail else ""))
    return bool(condition)


def load(fixture):
    with open(HERE / "fixtures" / fixture, "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_entry_gate():
    case = load("entry_gate_case.json")
    result = entry_gate.evaluate(case)
    codes = {f["code"] for f in result["findings"]}
    check("G1 判定为 CONDITIONAL", result["verdict"] == "CONDITIONAL", result["verdict"])
    check("G1 可进入 G2", result["can_proceed_to_g2"] is True)
    check("G1 检出许可缺口", "LICENSE_GAP" in codes)
    check("G1 检出政府采购前置", {"GOV_CR", "GOV_TAX", "GOV_GOSI"} <= codes)
    check("G1 检出 SABER 缺失", "SABER_MISSING" in codes)
    check("G1 始终给出官方复核提示", "OFFICIAL_CHECK" in codes)
    check("G1 必填动作非空", len(result["required_actions"]) >= 3, str(len(result["required_actions"])))

    blocked = entry_gate.evaluate(load("entry_gate_blocked.json"))
    bcodes = {f["code"] for f in blocked["findings"]}
    check("G1 阻断：股权结构不成立", blocked["verdict"] == "BLOCKED", blocked["verdict"])
    check("G1 阻断后不放行 G2", blocked["can_proceed_to_g2"] is False)
    check("G1 阻断码正确", "EQUITY_STRUCTURE" in bcodes)

    bad = entry_gate.evaluate({"activity_code": "x", "foreign_ownership_pct": 150})
    check("G1 参数越界被拦", bad["verdict"] == "BLOCKED"
          and "OWNERSHIP_INVALID" in {f["code"] for f in bad["findings"]})


def test_route_cost():
    result = route_cost.analyze(load("route_cost_case.json"))
    names = [r["name"] for r in result["ranking"]]
    check("G2 三条路径全部计算", len(names) == 3, str(names))
    check("G2 综合分单调不增",
          all(result["ranking"][i]["composite"] >= result["ranking"][i + 1]["composite"]
              for i in range(len(result["ranking"]) - 1)))
    best = result["detail"][0]
    wofe = next(r for r in result["detail"] if r["name"] == "独资公司")
    check("G2 首年运营系数按开业月折算",
          abs(wofe["year1_operating_factor"] - (12 - (8 - 1)) / 12) < 1e-3,
          str(wofe["year1_operating_factor"]))
    check("G2 未开业月份不计收入",
          wofe["years"][0]["revenue"] < 6000000,
          str(wofe["years"][0]["revenue"]))
    check("G2 三年账行数正确", len(best["years"]) == 3)
    check("G2 推荐路径在候选内", result["recommendation"]["primary"] in names)
    check("G2 给出备选路径", result["recommendation"]["alternate"] in names)
    negative = [r for r in result["detail"] if r["npv"] < 0]
    check("G2 负现值路径被保留而非删除", isinstance(negative, list))
    try:
        route_cost.analyze({"routes": [{"name": "bad", "gross_margin_pct": 32}]})
        check("G2 百分数口径误用被拒", False, "未抛错")
    except ValueError:
        check("G2 百分数口径误用被拒", True)


def test_partner_score():
    result = partner_score.analyze(load("partner_score_case.json"))
    by_name = {r["name"]: r for r in result["ranking"]}
    top = result["ranking"][0]
    check("G3 第一名是品类匹配最高者", "候选甲" in top["name"], top["name"])
    red = by_name["候选丙·达曼家族企业"]
    check("G3 红旗一票否决为 D", red["grade"] == "D", red["grade"])
    check("G3 红旗标记被记录", red["grade_overridden_by_red_flag"] is True)
    check("G3 红旗项描述已翻译", red["red_flags"][0]["label"] != "")
    check("G3 评分维度齐全", all(r["complete"] for r in result["ranking"]))
    check("G3 三家候选不触发扩充名单提示", result["warning"] == "")
    try:
        partner_score.analyze({"candidates": [{"name": "x", "scores": {"category_fit": 9}}]})
        check("G3 越界分数被拒", False, "未抛错")
    except ValueError:
        check("G3 越界分数被拒", True)


def test_pipeline():
    result = pipeline_rank.analyze(load("pipeline_case.json"))
    check("G4 三条商机全部排序", result["count"] == 3)
    check("G4 指数最高为 100", abs(result["ranking"][0]["index"] - 100.0) < 1e-6,
          str(result["ranking"][0]["index"]))
    check("G4 档位覆盖 A/B/C",
          set(result["tiers"]) == {"A", "B", "C"}, str(result["tiers"]))
    check("G4 每条都有处置动作", all(s["action"] for s in result["ranking"]))
    check("G4 快赢商机排在小额慢单之前",
          any("OPP-02" in s["name"] for s in result["ranking"][:2]),
          str([s["name"] for s in result["ranking"]]))


def test_cli():
    cases = [
        ("entry_gate.py", "entry_gate_case.json", (0,)),
        ("entry_gate.py", "entry_gate_blocked.json", (2,)),
        ("route_cost.py", "route_cost_case.json", (0,)),
        ("partner_score.py", "partner_score_case.json", (0,)),
        ("pipeline_rank.py", "pipeline_case.json", (0,)),
    ]
    for script, fixture, expected in cases:
        proc = subprocess.run(
            [sys.executable, str(HERE / script), "--input", str(HERE / "fixtures" / fixture)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        ok = proc.returncode in expected
        parsed = False
        try:
            json.loads(proc.stdout)
            parsed = True
        except json.JSONDecodeError:
            parsed = False
        check(f"CLI {script} 退出码 {expected}", ok, f"got {proc.returncode}")
        check(f"CLI {script} 输出合法 JSON", parsed)

    proc = subprocess.run(
        [sys.executable, str(HERE / "route_cost.py"), "--input",
         str(HERE / "fixtures" / "route_cost_case.json"), "--format", "md"],
        capture_output=True, text=True, encoding="utf-8",
    )
    check("CLI Markdown 输出可用", proc.returncode == 0 and "路径比选" in proc.stdout)


def main():
    print("沙特商务拓展专家·旗舰版 · 脚本自检")
    print(f"Python {sys.version.split()[0]} | 目录 {HERE}")
    print("-" * 56)
    test_entry_gate()
    test_route_cost()
    test_partner_score()
    test_pipeline()
    test_cli()
    print("-" * 56)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = [name for name, ok, _ in RESULTS if not ok]
    print(f"通过 {passed}/{len(RESULTS)}")
    if failed:
        print("失败项：")
        for name in failed:
            print(f"  - {name}")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
