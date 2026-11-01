#!/usr/bin/env python3
"""run_tests.py - self-test for the five bundled audit/deploy scripts.

Runs each script against the fixtures and asserts exit codes plus the lines that
matter. No network, no third-party packages.

Usage:
    python tests/run_tests.py [-v]

Exit codes: 0 = all passed, 1 = at least one failure.
"""

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIXTURES = HERE / "fixtures"
SCAN = ROOT / "skills/czl-site-build/scripts/project_scan.py"
AUDIT = ROOT / "skills/czl-site-build/scripts/audit_html.py"
BUDGET = ROOT / "skills/czl-site-build/scripts/budget_check.py"
SEO = ROOT / "skills/czl-site-build/scripts/seo_files.py"
PREFLIGHT = ROOT / "skills/czl-site-ship/scripts/deploy_preflight.py"

RESULTS = []


def run(script, *args, cwd=None):
    proc = subprocess.run(
        [sys.executable, str(script), *[str(a) for a in args]],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + ("" if condition else f"\n        {detail}"))


def make_over_budget(dirpath):
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / "index.html").write_text(
        "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        "<title>体积超预算样例</title></head><body><h1>样例</h1></body></html>",
        encoding="utf-8",
    )
    blob = base64.b64encode(os.urandom(420 * 1024)).decode("ascii")
    (dirpath / "app.js").write_text("var payload=\"" + blob + "\";\n", encoding="utf-8")
    return dirpath


def main():
    verbose = "-v" in sys.argv

    # --- project_scan ---------------------------------------------------
    code, out = run(SCAN, FIXTURES / "good-site")
    check("scan: good-site 识别为 static", code == 0 and "static" in out, out[:400])
    check("scan: 报告 404 与 robots 存在", "404 有" in out and "robots.txt 有" in out, out[:600])

    code, out = run(SCAN, FIXTURES / "leaky-app", "--json")
    try:
        data = json.loads(out)
        ok = data["serve_dir"] == "dist" and data["kind"] in ("node-other", "unknown")
    except Exception:
        ok = False
        data = {}
    check("scan: leaky-app JSON 可解析且指向 dist", ok, out[:400])

    # --- audit_html -----------------------------------------------------
    code, out = run(AUDIT, FIXTURES / "good-site")
    check("audit: good-site 退出码 0", code == 0, out[-600:])
    check("audit: good-site 无阻塞无高危", "阻塞 0" in out and "高 0" in out, out[-600:])

    code, out = run(AUDIT, FIXTURES / "bad-site")
    check("audit: bad-site 退出码 2", code == 2, out[-400:])
    for rule in ("H001", "H009", "H011", "H013"):
        check(f"audit: bad-site 命中 {rule}", rule in out, out[:800])

    code, out = run(AUDIT, FIXTURES / "bad-site", "--json")
    try:
        data = json.loads(out)
        ok = data["counts"]["blocker"] >= 1 and len(data["findings"]) >= 8
    except Exception:
        ok = False
    check("audit: bad-site JSON 含阻塞项与规则明细", ok, out[:400])

    # --- budget_check ---------------------------------------------------
    code, out = run(BUDGET, FIXTURES / "good-site")
    check("budget: good-site 通过", code == 0 and "结论：通过" in out, out[-500:])

    with tempfile.TemporaryDirectory() as tmp:
        heavy = make_over_budget(Path(tmp) / "over")
        code, out = run(BUDGET, heavy)
        check("budget: 超预算样例退出码 2", code == 2, out[-500:])
        check("budget: 指出 JS 超预算", "JS（gzip）" in out and "超预算" in out, out[-500:])

    # --- seo_files ------------------------------------------------------
    code, out = run(SEO, FIXTURES / "good-site", "--base-url", "https://example.com")
    check("seo: good-site 只读模式退出码 0", code == 0, out[-500:])
    check("seo: 404 被排除，进入 sitemap 2 页", "进入 sitemap：2 页" in out, out[-600:])

    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "site"
        shutil.copytree(FIXTURES / "good-site", copy)
        (copy / "sitemap.xml").unlink()
        (copy / "robots.txt").unlink()
        code, out = run(SEO, copy, "--base-url", "https://example.com", "--write", "--force")
        sm = (copy / "sitemap.xml").read_text(encoding="utf-8") if (copy / "sitemap.xml").exists() else ""
        rb = (copy / "robots.txt").read_text(encoding="utf-8") if (copy / "robots.txt").exists() else ""
        check("seo: --write 生成 sitemap 与 robots", code == 0 and sm.count("<loc>") == 2 and "Sitemap:" in rb,
              out[-500:])
        check("seo: 404 未进入 sitemap", "404.html" not in sm, sm[:300])

    code, out = run(SEO, FIXTURES / "good-site", "--base-url", "example.com")
    check("seo: 非法 base-url 退出码 2", code == 2, out[:300])

    # --- deploy_preflight -----------------------------------------------
    code, out = run(PREFLIGHT, FIXTURES / "good-site")
    check("preflight: good-site 无阻塞（退出码 0）", code == 0 and "阻塞 0" in out, out[-800:])
    check("preflight: good-site 结论为可上线", "可上线" in out, out[-400:])

    code, out = run(PREFLIGHT, FIXTURES / "leaky-app")
    check("preflight: leaky-app 退出码 2", code == 2, out[-500:])
    for pid in ("P03", "P04", "P05", "P12"):
        check(f"preflight: 命中 {pid}", pid in out, out[:900])
    check("preflight: 密钥已脱敏", "sk_live_51H8xQ2eZvKYlo2C9abcdefghijklmn" not in out, "输出里出现了完整密钥")
    check("preflight: 标注不可上线", "不可上线" in out, out[-300:])

    code, out = run(PREFLIGHT, FIXTURES / "leaky-app", "--json")
    try:
        data = json.loads(out)
        ok = data["failed"] is True and data["counts"]["blocker"] >= 1
    except Exception:
        ok = False
    check("preflight: JSON 结构与判定一致", ok, out[:400])

    # --- 参数与异常路径 -------------------------------------------------
    code, out = run(AUDIT, FIXTURES / "does-not-exist")
    check("audit: 路径不存在时退出码 1", code == 1, out[:200])

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print()
    print(f"结果：{passed}/{total} 通过")
    if passed != total:
        print("失败项：")
        for name, ok, detail in RESULTS:
            if not ok:
                print(f"  - {name}")
        return 1
    if verbose:
        print("所有脚本按预期工作。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
