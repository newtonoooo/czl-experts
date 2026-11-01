#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q1 选品站：七猫主收盘匹配 + 五维判定。纯标准库，离线运行。"""

import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 主收盘：分类 -> (关键词, 榜单/结构参考, 是否平台特色类型)
CHART = {
    "nv": [
        ("现实婚姻 / 离婚逆袭",
         ["离婚", "婚约", "婚姻", "太太", "前夫", "前妻", "复婚", "悔婚"],
         "《封总，太太想跟你离婚很久了》《离婚后她惊艳了世界》", False),
        ("豪门关系 / 追妻火葬场",
         ["总裁", "豪门", "京少", "薄总", "盛总", "驰先生", "宠", "失控"],
         "《盛总，太太让您签的是去父留子协议》《第五年重逢，驰先生再度失控》", False),
        ("多胎 / 带娃家庭",
         ["一胎", "三宝", "四宝", "孕", "崽", "小保姆", "单传", "通房"],
         "《大佬十代单传，我为他一胎生四宝》《首辅无嗣？小通房却一胎三宝》", False),
        ("年代重生",
         ["年代", "重生", "七零", "八零", "知青", "随军", "下乡", "公社"],
         "平台特色类型，全勤有独立分档（10% 起跳）", True),
        ("古言权谋 / 宫斗",
         ["王妃", "太子", "首辅", "皇叔", "凤池", "宫", "侯门", "嫡女"],
         "《皇叔借点功德，王妃把符画猛了》《凤池生春》", False),
        ("玄学 / 轻悬疑",
         ["符", "玄学", "惊悚", "聊天群", "阴司", "算命"],
         "《误入惊悚聊天群，我成内部员工》", False),
    ],
    "nan": [
        ("神医 / 医术",
         ["神医", "医术", "中医", "针灸", "药", "国手"],
         "《盖世神医》", False),
        ("战神 / 兵王归来",
         ["战神", "兵王", "出狱", "归来", "真龙", "龙婿", "边关"],
         "《警报！真龙出狱！》《边关兵王》", False),
        ("系统流",
         ["系统", "面板", "签到", "抽奖", "任务", "属性"],
         "七猫年轻读者对强冲突高爽点偏好明显，系统流是主收之一", False),
        ("都市重生 / 复仇",
         ["重生", "复仇", "赘婿", "上门女婿", "逆袭", "打脸"],
         "《逍遥四公子》《步步登阶》", False),
        ("玄幻升级",
         ["吞天", "霸体", "武神", "葬神", "荒古", "神体", "鸿蒙", "诀"],
         "《吞天神体》《鸿蒙霸体诀》《荒古武神》《葬神棺》", False),
        ("历史 / 权谋",
         ["骑奴", "武圣", "大乾", "朝堂", "将军", "世子", "科举"],
         "《从骑奴到大乾武圣》", False),
        ("武侠仙侠",
         ["武侠", "仙侠", "剑", "宗门", "修真", "飞升"],
         "平台特色类型，全勤有独立分档（8% 起跳）", True),
    ],
}

DIMENSIONS = ["读者基数", "壳的新鲜度", "爽点可复现性", "长线可续航", "合规安全"]


def match_genre(channel, genre):
    hits = []
    text = (genre or "")
    for name, keys, ref, special in CHART[channel]:
        hit_keys = [k for k in keys if k in text]
        if hit_keys:
            hits.append((name, hit_keys, ref, special))
    return hits


def print_chart_lookup(channel, genre):
    print("=" * 62)
    print("Q1 选品站 · 主收盘匹配")
    print("=" * 62)
    print("频道：%s    题材描述：%s" % ("女频" if channel == "nv" else "男频", genre))
    print()
    hits = match_genre(channel, genre)
    if not hits:
        print("[结果] 未命中七猫主收盘关键词。")
        print("[提示] 可能是逆流题。逆流不是不能写，但要按“逆流代价”处理：")
        print("       1) 读者基数按 6 折估算；2) 前 3 章必须给出主收盘读者也认的爽点；")
        print("       3) Q6 档位预估要提前做，别等上架才发现没有对应分档。")
        print()
        print("可对照的七猫主收盘：")
        for name, keys, ref, special in CHART[channel]:
            flag = "（特色类型）" if special else ""
            print("  - %s%s" % (name, flag))
        return
    for name, keys, ref, special in hits:
        flag = "  [特色类型，有独立全勤分档]" if special else ""
        print("[命中] %s%s" % (name, flag))
        print("       命中词：%s" % "、".join(keys))
        print("       结构参考：%s" % ref)
    print()
    print("[提醒] 榜单参考只用来拆结构，不要抄情节、不要抄书名。")


def print_score(scores):
    if len(scores) != 5:
        print("[错误] --scores 需要 5 个 0-5 的整数，用逗号分隔。你给了 %d 个。" % len(scores))
        return 2
    total = sum(scores)
    print("=" * 62)
    print("Q1 选品站 · 五维判定")
    print("=" * 62)
    for name, s in zip(DIMENSIONS, scores):
        bar = "#" * s + "." * (5 - s)
        print("  %-8s %s  %d/5" % (name, bar, s))
    print("  合计：%d/25" % total)
    print()
    weak = [n for n, s in zip(DIMENSIONS, scores) if s <= 2]
    if total >= 18 and scores[2] >= 3 and scores[4] >= 2:
        verdict = "放行"
        note = "可以进 Q2 包装站。"
    elif total <= 13 or scores[4] <= 1:
        verdict = "止损"
        note = "别改稿了，先换核或换壳。"
    else:
        verdict = "返工"
        note = "优先换壳不换核，成本最低。"
    print("[判定] %s" % verdict)
    print("[依据] 合计 %d；弱项：%s" % (total, "、".join(weak) if weak else "无"))
    print("[动作] %s" % note)
    print()
    print("[下一站进入条件] 五维合计 >= 18 且“爽点可复现性”>= 3，才进 Q2。")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Q1 七猫选品站：主收盘匹配与五维判定")
    ap.add_argument("--channel", choices=["nv", "nan"], help="nv=女频，nan=男频")
    ap.add_argument("--genre", help="题材描述，如“年代重生”“战神归来”")
    ap.add_argument("--scores", help="五维分数，逗号分隔，例：4,3,5,2,4")
    args = ap.parse_args()

    did = False
    if args.genre and args.channel:
        print_chart_lookup(args.channel, args.genre)
        did = True
    if args.scores:
        if did:
            print()
        try:
            scores = [int(x.strip()) for x in args.scores.split(",")]
        except ValueError:
            print("[错误] --scores 只能包含整数。")
            return 2
        if any(s < 0 or s > 5 for s in scores):
            print("[错误] 每维分数范围 0-5。")
            return 2
        rc = print_score(scores)
        if rc != 0:
            return 2
        did = True
    if not did:
        ap.print_help()
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
