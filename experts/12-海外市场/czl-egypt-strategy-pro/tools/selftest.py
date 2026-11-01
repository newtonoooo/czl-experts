#!/usr/bin/env python3
"""自检：用固定样例跑一遍全部工具，断言关键性质。

运行
    python selftest.py

输出每条断言的 PASS/FAIL，任一失败则退出码为 1。
用于发布前回归，也用于确认"工具还能跑"。
仅依赖标准库。
"""

from __future__ import annotations

import importlib.util
import sys
import traceback
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
RESULTS: list[tuple[str, bool, str]] = []


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def check(label: str, fn):
    try:
        fn()
        RESULTS.append((label, True, ""))
    except AssertionError as e:
        RESULTS.append((label, False, str(e) or "断言失败"))
    except Exception:
        RESULTS.append((label, False, traceback.format_exc(limit=2).strip().splitlines()[-1]))


def main() -> int:
    # ---------- fx_stress ----------
    fx = load("fx_stress")

    def t_fx_demo():
        r = fx.compute(fx.DEMO)
        assert len(r["scenarios"]) == 4, "情景数应为 4"
        assert r["base_gross_margin_pct"] > 0, "基准毛利率应为正"
        assert r["verdict"] in ("PASS", "CONDITIONAL", "STOP"), "判定取值非法"
        assert r["unhedged_notional"] >= 0, "未对冲敞口不应为负"
        assert r["scenarios"][0]["devaluation"] == 0.0, "首个情景应为基准"

    def t_fx_importer():
        p = dict(fx.DEMO)
        p["revenue"] = {"local_egp": 560_000_000, "export_usd": 0}
        p["costs"] = {"import_usd": 9_000_000, "local_egp": 84_000_000, "labor_egp": 28_000_000}
        r = fx.compute(p)
        assert r["verdict"] == "STOP", "高进口依赖 + 纯内销 + 负毛利应为 STOP"
        last = r["scenarios"][-1]
        assert last["gross_margin_pct"] < r["scenarios"][0]["gross_margin_pct"], "贬值应压缩内销型毛利"

    check("fx_stress / 出口型样例", t_fx_demo)
    check("fx_stress / 进口内销型应判 STOP", t_fx_importer)

    # ---------- site_score ----------
    ss = load("site_score")

    def t_site():
        r = ss.compute(ss.DEMO)
        scores = [x["weighted"] for x in r["ranking"]]
        assert scores == sorted(scores, reverse=True), "排名未按分数降序"
        assert r["ranking"][0]["rank"] == 1, "首位排名应为 1"
        assert 0 <= r["gap"] <= 100, "分差越界"
        assert r["verdict"] in ("TIE", "LEAN", "CLEAR"), "判定取值非法"
        assert isinstance(r["sensitivity_flips"], list), "敏感性结果应为列表"

    def t_site_single():
        p = {"criteria": ss.DEMO["criteria"], "sites": ss.DEMO["sites"][:1]}
        r = ss.compute(p)
        assert r["gap"] == 99, "单一候选时分差应置为 99"

    check("site_score / 排序与判定", t_site)
    check("site_score / 单一候选兜底", t_site_single)

    # ---------- entry_route ----------
    er = load("entry_route")

    def t_route():
        r = er.compute(er.DEMO)
        assert r["feasible"], "样例应至少有一条可行路径"
        labels = [b["label"] for b in r["blocked"]]
        assert "绿地全资建厂" in labels, "30 个月周期应被 24 个月上限过滤"
        assert "合同制造/代工" in labels, "技术外流应被过滤"
        ranks = [x["rank"] for x in r["feasible"]]
        assert ranks == list(range(1, len(ranks) + 1)), "可行路径排名应连续"
        for row in r["feasible"]:
            assert row["exit_cost_usd"] <= row["capex_usd"], "退出成本不应高于资本"

    def t_route_blocked():
        p = dict(er.DEMO)
        p["constraints"] = {"max_capex_usd": 1000, "max_months": 1, "allow_tech_leak": False}
        r = er.compute(p)
        assert r["verdict"] == "STOP", "全部路径被过滤时应判 STOP"

    check("entry_route / 过滤与排序", t_route)
    check("entry_route / 全过滤应判 STOP", t_route_blocked)

    # ---------- landed_cost ----------
    lc = load("landed_cost")

    def t_landed():
        r = lc.compute(lc.DEMO)
        assert r["landed_unit_cost"] > r["cif_unit"], "到厂单价应高于 CIF"
        expect_duty = r["cif_unit"] * lc.DEMO["duty_rate"]
        assert abs(r["duty_unit"] - expect_duty) < 0.01, "关税应等于 CIF x 税率"
        assert r["local_assembly_unit_cost"] > r["landed_unit_cost"], "含组装应更高"
        assert r["vat_cash_out"] > 0, "增值税现金流应大于 0"

    def t_landed_no_vat_recover():
        p = dict(lc.DEMO)
        p["vat_recoverable"] = False
        r = lc.compute(p)
        base = lc.compute(lc.DEMO)
        assert r["landed_unit_cost"] > base["landed_unit_cost"], "增值税不可抵扣时应进入成本"

    check("landed_cost / 结构完整性", t_landed)
    check("landed_cost / 增值税不可抵扣", t_landed_no_vat_recover)

    # ---------- labor_cost ----------
    lb = load("labor_cost")

    def t_labor():
        r = lb.compute(lb.DEMO)
        assert r["headcount"] == 101, "人数合计应为 101"
        assert r["blended_multiplier"] > 1.3, "全口径倍数应显著大于 1"
        assert r["year2_cost_egp"] > r["total_cost_egp"], "第二年含调薪应更高"
        assert r["labor_per_unit_egp"] is not None, "提供产量时应给出单位人工"
        for row in r["rows"]:
            assert row["annual_cost_egp"] > row["annual_base_egp"], "全口径应高于基本工资"

    def t_labor_no_output():
        p = dict(lb.DEMO)
        p["annual_output_units"] = 0
        r = lb.compute(p)
        assert r["labor_per_unit_egp"] is None, "无产量时不应给出单位人工"

    check("labor_cost / 全口径计算", t_labor)
    check("labor_cost / 无产量兜底", t_labor_no_output)

    # ---------- avatar_prep ----------
    ap = load("avatar_prep")

    def t_avatar():
        png = HERE.parent / "avatars" / "expert.png"
        if not png.exists():
            raise AssertionError("缺少 avatars/expert.png")
        img = ap.to_rgb(ap.read_png(png))
        assert img.width == img.height == 512, "头像应为 512x512"
        small = ap.box_resize(img, 64)
        assert small.width == 64 and len(small.pixels) == 64 * 64 * 3, "缩放结果尺寸错误"

    check("avatar_prep / 头像读取与缩放", t_avatar)

    # ---------- 汇总 ----------
    width = max(len(r[0]) for r in RESULTS) + 2
    print("=" * (width + 8))
    for label, ok, msg in RESULTS:
        print("{:<{w}} {}".format(label, "PASS" if ok else "FAIL", w=width) + ("  <- " + msg if msg else ""))
    print("=" * (width + 8))
    passed = sum(1 for r in RESULTS if r[1])
    print("总计 {}/{} 通过".format(passed, len(RESULTS)))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
