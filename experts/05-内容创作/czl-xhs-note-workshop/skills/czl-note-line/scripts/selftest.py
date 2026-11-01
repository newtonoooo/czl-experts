#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selftest.py - 整链自测

跑这一条命令，验证：文件完整、规则表可读、体检器能拦也能放、排期器能排且
同素材间隔达标、异常输入有正确退出码。结果可直接作为《测试报告》的附录。

用法：
    python selftest.py
    python selftest.py --out 测试记录.md

退出码：0 = 全部通过；1 = 有失败项
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import subprocess
import sys
import tempfile
from pathlib import Path

VERSION = "1.0.0"
BASE = Path(__file__).resolve().parent.parent
SCRIPTS = BASE / "scripts"
SAMPLES = BASE / "samples"
DATA = BASE / "data"

REQUIRED_FILES = [
    "SKILL.md",
    "workflows/00-intake.md",
    "workflows/01-positioning.md",
    "workflows/02-topic-matrix.md",
    "workflows/03-note-draft.md",
    "workflows/04-qc-gate.md",
    "workflows/05-calendar.md",
    "workflows/06-review.md",
    "references/01-title-engineering.md",
    "references/02-cover-spec.md",
    "references/03-body-skeletons.md",
    "references/04-tag-and-search.md",
    "references/05-material-angles.md",
    "references/06-human-voice.md",
    "references/07-compliance.md",
    "references/08-funnel-diagnosis.md",
    "templates/T1-material-card.md",
    "templates/T2-position-card.md",
    "templates/T3-topic-matrix.csv",
    "templates/T4-note-card.md",
    "templates/T5-calendar.csv",
    "templates/T6-review-sheet.md",
    "data/compliance_terms.json",
    "data/ai_tone_patterns.json",
    "scripts/note_lint.py",
    "scripts/build_calendar.py",
    "samples/good-note.md",
    "samples/bad-note.md",
    "samples/topics-demo.csv",
]

results = []


def record(name, passed, detail=""):
    results.append({"name": name, "passed": bool(passed), "detail": detail})
    mark = "PASS" if passed else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
    return passed


def run(script, args, timeout=60):
    cmd = [sys.executable, str(SCRIPTS / script)] + [str(a) for a in args]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_environment():
    ok = sys.version_info >= (3, 8)
    record("运行环境 Python >= 3.8", ok, f"当前 {sys.version.split()[0]}")
    return ok


def test_data_files():
    allok = True
    for name in ("compliance_terms.json", "ai_tone_patterns.json"):
        path = DATA / name
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            groups = payload.get("groups") or payload.get("patterns") or []
            record(f"规则表可解析：{name}", bool(groups), f"{len(groups)} 组")
        except Exception as exc:  # noqa: BLE001
            record(f"规则表可解析：{name}", False, str(exc))
            allok = False
    return allok


def test_file_integrity():
    missing = [rel for rel in REQUIRED_FILES if not (BASE / rel).exists()]
    record("文件完整性", not missing, "全部存在" if not missing else f"缺 {len(missing)} 个：{'、'.join(missing[:5])}")
    return not missing


def test_lint_good():
    code, out, err = run("note_lint.py", [SAMPLES / "good-note.md", "--json", _tmp_json()])
    data = _read_json(_tmp_json())
    ok = code == 0 and data is not None and data["summary"]["high"] == 0 and data["blocked"] is False
    record("干净稿件：无高危、放行、退出码 0", ok, f"exit={code} high={data['summary']['high'] if data else '?'}")
    if data:
        record(
            "干净稿件：结构识别正确（标题 5 / 封面 3 / 标签 8）",
            data["stats"]["titles"] == 5 and data["stats"]["cover_lines"] == 3 and data["stats"]["tags"] == 8,
            f"titles={data['stats']['titles']} cover={data['stats']['cover_lines']} tags={data['stats']['tags']}",
        )
    return ok


def test_lint_bad():
    code, out, err = run("note_lint.py", [SAMPLES / "bad-note.md", "--json", _tmp_json()])
    data = _read_json(_tmp_json())
    if data is None:
        record("故意写坏的稿：能产出报告", False, f"无 JSON，stderr={err[:80]}")
        return False

    ids = {f["id"] for f in data["findings"]}
    expected = {"T01", "T02", "T03", "T04", "B01", "B07", "B09", "B10", "K01", "K02", "K03", "K05"}
    missing = expected - ids
    record("坏稿：命中预期规则", not missing, f"缺 {sorted(missing)}" if missing else f"命中 {len(ids)} 条规则")
    record(
        "坏稿：阻断且退出码为 1",
        code == 1 and data["blocked"] is True and data["summary"]["high"] >= 4,
        f"exit={code} high={data['summary']['high']}",
    )
    record(
        "坏稿：高危项含合规与占位符",
        {"K01", "K03", "B10"} <= ids,
        "K01/K03/B10 均命中" if {"K01", "K03", "B10"} <= ids else "缺合规高危",
    )
    return True


def test_lint_errors():
    code, out, err = run("note_lint.py", [BASE / "samples" / "not-exists.md"])
    record("异常输入：文件不存在返回 2", code == 2, f"exit={code}")

    with tempfile.TemporaryDirectory() as tmp:
        plain = Path(tmp) / "plain.txt"
        plain.write_text(
            "上周我把厨房的抽油烟机拆开洗了一遍，滤网里的油能刮下来一层。"
            "洗完之后风力明显变大，炒菜时客厅闻不到味了。你们家的滤网多久洗一次？",
            encoding="utf-8",
        )
        code2, out2, err2 = run("note_lint.py", [plain])
        record(
            "纯文本（非笔记卡）也能体检",
            code2 in (0, 1) and "未找到笔记卡标题结构" in out2,
            f"exit={code2}",
        )
    return True


def test_calendar():
    with tempfile.TemporaryDirectory() as tmp:
        out_csv = Path(tmp) / "calendar.csv"
        code, out, err = run(
            "build_calendar.py",
            [SAMPLES / "topics-demo.csv", "--start", "2026-11-01", "--per-week", "3", "--days", "30", "--out", out_csv],
        )
        if code != 0 or not out_csv.exists():
            record("排期：能生成日历", False, f"exit={code} err={err[:100]}")
            return False
        record("排期：能生成日历", True, f"exit={code}")

        with out_csv.open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
        record("排期：输出行数等于发布位数", 0 < len(rows) <= 13, f"{len(rows)} 行")

        weekdays = {row["星期"] for row in rows}
        record("排期：星期字段正确", weekdays <= set("周一 周二 周三 周四 周五 周六 周日".split()), f"{len(weekdays)} 种")

        min_gap, violated = _min_source_gap(rows)
        # 真实样例里 M-001 素材占 8 条，30 天内做不到 5 天间隔；要求的是「不静默违规」
        record(
            "排期：素材不够时不静默违规（有告警）",
            violated == 0 or "间隔不足" in out,
            f"最小间隔 {min_gap} 天，告警 {'有' if '间隔不足' in out else '无'}",
        )

        # 素材充足时，必须真的拉开 5 天
        balanced = Path(tmp) / "balanced.csv"
        balanced.write_text(
            "选题,素材来源,角度\n"
            "题一,S1,亲历\n题二,S1,对照\n题三,S2,清单\n"
            "题四,S2,拆解\n题五,S3,亲历\n题六,S3,对照\n",
            encoding="utf-8",
        )
        out2 = Path(tmp) / "balanced_out.csv"
        code_b, out_b, err_b = run(
            "build_calendar.py",
            [balanced, "--start", "2026-11-02", "--per-week", "3", "--days", "21", "--out", out2],
        )
        if code_b != 0 or not out2.exists():
            record("排期：素材充足时能拉开间隔", False, f"exit={code_b} err={err_b[:80]}")
        else:
            with out2.open(encoding="utf-8-sig", newline="") as fh:
                rows_b = list(csv.DictReader(fh))
            gap_b, violated_b = _min_source_gap(rows_b)
            record(
                "排期：素材充足时同素材间隔 ≥5 天",
                violated_b == 0 and gap_b is not None and gap_b >= 5,
                f"排了 {len(rows_b)} 篇，最小间隔 {gap_b} 天",
            )

    code2, out2, err2 = run("build_calendar.py", [SAMPLES / "topics-demo.csv", "--start", "2026/11/01"])
    record("排期：日期格式错误返回 2", code2 == 2, f"exit={code2}")

    code3, out3, err3 = run("build_calendar.py", [SAMPLES / "topics-demo.csv", "--start", "2026-11-01", "--per-week", "9"])
    record("排期：产能越界返回 2", code3 == 2, f"exit={code3}")
    return True


def _min_source_gap(rows):
    """返回 (同素材最小间隔天数, 违规次数)。"""
    last = {}
    min_gap = None
    violated = 0
    for row in rows:
        src = (row.get("素材来源") or "").strip()
        if not src:
            continue
        day = dt.date.fromisoformat(row["日期"])
        if src in last:
            gap = (day - last[src]).days
            min_gap = gap if min_gap is None else min(min_gap, gap)
            if gap < 5:
                violated += 1
        last[src] = day
    return min_gap, violated


_TMP_JSON = {}


def _load_linter():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    import note_lint  # noqa: PLC0415

    return note_lint


BASE_TITLES = [
    "手裂到开口那晚我换了第四支",
    "三支护手霜 217 块只有一支没白买",
    "128 的和 39 的差在涂完十分钟",
    "四十五天用完三支我才摸清顺序",
    "手裂的人买手霜先看这两个条件",
]
BASE_COVER = ("第四支才不裂", "39 元 · 用了 60 天", "手裂过的")
BASE_TAGS = "#护手霜 #手部护理 #身体护理 #冬天手裂 #干皮 #办公室 #手裂口涂什么 #护手霜推荐平价"

DIGIT_FREE_BODY = (
    "成都入冬那阵子，手背的裂口又出来了。我换了三种涂法，最后留下的是最土的一种。\n\n"
    "先说结论：手裂的时候，缺的不只是水。涂完还黏的那类，第二天早上手背是软的；"
    "涂完立刻干爽的那类，第二天照样起皮。这个判断很土，但比看成分表快。\n\n"
    "后来我做了件小事，把洗手液换成无皂基的。这一步比换手霜管用，我自己的感觉是"
    "裂口收得快了一半。手上抹开，等一会儿，用食指蹭一下手背，有阻力又不粘手，就对了。\n\n"
    "第四支现在用了一个月，还没见底。你们那边冬天手会裂吗，一般裂在哪个位置。"
)


def test_rule_coverage():
    """针对样例没触发的规则，逐条构造最小输入，验证确实能命中。"""
    note_lint = _load_linter()
    compliance = note_lint.load_json("compliance_terms.json")
    tone_data = note_lint.load_json("ai_tone_patterns.json")

    base_body = note_lint.split_sections((SAMPLES / "good-note.md").read_text(encoding="utf-8"))[0]["body"]
    base_body = "\n".join(base_body).strip()

    def card(body=None, titles=None, cover=None, tags=None, comment="补一句：39 那支含香精。"):
        t = titles or BASE_TITLES
        c = cover or BASE_COVER
        return (
            "## 标题候选\n"
            + "\n".join(f"{i}. {x}" for i, x in enumerate(t, 1))
            + "\n\n## 封面\n主标：%s\n副标：%s\n角标：%s\n" % c
            + "\n## 正文\n" + (body if body is not None else base_body) + "\n"
            + "\n## 首评\n" + comment + "\n"
            + "\n## 标签\n" + (tags or BASE_TAGS) + "\n"
        )

    cases = {
        "T07": card(titles=[BASE_TITLES[0], BASE_TITLES[1], BASE_TITLES[2], BASE_TITLES[3], BASE_TITLES[0]]),
        "C03": card(cover=("第四支才不裂", "39 元一支，前后买了三支共 217 元", "手裂过的干皮女生啊")),
        "B02": card(body=base_body + "\n\n" + "这件事我后来又想了想，还是那几组数。" * 60),
        "B03": card(body=base_body + "\n\n" + "这一段没有任何标点只是为了测试段落长度会不会被拦下来" * 6),
        "B05": card(body=base_body.replace(
            "第四支现在用了一个月，还没见底。你们那边冬天手会裂吗？裂在哪个位置，我挺想知道是不是都从虎口开始。",
            "第四支现在用了一个月，还没见底。",
        )),
        "B06": card(body=base_body + "\n\n😀😃😄😁😆😊"),
        "B11": card(body=base_body + "\n\n收藏一下，点赞也行，关注我，蹲后续。"),
        "B12": card(body=DIGIT_FREE_BODY),
        "K02R": card(body=base_body + "\n\n这支宣称可以修复屏障。"),
        "K04": card(body=base_body + "\n\n有人在评论区说这个保本，我不信。"),
        "A05": card(body=base_body + "\n\n更值得问的是，我们为什么总在冬天才想起来护手。"),
        "A08": card(body=base_body + "\n\n质感很好，高级感也在，氛围感拉满。"),
        "A09": card(body=base_body + "\n\n那会儿心里五味杂陈。"),
        "A10": card(body=base_body + "\n\n我买它——不是为了便宜——是为了省事——结果都没省。"),
        "A11": card(body=base_body + "\n\n**重点一** **重点二** **重点三** **重点四** **重点五** **重点六**"),
        "A12": card(body=base_body + "\n\n1️⃣ 先洗手 2️⃣ 再涂 3️⃣ 等十分钟"),
    }

    passed = []
    failed = []
    for rule_id, text in cases.items():
        findings, _, _ = note_lint.lint_text(text, compliance, tone_data)
        hit = {f["id"] for f in findings}
        if rule_id in hit:
            passed.append(rule_id)
        else:
            failed.append(f"{rule_id}（实际命中 {','.join(sorted(hit)) or '无'}）")

    record(
        "规则冒烟：样例未覆盖的规则可被触发",
        not failed,
        f"{len(passed)}/{len(cases)} 通过" if not failed else "；".join(failed),
    )
    return set(passed)


def _sample_rule_ids():
    data = _read_json(_tmp_json())
    if not data:
        return set()
    return {f["id"] for f in data["findings"]}


def total_rule_count():
    note_lint = _load_linter()
    compliance = note_lint.load_json("compliance_terms.json")
    tone_data = note_lint.load_json("ai_tone_patterns.json")
    return note_lint.count_rules(compliance, tone_data)


COVERED_BY_SMOKE = set()


def coverage_note():
    bad = _read_json(_tmp_json())
    total = total_rule_count()
    sample_ids = _sample_rule_ids() if bad else set()
    covered = sample_ids | COVERED_BY_SMOKE
    missing = total - len(covered)
    return (
        f"规则覆盖：{len(covered)}/{total} 条被真实触发"
        f"（坏稿样例 {len(sample_ids)} 条 + 冒烟用例 {len(COVERED_BY_SMOKE)} 条"
        + (f"，未触发 {missing} 条" if missing > 0 else "")
        + "）"
    )


def _tmp_json():
    path = _TMP_JSON.get("path")
    if path is None:
        path = str(Path(tempfile.gettempdir()) / "note_lint_selftest.json")
        _TMP_JSON["path"] = path
    return path


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def main(argv=None):
    global COVERED_BY_SMOKE

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="笔记产线整链自测")
    parser.add_argument("--out", help="把测试记录写成 Markdown")
    args = parser.parse_args(argv)

    print(f"笔记产线自测 v{VERSION}")
    print(f"技能目录：{BASE}")
    print("-" * 52)

    test_environment()
    test_data_files()
    test_file_integrity()
    test_lint_good()
    test_lint_bad()
    test_lint_errors()
    test_calendar()
    COVERED_BY_SMOKE = test_rule_coverage()

    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed
    print("-" * 52)
    print(f"合计 {len(results)} 项 · 通过 {passed} · 失败 {failed}")
    print(coverage_note())

    if args.out:
        lines = [
            f"# 自测记录（{dt.datetime.now().strftime('%Y-%m-%d %H:%M')}）",
            "",
            f"- 自测脚本版本：{VERSION}",
            f"- Python：{sys.version.split()[0]}",
            f"- 技能目录：`{BASE}`",
            f"- 合计 {len(results)} 项，通过 {passed}，失败 {failed}",
            "",
            "| # | 检查项 | 结果 | 说明 |",
            "|---|---|---|---|",
        ]
        for idx, item in enumerate(results, 1):
            lines.append(
                f"| {idx} | {item['name']} | {'通过' if item['passed'] else '失败'} | {item['detail']} |"
            )
        lines.append("")
        lines.append(coverage_note())
        Path(args.out).write_text("\n".join(lines), encoding="utf-8")
        print(f"\n记录已写出：{Path(args.out).resolve()}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
