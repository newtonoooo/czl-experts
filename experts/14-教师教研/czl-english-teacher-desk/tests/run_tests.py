#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_tests.py — 脚本与成品自检的回归测试

运行：
    python tests/run_tests.py

输出：
    控制台摘要 + tests/last_run.md（每次覆盖，含时间戳与逐项结果）
退出码：0 全部通过；1 有失败。
"""
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
PY = sys.executable

results = []


def run(args, expect_code=0, expect_in=None, expect_err_in=None):
    proc = subprocess.run([PY] + args, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8")
    ok = proc.returncode == expect_code
    detail = f"exit={proc.returncode}（期望 {expect_code}）"
    if ok and expect_in:
        hit = all(s in proc.stdout for s in expect_in)
        ok = ok and hit
        detail += f"；输出含 {expect_in}：{'是' if hit else '否'}"
    if ok and expect_err_in:
        hit = all(s in (proc.stderr or "") for s in expect_err_in)
        ok = ok and hit
        detail += f"；stderr 含 {expect_err_in}：{'是' if hit else '否'}"
    return ok, detail, (proc.stdout or "") + (proc.stderr or "")


def case(name, args, **kw):
    ok, detail, raw = run(args, **kw)
    results.append({"name": name, "ok": ok, "detail": detail, "cmd": " ".join(args)})
    print(("PASS " if ok else "FAIL ") + name + " | " + detail)
    return ok, raw


def main():
    tmp = Path(tempfile.mkdtemp(prefix="etd_test_"))

    # 1 细目表生成
    out_bp = tmp / "blueprint.md"
    case("T01 细目表生成（正常配置）",
         ["scripts/blueprint.py", "--spec", str(FIX / "spec.json"), "--out", str(out_bp)],
         expect_in=["已生成"])
    if out_bp.exists():
        text = out_bp.read_text(encoding="utf-8")
        cond1 = "总分：100" in text
        cond2 = "题量：44" in text
        results.append({"name": "T01b 细目表内容校验", "ok": cond1 and cond2,
                        "detail": f"总分行：{cond1}；题量行：{cond2}", "cmd": "-"})
        print(("PASS " if cond1 and cond2 else "FAIL ") + "T01b 细目表内容校验")

    # 2 分值不一致应报 WARN
    bad_spec = json.loads((FIX / "spec.json").read_text(encoding="utf-8"))
    bad_spec["total_score"] = 120
    p = tmp / "spec_bad.json"
    p.write_text(json.dumps(bad_spec, ensure_ascii=False), encoding="utf-8")
    case("T02 分值不一致应告警",
         ["scripts/blueprint.py", "--spec", str(p), "--out", str(tmp / "bp_bad.md")],
         expect_code=0, expect_err_in=["WARN"])

    # 3 缺少 sections 应报错
    p2 = tmp / "spec_empty.json"
    p2.write_text(json.dumps({"title": "x", "sections": []}), encoding="utf-8")
    case("T03 空 sections 应报错",
         ["scripts/blueprint.py", "--spec", str(p2)], expect_code=2)

    # 4 学情统计
    out_st = tmp / "stats.md"
    ok, raw = case("T04 成绩统计生成",
                   ["scripts/item_stats.py", "--csv", str(FIX / "scores.csv"),
                    "--full", str(FIX / "full.json"), "--out", str(out_st)],
                   expect_in=["已生成"])
    if out_st.exists():
        st_text = out_st.read_text(encoding="utf-8")
        cond = "参考人数" in st_text and "得分率" in st_text
        results.append({"name": "T04b 统计报告字段完整", "ok": cond,
                        "detail": "含参考人数与得分率" if cond else "字段缺失", "cmd": "-"})
        print(("PASS " if cond else "FAIL ") + "T04b 统计报告字段完整")
    if out_st.exists():
        text = out_st.read_text(encoding="utf-8")
        cond = "| 11 | 100 |" in text and "缺考" in text
        results.append({"name": "T05 缺考行被排除（12 行 → 11 人）", "ok": cond,
                        "detail": "统计到 11 人且提示缺考" if cond else "人数或缺考提示不符", "cmd": "-"})
        print(("PASS " if cond else "FAIL ") + "T05 缺考行被排除（12 行 → 11 人）")

    # 6 列名不匹配应报错
    p3 = tmp / "full_bad.json"
    p3.write_text(json.dumps({"sections": {"听力": 30}}, ensure_ascii=False), encoding="utf-8")
    case("T06 列名不匹配应报错",
         ["scripts/item_stats.py", "--csv", str(FIX / "scores.csv"), "--full", str(p3)],
         expect_code=2)

    # 7 写作折算
    ok, raw = case("T07 读后续写折算",
                   ["scripts/essay_score.py", "--type", "continuation",
                    "--content", "4", "--language", "4", "--structure", "3", "--cohesion", "3"],
                   expect_in=["第四档", "18.5"])
    case("T08 应用文满分需复核",
         ["scripts/essay_score.py", "--type", "app",
          "--content", "5", "--language", "5", "--structure", "5", "--cohesion", "5"],
         expect_in=["第五档", "需复核"])
    case("T09 维度越界应报错",
         ["scripts/essay_score.py", "--type", "app",
          "--content", "9", "--language", "4", "--structure", "3", "--cohesion", "3"],
         expect_code=2)

    # 10 成品自检：合格样卷
    case("T10 合格样卷自检通过",
         ["scripts/qa_check.py", "--paper", str(FIX / "paper.md"), "--answers", str(FIX / "answers.md")],
         expect_in=["未发现占位符", "结论：FAIL 0 项"])
    # 11 缺陷样卷应失败
    case("T11 缺陷样卷应报错",
         ["scripts/qa_check.py", "--paper", str(FIX / "paper_bad.md")],
         expect_code=1, expect_in=["占位符", "缺号"])

    passed = sum(1 for r in results if r["ok"])
    total = len(results)
    print(f"\n合计：{passed}/{total} 通过")

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"# 回归测试记录（{stamp}）", "",
             f"- 运行环境：Python {sys.version.split()[0]} / {sys.platform}",
             f"- 结果：**{passed}/{total} 通过**", "",
             "| 用例 | 命令 | 结果 | 说明 |", "|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r['name']} | `{r['cmd']}` | {'PASS' if r['ok'] else 'FAIL'} | {r['detail']} |")
    (ROOT / "tests" / "last_run.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
