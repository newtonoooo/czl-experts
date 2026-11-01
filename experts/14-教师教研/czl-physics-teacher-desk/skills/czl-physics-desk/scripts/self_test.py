#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全量自检：把五个脚本各跑一遍，检查输出是否成立。

用法：python self_test.py
返回：0 全部通过；1 有失败项
"""

import os
import random
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def run(args, expect=0):
    p = subprocess.run(args, cwd=HERE, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def w(path, text, encoding="utf-8-sig"):
    with open(path, "w", encoding=encoding, newline="") as f:
        f.write(text)


GOOD_BLUEPRINT = (
    "题号,题型,考点,认知层级,难度,分值,用时\n"
    "1,单选,匀变速图像,识记,0.85,4,1.5\n"
    "2,单选,摩擦力方向,理解,0.80,4,1.5\n"
    "3,单选,超重失重,理解,0.75,4,1.5\n"
    "4,单选,功率估算,理解,0.80,4,1.5\n"
    "5,多选,连接体,应用,0.60,6,3\n"
    "6,多选,圆周临界,应用,0.55,6,3\n"
    "7,实验,打点计时器,应用,0.70,8,9\n"
    "8,实验,测电动势内阻,应用,0.65,10,9\n"
    "9,计算,多过程动力学,分析,0.60,12,10\n"
    "10,计算,功能关系,分析,0.50,14,12\n"
    "11,计算,动量能量综合,分析,0.40,16,13\n"
    "12,计算,带电粒子运动,应用,0.55,12,12\n"
)


def case_blueprint(tmp):
    src = os.path.join(tmp, "bp.csv")
    out = os.path.join(tmp, "bp.md")
    w(src, GOOD_BLUEPRINT)
    code, log = run([PY, "blueprint.py", "--in", src, "--out", out,
                     "--total", "100", "--difficulty", "0.60", "--minutes", "100"])
    md = open(out, encoding="utf-8").read() if os.path.exists(out) else ""
    ok = code == 0 and "校验汇总" in md and "校验通过" in md
    return ok, log.strip().splitlines()[-1] if log.strip() else ""


def case_blueprint_guard(tmp):
    """负向测试：总分不符时必须拦下（返回码 1 且提示）。"""
    src = os.path.join(tmp, "bp_bad.csv")
    out = os.path.join(tmp, "bp_bad.md")
    w(src, GOOD_BLUEPRINT)
    code, log = run([PY, "blueprint.py", "--in", src, "--out", out, "--total", "90", "--difficulty", "0.60"])
    md = open(out, encoding="utf-8").read() if os.path.exists(out) else ""
    ok = code == 1 and "需要修改" in md and "≠ 目标总分" in md
    return ok, "总分不符已被拦截" if ok else ""


def case_rubric(tmp):
    src = os.path.join(tmp, "rb.csv")
    out = os.path.join(tmp, "rb.md")
    w(src, "问,步骤,分值,说明\n1,画受力图,1,\n1,写牛顿第二定律方程,2,符号错给1分\n"
          "1,代入得a=2.0m/s²,1,无单位扣0.5\n2,判断两段过程,2,\n2,结果x=12m,2,\n")
    code, log = run([PY, "rubric_builder.py", "--in", src, "--out", out, "--total", "8"])
    md = open(out, encoding="utf-8").read() if os.path.exists(out) else ""
    ok = code == 0 and "合计" in md and "**8**" in md
    return ok, log.strip().splitlines()[-1] if log.strip() else ""


def case_item(tmp):
    scores = os.path.join(tmp, "scores.csv")
    out = os.path.join(tmp, "report.md")
    random.seed(7)
    header = "学号," + ",".join(f"Q{i}" for i in range(1, 7))
    full = [4, 4, 6, 8, 12, 14]
    lines = [header]
    for sid in range(1, 41):
        row = [f"{sid:02d}"]
        ability = random.gauss(0.62, 0.18)
        for f in full:
            p = min(max(ability + random.gauss(0, 0.12), 0.02), 0.99)
            row.append(str(round(f * p * 2) / 2))
        lines.append(",".join(row))
    w(scores, "\n".join(lines) + "\n")
    code, log = run([PY, "item_analysis.py", "--scores", scores, "--full-marks", ",".join(map(str, full)),
                     "--out", out, "--class", "自检班"])
    md = open(out, encoding="utf-8").read() if os.path.exists(out) else ""
    ok = code == 0 and "学情分析报告" in md and "区分度" in md and "讲评选题建议" in md and "40" in md
    return ok, log.strip().splitlines()[-1] if log.strip() else ""


def case_calc(tmp):
    code, log = run([PY, "physics_calc.py", "--self-check"])
    ok = code == 0 and "通过" in log
    tail = [x for x in log.strip().splitlines() if x.strip().endswith("通过")]
    return ok, tail[-1] if tail else log.strip()[-80:]


def case_docx(tmp):
    src = os.path.join(tmp, "demo.md")
    out = os.path.join(tmp, "demo.docx")
    w(src, "# 自检\n\n## 一、表格\n\n| 环节 | 时间 |\n|---|---|\n| 导入 | 3′ |\n| 探究 | 22′ |\n\n"
          "- 条目一\n- 条目二\n\n**加粗** 与 `代码`\n\n<!--pagebreak-->\n\n## 二、第二页\n\n正文。\n", "utf-8")
    code, log = run([PY, "docx_lite.py", "--in", src, "--out", out, "--title", "自检", "--meta", "高二"])
    ok = False
    detail = ""
    if code == 0 and os.path.exists(out):
        with zipfile.ZipFile(out) as z:
            names = set(z.namelist())
            doc = z.read("word/document.xml").decode("utf-8")
        need = {"word/document.xml", "word/styles.xml", "word/header1.xml", "word/footer1.xml"}
        ok = need.issubset(names) and "<w:tbl>" in doc and 'w:type="page"' in doc and "sectPr" in doc
        detail = f"{os.path.getsize(out) / 1024:.1f} KB，部件 {len(names)} 个"
    return ok, detail


CASES = [
    ("blueprint 双向细目表", case_blueprint),
    ("blueprint 负向拦截（总分不符）", case_blueprint_guard),
    ("rubric_builder 评分细则", case_rubric),
    ("item_analysis 学情分析", case_item),
    ("physics_calc 公式计算", case_calc),
    ("docx_lite 打印版导出", case_docx),
]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(f"Python {sys.version.split()[0]}  |  脚本目录 {HERE}\n")
    passed = 0
    with tempfile.TemporaryDirectory() as tmp:
        for name, fn in CASES:
            try:
                ok, detail = fn(tmp)
            except Exception as e:
                ok, detail = False, f"异常：{type(e).__name__}: {e}"
            print(("PASS  " if ok else "FAIL  ") + name + (f"  ({detail})" if detail else ""))
            passed += 1 if ok else 0
    print(f"\n{passed}/{len(CASES)} 通过")
    return 0 if passed == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(main())
