#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_tests.py — 专家包功能自测（本地可重复运行）

覆盖：包结构、资源引用、头像规格、三个工具脚本的正常与异常路径、docx 结构、头像内嵌与还原。
用法：
    python tests/run_tests.py
退出码：0 全部通过；1 有失败项。
"""

import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
RESULTS = []


def record(name, ok, detail=""):
    RESULTS.append((name, ok, detail))


def run(args, cwd=None):
    p = subprocess.run(args, cwd=cwd or ROOT, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def load_manifest():
    p = os.path.join(ROOT, ".codebuddy-plugin", "plugin.json")
    with open(p, "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_manifest(m):
    ok = all(k in m for k in ("name", "version", "expertType", "agentName", "displayName",
                              "profession", "displayDescription", "avatar", "tags", "quickPrompts"))
    record("清单必填字段", ok, "" if ok else "缺字段")
    record("tags=3", len(m.get("tags", [])) == 3, str(len(m.get("tags", []))))
    record("quickPrompts=3", len(m.get("quickPrompts", [])) == 3, str(len(m.get("quickPrompts", []))))
    record("名称合规（无空格/特殊字符）",
           " " not in m["displayName"]["zh"] and m["displayName"]["zh"].count("-") == 1,
           m["displayName"]["zh"])
    record("包名 czl- 前缀", m["name"].startswith("czl-"), m["name"])


def test_resources(m):
    agent = os.path.join(ROOT, "agents", m["agentName"] + ".md")
    record("Agent MD 存在", os.path.exists(agent), os.path.relpath(agent, ROOT))
    for rel in m.get("skills", []):
        record(f"技能路径 {rel}", os.path.exists(os.path.normpath(os.path.join(ROOT, rel))), "")
    wf = os.path.join(ROOT, "workflows")
    files = sorted(f for f in os.listdir(wf) if f.endswith(".md")) if os.path.isdir(wf) else []
    record("工作流 8 个", len(files) == 8, f"{len(files)} 个")
    refs = os.listdir(os.path.join(ROOT, "references")) if os.path.isdir(os.path.join(ROOT, "references")) else []
    record("参考资料 ≥6 份", len([r for r in refs if r.endswith(".md")]) >= 6, f"{len(refs)} 个")


def test_avatar(m):
    p = os.path.join(ROOT, m["avatar"])
    if not os.path.exists(p):
        record("头像文件存在", False, m["avatar"])
        return
    with open(p, "rb") as fh:
        head = fh.read(33)
    w, h = struct.unpack(">II", head[16:24])
    kb = os.path.getsize(p) / 1024
    record("头像为合法 PNG", head[:8] == b"\x89PNG\r\n\x1a\n", "")
    record("头像 512×512", (w, h) == (512, 512), f"{w}x{h}")
    record("头像 <500KB", kb < 500, f"{kb:.0f} KB")


def test_score_report(tmp):
    out = os.path.join(tmp, "report.md")
    code, log = run([PY, "skills/czl-bio-teacher-kit/scripts/score_report.py",
                     "-i", "tests/samples/scores-sample.csv",
                     "-f", "2,2,2,4,6,8,6,10", "-o", out,
                     "--sections", "1-4:基础判断,5-8:综合应用", "--title", "自测"])
    ok = code == 0 and os.path.exists(out)
    text = open(out, encoding="utf-8").read() if os.path.exists(out) else ""
    record("score_report 正常路径", ok and "均分" in text and "板块得分率" in text, f"exit={code}")
    record("score_report 缺考处理", "缺考 1" in text, "应识别 1 名缺考")

    bad = os.path.join(tmp, "bad.csv")
    with open(bad, "w", encoding="utf-8") as fh:
        fh.write("学号,Q1,Q2\nS1,1,1\n")
    code2, _ = run([PY, "skills/czl-bio-teacher-kit/scripts/score_report.py",
                    "-i", bad, "-f", "2,2,2"])
    record("score_report 参数异常报错", code2 == 2, f"exit={code2}")


def test_blueprint(tmp):
    code, log = run([PY, "skills/czl-bio-teacher-kit/scripts/blueprint_check.py",
                     "-i", "skills/czl-bio-teacher-kit/templates/blueprint-sample.csv",
                     "--total", "100", "--profile", "unit"])
    record("blueprint 正常路径", code == 0 and "通过" in log, f"exit={code}")

    bad = os.path.join(tmp, "bad-blueprint.csv")
    with open(bad, "w", encoding="utf-8") as fh:
        fh.write("题号,考点,认知层级,题型,分值,预估难度\n1,考点甲,记忆,单选,60,易\n2,考点乙,分析,简答,30,难\n")
    code2, log2 = run([PY, "skills/czl-bio-teacher-kit/scripts/blueprint_check.py",
                       "-i", bad, "--total", "100"])
    record("blueprint 分值不闭合拦截", code2 == 1 and "不一致" in log2, f"exit={code2}")


def test_docx(tmp):
    out = os.path.join(tmp, "test.docx")
    code, log = run([PY, "skills/czl-bio-teacher-kit/scripts/make_docx.py",
                     "-i", "tests/samples/lesson-sample.md", "-o", out, "--title", "自测"])
    ok = code == 0 and os.path.exists(out)
    record("make_docx 生成", ok, f"exit={code}")
    if not ok:
        return
    z = zipfile.ZipFile(out)
    record("docx 包完整", z.testzip() is None, "")
    names = z.namelist()
    need = {"[Content_Types].xml", "word/document.xml", "word/styles.xml", "word/footer1.xml"}
    record("docx 必需部件齐全", need.issubset(set(names)), ",".join(sorted(need - set(names))))
    try:
        for n in names:
            if n.endswith((".xml", ".rels")):
                ET.fromstring(z.read(n))
        parse_ok = True
    except Exception as exc:  # noqa: BLE001
        parse_ok = False
        record("docx XML 解析", False, str(exc))
    if parse_ok:
        record("docx XML 解析", True, "")
    doc = z.read("word/document.xml").decode("utf-8")
    record("docx 保留表格", doc.count("<w:tbl>") >= 2, f"{doc.count('<w:tbl>')} 个")
    record("docx A4 版面", 'w:w="11906"' in doc, "")


def test_avatar_switch(tmp):
    work = os.path.join(tmp, "pkg")
    if os.path.exists(work):
        shutil.rmtree(work)
    shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns("dist", "__pycache__", ".git"))
    code, log = run([PY, "bin/set_local_avatar.py", "--expert-dir", work, "--size", "192"], cwd=work)
    m = json.load(open(os.path.join(work, ".codebuddy-plugin", "plugin.json"), encoding="utf-8"))
    record("头像内嵌为 data URI", code == 0 and m["avatar"].startswith("data:image/png;base64,"), f"exit={code}")
    code2, _ = run([PY, "bin/set_local_avatar.py", "--expert-dir", work, "--restore"], cwd=work)
    m2 = json.load(open(os.path.join(work, ".codebuddy-plugin", "plugin.json"), encoding="utf-8"))
    record("头像还原为相对路径", code2 == 0 and m2["avatar"] == "avatars/expert.png", m2["avatar"])


def main() -> int:
    m = load_manifest()
    tmp = tempfile.mkdtemp(prefix="czl-bio-test-")
    try:
        test_manifest(m)
        test_resources(m)
        test_avatar(m)
        test_score_report(tmp)
        test_blueprint(tmp)
        test_docx(tmp)
        test_avatar_switch(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"专家包自测：{ROOT}\n")
    for name, ok, detail in RESULTS:
        flag = "PASS" if ok else "FAIL"
        print(f"[{flag}] {name}" + (f"  — {detail}" if detail else ""))
    print(f"\n合计 {len(RESULTS)} 项，通过 {passed} 项，失败 {len(RESULTS)-passed} 项")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
