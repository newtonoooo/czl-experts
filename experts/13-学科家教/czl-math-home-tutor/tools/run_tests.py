#!/usr/bin/env python3
"""run_tests.py - run every shipped script against a real case and check the result.

The point is not "it ran without crashing". Each case asserts something a user
would notice: the ledger reschedules to the right date, the drill plan never
exceeds its time budget, the exam planner admits when a target is unreachable,
the verifier refuses a hostile expression.

    python tools/run_tests.py                # run, print a table, write dist/selftest.*
    python tools/run_tests.py --no-write     # run only
    python tools/run_tests.py --verbose      # also print each command's output

Exit codes: 0 all cases passed, 1 at least one failed.
"""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
CASES = []


def case(name, script, args, expect_rc=0, expect=None, forbid=None, workdir=None):
    CASES.append({
        "name": name, "script": script, "args": args, "expect_rc": expect_rc,
        "expect": expect or [], "forbid": forbid or [], "workdir": workdir,
    })


def build_cases(tmp):
    ledger = os.path.join(tmp, "err.csv")
    for row in [
        # --- package integrity ------------------------------------------------
        ("自检：专家包 31 项", "tools/check_package.py", ["--verbose"], 0,
         ["0 failed"], []),
        ("自检：头像体积", "tools/check_package.py", ["--verbose"], 0,
         ["avatar.size        214 KB", "avatar.dimensions  512x512"], []),

        # --- verify.py --------------------------------------------------------
        ("验算：零点通过", "skills/czl-math-decompose/scripts/verify.py",
         ["--expr", "x^2-3*x+2", "--zero", "1,2"], 0, ["PASS", "全部通过"], []),
        ("验算：单调性不成立要报错", "skills/czl-math-decompose/scripts/verify.py",
         ["--expr", "x^3-3*x", "--mono", "inc", "--on", "-1,1"], 1,
         ["FAIL", "存在未通过项"], []),
        ("验算：范围采样", "skills/czl-math-decompose/scripts/verify.py",
         ["--expr", "x^2-2*x", "--minmax", "--on", "0,3"], 0, ["范围验"], []),
        ("验算：拒绝危险表达式", "skills/czl-math-decompose/scripts/verify.py",
         ["--expr", "__import__('os').system('echo x')", "--at", "1"], 1,
         ["function not allowed"], []),

        # --- diagnose.py ------------------------------------------------------
        ("诊断：样例卷面", "skills/czl-math-diagnose/scripts/diagnose.py",
         ["skills/czl-math-diagnose/samples/scores_demo.csv", "--top", "4"], 0,
         ["学情诊断表", "总得分率：50.0%", "数列压轴", "这周只做三件事"], []),
        ("诊断：主码决定性质", "skills/czl-math-diagnose/scripts/diagnose.py",
         ["skills/czl-math-diagnose/samples/scores_demo.csv"], 0,
         ["方法缺口"], ["基础缺口 —— 这条线的定义"]),
        ("诊断：可输出空白模板", "skills/czl-math-diagnose/scripts/diagnose.py",
         ["--template"], 0, ["题号,知识点,分值,得分,错因码"], []),

        # --- drill.py ---------------------------------------------------------
        ("训练：单断点配比", "skills/czl-math-drill/scripts/drill.py",
         ["--weak", "导数单调性:M", "--minutes", "45"], 0,
         ["同型", "换皮", "换轴", "预算 45 分钟"], []),
        ("训练：双断点不超总预算", "skills/czl-math-drill/scripts/drill.py",
         ["--weak", "导数单调性:M,解析几何弦长:M", "--minutes", "45"], 0,
         ["预算 27 分钟", "预算 18 分钟"], []),
        ("训练：非法错因码要拒绝", "skills/czl-math-drill/scripts/drill.py",
         ["--weak", "导数:Z"], 2, ["unknown code"], []),

        # --- ledger.py --------------------------------------------------------
        ("台账：入账", "skills/czl-math-ledger/scripts/ledger.py",
         ["add", "--csv", ledger, "--source", "周测三", "--today", "2026-10-31",
          "--item", "导数单调性|M|讨论f(x)=x^3-3ax的单调性|先求导再看参数位置",
          "--item", "数列求和|A|错位相减|减完先查最后一项符号"], 0,
         ["added #1", "下次复现 2026-11-01", "共 2 条"], []),
        ("台账：到期清单", "skills/czl-math-ledger/scripts/ledger.py",
         ["due", "--csv", ledger, "--today", "2026-11-02"], 0,
         ["到期 2 条", "先求导再看参数位置"], []),
        ("台账：答对进一级", "skills/czl-math-ledger/scripts/ledger.py",
         ["review", "--csv", ledger, "--id", "1", "--result", "right",
          "--today", "2026-11-02"], 0, ["阶段 1", "3 天后再见"], []),
        ("台账：答错退回明天", "skills/czl-math-ledger/scripts/ledger.py",
         ["review", "--csv", ledger, "--id", "2", "--result", "wrong",
          "--today", "2026-11-02"], 0, ["回到阶段 0", "明天再来"], []),
        ("台账：周报", "skills/czl-math-ledger/scripts/ledger.py",
         ["stats", "--csv", ledger, "--today", "2026-11-05"], 0,
         ["错题台账周报", "按错因码", "这周的动作"], []),
        ("台账：不存在的 id 返回 3", "skills/czl-math-ledger/scripts/ledger.py",
         ["review", "--csv", ledger, "--id", "99", "--result", "right"], 3,
         ["no item"], []),

        # --- scoreplan.py -----------------------------------------------------
        ("考场：目标 120", "skills/czl-math-examroom/scripts/scoreplan.py",
         ["--target", "120", "--current", "单选=30,多选=9,填空=7,解答=35"], 0,
         ["新高考 19 题", "放弃线", "三条硬规矩"], []),
        ("考场：不现实目标要点明", "skills/czl-math-examroom/scripts/scoreplan.py",
         ["--target", "150", "--current", "单选=20,多选=3,填空=2,解答=15"], 0,
         ["不现实", "建议先按"], []),
        ("考场：旧 22 题结构", "skills/czl-math-examroom/scripts/scoreplan.py",
         ["--target", "110", "--paper", "old22"], 0, ["22 题旧结构"], []),
        ("考场：超范围目标要拒绝", "skills/czl-math-examroom/scripts/scoreplan.py",
         ["--target", "200"], 2, ["must be within"], []),

        # --- tools ------------------------------------------------------------
        ("安装：演练不落盘", "tools/install.py", ["--dry-run"], 0,
         ["post-check (against source", "agent       : ok"], []),
        ("图像：读取头像元信息", "tools/png_resize.py",
         ["avatars/expert.png", "--probe"], 0, ["512x512", "colour type 2"], []),
    ]:
        case(*row)


def run_one(c, verbose):
    script = os.path.join(ROOT, c["script"])
    cmd = [PY, script] + c["args"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              cwd=ROOT, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, "could not run: %s" % exc, ""
    out = (proc.stdout or "") + (proc.stderr or "")
    if verbose:
        print("\n$ %s" % " ".join(cmd))
        print(out.rstrip())
    if proc.returncode != c["expect_rc"]:
        return False, "exit %d, expected %d" % (proc.returncode, c["expect_rc"]), out
    for needle in c["expect"]:
        if needle not in out:
            return False, "missing expected text: %r" % needle, out
    for needle in c["forbid"]:
        if needle in out:
            return False, "found forbidden text: %r" % needle, out
    return True, "", out


def plan_budget_ok():
    """Extra invariant: no drill plan may exceed the minutes it was given."""
    script = os.path.join(ROOT, "skills/czl-math-drill/scripts/drill.py")
    for minutes in (20, 30, 45, 60, 90):
        proc = subprocess.run(
            [PY, script, "--weak", "导数:M,解几:M,数列:A", "--minutes", str(minutes),
             "--json", os.path.join(tempfile.gettempdir(), "drill_check.json")],
            capture_output=True, text=True, cwd=ROOT, timeout=60)
        if proc.returncode != 0:
            return False, "drill.py failed at %d min: %s" % (minutes, proc.stderr[:200])
        path = os.path.join(tempfile.gettempdir(), "drill_check.json")
        data = json.load(open(path, encoding="utf-8"))
        total = sum(s["planned"] for s in data["sessions"])
        if total > minutes:
            return False, "at %d min the plan asks for %d min" % (minutes, total)
    return True, "20/30/45/60/90 分钟均未超预算"


def exam_total_ok():
    """Extra invariant: the section targets must add up to the target score."""
    script = os.path.join(ROOT, "skills/czl-math-examroom/scripts/scoreplan.py")
    for target in (90, 105, 120, 135):
        path = os.path.join(tempfile.gettempdir(), "plan_check.json")
        proc = subprocess.run(
            [PY, script, "--target", str(target), "--json", path],
            capture_output=True, text=True, cwd=ROOT, timeout=60)
        if proc.returncode != 0:
            return False, "scoreplan.py failed at %s: %s" % (target, proc.stderr[:200])
        data = json.load(open(path, encoding="utf-8"))
        got = sum(s["target"] for s in data["sections"])
        if abs(got - target) > 1.05:
            return False, "target %s but sections add to %.1f" % (target, got)
    return True, "90/105/120/135 分的目标均能对上（误差≤1）"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run the shipped scripts against real cases.")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args(argv)

    tmp = tempfile.mkdtemp(prefix="czl_math_selftest_")
    build_cases(tmp)

    results = []
    for c in CASES:
        ok, why, out = run_one(c, args.verbose)
        results.append({"case": c["name"], "passed": ok, "detail": why,
                        "cmd": "%s %s" % (c["script"], " ".join(c["args"]))})
        print("[%s] %s%s" % ("PASS" if ok else "FAIL", c["name"],
                             "" if ok else "  <- " + why))

    extra = [("不变量：训练计划不超预算", *plan_budget_ok()),
             ("不变量：分题型目标加总一致", *exam_total_ok())]
    for name, ok, detail in extra:
        results.append({"case": name, "passed": ok, "detail": detail, "cmd": "invariant"})
        print("[%s] %s  (%s)" % ("PASS" if ok else "FAIL", name, detail))

    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed
    print("\n%d passed, %d failed, %d total" % (passed, failed, len(results)))

    if not args.no_write:
        dist = os.path.join(ROOT, "dist")
        os.makedirs(dist, exist_ok=True)
        meta = {
            "package": "czl-math-home-tutor",
            "version": "1.0.0",
            "run_at": dt.datetime.now().isoformat(timespec="seconds"),
            "python": sys.version.split()[0],
            "platform": sys.platform,
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "cases": results,
        }
        with open(os.path.join(dist, "selftest.json"), "w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=2)
        with open(os.path.join(dist, "selftest.log"), "w", encoding="utf-8") as fh:
            for r in results:
                fh.write("[%s] %s\n        %s\n"
                         % ("PASS" if r["passed"] else "FAIL", r["case"], r["cmd"]))
                if not r["passed"]:
                    fh.write("        reason: %s\n" % r["detail"])
            fh.write("\n%d passed, %d failed, %d total\n" % (passed, failed, len(results)))
        print("written: dist/selftest.json, dist/selftest.log")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
