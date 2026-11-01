#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_tests.py - regression tests for the czl-product-decision-audit package.

Runs the three shipped tools against fixed fixtures, checks exit codes and key
output lines, then validates the package structure itself (plugin.json fields,
agent frontmatter, skill entry points, avatar).

Usage
-----
    python tests/run_tests.py
    python tests/run_tests.py -v

Exit code 0 = all passed.
"""

from __future__ import annotations

import json
import os
import py_compile
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EVIDENCE_DIR = os.path.join(ROOT, "skills", "evidence-ledger", "scripts")
METRIC_DIR = os.path.join(ROOT, "skills", "metric-integrity", "scripts")
PORTFOLIO_DIR = os.path.join(ROOT, "skills", "portfolio-fit", "scripts")

RESULTS = []


def run(script_dir, script, args, timeout=90):
    cmd = [sys.executable, os.path.join(script_dir, script)] + args
    proc = subprocess.run(
        cmd,
        cwd=script_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def check(name, condition, detail=""):
    RESULTS.append({"name": name, "ok": bool(condition), "detail": detail})
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f"  <- {detail}" if not condition and detail else ""))


def expect(name, script_dir, script, args, want_code=None, want_text=None, forbid_text=None):
    code, out = run(script_dir, script, args)
    ok = True
    detail = []
    if want_code is not None and code != want_code:
        ok = False
        detail.append(f"exit {code} != {want_code}")
    for text in want_text or []:
        if text not in out:
            ok = False
            detail.append(f"missing {text!r}")
    for text in forbid_text or []:
        if text in out:
            ok = False
            detail.append(f"unexpected {text!r}")
    check(name, ok, "; ".join(detail) + ("" if ok else "\n    " + out.strip()[:400]))
    return out


def main():
    verbose = "-v" in sys.argv

    print("=" * 70)
    print("1. evidence_check.py")
    print("=" * 70)
    expect(
        "坏台账：识别越级措辞 / 小样本百分比 / 用途门槛不足",
        EVIDENCE_DIR,
        "evidence_check.py",
        ["fixtures/ledger_bad.csv", "--conclusion-grade", "C", "--purpose", "invest"],
        want_code=1,
        want_text=["E_OVERCLAIM", "E_SMALL_N_PCT", "E_THRESHOLD"],
    )
    expect(
        "好台账：正常通过",
        EVIDENCE_DIR,
        "evidence_check.py",
        ["fixtures/ledger_good.csv", "--conclusion-grade", "B", "--purpose", "invest"],
        want_code=0,
        want_text=["通过"],
    )
    expect(
        "越级结论：D 级证据却给 B 级结论",
        EVIDENCE_DIR,
        "evidence_check.py",
        ["fixtures/ledger_overreach.csv", "--conclusion-grade", "B"],
        want_code=1,
        want_text=["E_OVERREACH"],
    )
    out = expect(
        "JSON 输出可被解析",
        EVIDENCE_DIR,
        "evidence_check.py",
        ["fixtures/ledger_good.csv", "--json"],
        want_code=0,
    )
    try:
        payload = json.loads(out)
        check("JSON 结构含 rows / grade_counts / strongest", "rows" in payload and "grade_counts" in payload)
    except json.JSONDecodeError as exc:
        check("JSON 结构可解析", False, str(exc))

    with tempfile.TemporaryDirectory() as tmp:
        bad_cols = os.path.join(tmp, "bad_columns.csv")
        with open(bad_cols, "w", encoding="utf-8") as fh:
            fh.write("id,note\n1,缺列\n")
        expect(
            "缺必需列：退出码 2",
            EVIDENCE_DIR,
            "evidence_check.py",
            [bad_cols],
            want_code=2,
        )

    print()
    print("=" * 70)
    print("2. metric_guard.py")
    print("=" * 70)
    expect(
        "口径卡：识别缺失字段与过短定义",
        METRIC_DIR,
        "metric_guard.py",
        ["card", "fixtures/metric_cards_bad.csv"],
        want_code=1,
        want_text=["E_MISSING", "E_SHORT_DEF"],
    )
    expect(
        "口径卡：完整卡片通过",
        METRIC_DIR,
        "metric_guard.py",
        ["card", "fixtures/metric_cards_good.csv"],
        want_code=0,
        want_text=["通过"],
    )
    expect(
        "A/B 显著且为正：给出可采信结论",
        METRIC_DIR,
        "metric_guard.py",
        ["ab", "--control", "10000", "512", "--treat", "10000", "583"],
        want_code=0,
        want_text=["统计上显著", "结论方向可以采信"],
    )
    expect(
        "A/B 不显著：给出样本需求量",
        METRIC_DIR,
        "metric_guard.py",
        ["ab", "--control", "5000", "250", "--treat", "5000", "270"],
        want_code=0,
        want_text=["未达统计显著", "每组约需"],
    )
    expect(
        "A/B 显著但为负：建议不上线",
        METRIC_DIR,
        "metric_guard.py",
        ["ab", "--control", "8000", "640", "--treat", "8000", "520"],
        want_code=0,
        want_text=["不要上线"],
    )
    expect(
        "A/B 非法输入：转化数大于样本量",
        METRIC_DIR,
        "metric_guard.py",
        ["ab", "--control", "100", "200", "--treat", "100", "10"],
        want_code=2,
    )
    expect(
        "辛普森反转：合计与组内方向相反",
        METRIC_DIR,
        "metric_guard.py",
        ["simpson", "fixtures/segments_simpson.csv"],
        want_code=1,
        want_text=["辛普森反转"],
    )
    expect(
        "波动带：平稳序列判为噪声",
        METRIC_DIR,
        "metric_guard.py",
        ["baseline", "412,401,398,420,405,410,388,402,395,418,406,410"],
        want_code=0,
        want_text=["属于噪声"],
    )
    expect(
        "波动带：突刺判为真实变化",
        METRIC_DIR,
        "metric_guard.py",
        ["baseline", "400,402,398,401,399,403,401,400,402,399,401,560"],
        want_code=0,
        want_text=["超出正常带"],
    )

    print()
    print("=" * 70)
    print("3. portfolio_fit.py")
    print("=" * 70)
    expect(
        "产能不足：产出砍单清单与脆弱项",
        PORTFOLIO_DIR,
        "portfolio_fit.py",
        ["fixtures/backlog_sample.csv", "--headcount", "5", "--weeks", "12", "--history", "6"],
        want_code=1,
        want_text=["砍单清单", "脆弱项", "计划量高于历史吞吐"],
    )
    expect(
        "产能充足：全部排入",
        PORTFOLIO_DIR,
        "portfolio_fit.py",
        ["fixtures/backlog_sample.csv", "--headcount", "20", "--weeks", "20"],
        want_code=0,
        want_text=["全部排入"],
    )
    expect(
        "吞吐之内：不再提示延期",
        PORTFOLIO_DIR,
        "portfolio_fit.py",
        ["fixtures/backlog_sample.csv", "--headcount", "5", "--weeks", "12", "--history", "10"],
        forbid_text=["计划量高于历史吞吐"],
    )
    expect(
        "JSON 输出可用",
        PORTFOLIO_DIR,
        "portfolio_fit.py",
        ["fixtures/backlog_sample.csv", "--headcount", "5", "--json"],
        want_code=1,
        want_text=['"capacity_person_weeks"'],
    )
    with tempfile.TemporaryDirectory() as tmp:
        bad_cols = os.path.join(tmp, "bad_backlog.csv")
        with open(bad_cols, "w", encoding="utf-8") as fh:
            fh.write("id,name\n1,缺列\n")
        expect(
            "缺必需列：退出码 2",
            PORTFOLIO_DIR,
            "portfolio_fit.py",
            [bad_cols, "--headcount", "3"],
            want_code=2,
        )

    print()
    print("=" * 70)
    print("4. 语法编译检查")
    print("=" * 70)
    for script_dir, script in [
        (EVIDENCE_DIR, "evidence_check.py"),
        (METRIC_DIR, "metric_guard.py"),
        (PORTFOLIO_DIR, "portfolio_fit.py"),
    ]:
        path = os.path.join(script_dir, script)
        try:
            py_compile.compile(path, doraise=True, cfile=os.path.join(tempfile.gettempdir(), script + "c"))
            check(f"{script} 编译通过", True)
        except py_compile.PyCompileError as exc:
            check(f"{script} 编译通过", False, str(exc))

    print()
    print("=" * 70)
    print("5. 包结构检查")
    print("=" * 70)
    pj_path = os.path.join(ROOT, ".codebuddy-plugin", "plugin.json")
    try:
        with open(pj_path, encoding="utf-8") as fh:
            pj = json.load(fh)
        check("plugin.json 可解析", True)
    except Exception as exc:  # noqa: BLE001
        check("plugin.json 可解析", False, str(exc))
        pj = {}

    check("name 以 czl- 开头且为 kebab-case", pj.get("name") == ROOT.split(os.sep)[-1])
    check("author 为虫志龙", pj.get("author", {}).get("name") == "虫志龙")
    check("author email 正确", pj.get("author", {}).get("email") == "47190078@qq.com")
    check("tags 恰好 3 个", len(pj.get("tags", [])) == 3)
    check("quickPrompts 恰好 3 个", len(pj.get("quickPrompts", [])) == 3)
    qp = pj.get("quickPrompts", [{}])
    check(
        "defaultInitPrompt == quickPrompts[0]",
        pj.get("defaultInitPrompt", {}).get("zh") == qp[0].get("zh") if qp else False,
    )
    check("plugin 字段等于 name", pj.get("plugin") == pj.get("name"))
    check("expertType 为 agent", pj.get("expertType") == "agent")

    desc_zh = pj.get("displayDescription", {}).get("zh", "")
    check(f"displayDescription.zh 长度 40-50（实际 {len(desc_zh)}）", 40 <= len(desc_zh) <= 50)

    avatar_path = os.path.join(ROOT, pj.get("avatar", ""))
    avatar_ok = os.path.exists(avatar_path)
    check("头像文件存在", avatar_ok)
    if avatar_ok:
        size = os.path.getsize(avatar_path)
        check(f"头像 ≤500KB（实际 {size // 1024}KB）", size <= 500 * 1024)

    agents = pj.get("agents", [])
    check("agents 路径全部存在", all(os.path.exists(os.path.join(ROOT, a[2:])) for a in agents))

    skills = pj.get("skills", [])
    check("skills 数量为 7", len(skills) == 7)
    all_skill_ok = all(
        os.path.exists(os.path.join(ROOT, s[2:], "SKILL.md")) for s in skills
    )
    check("每个 skill 目录都有 SKILL.md", all_skill_ok)

    agent_md = os.path.join(ROOT, "agents", f"{pj.get('agentName', 'x')}.md")
    if os.path.exists(agent_md):
        with open(agent_md, encoding="utf-8") as fh:
            content = fh.read()
        head = content.split("---")[1] if content.startswith("---") else ""
        check("frontmatter 不含 tools 字段", "tools:" not in head)
        check("frontmatter name 与文件名一致", f"name: {pj.get('agentName')}" in head)
        check("正文含五道闸", "G1 分诊" in content and "G5 交付" in content)
        check("正文含输出契约", "决策包" in content)
    else:
        check("agent md 存在", False, agent_md)

    forbidden = [d for d in ("hooks", "commands") if os.path.isdir(os.path.join(ROOT, d))]
    check("无禁用目录 hooks/ commands/", not forbidden, str(forbidden))
    check("无 .lsp.json", not os.path.exists(os.path.join(ROOT, ".lsp.json")))

    print()
    print("=" * 70)
    print("6. 交叉引用完整性")
    print("=" * 70)
    skill_names = [os.path.basename(s.rstrip("/")) for s in skills]
    if os.path.exists(agent_md):
        with open(agent_md, encoding="utf-8") as fh:
            agent_text = fh.read()
        referenced = [n for n in skill_names if "`" + n + "`" in agent_text]
        check(
            f"路由表引用了全部 7 个技能（实际 {len(referenced)}）",
            len(referenced) == 7,
            str(set(skill_names) - set(referenced)),
        )
        referenced_scripts = [
            "evidence_check.py",
            "metric_guard.py",
            "portfolio_fit.py",
            "run_tests.py",
        ]
        on_disk = set()
        for base, _dirs, files in os.walk(ROOT):
            for name in files:
                if name.endswith(".py"):
                    on_disk.add(name)
        absent = [s for s in referenced_scripts if s not in on_disk]
        check("文档中提到的脚本文件均存在", not absent, str(absent))

    missing_refs = []
    pattern = re.compile(r"(references/[A-Za-z0-9_\-]+\.md|scripts/[A-Za-z0-9_\-]+\.py)")
    for skill in skill_names:
        skill_dir = os.path.join(ROOT, "skills", skill)
        md = os.path.join(skill_dir, "SKILL.md")
        if not os.path.exists(md):
            continue
        with open(md, encoding="utf-8") as fh:
            body = fh.read()
        for rel in sorted(set(pattern.findall(body))):
            if not os.path.exists(os.path.join(skill_dir, rel)):
                missing_refs.append(f"{skill}: {rel}")
    check("技能内引用的 references/scripts 路径均存在", not missing_refs, str(missing_refs[:5]))

    print()
    print("=" * 70)
    passed = sum(1 for r in RESULTS if r["ok"])
    total = len(RESULTS)
    print(f"结果：{passed}/{total} 通过")
    if verbose:
        for r in RESULTS:
            print(("  ok   " if r["ok"] else "  FAIL ") + r["name"])
    failed = [r for r in RESULTS if not r["ok"]]
    if failed:
        print("\n失败项：")
        for r in failed:
            print(f"  - {r['name']}: {r['detail'][:300]}")
        return 1
    print("全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
