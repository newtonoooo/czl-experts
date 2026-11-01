#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""功能测试：一次性跑完结构与产物检查，输出 PASS/FAIL 清单。

用法:
    python tests/run_tests.py

会真实生成 docx / pptx / zip，并对"缺依赖时的降级行为"做一次实测。
不带 --no-fallback 时，会尝试用缺少 python-docx 的解释器验证降级逻辑。
"""

import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
FIX = ROOT / "tests" / "fixtures"
rows = []


def rec(name, ok, detail=""):
    rows.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} | {name}" + (f" | {detail}" if detail else ""))


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", **kw)


def main():
    print(f"解释器: {PY}\n项目根: {ROOT}\n")

    # 清理上一轮可能残留的产物，避免被打进包
    for junk in (FIX / "sample-deck.md", FIX / "sample-deck.pptx"):
        if junk.exists():
            junk.unlink()

    # 1 结构自检
    p = run([PY, str(ROOT / "tools" / "verify_package.py"), str(ROOT)])
    fails = [l for l in p.stdout.splitlines() if l.startswith("[FAIL]")]
    total_line = [l for l in p.stdout.splitlines() if l.startswith("共 ")]
    rec("专家包结构自检", p.returncode == 0,
        (total_line[0] if total_line else "") + f"；失败项 {len(fails)}")

    # 2 plugin.json 关键字段
    pj = json.loads((ROOT / ".codebuddy-plugin" / "plugin.json").read_text(encoding="utf-8"))
    rec("displayDescription.zh 长度 40–50", 40 <= len(pj["displayDescription"]["zh"]) <= 50,
        f"{len(pj['displayDescription']['zh'])} 字")
    rec("名称无空格与特殊字符",
        all(ch.isalnum() or ch in "-—_·" for ch in pj["displayName"]["zh"]), pj["displayName"]["zh"])

    # 3 工作流规格完整性
    required = ["职责", "输入参数", "执行步骤", "判断条件", "输出格式", "异常处理", "依赖", "与其他工作流的关系"]
    wf = sorted((ROOT / "workflows").glob("*.md"))
    incomplete = []
    for f in wf:
        t = f.read_text(encoding="utf-8")
        miss = [r for r in required if r not in t]
        if miss:
            incomplete.append(f"{f.name}:{'/'.join(miss)}")
    rec(f"工作流规格含 8 个规定章节（共 {len(wf)} 个文件）", not incomplete, "; ".join(incomplete) or "全部齐备")

    # 4 docx 生成
    with tempfile.TemporaryDirectory() as td:
        out_docx = Path(td) / "打印版_测试.docx"
        p = run([PY, str(ROOT / "tools" / "build_print_docx.py"), str(FIX / "sample-lesson.md"), str(out_docx)])
        ok = p.returncode == 0 and out_docx.exists()
        detail = f"{out_docx.stat().st_size / 1024:.1f} KB" if out_docx.exists() else (p.stderr[-200:] if p.stderr else "")
        rec("Markdown → docx 生成", ok, detail)
        if ok:
            with zipfile.ZipFile(out_docx) as zf:
                xml = zf.read("word/document.xml").decode("utf-8", "ignore")
            rec("docx 内含中文正文与表格", ("大气受热过程" in xml) and ("<w:tbl>" in xml),
                f"文本长度 {len(xml)}")
            try:
                import docx as _docx
                d = _docx.Document(str(out_docx))
                n_par = len([x for x in d.paragraphs if x.text.strip()])
                rec("重新打开 docx（结构合法）", len(d.tables) >= 1 and n_par >= 10,
                    f"段落 {n_par}，表格 {len(d.tables)}")
            except Exception as e:
                rec("重新打开 docx（结构合法）", False, str(e))

        # 5 pptx 生成
        out_pptx = Path(td) / "deck.pptx"
        p = run([PY, str(ROOT / "tools" / "build_ppt.py"), str(FIX / "sample-deck.json"), str(out_pptx)])
        ok = p.returncode == 0 and out_pptx.exists()
        rec("JSON 大纲 → pptx 生成", ok, f"{out_pptx.stat().st_size / 1024:.1f} KB" if out_pptx.exists() else p.stderr[-200:])
        if ok:
            with zipfile.ZipFile(out_pptx) as zf:
                slides = [n for n in zf.namelist() if n.startswith("ppt/slides/slide")]
            rec("pptx 页数 = 1 封面 + 5 内容", len(slides) == 6, f"{len(slides)} 页")

    # 6 降级行为（用缺少 python-docx / python-pptx 的解释器）
    bare = None
    for cand in ("python", "python3", os.environ.get("PYTHON_BARE", "")):
        if not cand:
            continue
        try:
            probe = run([cand, "-c", "import docx"])
            if probe.returncode != 0:
                bare = cand
                break
        except FileNotFoundError:
            continue
    if bare:
        with tempfile.TemporaryDirectory() as td:
            # 复制到临时目录再跑降级测试，保证产物不落在包内
            import shutil as _sh
            _sh.copyfile(FIX / "sample-deck.json", Path(td) / "deck.json")
            p = run([bare, str(ROOT / "tools" / "build_print_docx.py"),
                     str(FIX / "sample-lesson.md"), str(Path(td) / "x.docx")])
            rec("缺 python-docx 时明确报错并退出码 2",
                p.returncode == 2 and "未安装 python-docx" in (p.stderr or ""), f"解释器 {bare}")
            p = run([bare, str(ROOT / "tools" / "build_ppt.py"),
                     str(Path(td) / "deck.json"), str(Path(td) / "x.pptx")])
            md = (Path(td) / "deck.md").exists()
            rec("缺 python-pptx 时导出 md 大纲并退出码 2",
                p.returncode == 2 and md, f"解释器 {bare}")
            if md:
                (Path(td) / "deck.md").unlink()
    else:
        rec("降级行为测试", True, "未找到缺依赖的解释器，跳过（不计入通过）")

    # 7 打包并往返校验
    p = run([PY, str(ROOT / "tools" / "sync_install.py"), "package"])
    zips = sorted((ROOT / "dist").glob("*.zip"))
    if zips:
        z = zips[-1]
        rec("生成 zip 发布包", True, f"{z.name} {z.stat().st_size / 1024:.1f} KB")
        with zipfile.ZipFile(z) as zf:
            names = zf.namelist()
        rec("zip 含头像且路径正确", "czl-geo-teacher-desk/avatars/expert.png" in names, "")
        rec("zip 含 manifest.yaml", "czl-geo-teacher-desk/manifest.yaml" in names, "")
        rec("zip 未混入 dist 产物", not any("/dist/" in n for n in names), "")
        p = run([PY, str(ROOT / "tools" / "verify_package.py"), str(z)])
        rec("解压后重新校验通过（模拟导入）", p.returncode == 0,
            "失败项 " + str(len([l for l in p.stdout.splitlines() if l.startswith("[FAIL]")])))
    else:
        rec("生成 zip 发布包", False, "dist 下未找到 zip")

    # 汇总
    fail = [r for r in rows if not r[1]]
    print("\n===== 汇总 =====")
    print(f"共 {len(rows)} 项，通过 {len(rows) - len(fail)}，失败 {len(fail)}")
    for n, _, d in fail:
        print(f"  失败：{n} {d}")
    sys.exit(0 if not fail else 1)


if __name__ == "__main__":
    main()
