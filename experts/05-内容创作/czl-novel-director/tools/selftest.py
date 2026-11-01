#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selftest.py — 打包前自检（14 项，可重复执行）

用法：
    python tools/selftest.py [--root .] [--json out.json]

设计：所有检查都基于真实文件与真实脚本执行，不做静态假设。
任一项失败退出码为 1。

作者：虫志龙 <47190078@qq.com>
许可：MIT
"""

import argparse
import json
import os
import re
import struct
import shutil
import subprocess
import sys
import tempfile
import zipfile

RESULTS = []


def record(tid, name, ok, detail, blocking=True):
    RESULTS.append({"id": tid, "name": name, "ok": bool(ok),
                    "detail": detail, "blocking": blocking})
    print(("PASS " if ok else "FAIL ") + "%s %s" % (tid, name))
    if detail:
        print("      " + str(detail).replace("\n", "\n      "))


def run(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def py(root, script):
    return [sys.executable, os.path.join(root, script)]


# ---------------- 各项检查 ----------------

def t01_manifest(root):
    p = os.path.join(root, ".codebuddy-plugin", "plugin.json")
    if not os.path.exists(p):
        return record("T-01", "清单文件合法性与必填字段", False, "缺 .codebuddy-plugin/plugin.json")
    with open(p, "r", encoding="utf-8") as f:
        txt = f.read()
    try:
        d = json.loads(txt)
    except Exception as e:
        return record("T-01", "清单文件合法性与必填字段", False, "JSON 解析失败：%s" % e)

    need = ["name", "version", "description", "author", "agents", "skills",
            "expertType", "agentName", "displayName", "profession",
            "displayDescription", "avatar", "categoryId", "plugin",
            "tags", "defaultInitPrompt", "quickPrompts"]
    miss = [k for k in need if k not in d or d[k] in ("", None, [], {})]
    prob = []
    if miss:
        prob.append("缺字段：" + "、".join(miss))
    if d.get("name") != "czl-novel-director":
        prob.append("name 应为 czl-novel-director")
    if d.get("plugin") != d.get("name"):
        prob.append("plugin 与 name 不一致")
    if d.get("author", {}).get("name") != "虫志龙":
        prob.append("author.name 应为 虫志龙")
    if d.get("author", {}).get("email") != "47190078@qq.com":
        prob.append("author.email 不符")
    if not str(d.get("name", "")).startswith("czl-"):
        prob.append("包名未以 czl- 开头")
    # 名称字符集
    for k in ("zh", "en"):
        v = d.get("displayName", {}).get(k, "")
        if not re.fullmatch(r"[\u4e00-\u9fffA-Za-z0-9\-—]+", v):
            prob.append("displayName.%s 含不允许字符：%r" % (k, v))
    record("T-01", "清单文件合法性与必填字段", not prob,
           "；".join(prob) if prob else "17 项必填齐全，名称字符集合法")


def t02_skills(root):
    with open(os.path.join(root, ".codebuddy-plugin", "plugin.json"), encoding="utf-8") as f:
        d = json.load(f)
    prob = []
    for s in d["skills"]:
        p = os.path.join(root, s, "SKILL.md")
        if not os.path.exists(p):
            prob.append("缺 %s/SKILL.md" % s)
            continue
        with open(p, encoding="utf-8") as f:
            head = f.read(1200)
        if not head.startswith("---"):
            prob.append("%s 缺 frontmatter" % s)
        if "name:" not in head:
            prob.append("%s frontmatter 缺 name" % s)
        if "description:" not in head:
            prob.append("%s frontmatter 缺 description" % s)
    record("T-02", "%d 个 skill 齐全且含 frontmatter" % len(d["skills"]), not prob,
           "；".join(prob) if prob else "全部通过")


def t03_agent(root):
    with open(os.path.join(root, ".codebuddy-plugin", "plugin.json"), encoding="utf-8") as f:
        d = json.load(f)
    prob = []
    for a in d["agents"]:
        p = os.path.join(root, a)
        if not os.path.exists(p):
            prob.append("缺 %s" % a)
            continue
        with open(p, encoding="utf-8") as f:
            txt = f.read()
        if not txt.startswith("---"):
            prob.append("agent 缺 frontmatter")
        if d["agentName"] not in txt[:600]:
            prob.append("agent frontmatter name 与 agentName 不一致")
        # frontmatter 里声明的 skill 必须都在清单里
        fm = txt.split("---")[1] if txt.count("---") >= 2 else ""
        declared = re.findall(r"^\s*-\s*(czl-[\w-]+)\s*$", fm, re.M)
        listed = [os.path.basename(s) for s in d["skills"]]
        extra = [x for x in declared if x not in listed]
        if extra:
            prob.append("agent 声明了清单外的 skill：%s" % "、".join(extra))
    record("T-03", "agent 提示词与清单一致", not prob,
           "；".join(prob) if prob else "frontmatter 与 skills 列表一致")


def t04_avatar(root):
    with open(os.path.join(root, ".codebuddy-plugin", "plugin.json"), encoding="utf-8") as f:
        d = json.load(f)
    rel = d.get("avatar", "")
    p = os.path.join(root, rel)
    if not os.path.exists(p):
        return record("T-04", "头像格式与尺寸", False, "avatar 指向的文件不存在：%s" % rel)
    with open(p, "rb") as f:
        h = f.read(33)
    prob = []
    if h[:8] != b"\x89PNG\r\n\x1a\n":
        prob.append("不是真 PNG，文件头 %s" % h[:8].hex(" "))
    else:
        w, hh = struct.unpack(">II", h[16:24])
        bd, ct = h[24], h[25]
        if w != hh:
            prob.append("非正方形 %dx%d" % (w, hh))
        if w < 256:
            prob.append("边长过小 %d" % w)
        if ct not in (2, 6):
            prob.append("色彩类型异常 %d" % ct)
    size = os.path.getsize(p)
    if size > 500 * 1024:
        prob.append("体积 %.0f KB 超过平台上限 500 KB" % (size / 1024.0))
    elif size > 300 * 1024:
        prob.append("体积 %.0f KB 偏大，base64 后约 %.0f KB，建议压到 300 KB 内"
                    % (size / 1024.0, size * 4 / 3 / 1024))
    record("T-04", "头像格式与尺寸", not prob,
           "；".join(prob) if prob else "%dx%d 色彩类型 %d，%.1f KB（平台上限 500 KB）"
           % (w, hh, ct, size / 1024.0))


def t05_paths(root):
    with open(os.path.join(root, ".codebuddy-plugin", "plugin.json"), encoding="utf-8") as f:
        d = json.load(f)
    prob = []
    for rel in d["agents"] + d["skills"] + [d["avatar"]]:
        # 平台允许 "./xxx" 前缀，规范化为相对路径后再判断
        norm = rel[2:] if rel.startswith("./") else rel
        if norm.startswith(("/", "\\")) or ".." in norm or ":" in norm:
            prob.append("非规范相对路径：%s" % rel)
        if not os.path.exists(os.path.join(root, norm)):
            prob.append("路径不存在：%s" % rel)
    record("T-05", "清单内路径全部存在且为规范相对路径", not prob,
           "；".join(prob) if prob else "共 %d 条路径" % (len(d["agents"]) + len(d["skills"]) + 1))


def t06_encoding(root):
    bad = []
    n = 0
    for dirpath, _, files in os.walk(root):
        if "dist" in dirpath.split(os.sep):
            continue
        for fn in files:
            if not fn.endswith((".md", ".json", ".py", ".txt")):
                continue
            p = os.path.join(dirpath, fn)
            n += 1
            with open(p, "rb") as f:
                raw = f.read()
            if raw.startswith(b"\xef\xbb\xbf"):
                bad.append("含 BOM：%s" % os.path.relpath(p, root))
                continue
            try:
                raw.decode("utf-8")
            except UnicodeDecodeError:
                bad.append("非 UTF-8：%s" % os.path.relpath(p, root))
    record("T-06", "全部文本为 UTF-8 且无 BOM（%d 个文件）" % n, not bad,
           "；".join(bad[:6]) if bad else "通过")


def t07_zip(root):
    dist = os.path.join(root, "dist")
    zips = [f for f in os.listdir(dist) if f.endswith(".zip")] if os.path.isdir(dist) else []
    if not zips:
        return record("T-07", "发布包内头像条目与清单一致", False,
                      "dist/ 下还没有 zip，先打包再跑此项", blocking=False)
    z = os.path.join(dist, sorted(zips)[-1])
    with zipfile.ZipFile(z) as zf:
        names = zf.namelist()
        with open(os.path.join(root, ".codebuddy-plugin", "plugin.json"), encoding="utf-8") as f:
            d = json.load(f)
        rel = d["avatar"]
        # 顶层目录名（zip 内插件根）
        tops = {n.split("/")[0] for n in names if "/" in n}
        prob = []
        if len(tops) != 1:
            prob.append("zip 顶层应只有一个插件根目录，实际：%s" % sorted(tops))
        top = sorted(tops)[0] if tops else ""
        cand = [n for n in names if n.endswith(rel)]
        if not cand:
            prob.append("zip 内找不到 %s" % rel)
        else:
            exact = "%s/%s" % (top, rel)
            if exact not in names:
                prob.append("条目名与清单不一致，期望 %s，实际 %s" % (exact, cand[0]))
        for junk in (".DS_Store", "__MACOSX", "Thumbs.db"):
            if any(junk in n for n in names):
                prob.append("含垃圾条目 %s" % junk)
        # 清单本身也要在 zip 内
        if "%s/.codebuddy-plugin/plugin.json" % top not in names:
            prob.append("zip 内缺 .codebuddy-plugin/plugin.json")
    record("T-07", "发布包内头像条目与清单一致", not prob,
           "；".join(prob) if prob else "zip 根目录 %s，头像条目精确匹配，%d 个文件"
           % (top, len(names)))


def t08_voice(root, tmp):
    good = os.path.join(root, "skills/czl-voice-tune/samples/good_sample.md")
    bad = os.path.join(root, "skills/czl-voice-tune/samples/bad_sample.md")
    script = py(root, "skills/czl-voice-tune/scripts/voice_scan.py")
    c1, o1 = run(script + [good, "--json", os.path.join(tmp, "g.json"), "--quiet"], root)
    c2, o2 = run(script + [bad, "--json", os.path.join(tmp, "b.json"), "--quiet"], root)
    gj = json.load(open(os.path.join(tmp, "g.json"), encoding="utf-8"))
    bj = json.load(open(os.path.join(tmp, "b.json"), encoding="utf-8"))
    prob = []
    if gj["verdict"] != "PASS" or c1 != 0:
        prob.append("正样本未判 PASS（%s）" % o1.strip())
    if bj["verdict"] != "FAIL" or c2 == 0:
        prob.append("负样本未判 FAIL（%s）" % o2.strip())
    if not (bj["score"] < gj["score"]):
        prob.append("负样本分数不低于正样本")
    # 确定性：同稿两次结果必须一致
    run(script + [good, "--json", os.path.join(tmp, "g2.json"), "--quiet"], root)
    g2 = json.load(open(os.path.join(tmp, "g2.json"), encoding="utf-8"))
    if g2["score"] != gj["score"] or g2["verdict"] != gj["verdict"]:
        prob.append("同一文本两次扫描结果不一致")
    record("T-08", "体检脚本区分度与确定性", not prob,
           "；".join(prob) if prob else "正样本 %d 分/%s，负样本 %d 分/%s，复跑一致"
           % (gj["score"], gj["verdict"], bj["score"], bj["verdict"]))


def t09_nproj(root, tmp):
    d = os.path.join(tmp, "book")
    os.makedirs(d, exist_ok=True)
    s = py(root, "skills/czl-continuity-keeper/scripts/nproj.py")
    prob = []
    c, o = run(s + ["init", "--dir", d, "--title", "自检书", "--target", "10000",
                    "--chapter-words", "3000"], root)
    if c != 0 or not os.path.exists(os.path.join(d, ".nproj", "state.json")):
        prob.append("init 失败：%s" % o.strip())

    good = os.path.join(root, "skills/czl-voice-tune/samples/good_sample.md")
    c, o = run(py(root, "skills/czl-voice-tune/scripts/voice_scan.py") +
               [good, "--json", os.path.join(d, "qc", "ch-001.report.json"), "--quiet"], root)
    c, o = run(s + ["commit", "--dir", d, "--chapter", "1", "--file", good,
                    "--title", "第一章", "--force"], root)
    if c != 0 or "体检 pass" not in o:
        prob.append("commit 未识别体检通过：%s" % o.strip())

    c, o = run(s + ["thread", "--dir", d, "add", "--id", "t1",
                    "--content", "自检伏笔", "--planted", "1", "--due", "9"], root)
    if c != 0:
        prob.append("thread add 失败")

    c, o = run(s + ["status", "--dir", d], root)
    if "写到：第 1 章" not in o:
        prob.append("status 未报出进度")
    if "待复核" in o:
        prob.append("体检通过后仍显示待复核")

    c, o = run(s + ["words", "--dir", d], root)
    if "全书正文" not in o:
        prob.append("words 失败")

    c, o = run(s + ["export", "--dir", d], root)
    if c != 0 or not os.path.isdir(os.path.join(d, "export")):
        prob.append("export 失败")
    record("T-09", "项目脚本全链路（init/commit/thread/status/words/export）", not prob,
           "；".join(prob) if prob else "六个子命令全部按预期返回")


def t10_lint(root, tmp):
    d = os.path.join(tmp, "book")
    s = py(root, "skills/czl-continuity-keeper/scripts/nproj.py")
    lint = py(root, "skills/czl-continuity-keeper/scripts/lint_project.py")
    # 造一章缺体检的，制造缺章与待复核
    bad = os.path.join(root, "skills/czl-voice-tune/samples/bad_sample.md")
    run(s + ["commit", "--dir", d, "--chapter", "3", "--file", bad, "--force"], root)
    c, o = run(lint + ["--dir", d, "--json", os.path.join(d, "qc", "lint.json")], root)
    prob = []
    if c == 0:
        prob.append("有阻断项时退出码应为 1")
    for code in ("L1", "L3", "L6"):
        if code not in o:
            prob.append("未检出 %s" % code)
    r = json.load(open(os.path.join(d, "qc", "lint.json"), encoding="utf-8"))
    if r["verdict"] != "FAIL":
        prob.append("判定应为 FAIL")
    record("T-10", "结构核查检出缺章/体检缺失/待复核", not prob,
           "；".join(prob) if prob else "L1 L3 L6 全部命中，退出码 1")


def t11_funnel(root, tmp):
    csvp = os.path.join(root, "skills/czl-data-doctor/samples/funnel_demo.csv")
    out = os.path.join(tmp, "f.json")
    c, o = run(py(root, "skills/czl-data-doctor/scripts/funnel.py") +
               ["--csv", csvp, "--json-out", out], root)
    prob = []
    if c != 0:
        prob.append("脚本退出码非 0")
    r = json.load(open(out, encoding="utf-8"))
    # 手算核对：第 1→2 章 9021/12480
    expect = 9021 / 12480
    got = r["rows"][0]["ret_to_next"]
    if abs(expect - got) > 1e-4:
        prob.append("追读率算错：期望 %.4f，实际 %.4f" % (expect, got))
    # 掉点应命中第 7 章（70.5%）与第 1 章（72.3%）
    top = [d["chapter"] for d in r["drops"][:2]]
    if top != [7, 1]:
        prob.append("掉点排序异常：%s" % top)
    record("T-11", "漏斗计算与掉点定位", not prob,
           "；".join(prob) if prob else "第 1→2 章追读率 %.4f 与手算一致，掉点命中第 7、1 章" % got)


STDLIB_OK = set("""
argparse csv datetime hashlib json os re statistics struct subprocess sys tempfile
zipfile textwrap math random collections itertools string unicodedata pathlib shutil zlib
importlib glob
""".split())


def t12_no_deps(root):
    prob = []
    files = []
    for dirpath, _, fs in os.walk(os.path.join(root, "skills")):
        for fn in fs:
            if fn.endswith(".py"):
                files.append(os.path.join(dirpath, fn))
    for dirpath, _, fs in os.walk(os.path.join(root, "tools")):
        for fn in fs:
            if fn.endswith(".py"):
                files.append(os.path.join(dirpath, fn))
    for p in files:
        with open(p, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"\s*(?:import|from)\s+([A-Za-z_][\w.]*)", line)
                if not m:
                    continue
                mod = m.group(1).split(".")[0]
                if mod not in STDLIB_OK:
                    prob.append("%s 引入非标准库 %s" % (os.path.relpath(p, root), mod))
    record("T-12", "脚本零第三方依赖（%d 个文件）" % len(files), not prob,
           "；".join(prob) if prob else "全部 import 均为标准库")


def t13_texts(root):
    with open(os.path.join(root, ".codebuddy-plugin", "plugin.json"), encoding="utf-8") as f:
        d = json.load(f)
    prob = []
    # 这两份文件本身就在"列举"这些关键字，属合法的引用，不参与该项扫描
    QUOTING_DOCS = {"docs/测试报告.md", "docs/文件清单.md"}
    for dirpath, _, fs in os.walk(root):
        if "dist" in dirpath.split(os.sep) or "src-assets" in dirpath.split(os.sep):
            continue
        for fn in fs:
            if not fn.endswith((".md", ".json")):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root).replace("\\", "/")
            if rel in QUOTING_DOCS:
                continue
            with open(p, encoding="utf-8") as f:
                t = f.read()
            for bad in ("TODO", "FIXME", "publisher@example.com", "lorem ipsum",
                        "此处填写", "XXXX"):
                if bad in t:
                    prob.append("%s 残留 %s" % (rel, bad))
    record("T-13", "无占位符/示例邮箱残留", not prob,
           "；".join(prob[:6]) if prob else "通过（已排除两份引用关键字的报告文件）")


def t14_selfcontained(root):
    """包内文件不得引用包外绝对路径（除文档中的说明性路径）。"""
    prob = []
    for dirpath, _, fs in os.walk(root):
        if "dist" in dirpath.split(os.sep):
            continue
        for fn in fs:
            if not fn.endswith((".py", ".json")):
                continue
            p = os.path.join(dirpath, fn)
            with open(p, encoding="utf-8") as f:
                t = f.read()
            if re.search(r"[A-Za-z]:\\\\|[A-Za-z]:/", t):
                prob.append("%s 含本机绝对路径" % os.path.relpath(p, root))
    record("T-14", "脚本与配置无本机绝对路径", not prob,
           "；".join(prob[:6]) if prob else "通过")


def t15_master(root):
    """头像母图留档：证明 512 是从更大尺寸处理来的，属创作过程材料。"""
    d = os.path.join(root, "src-assets")
    if not os.path.isdir(d):
        return record("T-15", "头像母图留档（不随包发布）", False,
                      "缺 src-assets/ 过程稿目录", blocking=False)
    big = []
    for fn in os.listdir(d):
        if not fn.lower().endswith(".png"):
            continue
        p = os.path.join(d, fn)
        with open(p, "rb") as f:
            h = f.read(33)
        if h[:8] != b"\x89PNG\r\n\x1a\n":
            continue
        w, hh = struct.unpack(">II", h[16:24])
        if w >= 1024 and hh >= 1024:
            big.append("%s %dx%d" % (fn, w, hh))
    record("T-15", "头像母图留档（不随包发布）", bool(big),
           "；".join(big) if big else "src-assets 下没有 ≥1024 的母图", blocking=False)



def t16_pitch(root, tmp):
    s = py(root, "skills/czl-market-scout/scripts/pitch.py")
    prob = []
    c, o = run(s + ["proposition",
                    "别人都在写逆袭，这本写的是一个拆迁办主任给钉子户算账，所以读者在等账什么时候算不平"], root)
    if c != 0 or "通过" not in o:
        prob.append("好命题未判通过")
    c, o = run(s + ["title", "拆迁办主任的日常工作与内心世界"], root)
    if c == 0:
        prob.append("无留白的书名被判通过")
    c, o = run(s + ["title", "一个主任，两本账，三百户人家"], root)
    if c != 0:
        prob.append("有落差的书名未判通过：%s" % o.strip()[:80])
    record("T-16", "卖点命题与书名体检", not prob,
           "；".join(prob) if prob else "命题通过 / 无留白书名拒绝 / 有落差书名通过")


def t17_pacing(root, tmp):
    d = os.path.join(tmp, "pace")
    os.makedirs(d, exist_ok=True)
    for src, dst in (("pos/h1.md", "ch-001.md"), ("pos/h2.md", "ch-002.md"), ("neg/m1.md", "ch-003.md")):
        shutil.copy(os.path.join(root, "skills/czl-voice-tune/samples", src),
                    os.path.join(d, dst))
    c, o = run(py(root, "skills/czl-chapter-forge/scripts/pacing.py") + [d, "--min-hook", "3"], root)
    prob = []
    if "张力曲线" not in o:
        prob.append("没有输出张力曲线")
    if "H3" not in o:
        prob.append("未检出无对话章")
    if "全书没有检出爽点信号" not in o:
        prob.append("全书零爽点时未给提示（应对生活流豁免，而非直接红线）")
    if c == 0:
        prob.append("有红线时退出码应为 1")
    record("T-17", "章级节奏与钩子红线", not prob,
           "；".join(prob) if prob else "曲线输出、H3 命中、零爽点豁免提示、退出码 1")


def t18_rescue(root, tmp):
    out = os.path.join(tmp, "plan.md")
    c, o = run(py(root, "skills/czl-data-doctor/scripts/rescue.py") +
               ["--metrics", "吸量=300,追读=28,完读=7", "--plan", out], root)
    prob = []
    if "最拖后腿：完读" not in o:
        prob.append("未识别最弱项")
    if "30 天表" not in o or not os.path.exists(out):
        prob.append("未生成 30 天表")
    for phase in ("先定位", "改第一处", "观察", "复盘"):
        if phase not in o:
            prob.append("缺少阶段 %s" % phase)
    record("T-18", "指标分级与 30 天救书表", not prob,
           "；".join(prob) if prob else "识别完读最弱，30 天表含定位/改/观察/复盘")


def t19_verify(root, tmp):
    d = os.path.join(tmp, "vbook")
    os.makedirs(d, exist_ok=True)
    s = py(root, "skills/czl-continuity-keeper/scripts/nproj.py")
    run(s + ["init", "--dir", d, "--title", "校验", "--target", "20000"], root)
    good = os.path.join(root, "skills/czl-voice-tune/samples/pos/h1.md")
    run(s + ["commit", "--dir", d, "--chapter", "1", "--file", good, "--force"], root)
    c1, o1 = run(s + ["verify", "--dir", d], root)
    # 手改正文后再校验
    with open(os.path.join(d, "chapters", "ch-001.md"), "a", encoding="utf-8") as f:
        f.write("\n\n他多写了一句。\n")
    c2, o2 = run(s + ["verify", "--dir", d], root)
    prob = []
    if c1 != 0 or "一致" not in o1:
        prob.append("正常档案未通过校验")
    if c2 == 0 or "不符" not in o2:
        prob.append("手改正文后未检出")
    record("T-19", "档案完整性校验（指纹+依赖链）", not prob,
           "；".join(prob) if prob else "未改时通过，手改后检出指纹不符")



def t20_platform_schema(root):
    """平台上传校验器实际会拦的几条：tags 固定 3、quickPrompts 固定 3、
    defaultInitPrompt 必须与 quickPrompts[0] 完全一致。
    这几条是从本地 61 个已上架专家的清单统计出来的，不是猜的。"""
    with open(os.path.join(root, ".codebuddy-plugin", "plugin.json"), encoding="utf-8") as f:
        d = json.load(f)
    prob = []
    tags = d.get("tags") or []
    qp = d.get("quickPrompts") or []
    dip = d.get("defaultInitPrompt") or {}

    if len(tags) != 3:
        prob.append("tags 须固定 3 个，当前 %d 个" % len(tags))
    for tg in tags:
        for lang in ("zh", "en"):
            v = tg.get(lang, "")
            if not v:
                prob.append("tag 缺 %s" % lang)
            elif lang == "zh" and not (2 <= len(v) <= 8):
                prob.append("tag.zh 长度 %d 不在 2—8：%s" % (len(v), v))

    if len(qp) != 3:
        prob.append("quickPrompts 须固定 3 个，当前 %d 个" % len(qp))
    for i, q in enumerate(qp):
        for lang in ("zh", "en"):
            v = q.get(lang, "")
            if not v:
                prob.append("quickPrompts[%d] 缺 %s" % (i, lang))
            elif lang == "zh" and not (8 <= len(v) <= 138):
                prob.append("quickPrompts[%d].zh 长度 %d 不在 8—138" % (i, len(v)))

    if qp:
        if dip.get("zh") != qp[0].get("zh"):
            prob.append("defaultInitPrompt.zh 与 quickPrompts[0].zh 不一致")
        if dip.get("en") != qp[0].get("en"):
            prob.append("defaultInitPrompt.en 与 quickPrompts[0].en 不一致")

    record("T-20", "平台清单约束（tags=3 / quickPrompts=3 / 默认提示与首条一致）", not prob,
           "；".join(prob) if prob else "tags 3 个、quickPrompts 3 个、defaultInitPrompt 与首条逐字符一致")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--json", dest="json_out", default=None)
    a = ap.parse_args()
    root = os.path.abspath(a.root)

    print("自检根目录：%s\n" % root)
    with tempfile.TemporaryDirectory() as tmp:
        t01_manifest(root)
        t02_skills(root)
        t03_agent(root)
        t04_avatar(root)
        t05_paths(root)
        t06_encoding(root)
        t07_zip(root)
        t08_voice(root, tmp)
        t09_nproj(root, tmp)
        t10_lint(root, tmp)
        t11_funnel(root, tmp)
        t12_no_deps(root)
        t13_texts(root)
        t14_selfcontained(root)
        t15_master(root)
        t16_pitch(root, tmp)
        t17_pacing(root, tmp)
        t18_rescue(root, tmp)
        t19_verify(root, tmp)
        t20_platform_schema(root)

    ok = [r for r in RESULTS if r["ok"]]
    bad = [r for r in RESULTS if not r["ok"] and r["blocking"]]
    soft = [r for r in RESULTS if not r["ok"] and not r["blocking"]]
    print("\n" + "=" * 56)
    print("通过 %d / %d ｜ 阻断失败 %d ｜ 未执行 %d"
          % (len(ok), len(RESULTS), len(bad), len(soft)))
    print("=" * 56)
    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as f:
            json.dump({"results": RESULTS, "passed": len(ok), "total": len(RESULTS)},
                      f, ensure_ascii=False, indent=2)
        print("已写入：%s" % a.json_out)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
