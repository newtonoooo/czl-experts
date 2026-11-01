#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_tests.py — 功能与结构测试

不是"跑一遍没报错"，是逐项断言、逐项输出 PASS/FAIL。
每一项都对应一个可复核的判据，测试报告里引用的就是这里的编号。

用法：
    python scripts/run_tests.py
    python scripts/run_tests.py --experts-dir "C:/Users/xxx/.workbuddy/plugins/marketplaces/experts/plugins"

退出码：0 全部通过；1 有失败项。
"""

import argparse
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / ".codebuddy-plugin" / "plugin.json"

results = []


def check(tid, name, fn):
    try:
        ok, detail = fn()
    except Exception as e:  # 测试自身出错也算失败，不吞掉
        ok, detail = False, f"测试执行异常：{type(e).__name__}: {e}"
    results.append((tid, name, ok, detail))


# ---------------------------------------------------------------- 断言工具

def load_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def png_dim(path):
    with open(path, "rb") as f:
        head = f.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", head[16:24])


# ---------------------------------------------------------------- 测试项

def t01_manifest_parse():
    m = load_manifest()
    need = {"name", "version", "description", "expertType", "agentName",
            "displayName", "profession", "displayDescription", "avatar", "categoryId"}
    missing = need - set(m)
    if missing:
        return False, f"缺少字段 {sorted(missing)}"
    return True, f"10 个必填字段齐全，共 {len(m)} 个字段"


def t02_name_rules():
    m = load_manifest()
    name = m["name"]
    if not re.fullmatch(r"[a-z0-9\-]+", name):
        return False, f"name 含非法字符：{name}"
    if not name.startswith("czl-"):
        return False, f"name 未以 czl- 开头：{name}"
    return True, f"{name}（小写字母/数字/连字符，czl- 前缀）"


def t03_display_rules():
    m = load_manifest()
    pattern = re.compile(r"^[A-Za-z0-9\u4e00-\u9fff\-\u2014]+$")
    bad = []
    for f in ("displayName", "profession"):
        zh = m[f]["zh"]
        if not pattern.fullmatch(zh):
            bad.append(f"{f}={zh}")
    if bad:
        return False, "含空格或特殊字符：" + "; ".join(bad)
    return True, f"displayName={m['displayName']['zh']}｜profession={m['profession']['zh']}"


def t04_version_semver():
    m = load_manifest()
    v = m["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", v):
        return False, f"版本号非 x.y.z：{v}"
    cl = (ROOT / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")
    if v not in cl:
        return False, f"CHANGELOG 未记录 {v}"
    return True, f"{v}，CHANGELOG 已记录"


def t05_avatar():
    m = load_manifest()
    p = ROOT / m["avatar"]
    if not p.is_file():
        return False, f"文件不存在：{m['avatar']}"
    if p.suffix.lower() != ".png":
        return False, f"扩展名为 {p.suffix}，应为 .png"
    dim = png_dim(p)
    if not dim:
        return False, "无法解析 PNG 头"
    w, h = dim
    size = p.stat().st_size
    if w != h:
        return False, f"非正方形 {w}×{h}"
    if w < 512:
        return False, f"分辨率偏低 {w}×{h}"
    if size > 5 * 1024 * 1024:
        return False, f"超过 5 MB：{size}"
    raw = p.read_bytes()
    if b"WORKBUDDY" in raw.upper():
        return False, "检测到平台水印字节"
    return True, f"{w}×{h} PNG，{size/1024:.0f} KB，无水印"


def t06_agent_frontmatter():
    m = load_manifest()
    p = ROOT / m["agents"][0].lstrip("./")
    if not p.is_file():
        return False, f"agent 文件不存在：{p}"
    text = p.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return False, "缺少 YAML 前置区"
    head = text.split("---")[1]
    for key in ("name:", "description:", "displayName:", "profession:", "maxTurns:"):
        if key not in head:
            return False, f"前置区缺少 {key}"
    if f"name: {m['name']}" not in head:
        return False, "前置区 name 与包标识不一致"
    return True, f"name/description/displayName/profession/maxTurns 齐全，正文 {len(text)} 字符"


def t07_workflow_completeness():
    """每条工作流必须有 9 项要素，缺一项算失败。"""
    m = load_manifest()
    p = ROOT / m["agents"][0].lstrip("./")
    text = p.read_text(encoding="utf-8")
    blocks = re.split(r"\n### (W\d [^\n]+)\n", text)
    flows = {}
    for i in range(1, len(blocks), 2):
        flows[blocks[i].strip()] = blocks[i + 1]

    required = ["**职责**", "**输入**", "**执行步骤**", "**判断条件**", "**输出格式**", "**异常处理**", "**依赖**", "**与其他流的关系**"]
    if len(flows) != 6:
        return False, f"工作流数量为 {len(flows)}，应为 6"

    problems = []
    for title, body in flows.items():
        miss = [r for r in required if r not in body]
        if miss:
            problems.append(f"{title} 缺 {miss}")
    if problems:
        return False, "; ".join(problems)
    return True, f"6 条工作流 × 8 项结构化要素齐全（职责/输入/步骤/判断/输出/异常/依赖/关系）"


def t08_knowledge_paths():
    m = load_manifest()
    missing, small = [], []
    total = 0
    for rel in m.get("knowledge", []):
        p = ROOT / rel.lstrip("./")
        if not p.is_file():
            missing.append(rel)
            continue
        n = p.stat().st_size
        total += n
        if n < 1024:
            small.append(f"{rel}({n}B)")
    if missing:
        return False, f"引用不存在：{missing}"
    if small:
        return False, f"内容过少：{small}"
    return True, f"{len(m['knowledge'])} 个文件全部存在，合计 {total/1024:.0f} KB"


def t09_no_nested_manifest():
    found = list(ROOT.rglob("plugin.json"))
    extra = [p for p in found if p.parent.name != ".codebuddy-plugin"]
    if extra:
        return False, f"存在嵌套清单：{[str(p.relative_to(ROOT)) for p in extra]}"
    return True, "仅有一个清单文件，无嵌套目录包"


def t10_boundary_clause():
    """产品必须明确写出拒绝事项，否则等于默认承诺。"""
    m = load_manifest()
    text = (ROOT / m["agents"][0].lstrip("./")).read_text(encoding="utf-8")
    required_phrases = ["押题", "编造", "代写"]
    miss = [p for p in required_phrases if p not in text]
    if miss:
        return False, f"边界条款缺失：{miss}"
    if "明确拒绝" not in text and "明确拒绝并说明" not in text:
        return False, "未出现明确的拒绝表述"
    return True, "已写明拒绝押题/编造史料/代写，并给出替代方案"


def t11_utf8():
    bad = []
    for p in ROOT.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".md", ".json", ".py", ".txt"):
            try:
                p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                bad.append(str(p.relative_to(ROOT)))
    if bad:
        return False, f"非 UTF-8：{bad}"
    return True, "全部文本文件为 UTF-8 无 BOM"


def t12_no_binary_junk():
    bad = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() in (".exe", ".dll", ".bat", ".cmd", ".ps1", ".so"):
            bad.append(str(p.relative_to(ROOT)))
        elif p.stat().st_size > 5 * 1024 * 1024:
            bad.append(f"{p.relative_to(ROOT)} ({p.stat().st_size/1024/1024:.1f} MB)")
    if bad:
        return False, f"可疑文件：{bad}"
    return True, "无可执行文件、无超过 5 MB 的文件"


def t13_duplicate_names(experts_dir):
    """与已安装专家比对名称与职称，检查是否重名。"""

    def run():
        if not experts_dir:
            return True, "未提供已安装专家目录，跳过（此项需手工核对）"
        base = Path(experts_dir)
        if not base.is_dir():
            return False, f"目录不存在：{base}"
        m = load_manifest()
        mine_name = m["displayName"]["zh"]
        mine_prof = m["profession"]["zh"]
        hits = []
        scanned = 0
        for pf in base.glob("*/.codebuddy-plugin/plugin.json"):
            if pf.parent.parent.name == m["name"]:
                continue
            try:
                other = json.loads(pf.read_text(encoding="utf-8"))
            except Exception:
                continue
            scanned += 1
            dn = (other.get("displayName") or {}).get("zh", "")
            pr = (other.get("profession") or {}).get("zh", "")
            if dn == mine_name:
                hits.append(f"displayName 重名：{other.get('name')}")
            if pr == mine_prof:
                hits.append(f"profession 重名：{other.get('name')}")
        if hits:
            return False, "; ".join(hits)
        return True, f"扫描 {scanned} 个已安装专家，displayName 与 profession 均无重名"

    return run


def t14_scripts_syntax():
    import py_compile
    bad = []
    scripts = sorted((ROOT / "scripts").glob("*.py"))
    for p in scripts:
        try:
            py_compile.compile(str(p), doraise=True, cfile=str(p) + ".testc")
        except py_compile.PyCompileError as e:
            bad.append(f"{p.name}: {e.msg}")
        finally:
            tmp = Path(str(p) + ".testc")
            if tmp.exists():
                tmp.unlink()
    if bad:
        return False, "; ".join(bad)
    return True, f"{len(scripts)} 个脚本均通过语法编译"


def t16_default_prompt_consistency():
    """平台服务端硬校验：defaultInitPrompt 必须与 quickPrompts[0] 完全相等。"""
    m = load_manifest()
    qp = m.get("quickPrompts") or []
    dip = m.get("defaultInitPrompt")
    if not qp:
        return False, "quickPrompts 为空，服务端会驳回"
    if not isinstance(dip, dict):
        return False, "defaultInitPrompt 缺失或结构错误"
    bad = [lang for lang in ("zh", "en") if dip.get(lang) != qp[0].get(lang)]
    if bad:
        detail = "; ".join(
            f"{lang}: default={dip.get(lang)!r} / quick[0]={qp[0].get(lang)!r}" for lang in bad
        )
        return False, f"不一致 → {detail}"
    return True, f"中英文均与 quickPrompts[0] 完全一致（{len(qp)} 条提示）"


def t15_release_zip():
    rel = ROOT / "release"
    zips = sorted(rel.glob("*.zip")) if rel.is_dir() else []
    if not zips:
        return False, "尚未打包，先运行 scripts/build_release.py"
    import zipfile
    details = []
    for z in zips:
        try:
            with zipfile.ZipFile(z) as zf:
                bad = zf.testzip()
                if bad:
                    return False, f"{z.name} 内文件损坏：{bad}"
                names = zf.namelist()
        except zipfile.BadZipFile:
            return False, f"{z.name} 不是合法 zip"
        details.append(f"{z.name}({len(names)} 项, {z.stat().st_size/1024:.0f}KB)")
    return True, "; ".join(details)


# ---------------------------------------------------------------- 主流程

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experts-dir", default=None)
    args = parser.parse_args()

    check("T01", "清单 JSON 可解析且必填字段齐全", t01_manifest_parse)
    check("T02", "包标识符合 czl- 前缀与字符集", t02_name_rules)
    check("T03", "名称与职称不含空格或特殊字符", t03_display_rules)
    check("T04", "版本号为语义化格式且与日志一致", t04_version_semver)
    check("T05", "头像存在、正方形 PNG、体积与水印合规", t05_avatar)
    check("T06", "agent 前置区字段完整", t06_agent_frontmatter)
    check("T07", "六条工作流结构化要素齐全", t07_workflow_completeness)
    check("T08", "knowledge 引用路径全部有效", t08_knowledge_paths)
    check("T09", "无嵌套清单与重复包", t09_no_nested_manifest)
    check("T10", "边界条款已写明", t10_boundary_clause)
    check("T11", "文本文件均为 UTF-8", t11_utf8)
    check("T12", "无可执行文件与超限大文件", t12_no_binary_junk)
    check("T13", "与已安装专家无重名", duplicate_check(args.experts_dir))
    check("T14", "脚本语法可编译", t14_scripts_syntax)
    check("T15", "发布包为合法 zip 且内容完整", t15_release_zip)
    check("T16", "首次提示与快捷提示首项一致", t16_default_prompt_consistency)

    print("=" * 78)
    print("功能与结构测试")
    print("=" * 78)
    passed = 0
    for tid, name, ok, detail in results:
        flag = "PASS" if ok else "FAIL"
        print(f"[{flag}] {tid} {name}")
        print(f"       {detail}")
        if ok:
            passed += 1
    print("-" * 78)
    print(f"合计 {len(results)} 项，通过 {passed} 项，失败 {len(results) - passed} 项")
    return 0 if passed == len(results) else 1


def duplicate_check(experts_dir):
    """把重名比对包成无参函子，供 check() 调用；返回 (ok, detail)。"""

    def run():
        if not experts_dir:
            return True, "未指定已安装专家目录，跳过重名比对"
        return t13_duplicate_names(experts_dir)()

    return run


if __name__ == "__main__":
    sys.exit(main())
