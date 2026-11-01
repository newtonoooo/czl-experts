#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按评标办法生成技术方案骨架。

子命令：
    plan      按评分项分值分配章节与页数
    check     校验评分表输入
    template  输出评分表模板

分配原则：分值高的给篇幅，0 分项只做形式响应。
"""

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

FIXED_PAGES = 4  # 封面、目录、偏离表等
MAX_CHAPTER_PAGES = 15
MIN_CHAPTER_PAGES = 1

ELEMENT_MAP = [
    (("架构", "总体设计", "技术路线"), ["总体架构图", "部署架构图", "技术选型理由", "与现有系统的关系"]),
    (("数据", "治理", "共享", "交换"), ["数据来源与范围", "清洗与质量规则", "质量指标", "共享交换通道", "数据分级分类"]),
    (("安全", "等保", "密码", "密评"), ["等保级别与控制项对照", "密码算法使用点（SM2/SM3/SM4）", "日志审计", "备份与恢复"]),
    (("信创", "国产化", "自主可控"), ["CPU/OS/数据库/中间件型号", "兼容性证明", "迁移与回退路径"]),
    (("接口", "对接", "集成"), ["接口清单", "协议与频率", "异常处理", "对现有系统的影响"]),
    (("性能", "并发", "容量"), ["指标值", "测算口径", "压测方法", "扩容方案"]),
    (("实施", "计划", "进度", "组织"), ["里程碑", "甘特图", "人员投入曲线", "风险预案"]),
    (("运维", "服务", "售后", "保障"), ["SLA 指标", "响应时限", "驻场安排", "升级与备件机制"]),
    (("培训", "移交", "知识转移"), ["培训对象与场次", "教材", "考核方式", "移交清单"]),
    (("案例", "业绩", "经验"), ["案例名称与规模", "与本项目的相似点", "可核验材料"]),
    (("报价", "商务", "价格"), ["报价构成", "付款节点", "让利方式", "账期成本"]),
]

REQUIRED_CHAPTERS = [
    ("项目理解", ("理解", "需求", "背景")),
    ("总体架构", ("架构", "总体设计")),
    ("安全合规", ("安全", "等保", "密码")),
    ("实施计划", ("实施", "计划", "进度")),
    ("运维服务", ("运维", "服务", "售后")),
    ("案例业绩", ("案例", "业绩")),
]

TIPS = {
    "架构": "先讲一条业务线怎么走通，再落到分层；上来就摆五层架构图，评委记不住。",
    "数据": "数据治理是最容易做出差异化的脏活，写清脏数据长什么样、怎么洗、洗完谁验收。",
    "安全": "等保和密评不要放附录。架构、部署、运维三处各写一段，评委才认为你真的做过。",
    "信创": "列型号，不写'全面支持国产化'。型号对不上，现场一问就露。",
    "实施": "里程碑要挂在客户能感知的节点上（初验、试运行、上线），不是内部开发节点。",
    "案例": "案例写相似点，不写客户赞美。评委只关心'你干过一样的事吗'。",
    "性能": "性能指标必须带条件：多少用户、什么操作、多长响应。裸指标等于没写。",
    "报价": "报价章节只放结论与构成，测算过程留在内部，别把成本底牌写进标书。",
}


def load(path):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"找不到输入文件：{p}")
    return json.loads(p.read_text(encoding="utf-8"))


def elements_for(name):
    found = []
    for keys, elems in ELEMENT_MAP:
        if any(k in name for k in keys):
            for e in elems:
                if e not in found:
                    found.append(e)
    return found


def tip_for(name):
    for keys, elems in ELEMENT_MAP:
        if any(k in name for k in keys):
            key = elems[0][:2]
            for k, v in TIPS.items():
                if k in name:
                    return v
            return TIPS.get(key, "")
    return ""


def allocate(items, page_limit):
    pool = max(page_limit - FIXED_PAGES, len(items))
    total = sum(max(float(i.get("points", 0)), 0) for i in items) or 1.0
    pages = []
    for it in items:
        pts = max(float(it.get("points", 0)), 0)
        raw = pool * pts / total
        p = int(round(raw))
        if it.get("points", 0) == 0:
            p = MIN_CHAPTER_PAGES
        p = max(MIN_CHAPTER_PAGES, min(p, MAX_CHAPTER_PAGES))
        pages.append(p)

    # 四舍五入会超出页数池，从最肥的章节往回削，保证总数不超上限
    excess = sum(pages) - pool
    while excess > 0:
        idx = max(range(len(pages)), key=lambda i: pages[i])
        if pages[idx] <= MIN_CHAPTER_PAGES:
            break
        pages[idx] -= 1
        excess -= 1
    return pages


def plan(data, page_limit=None):
    items = data.get("items") or []
    limit = int(page_limit or data.get("page_limit") or 60)
    points_total = sum(float(i.get("points", 0)) for i in items)
    warnings = []

    declared = data.get("total_score")
    if declared and abs(float(declared) - points_total) > 0.01:
        warnings.append(
            f"评分项分值合计 {points_total:g} 与声明的总分 {declared:g} 不一致，按实际合计分配。"
        )
    if limit - FIXED_PAGES < len(items):
        warnings.append(
            f"页数上限 {limit} 页要装 {len(items)} 章，每章不足 1 页。建议合并同类项后再排。"
        )

    pages = allocate(items, limit)
    rows = []
    for it, p in zip(items, pages):
        name = it.get("name", "未命名章节")
        rows.append(
            {
                "name": name,
                "points": float(it.get("points", 0)),
                "pages": p,
                "must": elements_for(name),
                "tip": tip_for(name),
                "type": it.get("type", ""),
            }
        )

    names = " ".join(r["name"] for r in rows)
    missing = [label for label, keys in REQUIRED_CHAPTERS if not any(k in names for k in keys)]
    if missing:
        warnings.append("缺必备章节：" + "、".join(missing) + "。缺章在形式审查和技术评分里都会被扣。")

    return {
        "project": data.get("project", ""),
        "rows": rows,
        "warnings": warnings,
        "total_pages": sum(pages) + FIXED_PAGES,
        "page_limit": limit,
        "points_total": points_total,
    }


def render(result):
    out = []
    title = result["project"] or "技术方案"
    out.append(f"# 技术方案骨架：{title}")
    out.append("")
    out.append(
        f"- 章节数：{len(result['rows'])}；评分项分值合计：{result['points_total']:g}"
        f"；预计页数：{result['total_pages']} / 上限 {result['page_limit']}"
    )
    out.append("")
    out.append("## 一、方案骨架")
    out.append("")
    out.append("| 章节 | 分值 | 建议页数 | 必须出现 |")
    out.append("|---|---|---|---|")
    for i, r in enumerate(result["rows"], 1):
        must = "、".join(r["must"]) if r["must"] else "—"
        out.append(f"| {i}. {r['name']} | {r['points']:g} | {r['pages']} | {must} |")
    out.append("")
    out.append("## 二、逐章写作提示")
    out.append("")
    for i, r in enumerate(result["rows"], 1):
        out.append(f"### {i}. {r['name']}（{r['points']:g} 分 / {r['pages']} 页）")
        out.append("")
        if r["must"]:
            out.append("- 必须出现：" + "；".join(r["must"]))
        if r["tip"]:
            out.append("- 提示：" + r["tip"])
        if r["points"] == 0:
            out.append("- 注意：0 分项，只做形式响应，不超过 1 页。")
        out.append("")
    if result["warnings"]:
        out.append("## 三、风险提示")
        out.append("")
        for w in result["warnings"]:
            out.append(f"- {w}")
        out.append("")
    out.append("## 四、写作提醒")
    out.append("")
    out.append("1. 章节顺序对齐评分表顺序，评委翻页时的心理成本最低。")
    out.append("2. 每章开头一句话给结论，不要用'随着……的发展'开头。")
    out.append("3. 所有数字带来源与口径，方案里出现无法核对的数字，等于给对手递刀。")
    return "\n".join(out)


TEMPLATE = {
    "project": "XX区一网通办升级改造",
    "page_limit": 60,
    "total_score": 70,
    "items": [
        {"name": "项目理解与需求分析", "points": 8, "type": "商务"},
        {"name": "总体技术架构", "points": 12, "type": "技术"},
        {"name": "数据治理与共享交换", "points": 10, "type": "技术"},
        {"name": "安全与密码应用（等保三级/密评）", "points": 8, "type": "技术"},
        {"name": "信创适配方案", "points": 6, "type": "技术"},
        {"name": "实施计划与项目管理", "points": 8, "type": "技术"},
        {"name": "运维服务与培训", "points": 6, "type": "服务"},
        {"name": "类似案例与业绩", "points": 12, "type": "商务"},
    ],
}


def main():
    ap = argparse.ArgumentParser(description="按评标办法生成技术方案骨架")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("plan")
    p1.add_argument("--input", required=True)
    p1.add_argument("--out")
    p1.add_argument("--page-limit", type=int)
    p1.add_argument("--json", action="store_true")
    p1.set_defaults(name="plan")

    p2 = sub.add_parser("check")
    p2.add_argument("--input", required=True)
    p2.set_defaults(name="check")

    p3 = sub.add_parser("template")
    p3.set_defaults(name="template")

    args = ap.parse_args()

    if args.name == "template":
        print(json.dumps(TEMPLATE, ensure_ascii=False, indent=2))
        return 0

    try:
        data = load(args.input)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 2

    if args.name == "check":
        items = data.get("items") or []
        if not items:
            print("[错误] 没有 items，无法排章节。")
            return 2
        total = sum(float(i.get("points", 0)) for i in items)
        print(f"章节数：{len(items)}，分值合计：{total:g}")
        zero = [i.get("name") for i in items if float(i.get("points", 0)) == 0]
        if zero:
            print("0 分项：" + "、".join(map(str, zero)))
        print("可以排骨架。" if not zero else "可以排骨架，0 分项会被压到 1 页。")
        return 0

    result = plan(data, args.page_limit)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        text = render(result)
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
            print(f"已写出：{args.out}（{result['total_pages']} 页 / 上限 {result['page_limit']}）")
        else:
            print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
