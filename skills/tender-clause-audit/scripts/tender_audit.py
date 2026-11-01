#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""招标文件条款体检。

子命令：
    scan       按规则库扫描文件，输出分级风险报告
    response   生成条款响应表骨架
    materials  生成投标材料清单骨架

只做提示性检查，不替代人工通读，也不构成法律意见。
"""

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

LEVEL_ORDER = {"致命": 0, "严重": 1, "一般": 2}
DEFAULT_RULES = Path(__file__).parent / "rules" / "tender_rules.json"

DATE_RE = re.compile(
    r"(20\d{2}\s*[-/年]\s*\d{1,2}\s*[-/月]\s*\d{1,2}\s*日?|\d{4}-\d{2}-\d{2})"
)
MANDATORY_RE = re.compile(r"必须|应当|不得|须|严禁")
STAR_RE = re.compile(r"[★▲＊]|\(\*\)|（\*）")


def read_text(path):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"找不到文件：{p}")
    raw = p.read_bytes()
    for enc in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore"), "utf-8(容错)"


def load_rules(path):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"找不到规则文件：{p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    rules = data.get("rules", [])
    for r in rules:
        r["_re"] = re.compile(r["pattern"])
    return rules


def scan(text, rules, min_level="一般"):
    lines = text.splitlines()
    hits = []
    limit = LEVEL_ORDER.get(min_level, 2)
    for idx, line in enumerate(lines, 1):
        s = line.strip()
        if not s:
            continue
        for r in rules:
            if LEVEL_ORDER.get(r["level"], 2) > limit:
                continue
            if r["_re"].search(s):
                hits.append(
                    {
                        "line": idx,
                        "level": r["level"],
                        "category": r["category"],
                        "rule": r["id"],
                        "quote": s[:120],
                        "why": r["why"],
                        "action": r["action"],
                    }
                )
    hits.sort(key=lambda h: (LEVEL_ORDER.get(h["level"], 3), h["line"]))

    stars = []
    dates = []
    for idx, line in enumerate(lines, 1):
        s = line.strip()
        if not s:
            continue
        if STAR_RE.search(s):
            stars.append({"line": idx, "quote": s[:120]})
        m = DATE_RE.search(s)
        if m and re.search(r"截止|开标|报名|质疑|澄清|答疑|递交|获取", s):
            dates.append({"line": idx, "quote": s[:120], "date": m.group(1)})

    mandatory = len(MANDATORY_RE.findall(text))
    counts = {lv: sum(1 for h in hits if h["level"] == lv) for lv in LEVEL_ORDER}
    return {
        "counts": counts,
        "hits": hits,
        "stars": stars,
        "dates": dates,
        "mandatory_density": mandatory,
        "line_count": len(lines),
    }


def render_scan(result, source_name):
    c = result["counts"]
    out = []
    out.append(f"# 招标文件体检报告：{source_name}")
    out.append("")
    out.append(f"- 有效行数：{result['line_count']}")
    out.append(f"- 命中：致命 {c['致命']} 条 / 严重 {c['严重']} 条 / 一般 {c['一般']} 条")
    out.append(f"- 星号（实质性）条款：{len(result['stars'])} 处")
    out.append(f"- 带日期的时间节点：{len(result['dates'])} 处")
    out.append(f"- 强制性措辞（必须/应当/不得/须）出现：{result['mandatory_density']} 次")
    out.append("")

    if result["mandatory_density"] > 60:
        out.append("> 强制性措辞密度偏高。这类文件通常对偏离零容忍，不要指望用承诺函模糊带过。")
        out.append("")

    total = sum(c.values())
    if total == 0:
        out.append("## 未命中提示")
        out.append("")
        out.append("规则库没有命中，不等于没有风险。请人工核对：资格性审查、符合性审查两章，以及所有带星号的参数。")
        return "\n".join(out)

    for level in ("致命", "严重", "一般"):
        rows = [h for h in result["hits"] if h["level"] == level]
        if not rows:
            continue
        out.append(f"## {level}（{len(rows)} 条）")
        out.append("")
        for i, h in enumerate(rows, 1):
            out.append(f"**{level}-{i}｜第 {h['line']} 行｜{h['category']}**")
            out.append("")
            out.append(f"- 原文：{h['quote']}")
            out.append(f"- 为什么：{h['why']}")
            out.append(f"- 做什么：{h['action']}")
            out.append("")

    if result["stars"]:
        out.append("## 星号条款汇总（逐条进响应表）")
        out.append("")
        out.append("| 行号 | 原文摘录 | 响应状态 | 方案页码 |")
        out.append("|---|---|---|---|")
        for s in result["stars"]:
            out.append(f"| {s['line']} | {s['quote']} | 待填 | 待填 |")
        out.append("")

    if result["dates"]:
        out.append("## 时间节点倒排")
        out.append("")
        out.append("| 行号 | 日期 | 原文摘录 | 内部截止（提前 24 小时） |")
        out.append("|---|---|---|---|")
        for d in result["dates"]:
            out.append(f"| {d['line']} | {d['date']} | {d['quote']} | 待排 |")
        out.append("")

    out.append("## 说明")
    out.append("")
    out.append("本报告为提示性检查，命中只代表这句话值得看一眼，后果以招标文件原文为准。")
    return "\n".join(out)


RESPONSE_TABLE = """# 条款响应表

> 用法：左边抄招标文件条款编号与要求，右边写响应结论与方案页码。
> 有负偏离的条目必须先算条数上限，超过上限的项直接放弃该项投标。

| 序号 | 条款编号 | 招标要求（摘要） | 响应结论 | 偏离说明 | 方案页码 | 证明材料 | 责任人 |
|---|---|---|---|---|---|---|---|
| 1 |  |  | 响应 / 正偏离 / 负偏离 / 不响应 |  |  |  |  |
| 2 |  |  |  |  |  |  |  |
"""

MATERIALS = """# 投标材料清单

> 用法：每一行都要有"齐了没有"和"谁负责"，交标前一天全部打钩。

## 一、资格性材料（缺一项即无效）

- [ ] 营业执照（经营范围覆盖招标内容）
- [ ] 法定代表人身份证明 / 授权委托书（用招标文件给定格式）
- [ ] 近三年财务审计报告
- [ ] 依法缴纳税收证明
- [ ] 社会保险缴纳证明（拟投人员与投标主体一致）
- [ ] 无重大违法记录声明
- [ ] 信用中国 / 失信被执行人查询截图（查询日期在有效期内）
- [ ] 行业资质证书（CMMI / ITSS / ISO / 等保测评等，按招标要求）
- [ ] 类似业绩合同 + 验收报告（注意时间范围与金额口径）
- [ ] 联合体协议（如以联合体投标）
- [ ] 投标保证金缴纳回单 / 保函

## 二、符合性材料

- [ ] 投标函（报价、有效期按文件要求填写）
- [ ] 开标一览表 / 报价明细表（大小写一致，合计与总价一致）
- [ ] 技术偏离表（逐条）
- [ ] 商务偏离表（逐条）
- [ ] 法定代表人签字、公章、骑缝章、逐页签字（按文件要求）
- [ ] 招标文件要求的其他声明与承诺函

## 三、技术文件

- [ ] 技术方案（章节对齐评分表）
- [ ] 架构说明（总体 / 部署 / 数据流）
- [ ] 等保、密评、信创响应材料
- [ ] 项目实施计划与团队配置
- [ ] 售后与运维方案
- [ ] 案例材料（合同关键页 + 验收报告，做脱敏）

## 四、形式检查

- [ ] 目录与页码一致
- [ ] 正本 / 副本份数点清
- [ ] 密封、标识、封套贴纸
- [ ] 电子版（U 盘两份，格式与命名符合要求）
- [ ] 演示环境离线可用 + 录屏备份
"""


def main():
    ap = argparse.ArgumentParser(description="招标文件条款体检")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("scan", help="扫描文件输出体检报告")
    p1.add_argument("--file", required=True)
    p1.add_argument("--out")
    p1.add_argument("--rules", default=str(DEFAULT_RULES))
    p1.add_argument("--min-level", default="一般", choices=["致命", "严重", "一般"])
    p1.add_argument("--json", action="store_true")
    p1.set_defaults(cmd_name="scan")

    p2 = sub.add_parser("response", help="生成条款响应表骨架")
    p2.add_argument("--out")
    p2.set_defaults(cmd_name="response")

    p3 = sub.add_parser("materials", help="生成材料清单骨架")
    p3.add_argument("--out")
    p3.set_defaults(cmd_name="materials")

    args = ap.parse_args()

    if args.cmd_name == "scan":
        try:
            text, enc = read_text(args.file)
            rules = load_rules(args.rules)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"[错误] {e}", file=sys.stderr)
            return 2
        if not text.strip():
            print("[错误] 文件内容为空，文本提取可能失败。请改用可复制的文本再扫。", file=sys.stderr)
            return 2
        result = scan(text, rules, args.min_level)
        result["encoding"] = enc
        result["file"] = str(Path(args.file).name)

        if args.json:
            payload = {k: v for k, v in result.items()}
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            report = render_scan(result, Path(args.file).name)
            if args.out:
                Path(args.out).write_text(report, encoding="utf-8")
                print(f"已写出：{args.out}")
                c = result["counts"]
                print(f"致命 {c['致命']} / 严重 {c['严重']} / 一般 {c['一般']}；星号 {len(result['stars'])} 处")
            else:
                print(report)
        return 0

    if args.cmd_name == "response":
        text = RESPONSE_TABLE
    else:
        text = MATERIALS

    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"已写出：{args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
