#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""赢标主题压力测试：给每条主题句打分，指出它为什么会在评委那里贬值。

四道测试（每项 0-2.5 分，合计 10 分）：
  1. 客户特异 —— 换掉客户名还成立吗
  2. 证据可挂 —— 有没有可核的数字、项目、机制
  3. 差异成立 —— 对手能不能说一模一样的话
  4. 分数指向 —— 对应哪个评分项、值多少分

用法：
    python theme_stress.py themes.json
    python theme_stress.py themes.json --md out.md
"""

import argparse
import json
import re
import sys
from pathlib import Path

# 一出现就贬值的词：不是错字，是没有信息量的字
EMPTY_WORDS = [
    "强大的", "领先", "一流", "尖端", "先进", "卓越", "卓越的", "优质的",
    "赋能", "全方位", "一站式", "丰富的经验", "多年经验", "致力于",
    "专业的团队", "优秀的", "完善的", "高效的", "贴心", "深度", "全面",
    "行业领先", "国内领先", "国际领先", "顶尖", "资深团队", "强大实力",
]

# 有这些词，说明句子里有一个可被检验的机制，而不是一句表态
MECHANISM_WORDS = [
    "框架", "机制", "流程", "清单", "指标", "模板", "接口", "标准",
    "并行", "双跑", "灰度", "回滚", "验收", "基线", "口径", "台账",
    "工位", "排班", "阈值", "分级", "闭环", "抽检", "留痕", "台账",
    "响应时间", "到场", "驻场", "迁移", "压测", "演练", "复盘",
]

# 只能证明"我们能干"，不能证明"我们干过这个客户的活"
GENERIC_CAPABILITY = [
    "我们拥有", "我司具备", "我们能够", "我们提供", "我们有能力",
    "凭借", "依托", "基于多年", "积累了",
]

NUM_RE = re.compile(r"\d")


def load(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"文件不存在: {p}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"JSON 解析失败（第 {e.lineno} 行）：{e.msg}")


def score_theme(t: dict, client_tokens: list) -> dict:
    stmt = (t.get("statement") or "").strip()
    ev = (t.get("evidence") or "").strip()
    rubric = (t.get("rubric_item") or "").strip()
    issues, fixes = [], []

    # 1. 客户特异
    spec = 0.0
    hit_token = [k for k in client_tokens if k and k in stmt]
    if not client_tokens:
        spec = 1.0
        issues.append("未提供 client_tokens，无法验证客户特异性")
        fixes.append("在 themes.json 里补 client_tokens（客户名、项目名、下属机构名）")
    elif hit_token:
        spec = 2.5
    else:
        # 句子里没点名客户，看是否点了场景词（如"三个库房""两套老系统"）
        if re.search(r"[一二两三四五]个|[一二两三四五]套|[一二两三四五]期", stmt):
            spec = 1.5
            issues.append("未点名客户，但提到了具体场景数量")
            fixes.append("把场景数量换成客户方原话里的对象名（如“三个库房”写成“XX 公司 3 个前置仓”）")
        else:
            spec = 0.0
            issues.append("通不过换名测试：换掉客户名，这句话依然成立")
            fixes.append("把客户的具体处境写进句子：他们的系统、他们的期限、他们的验收口径")

    # 2. 证据可挂
    ev_score = 0.0
    if not ev or ev in ("无", "待补", "-"):
        issues.append("没有证据：这是一笔证据债")
        fixes.append("补一条可核证据（项目名+可公开的指标），补不上就降级成“方法预期”并写假设")
    else:
        if NUM_RE.search(ev):
            ev_score += 1.5
        else:
            ev_score += 0.75
            issues.append("证据里没有数字，评委无法衡量")
            fixes.append("给证据加一个数：可用率、工期、复工人数、差错率")
        if any(k in ev for k in ("案例", "项目", "客户", "验收", "上线")):
            ev_score += 1.0
        else:
            issues.append("证据不像一个“发生过的事”，更像一句承诺")
            fixes.append("换成“某项目在什么条件下做到什么”的句式")
        ev_score = min(ev_score, 2.5)

    # 3. 差异成立
    diff = 0.0
    mech = [w for w in MECHANISM_WORDS if w in stmt]
    empty = [w for w in EMPTY_WORDS if w in stmt]
    generic = [w for w in GENERIC_CAPABILITY if w in stmt]
    if mech:
        diff += 2.0 if len(mech) >= 2 else 1.5
    else:
        issues.append("句子里没有可检验的机制（框架/流程/指标/验收口径）")
        fixes.append("把“我们很专业”换成一个能被追问的做法名，比如“双跑迁移 + 每周比对台账”")
    if empty:
        diff -= 0.5 * min(len(empty), 3)
        issues.append(f"空洞形容词 {len(empty)} 个：{'、'.join(empty)}")
        fixes.append("删掉这些词，它们不承担信息")
    if generic:
        issues.append("以“我们拥有/我司具备”开头，属于能力自述，不是客户价值")
        fixes.append("改成“因为你们 X，所以我们做 Y，结果是 Z”")
    diff = max(0.0, min(diff, 2.5))

    # 4. 分数指向
    pt = 0.0
    if rubric:
        pt += 1.5
        if t.get("rubric_score"):
            pt += 0.5
        else:
            fixes.append("补 rubric_score：这条主题承接多少分，决定它值不值得花篇幅")
    else:
        issues.append("没有对应评分项：写了也不加分")
        fixes.append("从分数地图里挑一个主观项挂上去，一项对一条主题")

    # 长度
    n = len(stmt)
    if n == 0:
        issues.append("主题句为空")
    elif n < 12:
        issues.append(f"主题句过短（{n} 字），信息不足")
    elif n > 45:
        issues.append(f"主题句过长（{n} 字），评委记不住")
        fixes.append("压到 25-35 字：客户处境 + 我们的做法 + 结果")

    total = round(spec + ev_score + diff + pt, 1)
    if total >= 8:
        verdict = "保留"
    elif total >= 5.5:
        verdict = "改写"
    else:
        verdict = "删除或重写"

    return {
        "id": t.get("id") or stmt[:8],
        "statement": stmt,
        "rubric_item": rubric,
        "score": total,
        "dims": {"客户特异": round(spec, 1), "证据": round(ev_score, 1),
                 "差异": round(diff, 1), "分数指向": round(pt, 1)},
        "verdict": verdict,
        "issues": issues,
        "fixes": fixes,
        "length": n,
    }


def to_md(results, doc) -> str:
    keep = [r for r in results if r["verdict"] == "保留"]
    lines = ["# 赢标主题压力测试", ""]
    lines.append(f"共 {len(results)} 条，保留 {len(keep)} 条，"
                 f"改写 {sum(1 for r in results if r['verdict'] == '改写')} 条，"
                 f"淘汰 {sum(1 for r in results if r['verdict'].startswith('删除'))} 条。")
    if len(keep) < 3:
        lines.append("")
        lines.append("> 保留数少于 3 条。**宁可只交 2 条硬主题，也不要凑 5 条软话。**"
                     "主题数量不参与评分，硬不硬参与评分。")
    lines += ["", "| 主题 | 得分 | 客户特异 | 证据 | 差异 | 分数指向 | 结论 |",
              "|---|---|---|---|---|---|---|"]
    for r in results:
        d = r["dims"]
        lines.append(f"| {r['id']} | {r['score']}/10 | {d['客户特异']} | {d['证据']} | "
                     f"{d['差异']} | {d['分数指向']} | {r['verdict']} |")
    lines.append("")
    for r in results:
        lines.append(f"## {r['id']}　{r['score']}/10　{r['verdict']}")
        lines.append("")
        lines.append(f"> {r['statement'] or '（空）'}")
        lines.append("")
        if r["issues"]:
            lines.append("**问题**")
            for i in r["issues"]:
                lines.append(f"- {i}")
        if r["fixes"]:
            lines.append("")
            lines.append("**改法**")
            for f in r["fixes"]:
                lines.append(f"- {f}")
        lines.append("")
    tokens = doc.get("client_tokens") or []
    if tokens:
        lines += ["---", "", f"已用客户识别词：{'、'.join(tokens)}。"
                  "换名测试的口径：把上面这些词换成同行另一家，句子是否还成立。"]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="赢标主题压力测试")
    ap.add_argument("themes", help="themes.json")
    ap.add_argument("--md", default=None, help="Markdown 输出路径")
    ap.add_argument("--json", default=None, help="JSON 输出路径")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    doc = load(args.themes)
    themes = doc.get("themes") or []
    if not themes:
        raise SystemExit("themes.json 里没有 themes 数组")
    tokens = doc.get("client_tokens") or []

    results = [score_theme(t, tokens) for t in themes]
    md = to_md(results, doc)
    print(md)

    base = Path(args.themes).parent
    if args.md:
        Path(args.md).write_text(md, encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps(results, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
    if not args.md and not args.json:
        (base / "主题压测结果.md").write_text(md, encoding="utf-8")
        print(f"\n已写出：{base/'主题压测结果.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
