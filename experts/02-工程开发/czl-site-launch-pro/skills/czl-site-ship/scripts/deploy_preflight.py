#!/usr/bin/env python3
"""deploy_preflight.py - the last gate before a site goes live.

15 checks, five of them hard blockers. Secrets are redacted in output; the tool
never prints a full credential.

Usage:
    python deploy_preflight.py <project-dir> [--dist dist] [--json] [--fail-on blocker]

Exit codes: 0 = clear to deploy, 2 = findings at/above threshold, 1 = usage error.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SEV_ORDER = {"low": 1, "medium": 2, "high": 3, "blocker": 4}
SEV_LABEL = {"blocker": "阻塞", "high": "高", "medium": "中", "low": "低"}
SKIP_DIRS = {"node_modules", ".git", ".hg", ".svn", ".idea", ".vscode", "__pycache__", ".venv"}
TEXT_EXT = {".html", ".htm", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".vue", ".astro",
            ".css", ".json", ".xml", ".txt", ".svg", ".map", ".env", ".yml", ".yaml"}
ENV_PLACEHOLDER_FILES = {".env.example", ".env.sample", ".env.template", ".env.dist"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif", ".ico", ".svg"}

SECRET_PATTERNS = [
    ("私钥块", "blocker", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("Stripe 生产密钥", "blocker", re.compile(r"\bsk_live_[0-9a-zA-Z]{12,}")),
    ("Stripe 测试密钥", "medium", re.compile(r"\bsk_test_[0-9a-zA-Z]{12,}")),
    ("AWS Access Key", "blocker", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub Token", "blocker", re.compile(r"\bgh[pousr]_[0-9A-Za-z]{20,}")),
    ("Slack Token", "blocker", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}")),
    ("Google API Key", "blocker", re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}")),
    ("通用 sk- 密钥", "high", re.compile(r"\bsk-[A-Za-z0-9]{24,}")),
    ("企业微信/钉钉 Webhook", "medium", re.compile(r"https://(?:qyapi\.weixin\.qq\.com|oapi\.dingtalk\.com)/[^\s\"']+access_token=[0-9a-zA-Z\-]{10,}")),
]

ASSIGN_PATTERN = re.compile(
    r"(?i)\b[A-Za-z_]*(?:password|passwd|pwd|secret|api[_-]?key|apikey|access[_-]?token|auth[_-]?token)[A-Za-z_]*\b"
    r"\s*[:=]\s*[\"']([^\"'\s]{8,})[\"']"
)

ENV_REF = re.compile(r"(?:process\.env|import\.meta\.env)\.([A-Z][A-Z0-9_]{2,})")
IGNORE_ENV = {"NODE_ENV", "MODE", "DEV", "PROD", "SSR", "BASE_URL", "PUBLIC_URL", "HOST", "PORT"}

CACHE_CONFIG = ("vercel.json", "netlify.toml", "_headers", "staticwebapp.config.json", "wrangler.toml")
BUILD_CANDIDATES = ("dist", "build", "out", "_site", "public", "www")


def redact(value):
    if len(value) <= 6:
        return "*" * len(value)
    return value[:4] + "*" * min(8, len(value) - 4)


def text_files(root, limit_bytes=2 * 1024 * 1024):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = Path(dirpath) / name
            if name in ENV_PLACEHOLDER_FILES:
                continue
            if path.suffix.lower() not in TEXT_EXT and name not in (".env",):
                continue
            try:
                if path.stat().st_size > limit_bytes:
                    continue
            except OSError:
                continue
            yield path


def read_lines(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def pick_dist(project, explicit):
    if explicit:
        d = Path(explicit).expanduser()
        if not d.is_absolute():
            d = project / explicit
        return d if d.exists() else None
    for name in BUILD_CANDIDATES:
        d = project / name
        if d.is_dir() and any(d.iterdir()):
            return d
    # A plain static site is served from the project root itself.
    if any((project / n).exists() for n in ("index.html", "index.htm")):
        return project
    return None


def analyse(project, dist, threshold):
    findings = []

    def add(pid, severity, message, evidence=""):
        findings.append({"id": pid, "severity": severity, "message": message, "evidence": evidence})

    # P01 build output
    if dist is None:
        add("P01", "blocker", "没有构建产物：先把项目构建一次，部署的是产物不是源码")
    else:
        count = sum(len(f) for _, _, f in os.walk(dist))
        if count == 0:
            add("P01", "blocker", f"产物目录为空：{dist}")
        elif count < 2:
            add("P01", "medium", f"产物只有 {count} 个文件，确认构建是否完整")
    serve_root = dist or project

    # P02 shipped env files
    for name in (".env", ".env.local", ".env.production", ".env.prod"):
        if (serve_root / name).exists():
            add("P02", "blocker", f"产物目录里有 {name}，等于把配置连同密钥一起发布", str(serve_root / name))
    for name in (".env", ".env.local", ".env.production"):
        if (project / name).exists():
            gi = project / ".gitignore"
            covered = gi.exists() and ".env" in gi.read_text(encoding="utf-8", errors="replace")
            if not covered:
                add("P02", "medium", f"项目根有 {name} 且 .gitignore 未排除它，可能被提交到仓库", name)

    # P03/P04 secret patterns and hardcoded credentials
    for path in text_files(serve_root):
        rel = str(path.relative_to(serve_root)).replace("\\", "/")
        for idx, line in enumerate(read_lines(path), start=1):
            for label, severity, pattern in SECRET_PATTERNS:
                m = pattern.search(line)
                if m:
                    add("P03", severity, f"{label} 出现在 {rel}:{idx}", redact(m.group(0)))
            m2 = ASSIGN_PATTERN.search(line)
            if m2 and not any(k in line.lower() for k in ("example", "placeholder", "your_", "xxx", "<", "${")):
                add("P04", "blocker", f"疑似硬编码凭据 {rel}:{idx}", redact(m2.group(1)))

    # P05 localhost / loopback left in shipped files
    loop = re.compile(r"https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0)(?::\d+)?[^\s\"'<>]*")
    for path in text_files(serve_root):
        rel = str(path.relative_to(serve_root)).replace("\\", "/")
        for idx, line in enumerate(read_lines(path), start=1):
            m = loop.search(line)
            if m:
                add("P05", "blocker", f"产物残留本地地址 {rel}:{idx}", m.group(0)[:80])

    # P06 mixed content
    res_http = re.compile(r"(?:src|href)\s*=\s*[\"']http://[^\"']+\.(?:css|js|mjs|png|jpe?g|webp|avif|svg|woff2?|ttf)")
    css_http = re.compile(r"url\(\s*[\"']?http://")
    for path in text_files(serve_root):
        if path.suffix.lower() not in (".html", ".htm", ".css"):
            continue
        rel = str(path.relative_to(serve_root)).replace("\\", "/")
        for idx, line in enumerate(read_lines(path), start=1):
            if res_http.search(line) or css_http.search(line):
                add("P06", "high", f"资源用 http:// 引用 {rel}:{idx}", line.strip()[:90])

    # P07 404 page
    has404 = any((serve_root / n).exists() for n in ("404.html", "404/index.html", "404.htm"))
    if not has404:
        add("P07", "high", "产物缺 404 页面，静态托管会显示平台默认错误页")

    # P08 robots + sitemap
    if not (serve_root / "robots.txt").exists():
        add("P08", "medium", "缺 robots.txt（用 seo_files.py --write 生成）")
    if not (serve_root / "sitemap.xml").exists():
        add("P08", "medium", "缺 sitemap.xml（用 seo_files.py --write 生成）")

    # P09 favicon
    hasfav = any((serve_root / n).exists() for n in ("favicon.ico", "favicon.png", "favicon.svg"))
    if not hasfav:
        add("P09", "low", "缺 favicon，浏览器标签会显示默认图标")

    # P10 oversized files
    for dirpath, dirnames, filenames in os.walk(serve_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = Path(dirpath) / name
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > 2 * 1024 * 1024:
                rel = str(path.relative_to(serve_root)).replace("\\", "/")
                add("P10", "high", f"单文件超过 2MB：{rel}", f"{size / 1024 / 1024:.1f}MB")

    # P11 env vars referenced but not declared
    declared = set()
    for name in (".env.example", ".env.sample", ".env.template"):
        p = project / name
        if p.exists():
            for line in read_lines(p):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    declared.add(line.split("=", 1)[0].strip())
    referenced = set()
    for path in text_files(project):
        if path.suffix.lower() not in (".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".vue", ".astro", ".html"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        referenced.update(ENV_REF.findall(text))
    missing = sorted(referenced - declared - IGNORE_ENV)
    if missing:
        add("P11", "medium", "这些环境变量在代码里用到但没在 .env.example 声明", ", ".join(missing[:10]))

    # P12 sourcemaps shipped
    maps = []
    for dirpath, dirnames, filenames in os.walk(serve_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(".map"):
                maps.append(str((Path(dirpath) / name).relative_to(serve_root)).replace("\\", "/"))
    if maps:
        add("P12", "medium", f"产物含 {len(maps)} 个 sourcemap，源码会公开", ", ".join(maps[:3]))

    # P13 console.log leftovers
    log_count = 0
    for path in text_files(serve_root):
        if path.suffix.lower() not in (".js", ".mjs", ".html"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        log_count += len(re.findall(r"console\.(?:log|debug)\(", text))
    if log_count:
        add("P13", "low", f"产物里有 {log_count} 处 console.log/debug 残留")

    # P14 cache policy
    if not any((project / name).exists() for name in CACHE_CONFIG) and not (serve_root / "_headers").exists():
        add("P14", "medium", "没有缓存策略配置（vercel.json / netlify.toml / _headers），静态资源会反复回源")

    # P15 release identifier
    version = None
    pkg = project / "package.json"
    if pkg.exists():
        try:
            version = json.loads(pkg.read_text(encoding="utf-8")).get("version")
        except Exception:
            version = None
    for name in ("RELEASE", "VERSION", "release.txt"):
        p = project / name
        if p.exists() and not version:
            version = read_lines(p)[0].strip() if read_lines(p) else "unlabeled"
    if not version:
        add("P15", "low", "没有版本号或发布标识，出事时说不清要退回哪一版")

    worst = max([SEV_ORDER[f["severity"]] for f in findings], default=0)
    failed = worst >= SEV_ORDER[threshold]
    blockers = sum(1 for f in findings if f["severity"] == "blocker")
    if blockers:
        verdict = "不可上线"
    elif any(f["severity"] == "high" for f in findings):
        verdict = "有条件上线"
    else:
        verdict = "可上线"

    return {
        "project": str(project),
        "serve_root": str(serve_root),
        "findings": sorted(findings, key=lambda x: (-SEV_ORDER[x["severity"]], x["id"])),
        "counts": {k: sum(1 for f in findings if f["severity"] == k) for k in ("blocker", "high", "medium", "low")},
        "verdict": verdict,
        "failed": failed,
    }


def main():
    ap = argparse.ArgumentParser(description="上线前预检")
    ap.add_argument("path")
    ap.add_argument("--dist")
    ap.add_argument("--fail-on", default="blocker", choices=["low", "medium", "high", "blocker"])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    project = Path(args.path).expanduser()
    if not project.exists() or not project.is_dir():
        print(f"目录不存在: {project}")
        return 1
    project = project.resolve()

    dist = pick_dist(project, args.dist)
    report = analyse(project, dist, args.fail_on)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2 if report["failed"] else 0

    print(f"上线预检 · {report['project']}")
    print(f"产物目录 · {report['serve_root']}")
    print("-" * 56)
    if not report["findings"]:
        print("15 项全部通过。")
    for f in report["findings"]:
        ev = f" —— {f['evidence']}" if f["evidence"] else ""
        print(f"[{SEV_LABEL[f['severity']]}] {f['id']} {f['message']}{ev}")
    c = report["counts"]
    total = c["blocker"] + c["high"] + c["medium"] + c["low"]
    print()
    print(f"共 {total} 条：阻塞 {c['blocker']} / 高 {c['high']} / 中 {c['medium']} / 低 {c['low']}")
    print(f"结论：{report['verdict']}")
    if c["blocker"]:
        print("阻塞项清零之前，不给部署命令。先吊销已泄漏的密钥，再改代码。")
    return 2 if report["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
