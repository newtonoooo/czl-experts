#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键自检：证明"装上就能跑"，不联网、不用第三方包。

查六件事：
    1. 元数据一致：plugin.json / agentName / agent 文件 / skills 目录 / 头像
    2. 启动注入量（agent + skills）不超过 16KB（超出会稀释行为）
    3. 角色层硬规则在位（首字即标题、不许先问、不谎报）
    4. docx 导出：用样例生成正文
    5. docx 校验：结构、页面几何、页码
    6. 样稿要素：标题三要素、主送、署名、日期、结语

用法：python bin/selftest.py [--keep]
退出码：0 全过；1 有失败。
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXPERT = Path(__file__).resolve().parent.parent
SKILL = EXPERT / "skills" / "doc-craft"
SAMPLE = SKILL / "samples" / "通知.txt"


def run(args):
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    print(f"专家包：{EXPERT}")
    print(f"Python：{sys.executable}（{sys.version.split()[0]}）")
    print("-" * 60)
    results = []

    def rec(name, ok, detail=""):
        results.append((name, ok))
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))

    # 1 元数据
    pj = json.loads((EXPERT / ".codebuddy-plugin" / "plugin.json").read_text(encoding="utf-8"))
    agent = EXPERT / "agents" / f"{pj.get('agentName')}.md"
    rec("agentName 有对应 agent 文件", agent.exists(), f"agentName={pj.get('agentName')}")
    rec("plugin == name", pj.get("plugin") == pj.get("name"), pj.get("name", ""))
    rec("tags / quickPrompts 各 3 条",
        len(pj.get("tags", [])) == 3 and len(pj.get("quickPrompts", [])) == 3)
    rec("defaultInitPrompt == quickPrompts[0]",
        pj.get("defaultInitPrompt", {}).get("zh") == pj.get("quickPrompts", [{}])[0].get("zh"))
    desc = pj.get("displayDescription", {}).get("zh", "")
    rec("简介中文 40—50 字", 40 <= len(desc) <= 50, f"{len(desc)} 字")
    rec("skills 目录均有 SKILL.md",
        all((EXPERT / s.lstrip("./") / "SKILL.md").exists() for s in pj.get("skills", [])))
    avatar = EXPERT / pj.get("avatar", "")
    rec("头像存在且 ≤500KB", avatar.exists() and avatar.stat().st_size <= 500 * 1024,
        f"{avatar.stat().st_size // 1024}KB" if avatar.exists() else "缺")

    # 2 注入量
    injected = len(agent.read_text(encoding="utf-8"))
    for s in pj.get("skills", []):
        injected += len((EXPERT / s.lstrip("./") / "SKILL.md").read_text(encoding="utf-8"))
    rec("启动注入量 ≤16KB", injected <= 16 * 1024, f"{injected} 字符（约 {injected // 2} 汉字）")

    # 3 硬规则
    body = agent.read_text(encoding="utf-8")
    missing = [m for m in ("第一个字符是标题", "不许先提问", "不谎报") if m not in body]
    rec("角色层三条硬规则在位", not missing, ("缺：" + "、".join(missing)) if missing else "")
    fm = body.split("---")[1] if body.startswith("---") else ""
    rec("frontmatter 无 tools 字段", "tools:" not in fm)

    # 4-5 排版与校验
    tmp = Path(tempfile.mkdtemp(prefix="antou-"))
    out = tmp / "01_正文.docx"
    code, _ = run([sys.executable, str(EXPERT / "bin/docx_export.py"), str(SAMPLE), "--out", str(out)])
    rec("docx 导出", code == 0 and out.exists(), f"exit={code}")
    code, o = run([sys.executable, str(EXPERT / "bin/docx_check.py"), str(out), "--src", str(SAMPLE)])
    rec("docx 结构校验", code == 0, f"exit={code}")
    if code != 0 and o.strip():
        print("      " + o.strip().splitlines()[-1][:100])

    # 6 要素
    text = SAMPLE.read_text(encoding="utf-8")
    rec("样稿要素齐（标题/主送/署名/日期）",
        all(n in text for n in ("[标题]", "[主送]", "[署名]", "[日期]")))
    title = next((l.split("]", 1)[1].strip() for l in text.splitlines() if l.startswith("[标题]")), "")
    rec("标题三要素（机关+关于+文种）",
        "关于" in title and title.endswith("通知") and len(title) > 12, title[:26])
    rec("结语符合文种", "请认真抓好落实" in text)

    bad = sum(1 for _, ok in results if not ok)
    print("-" * 60)
    print(f"合计 {len(results)} 项：通过 {len(results) - bad}，失败 {bad}")
    if args.keep:
        print(f"临时产物：{tmp}")
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    print("结论：" + ("装上即可运行" if bad == 0 else "有失败项，修好再发布"))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
