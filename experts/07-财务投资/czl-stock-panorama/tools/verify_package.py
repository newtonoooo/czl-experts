"""包体检：把一个专家包按平台导入要求逐项过一遍。

检查项（任何一项 FAIL 都不应上架）：
 1. plugin.json 可解析、必填字段齐全；
 2. 包名 czl- 前缀、只含小写与连字符、与目录名一致；
 3. 版本号为语义化版本；
 4. 双语文案齐全（displayName / profession / displayDescription / defaultInitPrompt）；
 5. defaultInitPrompt 与 quickPrompts[0] 逐字一致（平台硬规则，不一致直接解析失败）；
 6. 头像格式符合所选模式：
      market（默认，提交平台上架）——必须是带 .png/.jpg/.jpeg/.webp 的路径；
      local（本地分发）——必须是内联 data URI；
 7. 头像文件真实存在、是合法 PNG、正方形、≤512KB；
 8. agents / skills 引用路径都存在；
 9. 全包无本机绝对路径；
10. agent frontmatter 关键字段齐全；
11. 全部 Python 脚本可编译；
12. 必需文档齐全、CHANGELOG 版本与包版本一致、免责声明存在；
13. 技能自测通过（可跳过）。

用法：
    python tools/verify_package.py                      # 按平台上架标准检查
    python tools/verify_package.py --avatar-mode local
    python tools/verify_package.py --no-tests
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import py_compile
import re
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, ".codebuddy-plugin", "plugin.json")
REQUIRED_DOCS = ("README.md", "USAGE.md", "CHANGELOG.md", "LICENSE", "NOTICE.md")
DOCS_DIR = ("docs/SPEC.md", "docs/平台展示文案.md", "docs/文件清单.md",
            "docs/开发记录.md", "docs/功能测试报告.md", "docs/商业发布风险清单.md")
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")
LANGS = ("zh", "en")

results = []


def ok(name, detail=""):
    results.append(("PASS", name, detail))


def bad(name, detail=""):
    results.append(("FAIL", name, detail))


def warn(name, detail=""):
    results.append(("WARN", name, detail))


def png_size(raw: bytes):
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    w, h = struct.unpack(">II", raw[16:24])
    return w, h


def check_manifest(mode: str):
    if not os.path.exists(PLUGIN):
        bad("plugin.json 存在")
        return None
    try:
        data = json.load(open(PLUGIN, "r", encoding="utf-8"))
    except Exception as exc:
        bad("plugin.json 可解析", str(exc))
        return None
    ok("plugin.json 可解析")

    need = ["name", "version", "description", "author", "agents", "skills",
            "expertType", "agentName", "displayName", "profession",
            "displayDescription", "avatar", "categoryId", "tags", "quickPrompts"]
    missing = [k for k in need if not data.get(k)]
    (ok if not missing else bad)("必填字段齐全", ",".join(missing) if missing else "")

    name = data.get("name", "")
    if not name.startswith("czl-"):
        bad("包名 czl- 前缀", name)
    elif not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
        bad("包名只含小写字母/数字/连字符", name)
    else:
        ok("包名格式", name)
    (ok if name == os.path.basename(ROOT) else bad)("包名与目录名一致",
                                                    f"{name} vs {os.path.basename(ROOT)}")
    ok("作者信息", json.dumps(data.get("author"), ensure_ascii=False))

    ver = data.get("version", "")
    (ok if re.fullmatch(r"\d+\.\d+\.\d+", ver) else bad)("版本号为语义化版本", ver)

    for key in ("displayName", "profession", "displayDescription", "defaultInitPrompt"):
        block = data.get(key) or {}
        got = [l for l in LANGS if isinstance(block, dict) and str(block.get(l) or "").strip()]
        (ok if len(got) == 2 else bad)(f"{key} 中英文齐全", ",".join(got))

    # 平台硬规则：初始提示词与首条快捷词必须逐字一致
    qp = data.get("quickPrompts") or []
    if qp:
        init = data.get("defaultInitPrompt") or {}
        same_zh = str(init.get("zh") or "").strip() == str(qp[0].get("zh") or "").strip()
        same_en = str(init.get("en") or "").strip() == str(qp[0].get("en") or "").strip()
        (ok if same_zh else bad)("defaultInitPrompt.zh == quickPrompts[0].zh",
                                 "" if same_zh else f"init={init.get('zh')!r} / qp0={qp[0].get('zh')!r}")
        (ok if same_en else bad)("defaultInitPrompt.en == quickPrompts[0].en",
                                 "" if same_en else f"init={init.get('en')!r} / qp0={qp[0].get('en')!r}")
        (ok if 1 <= len(qp) <= 3 else warn)("quickPrompts 条数 1–3", str(len(qp)))
    else:
        bad("quickPrompts 非空")

    tags = data.get("tags") or []
    (ok if len(tags) == 3 else warn)("tags 三条", str(len(tags)))

    for p in data.get("agents", []):
        full = os.path.normpath(os.path.join(ROOT, p))
        (ok if os.path.isfile(full) else bad)("agent 文件存在", p)
    for p in data.get("skills", []):
        full = os.path.normpath(os.path.join(ROOT, p))
        (ok if os.path.isdir(full) and os.path.isfile(os.path.join(full, "SKILL.md")) else bad)(
            "技能目录与 SKILL.md 存在", p)

    check_avatar(data.get("avatar", ""), mode)
    return data


def check_avatar(av: str, mode: str):
    if not av:
        bad("头像字段非空")
        return
    is_uri = av.startswith("data:image/")
    ext = "" if is_uri else os.path.splitext(av.split("?", 1)[0])[1].lower()

    if mode == "market":
        if is_uri:
            bad("头像为带扩展名的图片路径（平台上架要求）",
                "当前是 data URI，平台会报『格式不支持：无扩展名』；"
                "提交上架请用 set_avatar_mode.py --mode path")
            raw = base64.b64decode(av.split(",", 1)[1])
        elif ext in IMG_EXT:
            ok("头像扩展名合法", ext)
            p = os.path.normpath(os.path.join(ROOT, av))
            if not os.path.isfile(p):
                bad("头像文件存在", av)
                return
            raw = open(p, "rb").read()
            ok("头像文件存在", av)
        else:
            bad("头像扩展名合法", ext or "（无扩展名）")
            return
    else:
        if not is_uri:
            warn("本地分发包建议使用 data URI",
                 "相对路径在未上传 CDN 的环境会退化为文字图标；"
                 "如需本地分发请 set_avatar_mode.py --mode data-uri")
            p = os.path.normpath(os.path.join(ROOT, av))
            if not os.path.isfile(p):
                bad("头像文件存在", av)
                return
            raw = open(p, "rb").read()
        else:
            ok("头像为内联 data URI", f"{len(av)} chars")
            try:
                raw = base64.b64decode(av.split(",", 1)[1])
            except Exception as exc:
                bad("头像 data URI 可解码", str(exc))
                return

    size = png_size(raw)
    if not size:
        bad("头像为合法 PNG", raw[:8].hex())
        return
    w, h = size
    ok("头像为合法 PNG", f"{w}x{h}, {len(raw)} bytes")
    (ok if w == h else bad)("头像为正方形", f"{w}x{h}")
    (ok if max(w, h) <= 1024 else warn)("头像尺寸不超标", f"{w}x{h}")
    (ok if len(raw) <= 512 * 1024 else bad)("头像体积 ≤500KB", f"{len(raw)} bytes")


def check_paths():
    abs_pat = re.compile(r"(?:[A-Za-z]:\\\\|[A-Za-z]:/Users|/Users/|/home/)")
    hits = []
    for base, _, files in os.walk(ROOT):
        if "dist" in base or "__pycache__" in base:
            continue
        for f in files:
            if not f.endswith((".json", ".md", ".py", ".txt")):
                continue
            if f == "verify_package.py":   # 本文件内含绝对路径正则字面量，跳过自身
                continue
            p = os.path.join(base, f)
            try:
                text = open(p, "r", encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            if p.endswith("plugin.json") and '"avatar": "data:image' in text:
                text = text.split('"avatar": "data:image')[0]
            for m in abs_pat.finditer(text):
                hits.append(f"{os.path.relpath(p, ROOT)}: {m.group(0)}")
                break
    (ok if not hits else bad)("无本机绝对路径", "; ".join(hits[:4]))


def check_frontmatter():
    p = os.path.join(ROOT, "agents", "czl-stock-panorama.md")
    if not os.path.isfile(p):
        bad("agent frontmatter", "文件不存在")
        return
    text = open(p, "r", encoding="utf-8").read()
    if not text.startswith("---"):
        bad("agent frontmatter 起始标记")
        return
    fm = text.split("---", 2)[1]
    keys = [k for k in ("name:", "description:", "displayName", "profession", "maxTurns") if k in fm]
    (ok if len(keys) == 5 else bad)("agent frontmatter 字段", ",".join(keys))


def check_python():
    bad_files = []
    count = 0
    for base, _, files in os.walk(ROOT):
        if "__pycache__" in base or "dist" in base:
            continue
        for f in files:
            if not f.endswith(".py"):
                continue
            count += 1
            try:
                py_compile.compile(os.path.join(base, f), doraise=True,
                                   cfile=os.path.join(base, "__pycache__", f + "c"))
            except py_compile.PyCompileError as exc:
                bad_files.append(f"{f}: {exc.msg.splitlines()[0] if exc.msg else ''}")
    (ok if not bad_files else bad)("Python 脚本可编译",
                                   f"{count} 个文件" if not bad_files else "; ".join(bad_files))


def check_docs(data):
    for d in REQUIRED_DOCS:
        (ok if os.path.isfile(os.path.join(ROOT, d)) else bad)("文档存在", d)
    for d in DOCS_DIR:
        (ok if os.path.isfile(os.path.join(ROOT, d)) else bad)("文档存在", d)
    cl = os.path.join(ROOT, "CHANGELOG.md")
    if os.path.isfile(cl) and data:
        text = open(cl, "r", encoding="utf-8").read()
        (ok if data.get("version", "") and data["version"] in text[:800] else warn)(
            "CHANGELOG 版本与包版本一致", f"package={data.get('version')}")
    dis = os.path.join(ROOT, "agents", "czl-stock-panorama.md")
    if os.path.isfile(dis):
        (ok if "不构成投资建议" in open(dis, "r", encoding="utf-8").read() else bad)("免责声明存在")


def check_tests():
    scripts = os.path.join(ROOT, "skills", "stock-panorama-core", "scripts")
    tests = os.path.join(ROOT, "skills", "stock-panorama-core", "tests", "selftest.py")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, tests], cwd=scripts, capture_output=True,
                       text=True, encoding="utf-8", env=env)
    tail = (r.stdout or "").strip().splitlines()[-1] if r.stdout else ""
    (ok if r.returncode == 0 else bad)("技能自测通过", tail or r.stderr[-200:])


def main():
    global ROOT, PLUGIN
    ap = argparse.ArgumentParser()
    ap.add_argument("--avatar-mode", choices=["market", "local"], default="market")
    ap.add_argument("--no-tests", action="store_true")
    ap.add_argument("--zip", help="直接验收一个发布包（解压到临时目录后全量检查）")
    args = ap.parse_args()

    if args.zip:
        import tempfile
        import zipfile
        tmp = tempfile.mkdtemp(prefix="wb_pkg_verify_")
        with zipfile.ZipFile(args.zip) as zf:
            names = zf.namelist()
            tops = {n.split("/")[0] for n in names if n}
            if len(tops) != 1:
                print(f"[FAIL] zip 顶层目录唯一 :: 发现 {sorted(tops)}")
                return 1
            zf.extractall(tmp)
        ROOT = os.path.join(tmp, tops.pop())
        PLUGIN = os.path.join(ROOT, ".codebuddy-plugin", "plugin.json")
        print(f"验收目标：{os.path.abspath(args.zip)} -> {ROOT}")
        extra = [("PASS", "zip 顶层目录唯一", os.path.basename(ROOT))]
        results.extend(extra)

    data = check_manifest(args.avatar_mode)
    check_paths()
    check_frontmatter()
    check_python()
    check_docs(data)
    if not args.no_tests:
        check_tests()

    print("=" * 60)
    for level, name, detail in results:
        line = f"[{level}] {name}"
        if detail:
            line += f" :: {detail}"
        print(line)
    fails = [r for r in results if r[0] == "FAIL"]
    warns = [r for r in results if r[0] == "WARN"]
    print("=" * 60)
    print(f"模式 {args.avatar_mode}｜合计 {len(results)} 项：通过 {len(results)-len(fails)-len(warns)}，"
          f"警告 {len(warns)}，失败 {len(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
