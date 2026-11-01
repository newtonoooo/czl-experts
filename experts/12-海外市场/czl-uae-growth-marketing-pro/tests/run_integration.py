#!/usr/bin/env python3
"""
run_integration.py - End-to-end checks that exercise the shipped CLIs exactly
as an agent would call them (via subprocess, real exit codes, real stdout).

Unit tests cover internal logic; this script covers the contract: does the
command run, does it exit with the documented code, does it emit what the
workflow expects.

Usage: python tests/run_integration.py
Exit:  0 all checks pass, 1 any failure
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

CHECKS: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    CHECKS.append((name, passed, detail))


def run(args: list[str], expect_code: int = 0) -> subprocess.CompletedProcess:
    return subprocess.run([PY, *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")


def check_plan_cli() -> None:
    proc = run(["bin/uae_plan.py", "--budget", "300000", "--objective", "awareness",
                "--audience", "core", "--sector", "beauty", "--market", "uae_wide"])
    record("uae_plan 基础调用", proc.returncode == 0, f"exit={proc.returncode}")
    record("uae_plan 输出含渠道表", "| 渠道 |" in proc.stdout)
    record("uae_plan 输出含建模假设", "建模假设" in proc.stdout)

    proc = run(["bin/uae_plan.py", "--budget", "300000", "--objective", "conversion",
                "--audience", "expand", "--sector", "ecommerce", "--format", "json"])
    ok = proc.returncode == 0
    if ok:
        plan = json.loads(proc.stdout)
        ok = plan["totals"]["spend"] == plan["working_budget"]
    record("uae_plan JSON 模式且分配精确", ok)

    proc = run(["bin/uae_plan.py", "--budget", "0", "--objective", "awareness",
                "--audience", "core", "--sector", "beauty"], expect_code=2)
    record("uae_plan 拒绝非法预算", proc.returncode == 2, f"exit={proc.returncode}")

    # Sweep every objective x four budget tiers: no crash, always exact.
    sweep_ok = True
    detail = []
    for budget in (15000, 80000, 300000, 900000):
        for objective in ("awareness", "consideration", "conversion", "retention"):
            p = run(["bin/uae_plan.py", "--budget", str(budget), "--objective", objective,
                     "--audience", "mixed", "--sector", "travel", "--format", "json"])
            if p.returncode != 0:
                sweep_ok = False
                detail.append(f"{budget}/{objective} exit={p.returncode}")
                continue
            data = json.loads(p.stdout)
            if data["totals"]["spend"] != data["working_budget"]:
                sweep_ok = False
                detail.append(f"{budget}/{objective} drift")
    record("uae_plan 16 组预算×目标全通过", sweep_ok, "; ".join(detail))


def check_compliance_cli() -> None:
    proc = run(["bin/uae_compliance.py", "--text", "限时秒杀，100% 保证有效，全网第一品牌",
                "--sector", "beauty"], expect_code=1)
    record("uae_compliance High 风险返回 1", proc.returncode == 1, f"exit={proc.returncode}")
    record("uae_compliance 输出阻断结论", "阻断" in proc.stdout)

    proc = run(["bin/uae_compliance.py", "--text", "欢迎光临本店，营业时间见门口公告"])
    record("uae_compliance 干净文案返回 0", proc.returncode == 0, f"exit={proc.returncode}")

    proc = run(["bin/uae_compliance.py", "--text", "包就业，保录取", "--sector", "education",
                "--format", "json"], expect_code=1)
    data = json.loads(proc.stdout) if proc.stdout else {}
    record("uae_compliance 行业规则生效",
           any(f["rule_id"] == "EDU-01" for f in data.get("findings", [])))

    with tempfile.TemporaryDirectory() as tmp:
        sample = Path(tmp) / "copy.md"
        sample.write_text("我们的产品是行业唯一选择，保证收益。", encoding="utf-8")
        proc = run(["bin/uae_compliance.py", "--file", str(sample), "--sector", "fintech"])
        record("uae_compliance 文件模式", proc.returncode == 1 and "FIN-01" in proc.stdout,
               f"exit={proc.returncode}")


def check_calendar_cli() -> None:
    proc = run(["bin/uae_campaign_calendar.py", "--year", "2027"])
    record("uae_campaign_calendar 基础调用", proc.returncode == 0, f"exit={proc.returncode}")
    record("uae_campaign_calendar 含斋月窗口", "斋月期" in proc.stdout)
    record("uae_campaign_calendar 含官方观月提示", "官方观月" in proc.stdout)

    proc = run(["bin/uae_campaign_calendar.py", "--year", "2027",
                "--ramadan-start", "2027-02-12", "--format", "json"])
    data = json.loads(proc.stdout)
    record("uae_campaign_calendar 官方日期覆盖生效", data["ramadan_start"] == "2027-02-12")

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "campaign.ics"
        proc = run(["bin/uae_campaign_calendar.py", "--year", "2027",
                    "--format", "ics", "--out", str(out)])
        content = out.read_text(encoding="utf-8") if out.exists() else ""
        record("uae_campaign_calendar ICS 导出",
               proc.returncode == 0 and content.startswith("BEGIN:VCALENDAR")
               and content.count("BEGIN:VEVENT") >= 8)

    proc = run(["bin/uae_campaign_calendar.py", "--year", "1999"], expect_code=2)
    record("uae_campaign_calendar 拒绝越界年份", proc.returncode == 2, f"exit={proc.returncode}")


def check_intel_cli() -> None:
    proc = run(["skills/uae-market-intel/scripts/intel_query.py", "segments"])
    record("intel_query 人群查询", proc.returncode == 0 and "本国公民" in proc.stdout)

    proc = run(["skills/uae-market-intel/scripts/intel_query.py", "channel", "--id", "tiktok"])
    record("intel_query 渠道查询", proc.returncode == 0 and "TikTok" in proc.stdout)

    proc = run(["skills/uae-market-intel/scripts/intel_query.py", "channels-for",
                "--sector", "beauty", "--format", "json"])
    data = json.loads(proc.stdout) if proc.returncode == 0 else []
    record("intel_query 行业渠道排序", len(data) == 13 and data[0]["fit_score"] >= data[-1]["fit_score"])

    proc = run(["skills/uae-market-intel/scripts/intel_query.py", "channel", "--id", "nope"],
               expect_code=2)
    record("intel_query 拒绝未知 id", proc.returncode == 2, f"exit={proc.returncode}")


def check_package_cli() -> None:
    proc = run(["bin/package_check.py"])
    record("package_check 自检通过", proc.returncode == 0, f"exit={proc.returncode}")
    record("package_check 无 FAIL", "FAIL 0" in proc.stdout)

    proc = run(["bin/avatar_tool.py", "avatars/expert.png", "avatars/_selftest.png",
                "--size", "256", "--radius", "0"])
    record("avatar_tool 可重新归一化", proc.returncode == 0)
    (ROOT / "avatars" / "_selftest.png").unlink(missing_ok=True)


def main() -> int:
    check_plan_cli()
    check_compliance_cli()
    check_calendar_cli()
    check_intel_cli()
    check_package_cli()

    print("# 集成测试结果\n")
    print("| 结果 | 检查项 | 详情 |")
    print("|------|--------|------|")
    for name, passed, detail in CHECKS:
        print(f"| {'PASS' if passed else 'FAIL'} | {name} | {detail or '—'} |")

    failed = [c for c in CHECKS if not c[1]]
    print(f"\n合计：{len(CHECKS) - len(failed)} PASS · {len(failed)} FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
