# -*- coding: utf-8 -*-
"""三棱镜 · 自动化测试

只测真实可验证的行为，不做「假装通过」的标记。
运行：python tests/run_tests.py [-v]
退出码：0 全部通过 / 1 有失败
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import traceback
import zipfile
from xml.etree import ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOLS = os.path.join(ROOT, "tools")
sys.path.insert(0, TOOLS)

import triad_analyze as A            # noqa: E402
import triad_contract as C           # noqa: E402
import triad_profile as P            # noqa: E402
import triad_render as R             # noqa: E402
import triad_verify as V             # noqa: E402
import triad_xlsx as X               # noqa: E402
from triad_io import TableError, read_table, parse_date   # noqa: E402

FIX = os.path.join(HERE, "fixtures")
SALES = os.path.join(FIX, "sales_demo.csv")
DIRTY = os.path.join(FIX, "dirty_demo.csv")

RESULTS = []


def test(name):
    def deco(fn):
        try:
            fn()
            RESULTS.append((name, "PASS", ""))
            print(f"  PASS  {name}")
        except AssertionError as exc:
            RESULTS.append((name, "FAIL", str(exc)))
            print(f"  FAIL  {name} :: {exc}")
        except Exception as exc:  # noqa: BLE001
            RESULTS.append((name, "ERROR", f"{type(exc).__name__}: {exc}"))
            print(f"  ERROR {name} :: {type(exc).__name__}: {exc}")
            if "-v" in sys.argv:
                traceback.print_exc()
        return fn
    return deco


def make_tiny(path):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write("月份,销售额\n2025-01,100\n2025-02,120\n")


def make_neg(path):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write("日期,金额,备注\n")
        for i in range(12):
            fh.write(f"2025-{i+1:02d}-01,{1000+i*50},正常\n")
        fh.write("2025-12-31,-9999,冲销\n")


def make_messy(path):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write("月份,区域,销售额\n")
        fh.write('2025-01,华东,"¥1,234.50"\n')
        fh.write("2025-02,华东,1200\n")
        fh.write("2025-03,华东,abc\n")
        fh.write("2025/04,华东,1500\n")
        fh.write("2025年5月,华东,1600\n")


print("三棱镜 · 自动化测试")
print("=" * 60)

print("\n[1] 读取与类型推断")


@test("CSV 正常读取，行列数正确")
def _():
    t = read_table(SALES)
    assert t.n_rows == 108, f"期望 108 行，实际 {t.n_rows}"
    assert t.n_cols == 6, f"期望 6 列，实际 {t.n_cols}"
    assert t.headers[0] == "月份"


@test("月份列被识别为日期，粒度为 month")
def _():
    prof = P.profile_table(SALES)
    assert prof["time_axis"]["column"] == "月份"
    assert prof["time_axis"]["grain"] == "month", prof["time_axis"]["grain"]
    assert prof["time_axis"]["points"] == 12


@test("金额列被识别为数值")
def _():
    t = read_table(SALES)
    kinds = {c.name: c.kind for c in t.columns}
    assert kinds["销售额"] == "number" and kinds["订单数"] == "number", kinds


@test("带千分位与货币符号的金额可解析")
def _():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "m.csv")
        make_messy(p)
        t = read_table(p)
        col = t.column("销售额")
        assert 1234.5 in col.values, col.values[:5]


@test("多种日期写法都能解析")
def _():
    for s in ("2025-01-02", "2025/01/02", "2025年1月2日", "20250102", "2025-01"):
        assert parse_date(s) is not None, s
    assert parse_date("abc") is None


@test("列数不齐的 CSV 被补齐而不是丢行")
def _():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "r.csv")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("a,b,c\n1,2\n3,4,5\n")
        t = read_table(p)
        assert t.n_rows == 2 and t.n_cols == 3


print("\n[2] 体检与闸门")


@test("干净表评为 A 且放行")
def _():
    prof = P.profile_table(SALES)
    assert prof["quality"]["grade"] == "A", prof["quality"]
    assert prof["quality"]["gate"] == "pass"


@test("脏表被降级并给出告警")
def _():
    prof = P.profile_table(DIRTY)
    assert prof["quality"]["grade"] in ("B", "C"), prof["quality"]["grade"]
    assert prof["quality"]["gate"] in ("warn", "pass")
    codes = {i["code"] for i in prof["quality"]["issues"]}
    assert "duplicate_rows" in codes, codes


@test("行数过少的表被闸门拦截")
def _():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.csv")
        make_tiny(p)
        prof = P.profile_table(p)
        assert prof["quality"]["gate"] == "block", prof["quality"]


@test("没有数值列的表被拦截")
def _():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "n.csv")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("名称,备注\n" + "\n".join(f"项目{i},说明{i}" for i in range(20)))
        prof = P.profile_table(p)
        assert prof["quality"]["gate"] == "block"
        assert any(i["code"] == "no_numeric" for i in prof["quality"]["issues"])


@test("不存在的文件给出明确错误而不是崩溃")
def _():
    try:
        read_table(os.path.join(FIX, "no_such_file.csv"))
    except TableError as exc:
        assert "找不到文件" in str(exc)
    else:
        raise AssertionError("应当抛出 TableError")


print("\n[3] 口径层")


@test("自动起草口径时优先选择金额类指标")
def _():
    prof = P.profile_table(SALES)
    c = C.draft_contract(prof)
    assert c["metrics"][0]["name"] == "销售额", [m["name"] for m in c["metrics"]]
    assert c["time_field"] == "月份"
    assert c["grain"] == "month"


@test("口径校验能发现字段不存在")
def _():
    t = read_table(SALES)
    bad = {"contract_version": 1, "grain": "month", "time_field": "月份",
           "metrics": [{"id": "M1", "name": "毛利", "field": "毛利", "agg": "sum", "unit": "元"}]}
    ok, errs, _ = C.check_contract(bad, t)
    assert not ok and any("不存在" in e for e in errs), errs


@test("口径校验能发现非法粒度")
def _():
    t = read_table(SALES)
    bad = {"contract_version": 1, "grain": "fortnight", "time_field": "月份",
           "metrics": [{"id": "M1", "name": "销售额", "field": "销售额", "agg": "sum", "unit": "元"}]}
    ok, errs, _ = C.check_contract(bad, t)
    assert not ok and any("grain" in e for e in errs), errs


@test("合法口径通过校验")
def _():
    t = read_table(SALES)
    prof = P.profile_table(SALES)
    ok, errs, _ = C.check_contract(C.draft_contract(prof), t)
    assert ok, errs


print("\n[4] 三路分析")


@test("走势线算出正斜率与累计涨幅")
def _():
    t = read_table(SALES)
    prof = P.profile_table(SALES)
    c = C.draft_contract(prof)
    res = A.analyze_course(t, c, c["metrics"][0])
    assert res["available"]
    assert res["stats"]["slope_per_period"] > 0
    assert res["stats"]["change_pct"] > 30, res["stats"]
    assert len(res["series"]) == 12


@test("走势线在时点不足时降级而不是硬算")
def _():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.csv")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("月份,销售额\n2025-01,100\n")
        t = read_table(p)
        c = {"grain": "month", "time_field": "月份",
             "metrics": [{"id": "M1", "name": "销售额", "field": "销售额", "agg": "sum", "unit": "元"}]}
        res = A.analyze_course(t, c, c["metrics"][0])
        assert res["available"] is False
        assert res["findings"] == []


@test("拆解线占比合计为 100%")
def _():
    t = read_table(SALES)
    prof = P.profile_table(SALES)
    c = C.draft_contract(prof)
    res = A.analyze_composition(t, c, c["metrics"][0], "区域")
    total = sum(r["share"] for r in res["rows"])
    assert abs(total - 100) < 0.5, total
    assert res["hhi"] > 0


@test("等分四组的 HHI 接近 2500")
def _():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "e.csv")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("分组,值\n")
            for g in "ABCD":
                for _i in range(10):
                    fh.write(f"{g},100\n")
        t = read_table(p)
        c = {"grain": "year", "dimensions": ["分组"],
             "metrics": [{"id": "M1", "name": "值", "field": "值", "agg": "sum", "unit": ""}]}
        res = A.analyze_composition(t, c, c["metrics"][0], "分组")
        assert abs(res["hhi"] - 2500) < 1, res["hhi"]


@test("验伤线抓到负值")
def _():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "neg.csv")
        make_neg(p)
        t = read_table(p)
        c = {"grain": "month", "time_field": "日期",
             "metrics": [{"id": "M1", "name": "金额", "field": "金额", "agg": "sum", "unit": "元"}]}
        res = A.analyze_integrity(t, c)
        assert res["counts"]["CRITICAL"] >= 1, res["counts"]
        assert any(i["code"] == "negative_value" for i in res["items"])


@test("验伤线抓到重复行")
def _():
    t = read_table(DIRTY)
    prof = P.profile_table(DIRTY)
    c = C.draft_contract(prof)
    res = A.analyze_integrity(t, c)
    assert any(i["code"] == "duplicate_row" for i in res["items"]), [i["code"] for i in res["items"]]


@test("验伤线抓到未来日期")
def _():
    t = read_table(DIRTY)
    prof = P.profile_table(DIRTY)
    c = C.draft_contract(prof)
    res = A.analyze_integrity(t, c)
    assert any(i["code"] == "future_date" for i in res["items"])


@test("验伤线能在分组内发现结构性偏离")
def _():
    t = read_table(SALES)
    prof = P.profile_table(SALES)
    c = C.draft_contract(prof)
    res = A.analyze_integrity(t, c)
    codes = {i["code"] for i in res["items"]}
    assert codes & {"group_outlier", "group_deviation"}, codes


print("\n[5] 证据链")


@test("全量结论复算全部通过")
def _():
    t = read_table(SALES)
    prof = P.profile_table(SALES)
    c = C.draft_contract(prof)
    bundle = A.run_lanes(t, c)
    rep = V.verify_findings(t, bundle)
    assert rep["overall"] == "PASS", rep
    assert rep["failed"] == 0
    assert rep["passed"] >= 5


@test("篡改结论数值会被复算抓住并作废")
def _():
    t = read_table(SALES)
    prof = P.profile_table(SALES)
    c = C.draft_contract(prof)
    bundle = A.run_lanes(t, c)
    bundle["lanes"]["course"]["findings"][0]["value"] = 999.0
    rep = V.verify_findings(t, bundle)
    assert rep["overall"] == "FAIL"
    assert rep["failed"] == 1
    V.demote(bundle, rep)
    f = bundle["lanes"]["course"]["findings"][0]
    assert f["grade"] == "D" and f["verified"] is False, f


print("\n[6] 交付渲染")


@test("HTML 报告包含关键区块与真实数字")
def _():
    t = read_table(SALES)
    prof = P.profile_table(SALES)
    c = C.draft_contract(prof)
    bundle = A.run_lanes(t, c)
    rep = V.verify_findings(t, bundle)
    V.demote(bundle, rep)
    html = R.build_html(bundle, prof, rep, {"title": "T", "product": "P", "author": "A", "version": "1"})
    for token in ("一页纸结论", "数据体检", "走势线", "拆解线", "验伤线", "证据链", "<svg"):
        assert token in html, token
    assert "108" in html


@test("XLSX 可被自身解析器读回，工作表齐全")
def _():
    t = read_table(SALES)
    prof = P.profile_table(SALES)
    c = C.draft_contract(prof)
    bundle = A.run_lanes(t, c)
    rep = V.verify_findings(t, bundle)
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "wb.xlsx")
        R.build_xlsx(bundle, prof, rep, p)
        assert zipfile.is_zipfile(p)
        with zipfile.ZipFile(p) as zf:
            names = zf.namelist()
            for must in ("[Content_Types].xml", "xl/workbook.xml", "xl/styles.xml",
                         "xl/worksheets/sheet1.xml"):
                assert must in names, must
            for n in names:
                if n.endswith(".xml") or n.endswith(".rels"):
                    ET.fromstring(zf.read(n))     # 每个部件都是良构 XML
        back = read_table(p)
        assert back.n_rows >= 5, back.n_rows


@test("XLSX 首表内容与写入一致")
def _():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.xlsx")
        X.write_workbook(p, [X.Sheet("S1", ["名称", "数值"], [["甲", 12.5], ["乙", 7]])])
        back = read_table(p)
        assert back.headers == ["名称", "数值"], back.headers
        assert back.n_rows == 2
        assert back.column("数值").values == [12.5, 7.0]


@test("幻灯片与一页纸都包含结论文字")
def _():
    t = read_table(SALES)
    prof = P.profile_table(SALES)
    c = C.draft_contract(prof)
    bundle = A.run_lanes(t, c)
    rep = V.verify_findings(t, bundle)
    V.demote(bundle, rep)
    meta = {"title": "T", "product": "P", "author": "A", "version": "1"}
    spec = R.build_deck(bundle, prof, rep, meta)
    assert len(spec["slides"]) >= 4
    html = R.deck_html(spec, meta)
    assert "下一步动作" in html
    md = R.onepager_md(bundle, prof, rep, meta)
    assert "## 三句话" in md and "## 下一步" in md


print("\n[7] 命令行端到端")


@test("run 子命令产出五件套")
def _():
    with tempfile.TemporaryDirectory() as d:
        import triad_cli as CLI
        rc = CLI.main(["run", "--path", SALES, "--outdir", d, "--title", "T"])
        assert rc == 0, rc
        for f in ("report.html", "onepager.md", "deck.html", "deck_spec.json",
                  "workbook.xlsx", "profile.json", "bundle.json", "verify.json", "run.json"):
            assert os.path.exists(os.path.join(d, f)), f
        man = json.load(open(os.path.join(d, "run.json"), encoding="utf-8"))
        assert man["verification"]["overall"] == "PASS"
        assert man["input"]["rows"] == 108
        assert len(man["outputs"]) == 5


@test("run 子命令在闸门拦截时返回 3 且不产出报告")
def _():
    with tempfile.TemporaryDirectory() as d:
        import triad_cli as CLI
        p = os.path.join(d, "tiny.csv")
        make_tiny(p)
        rc = CLI.main(["run", "--path", p, "--outdir", d])
        assert rc == 3, rc
        assert os.path.exists(os.path.join(d, "blocked.md"))
        assert not os.path.exists(os.path.join(d, "report.html"))


@test("run 子命令对不支持格式给出明确错误")
def _():
    with tempfile.TemporaryDirectory() as d:
        import triad_cli as CLI
        p = os.path.join(d, "x.xls")
        open(p, "wb").write(b"\xd0\xcf\x11\xe0")
        rc = CLI.main(["run", "--path", p, "--outdir", d])
        assert rc == 2, rc


print("\n" + "=" * 60)
total = len(RESULTS)
passed = sum(1 for r in RESULTS if r[1] == "PASS")
failed = [r for r in RESULTS if r[1] != "PASS"]
print(f"共 {total} 项，通过 {passed}，失败 {len(failed)}")
for name, status, msg in failed:
    print(f"  {status}  {name} :: {msg}")
sys.exit(0 if not failed else 1)
