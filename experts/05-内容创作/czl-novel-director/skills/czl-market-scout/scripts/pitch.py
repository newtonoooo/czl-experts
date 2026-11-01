#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pitch.py — 卖点命题与书名的可算体检（纯标准库，离线）

补的是 czl-market-scout 里原来只能靠人judge的两件事：
    1) 卖点命题是不是"贴到任何同类书上还成立"（通用性风险）
    2) 书名有没有留白、有没有把结论写进标题、有没有歧义词

用法：
    python pitch.py proposition "别人都在写X，这本写的是Y，所以读者在等Z"
    python pitch.py title "同一块479的牌子／一个班42个985／一个班4个"
    python pitch.py title --file titles.txt          # 一行一个，批量打分
    python pitch.py title "书名" --ambiguity 学区,划片   # 指定本赛道的歧义词

判定口径（与 SKILL.md 对应，不是平台规则）：
    命题三段齐 + Y 含具体物/动作/数字 + 无通用词   → 才放行
    书名 长度合适 + 有具体锚 + 不前置结论 + 无歧义词 → 才放行

退出码：0 通过；1 不通过；2 输入错误

作者：虫志龙 <47190078@qq.com>
许可：MIT
"""

import argparse
import json
import os
import re
import sys

HANZI = re.compile(r"[\u4e00-\u9fff]")
NUM = re.compile(r"\d+|[一二三四五六七八九十百千万零两]{1,4}(?=[个班人年块万千百元岁天章])")

# 通用词：写进任何同类书都成立，等于没有信息量
GENERIC = [
    "更爽", "更燃", "更精彩", "更好看", "节奏更快", "节奏紧凑", "设定新颖",
    "脑洞大开", "爽点密集", "反转不断", "引人入胜", "跌宕起伏", "热血沸腾",
    "不一样", "全新", "颠覆", "创新", "独特",
]

# 抽象名词：出现在标题里，读者抓不住空位
ABSTRACT = [
    "根子", "问题", "关键", "本质", "真相", "逻辑", "底层", "内核",
    "意义", "价值", "逻辑自洽", "方法论",
]

# 结论前置：标题已经把答案说完，点开动机被提前用完
CONCLUSION = [
    "才是", "才能", "就该", "必须", "一定要", "为什么", "原因", "答案",
    "才是真正的", "根本在于", "取决于",
]

# 留白信号：读者得点进去才知道答案
BLANK = ["不是", "没人", "没有", "不靠", "不在", "不用", "都不", "连", "竟", "却",
         "偏偏", "反被", "结果", "另一", "倒", "居然"]

# 具体锚：职业/场景/物件/身份
ANCHOR_WORDS = [
    "老师", "学生", "家长", "孩子", "学校", "校长", "老板", "公司", "工厂",
    "医院", "医生", "警察", "律师", "外卖", "快递", "工地", "地铁", "公交",
    "房子", "房贷", "工资", "加班", "考试", "卷子", "分数", "班级", "宿舍",
    "结婚", "离婚", "相亲", "彩礼", "养老", "退休", "摆摊", "开店", "直播",
    "系统", "面板", "副本", "宗门", "灵气", "异能", "丧尸", "末世", "穿越",
    "重生", "签到", "抽奖", "任务", "积分", "排行榜",
    "拆迁", "物业", "中介", "租客", "房东", "业主", "小区", "村", "镇长",
    "裁员", "欠债", "讨债", "面试", "简历", "工位", "食堂", "夜班", "流水线",
]

# 身份后缀：中文里"某职业+主任/经理/师傅"本身就是强锚点，用规则补词表
ROLE_RE = re.compile(
    r"[\u4e00-\u9fff]{0,6}?(主任|经理|科长|处长|局长|队长|班长|组长|师傅|阿姨|"
    r"大哥|大姐|医生|护士|律师|警察|保安|护工|店长|摊主|房东|租客|老板|教练|"
    r"编辑|主播|作者|司机|厨师|柜员)")

GAP_WORDS = ["不是", "而不是", "却在", "偏偏", "反被", "却要", "结果", "所以"]


def hanzi_len(s):
    return len(HANZI.findall(s))


def count_generic(s):
    return [w for w in GENERIC if w in s]


def has_number(s):
    return bool(NUM.search(s))


def has_anchor(s):
    hits = [w for w in ANCHOR_WORDS if w in s]
    m = ROLE_RE.search(s)
    if m and m.group(1) not in hits:
        hits.append(m.group(1))
    return hits


def split_parts(title):
    """按全角/半角斜杠、换行、竖线拆主标与副标。"""
    for sep in ("／", "/", "|", "｜", "\n"):
        if sep in title:
            return [p.strip() for p in re.split(r"[／/|｜\n]", title) if p.strip()]
    return [title.strip()]


# ---------------- 命题 ----------------

def score_proposition(text):
    prob, ok, score = [], [], 100.0
    t = text.strip()

    # 三段式：X（别人写什么）/ Y（这本写什么）/ Z（读者等什么）
    has_gap = any(w in t for w in GAP_WORDS)
    has_wait = any(w in t for w in ("在等", "等着", "想看", "要看到", "期待"))
    if not has_gap:
        prob.append("缺「对比」：没写清别人写什么、这本写什么")
        score -= 25
    else:
        ok.append("有对比结构")
    if not has_wait:
        prob.append("缺「读者在等什么」：卖点没有落到可期待的东西上")
        score -= 20
    else:
        ok.append("有可期待对象")

    # Y 段的具体性：数字、具体物、具体动作
    concrete = bool(has_number(t)) or bool(has_anchor(t))
    if concrete:
        ok.append("含具体物或数字")
    else:
        prob.append("Y 段不具体：没有人、没有动作、没有数字")
        score -= 30

    # 通用词
    g = count_generic(t)
    if g:
        prob.append("含通用词：%s（贴到任何同类书都成立）" % "、".join(g))
        score -= 15 * len(g)

    score = max(0, min(100, score))
    return {
        "kind": "proposition",
        "text": t,
        "score": round(score),
        "pass": not prob,
        "ok": ok,
        "problems": prob,
        "rule": "三段齐 + Y 具体 + 无通用词，三条同时成立才放行",
    }


# ---------------- 书名 ----------------

def score_title(text, ambiguity=None):
    ambiguity = [a for a in (ambiguity or []) if a]
    parts = split_parts(text)
    main = parts[0] if parts else text
    sub = parts[1] if len(parts) > 1 else ""

    prob, ok, score = [], [], 100.0

    # 1 长度
    n = hanzi_len(main)
    if n < 4:
        prob.append("主标只有 %d 字，读者来不及形成画面" % n)
        score -= 20
    elif n > 16:
        prob.append("主标 %d 字偏长，列表页会截断" % n)
        score -= 15
    else:
        ok.append("主标 %d 字，长度合适" % n)

    # 2 具体锚
    anchors = has_anchor(main)
    if anchors or has_number(main):
        ok.append("有具体锚：%s" % ("、".join(anchors[:3]) if anchors else "数字"))
    else:
        prob.append("没有读者认识的具体锚（职业/场景/物件/数字）")
        score -= 25

    # 3 结论前置
    conc = [w for w in CONCLUSION if w in main]
    if conc:
        prob.append("结论写进标题：%s（点开动机被提前用完）" % "、".join(conc))
        score -= 20
    else:
        ok.append("没有结论前置")

    # 4 留白：三种来源——否定/转折词、两个数字的落差、并列对立项
    blank = [w for w in BLANK if w in main]
    nums = set(re.findall(r"\d+|[一二三四五六七八九十百千万两]{1,2}(?=[个班人年块万千百元岁天章本户条])", main))
    if len(nums) >= 2:
        ok.append("有两组数字构成落差：%s" % "、".join(sorted(nums)[:4]))
        blank = blank or ["数字落差"]
    if blank:
        ok.append("有留白信号：%s" % "、".join(blank[:3]) if blank != ["数字落差"] else "有留白信号：数字落差")
    else:
        prob.append("没有留白：读者看不出「那我得知道什么」")
        score -= 15

    # 5 抽象词
    abst = [w for w in ABSTRACT if w in main]
    if abst:
        prob.append("含抽象名词：%s（读者抓不住空位）" % "、".join(abst))
        score -= 15 * len(abst)

    # 6 歧义
    amb = [w for w in ambiguity if w in main]
    if amb:
        prob.append("含本赛道歧义词：%s（正文要澄清的词不要放标题）" % "、".join(amb))
        score -= 20

    # 7 副标
    if sub:
        gn = hanzi_len(sub)
        if gn > 20:
            prob.append("副标 %d 字偏长" % gn)
            score -= 8
        elif any(w in sub for w in ("好使", "有效", "有用", "方法", "办法")):
            prob.append("副标是泛化承诺（“%s”），给指向不给承诺" % sub)
            score -= 10
        else:
            ok.append("副标 %d 字，有指向" % gn)

    # 8 特殊符号
    if re.search(r"[!！?？~～]", main):
        prob.append("主标含感叹/问号，列表页显得吵")
        score -= 8

    score = max(0, min(100, score))
    return {
        "kind": "title",
        "text": text.strip(),
        "main": main,
        "sub": sub,
        "score": round(score),
        "pass": not [p for p in prob if not p.startswith("副标")],
        "ok": ok,
        "problems": prob,
        "rule": "长度 4—16 + 有具体锚 + 无结论前置 + 有留白 + 无歧义词",
    }


def render(r):
    if r["kind"] == "proposition":
        L = ["【卖点命题】%d 分 ｜ %s" % (r["score"], "通过" if r["pass"] else "不通过")]
        L.append("原文：%s" % r["text"])
    else:
        L = ["【书名】%d 分 ｜ %s" % (r["score"], "通过" if r["pass"] else "不通过")]
        L.append("主标：%s%s" % (r["main"], ("　副标：" + r["sub"]) if r["sub"] else ""))
    for x in r["ok"]:
        L.append("  · %s" % x)
    for x in r["problems"]:
        L.append("  ✗ %s" % x)
    L.append("  判据：%s" % r["rule"])
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="卖点命题与书名体检")
    ap.add_argument("kind", choices=["proposition", "title"])
    ap.add_argument("text", nargs="?", default=None)
    ap.add_argument("--file", default=None, help="批量：一行一个")
    ap.add_argument("--ambiguity", default="", help="本赛道歧义词，逗号分隔")
    ap.add_argument("--json", dest="json_out", default=None)
    a = ap.parse_args()

    amb = [x.strip() for x in a.ambiguity.split(",") if x.strip()]
    fn = score_proposition if a.kind == "proposition" else (lambda t: score_title(t, amb))

    items = []
    if a.file:
        if not os.path.exists(a.file):
            print("找不到文件：%s" % a.file)
            return 2
        with open(a.file, "r", encoding="utf-8") as f:
            items = [ln.strip() for ln in f if ln.strip()]
    elif a.text:
        items = [a.text]
    else:
        print("需要给文本，或用 --file 批量")
        return 2

    results = []
    bad = 0
    for it in items:
        r = fn(it)
        results.append(r)
        print(render(r))
        print()
        if not r["pass"]:
            bad += 1

    if len(results) > 1:
        print("共 %d 条，通过 %d，不通过 %d" % (len(results), len(results) - bad, bad))
        results.sort(key=lambda x: -x["score"])
        print("最优：%d 分 —— %s" % (results[0]["score"], results[0].get("main") or results[0]["text"]))

    if a.json_out:
        d = os.path.dirname(os.path.abspath(a.json_out))
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        with open(a.json_out, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print("已写入：%s" % a.json_out)
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
