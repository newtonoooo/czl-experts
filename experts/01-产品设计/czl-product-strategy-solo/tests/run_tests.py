#!/usr/bin/env python3
"""Package self-test (solo edition).

Two halves:
  A. behaviour tests - every bundled script is run against a passing fixture and
     a failing fixture, and both the exit code and a signature line are asserted.
  B. structure tests - the manifest, agent file, avatar, skills and docs are
     checked against what the platform loader expects for a single-agent expert.

Standard library only. No network. Exit code 0 = all green.

Usage:
    python tests/run_tests.py [-v]
"""
import json
import os
import re
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
VERBOSE = "-v" in sys.argv

results = []


def record(name, ok, detail=""):
    results.append((name, ok, detail))
    if VERBOSE or not ok:
        print("%s %s%s" % ("[PASS]" if ok else "[FAIL]", name, ("  -> " + detail) if detail else ""))


def run(args, expect_code, expect_text=None):
    proc = subprocess.run([PY] + args, cwd=ROOT, capture_output=True)
    out = (proc.stdout or b"").decode("utf-8", "replace") + (proc.stderr or b"").decode("utf-8", "replace")
    ok = proc.returncode == expect_code
    if ok and expect_text and expect_text not in out:
        return False, "退出码正确但输出缺少签名「%s」" % expect_text
    if not ok:
        tail = out.strip().splitlines()[-1:] or [""]
        return False, "期望退出码 %d，实际 %d：%s" % (expect_code, proc.returncode, tail[0])
    return True, ""


def script_tests():
    S = "skills"
    cases = [
        ("证据台账-合格样例", ["%s/evidence-ledger/scripts/evidence_grade.py" % S, "--csv",
                               "%s/evidence-ledger/fixtures/ledger_good.csv" % S,
                               "--today", "2026-10-28"], 0, "结果：通过"),
        ("证据台账-不合格样例", ["%s/evidence-ledger/scripts/evidence_grade.py" % S, "--csv",
                                 "%s/evidence-ledger/fixtures/ledger_bad.csv" % S,
                                 "--today", "2026-10-28"], 1, "编号重复"),
        ("规格校验-合格样例", ["%s/spec-architect/scripts/spec_lint.py" % S,
                               "%s/spec-architect/fixtures/spec_good.md" % S], 0, "结果：通过"),
        ("规格校验-不合格样例", ["%s/spec-architect/scripts/spec_lint.py" % S,
                                 "%s/spec-architect/fixtures/spec_bad.md" % S], 1, "P0 占比过高"),
        ("产能装箱-装得下", ["%s/capacity-packing/scripts/capacity_pack.py" % S, "--backlog",
                             "%s/capacity-packing/fixtures/backlog_ok.csv" % S,
                             "--people", "6", "--weeks", "13"], 0, "结果：通过"),
        ("产能装箱-P0 装不下", ["%s/capacity-packing/scripts/capacity_pack.py" % S, "--backlog",
                                "%s/capacity-packing/fixtures/backlog_overload.csv" % S,
                                "--people", "6", "--weeks", "13"], 1, "P0 未装进计划"),
        ("口径卡-合格样例", ["%s/metric-guard/scripts/metric_check.py" % S, "--cards",
                             "%s/metric-guard/fixtures/cards_good.csv" % S], 0, "结果：通过"),
        ("口径卡-不合格样例", ["%s/metric-guard/scripts/metric_check.py" % S, "--cards",
                               "%s/metric-guard/fixtures/cards_bad.csv" % S], 1, "缺少 denominator"),
        ("辛普森反转识别", ["%s/metric-guard/scripts/metric_check.py" % S, "--segments",
                            "%s/metric-guard/fixtures/segments_simpson.csv" % S], 1, "辛普森反转"),
        ("一致性-闭环样例", ["%s/chain-consistency/scripts/chain_check.py" % S,
                             "%s/chain-consistency/fixtures/chain_ok" % S], 0, "结果：通过"),
        ("一致性-断链样例", ["%s/chain-consistency/scripts/chain_check.py" % S,
                             "%s/chain-consistency/fixtures/chain_broken" % S], 1, "[C8]"),
    ]
    for name, args, code, text in cases:
        ok, detail = run(args, code, text)
        record(name, ok, detail)


def png_size(path):
    with open(path, "rb") as fh:
        head = fh.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    w, h = struct.unpack(">II", head[16:24])
    return w, h, os.path.getsize(path)


def structure_tests():
    manifest_path = os.path.join(ROOT, ".codebuddy-plugin", "plugin.json")
    record("manifest 存在", os.path.isfile(manifest_path))
    if not os.path.isfile(manifest_path):
        return
    try:
        m = json.load(open(manifest_path, "r", encoding="utf-8"))
        record("manifest 可解析", True)
    except json.JSONDecodeError as exc:
        record("manifest 可解析", False, str(exc))
        return

    for field in ("name", "version", "description", "author", "license", "expertType",
                  "agentName", "displayName", "profession", "displayDescription",
                  "avatar", "categoryId", "agents", "skills"):
        record("manifest 字段 %s" % field, field in m)

    record("包名以 czl- 开头", str(m.get("name", "")).startswith("czl-"))
    record("作者信息", (m.get("author") or {}).get("name") == "虫志龙"
           and (m.get("author") or {}).get("email") == "47190078@qq.com")
    record("expertType=agent（单专家形态）", m.get("expertType") == "agent")
    record("单专家不应包含 teamInfo", "teamInfo" not in m)
    record("单专家不应包含 members", "members" not in m)

    # 平台校验规则（上架解析失败的三条）
    tags = m.get("tags") or []
    record("tags 恰好 3 个", len(tags) == 3, "实际 %d 个" % len(tags))
    record("tags 每项含 zh/en",
           all(isinstance(t, dict) and (t.get("zh") or "").strip() and (t.get("en") or "").strip()
               for t in tags))
    dip = m.get("defaultInitPrompt") or {}
    qps = m.get("quickPrompts") or []
    record("quickPrompts 至少 1 条", len(qps) >= 1, "实际 %d 条" % len(qps))
    record("defaultInitPrompt.zh 与 quickPrompts[0].zh 一致",
           bool(qps) and dip.get("zh") == qps[0].get("zh"))
    record("defaultInitPrompt.en 与 quickPrompts[0].en 一致",
           bool(qps) and dip.get("en") == qps[0].get("en"))

    agents = m.get("agents") or []
    record("agents 是数组且只有 1 个", isinstance(agents, list) and len(agents) == 1)
    agent_name = m.get("agentName")
    record("agentName 与 agents[0] 文件名一致",
           agents and os.path.basename(agents[0]) == "%s.md" % agent_name)
    agent_path = os.path.join(ROOT, "agents", "%s.md" % agent_name)
    record("agent 文件存在", os.path.isfile(agent_path))
    if os.path.isfile(agent_path):
        text = open(agent_path, "r", encoding="utf-8").read()
        record("agent 提示词非空（>3000 字符）", len(text) > 3000, "仅 %d 字符" % len(text))
        fm = text.split("---")[1] if text.startswith("---") else ""
        record("agent frontmatter name 匹配", ("name: %s" % agent_name) in fm)
        for hat in ("立案", "取据", "成文", "排产", "度量", "汇报"):
            record("提示词含六段链环节：%s" % hat, hat in text)
        for gate in ("G1", "G2", "G3", "G4"):
            record("提示词含闸门：%s" % gate, gate in text)
        record("提示词含换帽铁律", "换帽" in text)
        record("提示词含红队/反证机制", ("反证" in text) and ("红队" in text))

    info = png_size(os.path.join(ROOT, m.get("avatar", ""))) if m.get("avatar") else None
    record("头像存在且为正方形 PNG、≥256px、<512KB",
           bool(info) and info[0] == info[1] and info[0] >= 256 and info[2] < 512 * 1024,
           "实际：%s" % (info,))

    skills = m.get("skills") or []
    record("skills 是数组且非空", isinstance(skills, list) and len(skills) > 0)
    for rel in skills:
        sdir = os.path.join(ROOT, rel)
        skill_md = os.path.join(sdir, "SKILL.md")
        record("技能存在：%s" % rel, os.path.isfile(skill_md))
        if os.path.isfile(skill_md):
            text = open(skill_md, "r", encoding="utf-8").read()
            name = os.path.basename(rel)
            record("技能 frontmatter name 匹配：%s" % name,
                   text.startswith("---") and ("name: %s" % name) in text.split("---")[1])

    for doc in ("README.md", "LICENSE", "CHANGELOG.md", "NOTICE.md",
                "docs/产品规格说明.md", "docs/使用说明.md", "docs/平台展示文案.md",
                "docs/文件清单与开发记录.md", "docs/测试报告.md", "docs/商业发布风险清单.md"):
        record("文档存在：%s" % doc, os.path.isfile(os.path.join(ROOT, doc)))

    readme = os.path.join(ROOT, "README.md")
    record("README 含作者与包标识",
           os.path.isfile(readme) and "虫志龙" in open(readme, "r", encoding="utf-8").read())

    pattern = re.compile(r"(?:[|:：]\s*待补充\s*(?:\||$)|\b(?:TBD|TODO|FIXME)\b)")
    offenders = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        if ".git" in dirpath or "fixtures" in dirpath or "__pycache__" in dirpath:
            continue
        for fn in filenames:
            if fn.endswith((".md", ".json")) and not fn.startswith("测试报告"):
                p = os.path.join(dirpath, fn)
                for no, line in enumerate(open(p, "r", encoding="utf-8", errors="ignore"), 1):
                    if "占位符" in line or "残留" in line:
                        continue
                    if pattern.search(line):
                        offenders.append("%s:%d" % (os.path.relpath(p, ROOT), no))
    record("交付文件中无占位符", not offenders, ",".join(offenders[:5]))


def main():
    print("包路径：%s" % ROOT)
    print("Python：%s" % PY)
    print("")
    script_tests()
    structure_tests()
    passed = sum(1 for _, ok, _ in results if ok)
    failed = [(n, d) for n, ok, d in results if not ok]
    print("")
    print("用例 %d 项，通过 %d，失败 %d" % (len(results), passed, len(failed)))
    for name, detail in failed:
        print("  [FAIL] %s  %s" % (name, detail))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
