#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""任务简报完整性校验器（czl-uae-pa-toolkit）

按主 Agent 的 W0 工作流，校验 12 项简报字段是否齐备，给出缺口分级与建议路由。

用法:
    python brief_check.py --file brief.json
    python brief_check.py --demo

brief.json 结构（缺项可省略或留空）:
{
  "entity_type": "中资独资",
  "industry": "储能电芯",
  "emirate": "未定",
  "action": "设立区域总部",
  "timeline": "2027 Q1 前",
  "existing_license": "无",
  "domains": ["商业登记", "劳动"],
  "sensitive": "无",
  "deliverable": "决策备忘",
  "language": "中文+英文",
  "confidentiality": "可引用客户名称",
  "decision_maker": "集团投委会"
}

退出码: 0 可进入下一跳; 1 存在必问缺口; 2 参数/文件错误。
"""

import argparse
import json
import os
import sys

# (字段, 中文名, 等级: must=必问 / infer=可推 / optional=可略)
FIELDS = [
    ("entity_type", "主体类型", "must"),
    ("industry", "行业与产品", "must"),
    ("emirate", "目标酋长国", "infer"),
    ("action", "业务动作", "must"),
    ("timeline", "时间窗", "infer"),
    ("existing_license", "已有资质", "infer"),
    ("domains", "涉及监管域", "infer"),
    ("sensitive", "敏感面", "must"),
    ("deliverable", "交付形态", "infer"),
    ("language", "语言", "infer"),
    ("confidentiality", "保密级别", "optional"),
    ("decision_maker", "决策人", "infer"),
]

# 业务动作 -> 建议工作流
ROUTING = {
    "设立": ["W0", "W1", "W2", "W3", "W5"],
    "选址": ["W0", "W1", "W2", "W5"],
    "投标": ["W0", "W1", "W3", "W4", "W5"],
    "并购": ["W0", "W1", "W3", "W5"],
    "宣传": ["W0", "W4"],
    "内容": ["W0", "W4"],
    "检查": ["W0", "W1", "W4", "W5"],
    "舆情": ["W6"],
    "危机": ["W6"],
    "政策": ["W0", "W1", "W5"],
}

DEMO = {
    "entity_type": "中资独资",
    "industry": "储能电芯",
    "emirate": "未定",
    "action": "设立区域总部",
    "timeline": "2027 Q1 前",
    "sensitive": "无",
    "deliverable": "决策备忘",
}


def is_filled(value):
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() not in ("", "未定", "待定", "unknown", "TBD")
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def route_for(action):
    if not action:
        return ["W0"]
    for key, flow in ROUTING.items():
        if key in action:
            return flow
    return ["W0", "W1", "W5"]


def check(brief):
    filled, missing = [], []
    for key, label, tier in FIELDS:
        if is_filled(brief.get(key)):
            filled.append((key, label))
        else:
            missing.append((key, label, tier))

    must_missing = [m for m in missing if m[2] == "must"]
    infer_missing = [m for m in missing if m[2] == "infer"]

    if not must_missing:
        gate = "PASS"
    elif len(must_missing) <= 2:
        gate = "ASK_ONCE"
    else:
        gate = "ASSUME_AND_FLAG"

    return {
        "total_fields": len(FIELDS),
        "filled_count": len(filled),
        "completeness": round(len(filled) / len(FIELDS) * 100, 1),
        "filled": [{"key": k, "label": v} for k, v in filled],
        "missing_must": [{"key": k, "label": v} for k, v, _ in must_missing],
        "missing_infer": [{"key": k, "label": v} for k, v, _ in infer_missing],
        "gate": gate,
        "routing": route_for(brief.get("action")),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="阿联酋公共事务任务简报完整性校验")
    ap.add_argument("--file", help="brief.json 路径")
    ap.add_argument("--demo", action="store_true", help="使用内置示例运行")
    ap.add_argument("--format", default="text", choices=["text", "json"])
    args = ap.parse_args(argv)

    if args.demo:
        brief = DEMO
    elif args.file:
        if not os.path.exists(args.file):
            print("文件不存在: %s" % args.file, file=sys.stderr)
            return 2
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                brief = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print("读取失败: %s" % e, file=sys.stderr)
            return 2
    else:
        print("请提供 --file 或 --demo", file=sys.stderr)
        return 2

    r = check(brief)

    if args.format == "json":
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print("=" * 46)
        print("任务简报完整性: %s%% (%d/%d)" % (r["completeness"], r["filled_count"], r["total_fields"]))
        print("闸门判定: %s" % r["gate"])
        if r["missing_must"]:
            print("必问缺口: " + "、".join(m["label"] for m in r["missing_must"]))
        if r["missing_infer"]:
            print("可推缺口: " + "、".join(m["label"] for m in r["missing_infer"]))
        print("建议路由: " + " → ".join(r["routing"]))
        print("=" * 46)

    return 0 if r["gate"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
