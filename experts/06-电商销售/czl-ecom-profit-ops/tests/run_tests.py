#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_tests.py - czl-ecom-profit-ops 的回归测试。

覆盖四件事：
1. 四个工具的用例（正常 / 亏损 / 越界输入 / JSON 输出 / 退出码）
2. 源代码可编译
3. 包结构：plugin.json 字段、agent frontmatter、技能入口、头像
4. 交叉引用：主提示词提到的技能与文档引用的文件是否都真实存在

用法
----
    python tests/run_tests.py
    python tests/run_tests.py -v

退出码 0 = 全部通过。
"""

from __future__ import annotations

import json
import os
import py_compile
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DIR_SKU = os.path.join(ROOT, "skills", "sku-margin", "scripts")
DIR_PROMO = os.path.join(ROOT, "skills", "promo-math", "scripts")
DIR_FUNNEL = os.path.join(ROOT, "skills", "funnel-review", "scripts")
DIR_COPY = os.path.join(ROOT, "skills", "copy-compliance", "scripts")

RESULTS = []


def run(script_dir, script, args, timeout=120):
    cmd = [sys.executable, os.path.join(script_dir, script)] + args
    proc = subprocess.run(
        cmd, cwd=script_dir, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def check(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": detail})
    print(("[PASS] " if ok else "[FAIL] ") + name + (f"  <- {detail}" if not ok and detail else ""))


def expect(name, script_dir, script, args, want_code=None, want_text=None, forbid_text=None):
    code, out = run(script_dir, script, args)
    ok, detail = True, []
    if want_code is not None and code != want_code:
        ok = False
        detail.append(f"exit {code} != {want_code}")
    for t in want_text or []:
        if t not in out:
            ok = False
            detail.append(f"missing {t!r}")
    for t in forbid_text or []:
        if t in out:
            ok = False
            detail.append(f"unexpected {t!r}")
    check(name, ok, "; ".join(detail) + ("" if ok else "\n    " + out.strip()[:400]))
    return out


def main():
    verbose = "-v" in sys.argv

    print("=" * 72)
    print("1. sku_margin.py（单品账本）")
    print("=" * 72)
    expect(
        "健康链接：给出保本 ROI 与三个生死数",
        DIR_SKU, "sku_margin.py",
        ["ledger", "--price", "129", "--cost", "38", "--ship", "6", "--commission", "0.05",
         "--payment", "0.006", "--refund", "0.18", "--return-ship", "8", "--return-handling", "2",
         "--restock", "0.8", "--ad-ratio", "0.2", "--fixed", "30000"],
        want_code=0,
        want_text=["保本 ROI", "单均贡献毛利", "盈亏平衡单量", "最大可承受退货率"],
    )
    expect(
        "亏损链接：退出码 1 并判为亏损",
        DIR_SKU, "sku_margin.py",
        ["ledger", "--price", "39", "--cost", "30", "--ship", "6", "--refund", "0.3", "--ad-ratio", "0.2"],
        want_code=1, want_text=["亏损"],
    )
    expect(
        "退货率敏感性：给出临界退货率",
        DIR_SKU, "sku_margin.py",
        ["sensitivity", "--price", "99", "--cost", "40", "--ship", "6", "--refund", "0.2", "--ad-ratio", "0.15"],
        want_text=["退货率敏感性", "临界退货率"],
    )
    expect(
        "批量测算：识别出亏损款",
        DIR_SKU, "sku_margin.py",
        ["batch", "fixtures/skus.csv", "--fixed", "60000"],
        want_code=1, want_text=["不锈钢饭盒", "亏损"],
    )
    out = expect(
        "账本 JSON 可解析",
        DIR_SKU, "sku_margin.py",
        ["ledger", "--price", "129", "--cost", "38", "--refund", "0.1", "--json"],
        want_code=0,
    )
    try:
        payload = json.loads(out)
        check("JSON 含 per_order_contribution / breakeven_roi",
              "per_order_contribution" in payload and "breakeven_roi" in payload)
    except json.JSONDecodeError as exc:
        check("JSON 可解析", False, str(exc))
    expect(
        "非法退货率：退出码 2",
        DIR_SKU, "sku_margin.py",
        ["ledger", "--price", "100", "--cost", "40", "--refund", "1.5"],
        want_code=2,
    )

    print()
    print("=" * 72)
    print("2. promo_math.py（大促机制与备货）")
    print("=" * 72)
    expect(
        "机制叠加：健康活动价",
        DIR_PROMO, "promo_math.py",
        ["stack", "--price", "199", "--cost", "62", "--ship", "8", "--commission", "0.05",
         "--payment", "0.006", "--item-discount", "0.9", "--member", "0.95",
         "--store-threshold", "199", "--store-coupon", "20",
         "--cross-threshold", "300", "--cross-off", "50"],
        want_code=0, want_text=["保本实收", "让利最大的一层", "健康"],
    )
    expect(
        "店铺券未达门槛：明确指出",
        DIR_PROMO, "promo_math.py",
        ["stack", "--price", "199", "--cost", "62", "--item-discount", "0.9",
         "--store-threshold", "199", "--store-coupon", "20"],
        want_text=["未达门槛"],
    )
    expect(
        "活动价打穿成本：退出码 1",
        DIR_PROMO, "promo_math.py",
        ["stack", "--price", "199", "--cost", "160", "--ship", "10", "--item-discount", "0.8",
         "--cross-threshold", "300", "--cross-off", "50"],
        want_code=1, want_text=["亏损"],
    )
    expect(
        "缺跨店门槛：退出码 2",
        DIR_PROMO, "promo_math.py",
        ["stack", "--price", "199", "--cost", "62", "--cross-off", "50"],
        want_code=2,
    )
    expect(
        "备货健康：两端风险都在容忍范围",
        DIR_PROMO, "promo_math.py",
        ["stock", "--daily", "20", "--uplift", "3", "--days", "3", "--lead-days", "5",
         "--safety-days", "1", "--moq", "50", "--unit-cost", "62", "--settle-days", "15"],
        want_code=0, want_text=["现金占用天数", "容忍范围"],
    )
    expect(
        "备货偏紧：提示断货",
        DIR_PROMO, "promo_math.py",
        ["stock", "--daily", "20", "--uplift", "3", "--days", "3", "--lead-days", "5",
         "--safety-days", "0", "--unit-cost", "62"],
        want_code=1, want_text=["断货"],
    )
    out = expect(
        "备货 JSON 可解析",
        DIR_PROMO, "promo_math.py",
        ["stock", "--daily", "10", "--unit-cost", "50", "--json"],
        want_code=0,
    )
    try:
        payload = json.loads(out)
        check("JSON 含 buy_qty / scenarios", "buy_qty" in payload and "scenarios" in payload)
    except json.JSONDecodeError as exc:
        check("JSON 可解析", False, str(exc))

    print()
    print("=" * 72)
    print("3. funnel_check.py（GMV 拆解）")
    print("=" * 72)
    out = expect(
        "四项贡献可加总，残差为 0",
        DIR_FUNNEL, "funnel_check.py",
        ["decompose", "--p1-uv", "120000", "--p1-cvr", "0.031", "--p1-aov", "168", "--p1-refund", "0.14",
         "--p2-uv", "98000", "--p2-cvr", "0.028", "--p2-aov", "181", "--p2-refund", "0.19"],
        want_code=0, want_text=["主因排序", "差额 0.0"],
    )
    try:
        payload = json.loads(run(
            DIR_FUNNEL, "funnel_check.py",
            ["decompose", "--p1-uv", "100", "--p1-cvr", "0.02", "--p1-aov", "100",
             "--p2-uv", "120", "--p2-cvr", "0.02", "--p2-aov", "100", "--json"],
        )[1])
        total = sum(s["effect"] for s in payload["steps"])
        check("JSON 内四项贡献之和等于 delta", abs(total - payload["delta"]) < 0.05,
              f"{total} vs {payload['delta']}")
    except Exception as exc:  # noqa: BLE001
        check("JSON 可解析", False, str(exc))
    expect(
        "转化率越界：退出码 2",
        DIR_FUNNEL, "funnel_check.py",
        ["decompose", "--p1-uv", "100", "--p1-cvr", "1.2", "--p1-aov", "100",
         "--p2-uv", "100", "--p2-cvr", "0.02", "--p2-aov", "100"],
        want_code=2,
    )

    print()
    print("=" * 72)
    print("4. copy_lint.py（文案合规）")
    print("=" * 72)
    expect(
        "高风险文案：命中绝对化/比价/诱导评价",
        DIR_COPY, "copy_lint.py",
        ["--text", "儿童保温杯 食品级 最安全 宝宝专用 316不锈钢 全网最低 好评返现"],
        want_code=1, want_text=["最安全", "全网最低", "好评返现", "不可直接上架"],
    )
    expect(
        "干净文案：退出码 0",
        DIR_COPY, "copy_lint.py",
        ["--text", "316不锈钢儿童保温杯 6小时保温 400ml 吸管盖 可拆洗"],
        want_code=0,
    )
    expect(
        "标题超长：指出超出字数",
        DIR_COPY, "copy_lint.py",
        ["--text", "316不锈钢儿童保温杯吸管盖可拆洗400ml长效保温", "--title", "--limit", "20"],
        want_text=["标题超长"],
    )
    expect(
        "关键词堆砌：识别重复词",
        DIR_COPY, "copy_lint.py",
        ["--text", "水杯 水杯 水杯 大容量"],
        want_text=["关键词堆砌"],
    )
    out = expect(
        "合规 JSON 可解析",
        DIR_COPY, "copy_lint.py",
        ["--text", "最好用的杯子", "--json"],
        want_code=1,
    )
    try:
        payload = json.loads(out)
        check("JSON 含 hits / counts", "hits" in payload and payload["counts"]["high"] >= 1)
    except json.JSONDecodeError as exc:
        check("JSON 可解析", False, str(exc))
    expect(
        "文件不存在：退出码 2",
        DIR_COPY, "copy_lint.py",
        ["--file", "no_such_file.txt"],
        want_code=2,
    )

    print()
    print("=" * 72)
    print("5. 源码编译")
    print("=" * 72)
    for d, s in [(DIR_SKU, "sku_margin.py"), (DIR_PROMO, "promo_math.py"),
                 (DIR_FUNNEL, "funnel_check.py"), (DIR_COPY, "copy_lint.py")]:
        try:
            py_compile.compile(os.path.join(d, s), doraise=True,
                               cfile=os.path.join(tempfile.gettempdir(), s + "c"))
            check(f"{s} 编译通过", True)
        except py_compile.PyCompileError as exc:
            check(f"{s} 编译通过", False, str(exc))

    print()
    print("=" * 72)
    print("6. 包结构")
    print("=" * 72)
    pj_path = os.path.join(ROOT, ".codebuddy-plugin", "plugin.json")
    try:
        with open(pj_path, encoding="utf-8") as fh:
            pj = json.load(fh)
        check("plugin.json 可解析", True)
    except Exception as exc:  # noqa: BLE001
        check("plugin.json 可解析", False, str(exc))
        pj = {}

    check("name 与目录名一致且以 czl- 开头",
          pj.get("name") == os.path.basename(ROOT) and str(pj.get("name", "")).startswith("czl-"))
    check("author 为虫志龙", pj.get("author", {}).get("name") == "虫志龙")
    check("author 邮箱正确", pj.get("author", {}).get("email") == "47190078@qq.com")
    check("tags 恰好 3 个", len(pj.get("tags", [])) == 3)
    check("quickPrompts 恰好 3 个", len(pj.get("quickPrompts", [])) == 3)
    qp = pj.get("quickPrompts") or [{}]
    check("defaultInitPrompt.zh == quickPrompts[0].zh",
          pj.get("defaultInitPrompt", {}).get("zh") == qp[0].get("zh"))
    check("plugin 字段等于 name", pj.get("plugin") == pj.get("name"))
    check("expertType 为 agent", pj.get("expertType") == "agent")
    check("categoryId 为 07-SalesCommerce", pj.get("categoryId") == "07-SalesCommerce")
    check("version 为语义化版本", bool(re.match(r"^\d+\.\d+\.\d+$", pj.get("version", ""))))

    desc = pj.get("displayDescription", {}).get("zh", "")
    check(f"displayDescription.zh 长度 40-50（实际 {len(desc)}）", 40 <= len(desc) <= 50)

    avatar = os.path.join(ROOT, pj.get("avatar", ""))
    exists = os.path.exists(avatar)
    check("头像文件存在", exists)
    if exists:
        size = os.path.getsize(avatar)
        check(f"头像 ≤500KB（实际 {size // 1024}KB）", size <= 500 * 1024)
        with open(avatar, "rb") as fh:
            check("头像为 PNG 格式", fh.read(8) == b"\x89PNG\r\n\x1a\n")

    agents = pj.get("agents", [])
    check("agents 路径全部存在",
          all(os.path.exists(os.path.join(ROOT, a.lstrip("./"))) for a in agents))

    skills = pj.get("skills", [])
    check("skills 数量为 7", len(skills) == 7)
    check("每个 skill 都有 SKILL.md",
          all(os.path.exists(os.path.join(ROOT, s.lstrip("./"), "SKILL.md")) for s in skills))

    agent_md = os.path.join(ROOT, "agents", f"{pj.get('agentName', 'x')}.md")
    agent_text = ""
    if os.path.exists(agent_md):
        with open(agent_md, encoding="utf-8") as fh:
            agent_text = fh.read()
        head = agent_text.split("---")[1] if agent_text.startswith("---") else ""
        check("frontmatter 不含 tools 字段", "tools:" not in head)
        check("frontmatter name 与 agentName 一致", f"name: {pj.get('agentName')}" in head)
        check("正文含操盘单契约", "操盘单" in agent_text)
        check("正文含硬规则", "硬规则" in agent_text)
        check("正文含异常处理", "异常处理" in agent_text)
    else:
        check("agent md 存在", False, agent_md)

    forbidden = [d for d in ("hooks", "commands") if os.path.isdir(os.path.join(ROOT, d))]
    check("无禁用目录 hooks/ commands/", not forbidden, str(forbidden))
    check("无 .lsp.json", not os.path.exists(os.path.join(ROOT, ".lsp.json")))

    print()
    print("=" * 72)
    print("7. 交叉引用与占位符")
    print("=" * 72)
    skill_names = [os.path.basename(s.rstrip("/")) for s in skills]
    if agent_text:
        referenced = [n for n in skill_names if "`" + n + "`" in agent_text]
        check(f"主提示词引用了全部 7 个技能（实际 {len(referenced)}）",
              len(referenced) == 7, str(set(skill_names) - set(referenced)))

    missing_refs = []
    pattern = re.compile(
        r"(?<![\w/])(?:references/[A-Za-z0-9_\-]+\.md|scripts/[A-Za-z0-9_\-]+\.py|fixtures/[A-Za-z0-9_\-]+\.csv)"
    )
    for skill in skill_names:
        sdir = os.path.join(ROOT, "skills", skill)
        md = os.path.join(sdir, "SKILL.md")
        if not os.path.exists(md):
            continue
        with open(md, encoding="utf-8") as fh:
            body = fh.read()
        for rel in sorted(set(pattern.findall(body))):
            if not os.path.exists(os.path.join(sdir, rel)):
                missing_refs.append(f"{skill}: {rel}")
    check("技能内引用的文件路径均存在", not missing_refs, str(missing_refs[:5]))

    todo = []
    token = "[TO" + "DO"   # 拆开写，避免本文件把自己判成占位符
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
        for name in files:
            if not name.endswith((".md", ".json", ".py", ".csv", ".txt")):
                continue
            path = os.path.join(base, name)
            try:
                with open(path, encoding="utf-8") as fh:
                    if token in fh.read():
                        todo.append(os.path.relpath(path, ROOT))
            except UnicodeDecodeError:
                continue
    check("包内无未填充的占位符", not todo, str(todo[:5]))

    print()
    print("=" * 72)
    passed = sum(1 for r in RESULTS if r["ok"])
    total = len(RESULTS)
    print(f"结果：{passed}/{total} 通过")
    if verbose:
        for r in RESULTS:
            print(("  ok   " if r["ok"] else "  FAIL ") + r["name"])
    failed = [r for r in RESULTS if not r["ok"]]
    if failed:
        print("\n失败项：")
        for r in failed:
            print(f"  - {r['name']}: {r['detail'][:300]}")
        return 1
    print("全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
