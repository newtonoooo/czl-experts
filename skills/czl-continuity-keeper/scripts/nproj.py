#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nproj.py — 网文项目档案管理（纯标准库，离线可用）

子命令：
    init      建项目，生成 .nproj/state.json 与目录骨架
    status    一句话报告：写到第几章、多少字、欠什么、下一步
    commit    提交一章正文入档（记录字数、指纹、体检结论）
    thread    增删改伏笔
    words     统计全书字数（按汉字+字母+数字逐字符计）
    export    导出全本到 export/

字数口径：正文汉字、其他字母、数字逐字符计数；标点、空白、Markdown 标题行不计。

作者：虫志龙 <47190078@qq.com>
许可：随本专家包发布的原创代码，MIT。
"""

import argparse
import hashlib
import json
import os
import re
import sys
import datetime

HANZI = re.compile(r"[\u4e00-\u9fff]")
ALNUM = re.compile(r"[A-Za-z0-9]")
HEADING = re.compile(r"^\s*#")


def now():
    return datetime.datetime.now().replace(microsecond=0).isoformat()


def count_chars(text):
    """正文字数：汉字 + 字母 + 数字；标题行与标点空白不计。"""
    n = 0
    for line in text.splitlines():
        if HEADING.match(line):
            continue
        n += len(HANZI.findall(line)) + len(ALNUM.findall(line))
    return n


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def paths(root):
    return {
        "state": os.path.join(root, ".nproj", "state.json"),
        "chapters": os.path.join(root, "chapters"),
        "qc": os.path.join(root, "qc"),
        "export": os.path.join(root, "export"),
        "nproj": os.path.join(root, ".nproj"),
    }


def load_state(root):
    p = paths(root)["state"]
    if not os.path.exists(p):
        raise SystemExit("还没有项目档案：%s\n先跑 nproj.py init" % p)
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(root, st):
    p = paths(root)["state"]
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


def ensure_dirs(root):
    for k in ("chapters", "qc", "export", "nproj"):
        os.makedirs(paths(root)[k], exist_ok=True)


# ---------------- init ----------------

def cmd_init(a):
    root = os.path.abspath(a.dir)
    ensure_dirs(root)
    st = {
        "schema": 1,
        "project": os.path.basename(root),
        "title": a.title or os.path.basename(root),
        "created_at": now(),
        "target_chars": a.target,
        "chapter_words": a.chapter_words,
        "chapter_range": [int(a.chapter_words * 0.8), int(a.chapter_words * 1.25)],
        "chapters": [],
        "threads": [],
        "next_action": "先跑 czl-market-scout 定卖点，再跑 czl-story-architect 立设定",
        "stale": False,
        "stale_reason": "",
    }
    save_state(root, st)
    print("已建项目：%s" % root)
    print("目标 %d 字，单章 %d 字（区间 %d—%d）"
          % (st["target_chars"], st["chapter_words"], *st["chapter_range"]))
    return 0


# ---------------- commit ----------------

def cmd_commit(a):
    root = os.path.abspath(a.dir)
    st = load_state(root)
    src = os.path.abspath(a.file)
    if not os.path.exists(src):
        print("找不到正文文件：%s" % src)
        return 2
    with open(src, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    n = count_chars(text)
    if n < 200:
        print("正文字数只有 %d，看起来不像一章。确认后加 --force 再提交。" % n)
        if not a.force:
            return 2

    ch = int(a.chapter)
    dst = os.path.join(paths(root)["chapters"], "ch-%03d.md" % ch)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    # 原子替换，避免半截文件
    tmp = dst + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, dst)

    qc_path = os.path.join(paths(root)["qc"], "ch-%03d.report.json" % ch)
    qc = "missing"
    qc_score = None
    if os.path.exists(qc_path):
        try:
            with open(qc_path, "r", encoding="utf-8") as f:
                q = json.load(f)
            qc = "pass" if q.get("verdict") == "PASS" else "fail"
            qc_score = q.get("score")
        except Exception:
            qc = "unreadable"

    rec = {
        "n": ch,
        "title": a.title or "",
        "file": os.path.relpath(dst, root).replace("\\", "/"),
        "chars": n,
        "sha256": sha(text),
        "prev_sha": "",
        "committed_at": now(),
        "qc": qc,
        "qc_score": qc_score,
        "summary": a.summary or "",
    }
    # 依赖链：记录前一个已入档章节的指纹，前章一改，本章即"链断"
    earlier = [c for c in st["chapters"] if c["n"] < ch]
    if earlier:
        rec["prev_sha"] = sorted(earlier, key=lambda c: c["n"])[-1]["sha256"]

    st["chapters"] = [c for c in st["chapters"] if c["n"] != ch]
    st["chapters"].append(rec)
    st["chapters"].sort(key=lambda c: c["n"])

    lo, hi = st["chapter_range"]
    if n < lo:
        print("提示：本章 %d 字，低于区间下限 %d。" % (n, lo))
    elif n > hi:
        print("提示：本章 %d 字，高于区间上限 %d。" % (n, hi))

    # 待复核状态按全书重算，不能只按本次提交：补上体检后应当自动解除
    bad = [c["n"] for c in st["chapters"] if c.get("qc") != "pass"]
    if bad:
        st["stale"] = True
        st["stale_reason"] = "第 %s 章未通过人味体检（%s）" % (
            "、".join(str(b) for b in sorted(bad)[:5]),
            "missing" if any(c.get("qc") in (None, "missing") for c in st["chapters"] if c["n"] in bad) else "FAIL")
    else:
        st["stale"] = False
        st["stale_reason"] = ""

    st["next_action"] = "写第 %d 章：先出写作包，再写正文" % (ch + 1) if not bad \
        else "先过 czl-voice-tune，把第 %s 章的体检清零" % "、".join(str(b) for b in sorted(bad)[:3])
    save_state(root, st)

    print("已入档：第 %d 章，%d 字，体检 %s%s"
          % (ch, n, qc, "" if qc_score is None else "（%d 分）" % qc_score))
    if qc != "pass":
        print("档案已标记待复核：先过 czl-voice-tune 再写下一章。")
    return 0 if qc == "pass" else 1


# ---------------- status ----------------

def cmd_status(a):
    root = os.path.abspath(a.dir)
    st = load_state(root)
    chs = st["chapters"]
    total = sum(c["chars"] for c in chs)
    nums = sorted(c["n"] for c in chs)
    last = nums[-1] if nums else 0

    print("《%s》" % st["title"])
    print("写到：第 %d 章 ｜ 已入档 %d 章 ｜ %d 字 / 目标 %d 字（%.0f%%）"
          % (last, len(chs), total, st["target_chars"],
             100.0 * total / st["target_chars"] if st["target_chars"] else 0))

    # 缺章
    gaps = [i for i in range(1, last + 1) if i not in nums]
    if gaps:
        print("缺章：%s" % "、".join(str(g) for g in gaps[:12]))
    else:
        print("缺章：无")

    # 体检未过
    bad = [c["n"] for c in chs if c["qc"] != "pass"]
    print("体检未过：%s" % ("无" if not bad else "、".join(str(b) for b in bad)))

    # 伏笔
    open_th = [t for t in st["threads"] if t.get("status") == "open"]
    overdue = [t for t in open_th
               if t.get("due_chapter") and t["due_chapter"] <= last]
    print("未回收伏笔：%d 条%s"
          % (len(open_th), "" if not overdue else "，其中 %d 条已到期" % len(overdue)))
    for t in overdue[:6]:
        print("   到期未收：%s（应于第 %s 章回收）" % (t.get("content", t.get("id")),
                                                t.get("due_chapter")))

    if st.get("stale"):
        print("状态：待复核 —— %s" % st.get("stale_reason", ""))
    print("下一步：%s" % st.get("next_action", "未设置"))
    return 0


# ---------------- thread ----------------

def cmd_thread(a):
    root = os.path.abspath(a.dir)
    st = load_state(root)
    th = st["threads"]

    if a.action == "add":
        if any(t["id"] == a.id for t in th):
            print("伏笔 id 已存在：%s" % a.id)
            return 2
        th.append({
            "id": a.id,
            "content": a.content or "",
            "planted_chapter": a.planted,
            "due_chapter": a.due,
            "status": "open",
            "note": a.note or "",
        })
        print("已埋：%s（第 %s 章埋，第 %s 章到期）" % (a.id, a.planted, a.due))
    elif a.action == "resolve":
        hit = [t for t in th if t["id"] == a.id]
        if not hit:
            print("没有这条伏笔：%s" % a.id)
            return 2
        hit[0]["status"] = "resolved"
        hit[0]["resolved_chapter"] = a.chapter
        print("已收：%s（第 %s 章）" % (a.id, a.chapter))
    elif a.action == "drop":
        hit = [t for t in th if t["id"] == a.id]
        if not hit:
            print("没有这条伏笔：%s" % a.id)
            return 2
        hit[0]["status"] = "dropped"
        hit[0]["note"] = a.note or "作者主动放弃"
        print("已弃：%s（需在正文或作者备忘中交代，不许默默消失）" % a.id)
    elif a.action == "list":
        if not th:
            print("还没有伏笔。")
        for t in th:
            print("%-12s %-8s 埋 %s 到期 %s  %s"
                  % (t["id"], t["status"], t.get("planted_chapter"),
                     t.get("due_chapter"), t.get("content", "")[:30]))
    else:
        print("未知动作：%s（add/resolve/drop/list）" % a.action)
        return 2

    save_state(root, st)
    return 0


# ---------------- verify ----------------

def cmd_verify(a):
    """校验档案可信度：文件是否被改、依赖链是否断。"""
    root = os.path.abspath(a.dir)
    st = load_state(root)
    chs = sorted(st["chapters"], key=lambda c: c["n"])
    bad, warns = [], []

    prev = None
    for c in chs:
        p = os.path.join(root, c["file"])
        if not os.path.exists(p):
            bad.append("第 %d 章文件缺失：%s" % (c["n"], c["file"]))
            prev = c
            continue
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            cur = sha(f.read())
        if cur != c.get("sha256"):
            bad.append("第 %d 章正文与入档指纹不符（可能被手改而未重新提交）" % c["n"])
        if prev is not None:
            want = prev.get("sha256")
            if c.get("prev_sha") and c["prev_sha"] != want:
                bad.append("第 %d 章的依赖链断了：记录的前章指纹与第 %d 章当前指纹不一致"
                           % (c["n"], prev["n"]))
            elif not c.get("prev_sha"):
                warns.append("第 %d 章没有记录前章指纹（老版本档案，建议重跑 commit）" % c["n"])
        prev = c

    print("=" * 60)
    print("档案校验 ｜ %d 章 ｜ 阻断 %d ｜ 提示 %d" % (len(chs), len(bad), len(warns)))
    print("=" * 60)
    for x in bad:
        print("✗ " + x)
    for x in warns:
        print("! " + x)
    if not bad:
        print("正文与入档记录一致，依赖链完整。")
        print("说明：这是完整性校验，不是防篡改签名——能发现手改，挡不住刻意伪造。")
    return 0 if not bad else 1


# ---------------- words / export ----------------

def iter_chapter_files(root, st):
    for c in sorted(st["chapters"], key=lambda x: x["n"]):
        p = os.path.join(root, c["file"])
        if os.path.exists(p):
            yield c, p


def cmd_words(a):
    root = os.path.abspath(a.dir)
    st = load_state(root)
    total = 0
    for c, p in iter_chapter_files(root, st):
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            total += count_chars(f.read())
    print("全书正文 %d 字（汉字+字母+数字，不含标点标题）" % total)
    print("目标 %d 字，完成 %.1f%%" % (st["target_chars"],
                                   100.0 * total / st["target_chars"] if st["target_chars"] else 0))
    return 0


def cmd_export(a):
    root = os.path.abspath(a.dir)
    st = load_state(root)
    os.makedirs(paths(root)["export"], exist_ok=True)
    out = a.out or os.path.join(paths(root)["export"],
                                "%s-v%d.md" % (re.sub(r"[\\/:*?\"<>|]", "_", st["title"]),
                                               len(os.listdir(paths(root)["export"])) + 1))
    parts = ["# %s\n" % st["title"]]
    total = 0
    for c, p in iter_chapter_files(root, st):
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            body = f.read()
        total += count_chars(body)
        parts.append("\n\n## 第 %d 章 %s\n\n%s" % (c["n"], c.get("title", ""), body.strip()))
    with open(out, "w", encoding="utf-8") as f:
        f.write("".join(parts))
    print("已导出：%s" % out)
    print("共 %d 章，%d 字" % (len(st["chapters"]), total))
    return 0


# ---------------- main ----------------

def build_parser():
    ap = argparse.ArgumentParser(description="网文项目档案管理")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="建项目")
    p.add_argument("--dir", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--target", type=int, default=100000, help="全书目标字数")
    p.add_argument("--chapter-words", type=int, default=3000, help="单章目标字数")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("commit", help="提交一章入档")
    p.add_argument("--dir", required=True)
    p.add_argument("--chapter", required=True, type=int)
    p.add_argument("--file", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--summary", default="")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_commit)

    p = sub.add_parser("status", help="报告进度")
    p.add_argument("--dir", required=True)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("thread", help="伏笔登记")
    p.add_argument("--dir", required=True)
    p.add_argument("action", choices=["add", "resolve", "drop", "list"])
    p.add_argument("--id", default="")
    p.add_argument("--content", default="")
    p.add_argument("--planted", type=int, default=0)
    p.add_argument("--due", type=int, default=0)
    p.add_argument("--chapter", type=int, default=0)
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_thread)

    p = sub.add_parser("verify", help="校验正文与档案是否一致、依赖链是否完整")
    p.add_argument("--dir", required=True)
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("words", help="统计字数")
    p.add_argument("--dir", required=True)
    p.set_defaults(func=cmd_words)

    p = sub.add_parser("export", help="导出全本")
    p.add_argument("--dir", required=True)
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_export)
    return ap


def main():
    ap = build_parser()
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
