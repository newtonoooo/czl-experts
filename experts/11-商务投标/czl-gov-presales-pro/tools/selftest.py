#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本专家包的功能自检（发布前跑一遍）。

跑法：
    python tools/selftest.py

覆盖：机会打分、标书体检、方案骨架、合规矩阵、包自检（含"头像路径失配"的反向用例）。
输出 PASS/FAIL 明细，任一 FAIL 则退出码非 0。
"""

import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
RADAR = ROOT / "skills" / "gov-opportunity-radar" / "scripts" / "radar.py"
TENDER = ROOT / "skills" / "tender-clause-audit" / "scripts" / "tender_audit.py"
PROPOSAL = ROOT / "skills" / "proposal-architect" / "scripts" / "proposal_plan.py"
MATRIX = ROOT / "skills" / "compliance-matrix" / "scripts" / "matrix.py"
PACK = ROOT / "tools" / "pack_check.py"

results = []


def run(args, expect=0):
    p = subprocess.run(
        [sys.executable] + [str(a) for a in args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if p.returncode != expect:
        raise AssertionError(
            f"退出码 {p.returncode} != {expect}\nSTDOUT:\n{p.stdout[:800]}\nSTDERR:\n{p.stderr[:800]}"
        )
    return p.stdout


def case(name):
    def deco(fn):
        try:
            detail = fn()
            results.append((name, "PASS", detail or ""))
        except Exception as e:  # noqa: BLE001
            msg = (str(e) or type(e).__name__).strip()
            results.append((name, "FAIL", (msg.splitlines() or [msg])[0][:200]))
        return fn

    return deco


@case("T01 机会打分：正常输入给出档位与短板")
def t01():
    out = run([RADAR, "score", "--input", FIX / "opportunity.json", "--json"])
    d = json.loads(out)
    assert d["gate"] == "pass", d
    assert d["tier"] in ("全力投入", "选择性参与"), d["tier"]
    assert 0 < d["total"] <= 100
    assert 1 <= len(d["weak"]) <= 3
    assert d["dims"] and abs(sum(x["contribution"] for x in d["dims"]) - d["total"]) < 1.0
    return f"总分 {d['total']}，档位「{d['tier']}」，短板 {len(d['weak'])} 条"


@case("T02 机会打分：资格不满足时一票否决")
def t02():
    out = run([RADAR, "score", "--input", FIX / "opportunity_gate_fail.json", "--json"])
    d = json.loads(out)
    assert d["gate"] == "fail", d
    assert d["tier"] == "不建议投标", d["tier"]
    return "资格不符 → 不建议投标（未进入加权）"


@case("T03 机会打分：缺维度时结论为待定")
def t03():
    tmp = Path(tempfile.mkdtemp()) / "half.json"
    tmp.write_text(
        json.dumps(
            {"project": "半截信息", "qualification_ok": True, "scores": {"funding": 4, "competition": 3}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out = run([RADAR, "score", "--input", tmp, "--json"])
    d = json.loads(out)
    assert d["tier"] == "待定", d["tier"]
    assert len(d["missing"]) >= 3
    return f"待定，缺 {len(d['missing'])} 项信息"


@case("T04 标书体检：识别致命条款与星号条款")
def t04():
    out = run([TENDER, "scan", "--file", FIX / "tender_sample.txt", "--json"])
    d = json.loads(out)
    assert d["counts"]["致命"] >= 3, d["counts"]
    assert len(d["stars"]) >= 2, len(d["stars"])
    assert len(d["dates"]) >= 2, len(d["dates"])
    assert all(h["line"] > 0 for h in d["hits"])
    return f"致命 {d['counts']['致命']} / 严重 {d['counts']['严重']} / 一般 {d['counts']['一般']}，星号 {len(d['stars'])}，日期 {len(d['dates'])}"


@case("T05 标书体检：空文件报错不静默")
def t05():
    tmp = Path(tempfile.mkdtemp()) / "empty.txt"
    tmp.write_text("   \n\n", encoding="utf-8")
    p = subprocess.run(
        [sys.executable, str(TENDER), "scan", "--file", str(tmp)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert p.returncode == 2, p.returncode
    assert "空" in p.stderr
    return "空文件退出码 2，提示文本提取失败"


@case("T06 方案骨架：页数不超上限且每章≥1页")
def t06():
    out = run([PROPOSAL, "plan", "--input", FIX / "scoring.json", "--json"])
    d = json.loads(out)
    assert d["total_pages"] <= d["page_limit"], (d["total_pages"], d["page_limit"])
    assert all(r["pages"] >= 1 for r in d["rows"])
    assert all(r["must"] for r in d["rows"] if "架构" in r["name"])
    return f"{len(d['rows'])} 章，合计 {d['total_pages']} 页 / 上限 {d['page_limit']}"


@case("T07 合规矩阵：三级条目多于二级，含集中审计")
def t07():
    o3 = run([MATRIX, "dengbao", "--level", "3", "--format", "csv"])
    o2 = run([MATRIX, "dengbao", "--level", "2", "--format", "csv"])
    n3, n2 = len(o3.strip().splitlines()), len(o2.strip().splitlines())
    assert n3 > n2, (n3, n2)
    assert "集中审计" in o3
    return f"三级 {n3-1} 项 / 二级 {n2-1} 项"


@case("T08 合规矩阵：三表合一输出")
def t08():
    out = run([MATRIX, "all", "--level", "3"])
    for token in ("等保 3 级", "商用密码应用安全性评估", "信创适配清单", "SM4"):
        assert token in out, token
    return "等保/密评/信创三表齐全"


@case("T09 包自检：真实专家目录通过")
def t09():
    out = run([PACK, ROOT, "--json"])
    d = json.loads(out)
    assert d["passed"], d["errors"]
    return f"{len(d['ok'])} 项通过，头像 {d['avatar']}"


@case("T10 包自检：头像路径失配时能被抓出来（反向用例）")
def t10():
    tmp = Path(tempfile.mkdtemp()) / "broken"
    shutil.copytree(ROOT, tmp)
    pj = tmp / ".codebuddy-plugin" / "plugin.json"
    data = json.loads(pj.read_text(encoding="utf-8"))
    data["avatar"] = "avatars/not-exists.png"
    pj.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    p = subprocess.run(
        [sys.executable, str(PACK), str(tmp), "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert p.returncode == 1, p.returncode
    d = json.loads(p.stdout)
    assert not d["passed"]
    assert any("avatar" in e for e in d["errors"]), d["errors"]
    return "路径失配 → 退出码 1，报 avatar 不存在"


@case("T11 zip 校验：被引用文件全部在包内")
def t11():
    tmpdir = Path(tempfile.mkdtemp())
    zpath = tmpdir / f"{ROOT.name}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in ROOT.rglob("*"):
            if f.is_file() and not any(part.startswith(".") and part != ".codebuddy-plugin" for part in f.relative_to(ROOT).parts):
                z.write(f, f"{ROOT.name}/{f.relative_to(ROOT).as_posix()}")
    out = run([PACK, ROOT, "--zip", zpath, "--json"])
    d = json.loads(out)
    assert d["passed"], d["errors"]
    assert any("被引用文件全部存在" in s for s in d["ok"])
    return f"zip 条目齐全，{zpath.stat().st_size/1024:.0f} KB"


def main():
    print(f"自检对象：{ROOT}")
    print("=" * 72)
    for name, status, detail in results:
        mark = "PASS" if status == "PASS" else "FAIL"
        print(f"[{mark}] {name}")
        if detail:
            print(f"       {detail}")
    passed = sum(1 for _, s, _ in results if s == "PASS")
    print("=" * 72)
    print(f"合计 {len(results)} 项：通过 {passed}，失败 {len(results) - passed}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
