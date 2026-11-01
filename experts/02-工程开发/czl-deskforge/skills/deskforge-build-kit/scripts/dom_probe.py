#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dom_probe.py — 单文件工作台的 DOM 与调用关系体检

© 2026 虫志龙 · 版权所有 ｜ 授权范围见包内 LICENSE
纯标准库实现：不联网、不装依赖、不上传任何数据。

检查项：
  1 getElementById / querySelector('#x') 的目标 id 是否存在 —— error
  2 渲染函数之间是否形成调用环（A→B→A）—— error
  3 初始化入口是否唯一（DOMContentLoaded / window.onload）—— warning
  4 是否存在对未定义函数的调用 —— warning
  5 静态摘要：id 数、函数数、调用边数

用法：
  python dom_probe.py --file 台子.html
  python dom_probe.py --file 台子.html --json
  python dom_probe.py --file 台子.html --allow renderX,renderY   # 额外白名单

退出码：0 通过 ｜ 1 有 warning ｜ 2 有 error
"""

import argparse
import json
import re
import sys
from pathlib import Path

ID_RE = re.compile(r"""\bid\s*=\s*["']([^"']+)["']""")
GETID_RE = re.compile(r"""getElementById\s*\(\s*["']([^"']+)["']""")
QSEL_ID_RE = re.compile(r"""querySelector\s*\(\s*["']#([\w-]+)["']""")

FUNC_DECL_RE = re.compile(r"""\bfunction\s+([A-Za-z_$][\w$]*)\s*\(""")
FUNC_VAR_RE = re.compile(
    r"""(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?(?:function\b|\([^)]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)"""
)
CALL_RE = re.compile(r"""([A-Za-z_$][\w$]*)\s*\(""")

KEYWORDS = {
    "if", "for", "while", "switch", "catch", "function", "return", "typeof", "new",
    "delete", "void", "do", "else", "try", "finally", "in", "of", "await", "async",
    "case", "throw", "with", "yield", "instanceof",
}

BUILTINS = {
    "console", "Math", "JSON", "Date", "Object", "Array", "String", "Number", "Boolean",
    "parseInt", "parseFloat", "isNaN", "isFinite", "setTimeout", "setInterval",
    "clearTimeout", "clearInterval", "requestAnimationFrame", "alert", "confirm", "prompt",
    "Blob", "URL", "FileReader", "encodeURIComponent", "decodeURIComponent", "Set", "Map",
    "Promise", "RegExp", "Error", "CustomEvent", "Event", "structuredClone", "queueMicrotask",
    "document", "window", "localStorage", "sessionStorage", "navigator", "location",
    "fetch", "atob", "btoa", "Intl", "Symbol", "WeakMap", "WeakSet", "globalThis",
}

SCRIPT_RE = re.compile(r"<script\b[^>]*>(.*?)</script>", re.S | re.I)


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, code, msg, detail=None):
        self.items.append({"level": level, "code": code, "msg": msg, "detail": detail})

    def count(self, level):
        return sum(1 for i in self.items if i["level"] == level)

    @property
    def exit_code(self):
        if self.count("error"):
            return 2
        if self.count("warning"):
            return 1
        return 0


def script_text(text):
    return "\n".join(m.group(1) for m in SCRIPT_RE.finditer(text))


REGEX_PREV = set("([{,;:=!&|?+-*%~^<>")


def _skip_string(src, j):
    q = src[j]
    j += 1
    n = len(src)
    while j < n:
        if src[j] == "\\":
            j += 2
            continue
        if src[j] == q:
            return j + 1
        j += 1
    return n


def _skip_regex(src, j):
    """j 指向起始 '/'，返回正则结束（含 flags）后的位置。"""
    j += 1
    n, in_class = len(src), False
    while j < n:
        c = src[j]
        if c == "\\":
            j += 2
            continue
        if c == "[":
            in_class = True
        elif c == "]":
            in_class = False
        elif c == "/" and not in_class:
            j += 1
            while j < n and src[j].isalpha():
                j += 1
            return j
        elif c == "\n":
            return j
        j += 1
    return n


def find_body(src, start):
    """从 start 起找到第一个 '{'，做括号配对（跳过字符串、注释与正则字面量）。"""
    i = start
    n = len(src)
    while i < n and src[i] != "{":
        if src[i] in "\"'`":
            i = _skip_string(src, i)
            continue
        i += 1
    if i >= n:
        return ""
    depth, j = 0, i
    prev_sig = ""
    while j < n:
        c = src[j]
        if c in "\"'`":
            j = _skip_string(src, j)
            continue
        if c == "/" and j + 1 < n and src[j + 1] == "/":
            k = src.find("\n", j)
            j = n if k < 0 else k
            continue
        if c == "/" and j + 1 < n and src[j + 1] == "*":
            k = src.find("*/", j)
            j = n if k < 0 else k + 2
            continue
        if c == "/" and (prev_sig == "" or prev_sig in REGEX_PREV):
            j = _skip_regex(src, j)
            prev_sig = "/"
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[i: j + 1]
        if not c.isspace():
            prev_sig = c
        j += 1
    return src[i:]


def collect_functions(src):
    funcs = {}
    for m in FUNC_DECL_RE.finditer(src):
        funcs.setdefault(m.group(1), find_body(src, m.end()))
    for m in FUNC_VAR_RE.finditer(src):
        funcs.setdefault(m.group(1), find_body(src, m.end()))
    return funcs


def iter_calls(body):
    """逐个吐出 (标识符, 位置)，只保留形如 name( 的调用点，跳过字符串/注释/正则。"""
    out = []
    i, n = 0, len(body)
    prev_sig = ""
    while i < n:
        c = body[i]
        if c in "\"'`":
            i = _skip_string(body, i)
            prev_sig = c
            continue
        if c == "/" and i + 1 < n and body[i + 1] == "/":
            k = body.find("\n", i)
            i = n if k < 0 else k
            continue
        if c == "/" and i + 1 < n and body[i + 1] == "*":
            k = body.find("*/", i)
            i = n if k < 0 else k + 2
            continue
        if c == "/" and (prev_sig == "" or prev_sig in REGEX_PREV):
            i = _skip_regex(body, i)
            prev_sig = "/"
            continue
        if c.isalpha() or c in "_$":
            j = i
            while j < n and (body[j].isalnum() or body[j] in "_$"):
                j += 1
            name = body[i:j]
            k = j
            while k < n and body[k].isspace():
                k += 1
            if k < n and body[k] == "(":
                out.append((name, i))
            prev_sig = name[-1]
            i = j
            continue
        if not c.isspace():
            prev_sig = c
        i += 1
    return out


def calls_in(body, known):
    out = set()
    for name, pos in iter_calls(body):
        if name in KEYWORDS:
            continue
        p = pos - 1
        while p >= 0 and body[p].isspace():
            p -= 1
        if p >= 0 and body[p] == ".":
            continue
        if name in known:
            out.add(name)
    return out


def find_cycles(graph):
    WHITE, GREY, BLACK = 0, 1, 2
    color = {k: WHITE for k in graph}
    cycles, stack = [], []

    def dfs(u):
        color[u] = GREY
        stack.append(u)
        for v in sorted(graph.get(u, ())):
            if color.get(v, WHITE) == GREY:
                idx = stack.index(v) if v in stack else -1
                if idx >= 0:
                    cycles.append(stack[idx:] + [v])
            elif color.get(v, WHITE) == WHITE:
                dfs(v)
        stack.pop()
        color[u] = BLACK

    for node in graph:
        if color[node] == WHITE:
            dfs(node)
    return cycles


def probe(path, extra_allow=None):
    text = path.read_text(encoding="utf-8", errors="replace")
    src = script_text(text)
    rep = Report()

    ids = set(ID_RE.findall(text))
    refs = set(GETID_RE.findall(text)) | set(QSEL_ID_RE.findall(text))
    missing = sorted(refs - ids)
    for mid in missing:
        rep.add("error", "DOM-MISSING", f"引用了不存在的 id：#{mid}（getElementById/querySelector 目标未定义）")

    funcs = collect_functions(src)
    graph = {name: calls_in(body, funcs) for name, body in funcs.items()}
    cycles = find_cycles(graph)
    for cyc in cycles:
        if len(cyc) == 2 and cyc[0] == cyc[1]:
            rep.add("warning", "CALL-SELF",
                    f"自递归：{cyc[0]}() 调用了自己（若为遍历/重试则属正常，确认一下）")
        else:
            chain = " → ".join(cyc)
            rep.add("error", "CALL-CYCLE",
                    f"函数互调成环：{chain}（渲染函数之间必须由 refreshAll() 统一调度）")

    entries = len(re.findall(r"DOMContentLoaded", src)) + len(re.findall(r"window\.onload", src))
    if entries == 0:
        rep.add("warning", "INIT-NONE", "未发现 DOMContentLoaded / window.onload，确认初始化入口在哪")
    elif entries > 1:
        rep.add("warning", "INIT-MULTI", f"发现 {entries} 处初始化入口，约定只保留 1 个")

    allow = set(BUILTINS) | set(funcs) | set(extra_allow or [])
    undefined = []
    for name, pos in iter_calls(src):
        if name in KEYWORDS or name in allow:
            continue
        p = pos - 1
        while p >= 0 and src[p].isspace():
            p -= 1
        if p >= 0 and src[p] == ".":
            continue
        undefined.append(name)
    for name in sorted(set(undefined))[:10]:
        rep.add("warning", "CALL-UNKNOWN", f"疑似调用了未定义的函数：{name}()（若来自浏览器 API 可加入白名单）")

    edges = sum(len(v) for v in graph.values())
    rep.add("info", "SUMMARY", f"id {len(ids)} 个 ｜ 引用 {len(refs)} 个 ｜ 函数 {len(funcs)} 个 ｜ 调用边 {edges} 条")
    return rep


ICON = {"error": "[x]", "warning": "[!]", "info": "[·]"}


def render(rep, path):
    lines = [f"# 结构体检 · {path.name}", ""]
    for it in rep.items:
        lines.append(f"{ICON[it['level']]} {it['level'].upper():7s} {it['code']:13s}  {it['msg']}")
    lines.append("")
    e, w = rep.count("error"), rep.count("warning")
    verdict = "不通过" if e else ("有警告，需逐条说明" if w else "通过")
    lines.append(f"合计：error {e} ｜ warning {w} ｜ info {rep.count('info')}  →  {verdict}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="单文件工作台 DOM 与调用关系体检（零依赖）")
    ap.add_argument("--file", required=True, help="待检 .html 文件")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--allow", default="", help="额外白名单函数名，逗号分隔")
    args = ap.parse_args()

    p = Path(args.file)
    if not p.exists():
        print(f"找不到文件：{args.file}", file=sys.stderr)
        return 3

    extra = [x.strip() for x in args.allow.split(",") if x.strip()]
    rep = probe(p, extra)

    if args.json:
        print(json.dumps({
            "file": str(p), "error": rep.count("error"), "warning": rep.count("warning"),
            "info": rep.count("info"), "items": rep.items, "exit": rep.exit_code,
        }, ensure_ascii=False, indent=2))
    else:
        print(render(rep, p))
    return rep.exit_code


if __name__ == "__main__":
    sys.exit(main())
