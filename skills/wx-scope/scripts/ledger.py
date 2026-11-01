#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ledger.py — 小程序交付条目台账（纯标准库，无第三方依赖）

台账是人看的 Markdown，条目是机器读的 JSON。两边一一对应：
  docs/交付台账.md  ← 人读，五段固定结构
  docs/acceptance.json ← 机器读，本脚本维护

设计原则：状态不许自欺。条目要进 accepted，必须同时有"验证动作"和"对应文件"，
否则脚本拒绝写入并报错 —— 拦住"基本完成"这种说法。

子命令:
  init   <file> --project <名>              建台账
  add    <file> --title <需求> --verify <怎么验> [--files a,b] [--gate W2]
  set    <file> --id A-01 --status todo|doing|done|accepted [--note <备注>]
  list   <file> [--status todo]
  next   <file>                              打印下一条该干的
  report <file>                              统计 + 完整性校验（有问题返回码 1）

状态四态：todo → doing → done(已写完待验) → accepted(已验)
退出码：0 正常；1 校验不过；2 参数或文件错误
"""
import argparse
import json
import os
import sys
from datetime import date

STATUSES = ["todo", "doing", "done", "accepted"]
STATUS_LABEL = {"todo": "未开始", "doing": "开发中", "done": "已完成(待验)", "accepted": "已验收"}


def die(msg, code=2):
    sys.stderr.write("错误: %s\n" % msg)
    sys.exit(code)


def load(path):
    if not os.path.exists(path):
        die("台账文件不存在: %s（先跑 init）" % path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        die("台账 JSON 解析失败: %s" % e)
    if not isinstance(data.get("items"), list):
        die("台账结构不对：缺少 items 数组")
    return data


def save(path, data):
    data["updated"] = date.today().isoformat()
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def next_id(items):
    nums = []
    for it in items:
        s = str(it.get("id", ""))
        if s.startswith("A-") and s[2:].isdigit():
            nums.append(int(s[2:]))
    return "A-%02d" % (max(nums) + 1 if nums else 1)


def cmd_init(args):
    if os.path.exists(args.file):
        die("文件已存在: %s（不覆盖，避免丢历史）" % args.file)
    data = {"schema": 1, "project": args.project, "created": date.today().isoformat(),
            "updated": date.today().isoformat(), "items": []}
    save(args.file, data)
    print("已建台账: %s" % args.file)
    print("项目: %s" % args.project)
    print("下一步: ledger.py add %s --title \"...\" --verify \"...\"" % args.file)


def cmd_add(args):
    data = load(args.file)
    if not args.title.strip():
        die("--title 不能为空")
    if not args.verify.strip():
        die("--verify 不能为空。写不出\"怎么验\"的条目，说明需求还没想清楚，退回去重写。")
    item = {
        "id": next_id(data["items"]),
        "title": args.title.strip(),
        "verify": args.verify.strip(),
        "files": [x.strip() for x in (args.files or "").split(",") if x.strip()],
        "status": "todo",
        "gate": args.gate or "",
        "note": "",
    }
    data["items"].append(item)
    save(args.file, data)
    print("已加 %s  %s" % (item["id"], item["title"]))
    print("  验收动作: %s" % item["verify"])
    if item["files"]:
        print("  对应文件: %s" % ", ".join(item["files"]))
    else:
        print("  提醒: 还没绑文件。进 done / accepted 前必须绑。")


def cmd_set(args):
    data = load(args.file)
    if args.status not in STATUSES:
        die("--status 只能是 %s" % "/".join(STATUSES))
    target = None
    for it in data["items"]:
        if it["id"] == args.id:
            target = it
            break
    if target is None:
        die("找不到条目 %s" % args.id)

    # 闸门：不许用状态糊弄
    if args.status in ("done", "accepted"):
        files = target.get("files") or []
        if not files:
            die("%s 要进\"%s\"，必须先绑对应文件（--files）。没绑文件的状态没有意义。"
                % (args.id, STATUS_LABEL[args.status]))
        if not target.get("verify"):
            die("%s 缺验收动作，不能进\"%s\"" % (args.id, STATUS_LABEL[args.status]))

    old = target["status"]
    target["status"] = args.status
    if args.note:
        target["note"] = args.note
    save(args.file, data)
    print("%s: %s -> %s  (%s)" % (args.id, STATUS_LABEL[old], STATUS_LABEL[args.status], target["title"]))


def cmd_list(args):
    data = load(args.file)
    items = data["items"]
    if args.status:
        items = [i for i in items if i["status"] == args.status]
    if not items:
        print("（没有符合条件的条目）")
        return 0
    print("%-6s %-10s %-32s %s" % ("ID", "状态", "需求", "文件"))
    for it in items:
        print("%-6s %-10s %-32s %s" % (it["id"], STATUS_LABEL.get(it["status"], it["status"]),
                                       it["title"][:30], ",".join(it.get("files") or []) or "-"))
    return 0


def cmd_next(args):
    data = load(args.file)
    doing = [i for i in data["items"] if i["status"] == "doing"]
    todo = [i for i in data["items"] if i["status"] == "todo"]
    pick = doing[0] if doing else (todo[0] if todo else None)
    if pick is None:
        done_n = len([i for i in data["items"] if i["status"] == "done"])
        if done_n:
            print("没有待开发条目，但有 %d 条待验收。逐条验完改成 accepted，别跳。" % done_n)
            for i in data["items"]:
                if i["status"] == "done":
                    print("  待验 %s  %s\n       怎么验: %s" % (i["id"], i["title"], i["verify"]))
        else:
            print("条目已全部验收。下一步跑体检：wx_doctor.py scan <项目>")
        return 0
    print("%s  %s" % (pick["id"], pick["title"]))
    print("  怎么验: %s" % pick["verify"])
    print("  文件  : %s" % (", ".join(pick.get("files") or []) or "（还没绑）"))
    print("  闸门  : %s" % (pick.get("gate") or "-"))
    return 0


def cmd_report(args):
    data = load(args.file)
    items = data["items"]
    counts = {s: len([i for i in items if i["status"] == s]) for s in STATUSES}
    total = len(items)
    print("项目: %s   条目: %d   更新: %s" % (data.get("project", "-"), total, data.get("updated", "-")))
    print("")
    for s in STATUSES:
        bar = "#" * counts[s]
        print("  %-10s %3d  %s" % (STATUS_LABEL[s], counts[s], bar))
    pct = (counts["accepted"] / float(total) * 100) if total else 0.0
    print("  验收完成度: %.0f%%" % pct)
    print("")

    problems = []
    for it in items:
        if it["status"] in ("done", "accepted") and not (it.get("files") or []):
            problems.append("%s 状态是%s，但没绑文件" % (it["id"], STATUS_LABEL[it["status"]]))
        if it["status"] == "accepted" and not it.get("verify"):
            problems.append("%s 已验收但没有验收动作记录" % it["id"])
        if not it.get("verify"):
            problems.append("%s 缺验收动作（这条需求还不算可验收）" % it["id"])

    if problems:
        print("完整性校验: 不通过（%d 项）" % len(problems))
        for p in problems:
            print("  ! %s" % p)
        return 1
    print("完整性校验: 通过")
    if total and counts["accepted"] == total:
        print("全部条目已验收，可以进体检闸门。")
    return 0


def build_parser():
    p = argparse.ArgumentParser(description="小程序交付条目台账")
    sub = p.add_subparsers(dest="cmd")

    p1 = sub.add_parser("init", help="建台账")
    p1.add_argument("file")
    p1.add_argument("--project", required=True)
    p1.set_defaults(func=cmd_init)

    p2 = sub.add_parser("add", help="加条目")
    p2.add_argument("file")
    p2.add_argument("--title", required=True)
    p2.add_argument("--verify", required=True)
    p2.add_argument("--files", default="")
    p2.add_argument("--gate", default="")
    p2.set_defaults(func=cmd_add)

    p3 = sub.add_parser("set", help="改状态")
    p3.add_argument("file")
    p3.add_argument("--id", required=True)
    p3.add_argument("--status", required=True)
    p3.add_argument("--note", default="")
    p3.set_defaults(func=cmd_set)

    p4 = sub.add_parser("list", help="列条目")
    p4.add_argument("file")
    p4.add_argument("--status", default="")
    p4.set_defaults(func=cmd_list)

    p5 = sub.add_parser("next", help="下一条该干什么")
    p5.add_argument("file")
    p5.set_defaults(func=cmd_next)

    p6 = sub.add_parser("report", help="统计与校验")
    p6.add_argument("file")
    p6.set_defaults(func=cmd_report)
    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not getattr(args, "cmd", None):
        parser.print_help()
        return 2
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
