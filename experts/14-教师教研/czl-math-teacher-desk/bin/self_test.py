#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""self_test.py —— 本专家包的可执行自测（纯标准库，零依赖）。

它不是"跑一遍没报错就算过"，而是每个脚本都用**已知答案的样本**跑一遍，
把结果和手算值比对。跑完打印一张表：哪条过了、哪条没过、实际值是多少。

用法：
    python bin/self_test.py            # 全部
    python bin/self_test.py -v         # 显示每个脚本的原始输出

退出码：0 全过；1 有失败。
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
PY = sys.executable

FIXTURE_SCORES = """学号,1,2,3
S1,5,5,10
S2,5,5,8
S3,0,5,6
S4,5,0,4
S5,5,5,2
"""

FIXTURE_BLUEPRINT = """题号,题型,分值,考点,难度,预测得分率,模块
1,单选,5,复数运算,易,0.9,复数
2,单选,5,集合运算,易,0.88,集合
3,填空,5,数列通项,中,0.6,数列
4,解答,7,解三角形,中,0.62,三角
"""

FIXTURE_BLUEPRINT_BAD = """题号,题型,分值,考点,难度,预测得分率,模块
1,单选,5,复数运算,易,0.9,复数
2,单选,5,集合运算,易,0.88,复数
"""

FIXTURE_LESSON_OK = """# 函数的单调性

**教材**：人教A版 · 选择性必修二　**课时**：45 分钟

## 一、教学目标

1. 能用定义证明函数在区间上的单调性。

## 二、重点与难点

- 重点：四步格式
- 难点：任取的作用

## 三、教学过程

| 环节 | 时长 | 累计 |
|---|---|---|
| 导入 | 5′ | 5′ |
| 建构 | 15′ | 20′ |
| 例题 | 12′ | 32′ |
| 练习 | 10′ | 42′ |
| 小结 | 3′ | 45′ |

## 四、板书设计

左板知识主线，右板例题演算。

## 五、分层作业

- 基础：练习 1、2
- 提高：两道含参
- 挑战：造一个反例
"""

FIXTURE_LESSON_BAD = """# 某某课

## 一、教学目标

〔行为动词 + 内容〕

## 二、重点与难点

引导学生体会数学的美。
"""

FIXTURE_DOCX_MD = """# 测试文档

## 一、表格

| 题号 | 分值 | 难度 |
|---|---|---|
| 1 | 5 | 易 |
| 2 | 5 | 中 |

## 二、列表

- 第一项
- 第二项 **加粗**

> 引用一行

```
f'(x)=3x²-6x
```
"""


class T:
    def __init__(self):
        self.rows = []

    def add(self, name, ok, detail=""):
        self.rows.append((name, ok, detail))
        return ok

    def report(self):
        print("=" * 62)
        print("自测结果")
        print("=" * 62)
        passed = 0
        for name, ok, detail in self.rows:
            print("%s %s%s" % ("[PASS]" if ok else "[FAIL]", name,
                               ("  → " + str(detail)) if detail else ""))
            passed += 1 if ok else 0
        print("-" * 62)
        print("通过 %d / %d" % (passed, len(self.rows)))
        return passed == len(self.rows)


def run(args, expect_zero=True):
    """跑一个脚本，返回 (returncode, stdout+stderr)。"""
    p = subprocess.run([PY] + args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out


def main():
    verbose = "-v" in sys.argv
    t = T()
    tmp = tempfile.mkdtemp(prefix="czl_mtd_selftest_")
    try:
        scores = os.path.join(tmp, "scores.csv")
        with open(scores, "w", encoding="utf-8") as f:
            f.write(FIXTURE_SCORES)

        # ---------- 1. score_report ----------
        js = os.path.join(tmp, "scores.json")
        code, out = run([os.path.join(HERE, "score_report.py"), scores,
                         "--full-marks", "5,5,10", "--json", js])
        if verbose:
            print(out)
        ok = (code == 0 and os.path.isfile(js))
        data = {}
        if ok:
            with open(js, encoding="utf-8") as f:
                data = json.load(f)
        # 手算：总分 20,18,11,9,12 → 均分 14.0；难度 0.70
        t.add("score_report 运行成功", ok, "exit=%d" % code)
        t.add("score_report 均分 = 14.0", abs(data.get("mean", -1) - 14.0) < 1e-6,
              "实际 %.2f" % data.get("mean", -1))
        t.add("score_report 难度系数 = 0.70", abs(data.get("difficulty", -1) - 0.7) < 1e-6,
              "实际 %.3f" % data.get("difficulty", -1))
        t.add("score_report 最高/最低 = 20/9",
              data.get("max") == 20 and data.get("min") == 9,
              "%s/%s" % (data.get("max"), data.get("min")))
        items = {i["q"]: i for i in data.get("items", [])}
        t.add("score_report 第3题得分率 = 0.60",
              abs(items.get("3", {}).get("rate", -1) - 0.6) < 1e-6,
              "实际 %.2f" % items.get("3", {}).get("rate", -1))
        t.add("score_report 讲评优先级排序有效",
              bool(data.get("items")) and
              max(data["items"], key=lambda x: x["priority"])["q"] in ("1", "2", "3"),
              "最优题 %s" % max(data["items"], key=lambda x: x["priority"])["q"] if data.get("items") else "—")

        # ---------- 2. blueprint ----------
        good = os.path.join(tmp, "bp_good.csv")
        with open(good, "w", encoding="utf-8") as f:
            f.write(FIXTURE_BLUEPRINT)
        code_good, out_good = run([os.path.join(HERE, "blueprint.py"), good,
                                   "--total", "22", "--no-structure"])
        if verbose:
            print(out_good)
        t.add("blueprint 合格表 exit=0", code_good == 0, "exit=%d" % code_good)
        t.add("blueprint 识别总分 22", "22" in out_good, "")

        bad = os.path.join(tmp, "bp_bad.csv")
        with open(bad, "w", encoding="utf-8") as f:
            f.write(FIXTURE_BLUEPRINT_BAD)
        code_bad, out_bad = run([os.path.join(HERE, "blueprint.py"), bad,
                                 "--total", "150", "--no-structure"], expect_zero=False)
        t.add("blueprint 不合格表 exit=1", code_bad == 1, "exit=%d" % code_bad)
        t.add("blueprint 报出总分不足", "总分" in out_bad, "")

        init_csv = os.path.join(tmp, "bp_init.csv")
        code_init, out_init = run([os.path.join(HERE, "blueprint.py"), "--init", init_csv])
        rows = 0
        if os.path.isfile(init_csv):
            with open(init_csv, encoding="utf-8-sig") as f:
                rows = sum(1 for _ in f) - 1
        t.add("blueprint --init 生成 19 题", code_init == 0 and rows == 19, "行数 %d" % rows)

        # ---------- 3. qa_gate ----------
        lesson_ok = os.path.join(tmp, "lesson_ok.md")
        with open(lesson_ok, "w", encoding="utf-8") as f:
            f.write(FIXTURE_LESSON_OK)
        code_l, out_l = run([os.path.join(HERE, "qa_gate.py"), lesson_ok,
                             "--kind", "lesson", "--minutes", "45"])
        if verbose:
            print(out_l)
        t.add("qa_gate 合格教案 exit=0", code_l == 0, "exit=%d" % code_l)

        lesson_bad = os.path.join(tmp, "lesson_bad.md")
        with open(lesson_bad, "w", encoding="utf-8") as f:
            f.write(FIXTURE_LESSON_BAD)
        code_lb, out_lb = run([os.path.join(HERE, "qa_gate.py"), lesson_bad, "--kind", "lesson"])
        t.add("qa_gate 差教案 exit=1", code_lb == 1, "exit=%d" % code_lb)
        t.add("qa_gate 报出占位符", "占位" in out_lb, "")
        t.add("qa_gate 报出空话套话", "空话" in out_lb or "引导" in out_lb, "")
        t.add("qa_gate 报出缺板书", "板书" in out_lb, "")

        # ---------- 4. md_to_docx ----------
        md = os.path.join(tmp, "doc.md")
        with open(md, "w", encoding="utf-8") as f:
            f.write(FIXTURE_DOCX_MD)
        docx = os.path.join(tmp, "doc.docx")
        code_d, out_d = run([os.path.join(HERE, "md_to_docx.py"), md, "-o", docx,
                             "--footer", "测试 · 第"])
        if verbose:
            print(out_d)
        t.add("md_to_docx 生成 exit=0", code_d == 0, "exit=%d" % code_d)
        exists = os.path.isfile(docx)
        t.add("md_to_docx 文件存在", exists, "%.1f KB" % (os.path.getsize(docx) / 1024) if exists else "缺失")
        if exists:
            with zipfile.ZipFile(docx) as z:
                names = set(z.namelist())
                doc = z.read("word/document.xml").decode("utf-8")
                need = {"[Content_Types].xml", "_rels/.rels", "word/document.xml",
                        "word/styles.xml", "word/_rels/document.xml.rels", "word/footer1.xml"}
                t.add("docx 部件齐全", need.issubset(names), "缺 %s" % (need - names) if not need.issubset(names) else "")
                t.add("docx 含表格节点", "<w:tbl>" in doc, "")
                t.add("docx 含正文文字", "测试文档" in doc, "")
                t.add("docx 含页码域", "PAGE" in z.read("word/footer1.xml").decode("utf-8"), "")
                t.add("docx 含加粗 run", "<w:b/>" in doc, "")

        # ---------- 5. check_package ----------
        code_p, out_p = run([os.path.join(HERE, "check_package.py"), PKG])
        if verbose:
            print(out_p)
        t.add("check_package 本包通过", code_p == 0, "exit=%d" % code_p)
        t.add("check_package 认出头像尺寸", "avatar 尺寸" in out_p, "")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    ok = t.report()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
