#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""择日择时 almanac.py

职责：日级与时辰级的通用择日参考。
  - 建除十二神、黄道黑道十二神、二十八宿值日
  - 日冲、煞方、旬空、纳音、彭祖百忌
  - 黄道吉时（十二时辰吉凶）
  - 按用途给出日候选排序

边界声明：本模块是**简化择日参考**，只取建除、值神、宿、冲煞四层，
不等同于完整黄历（完整黄历还需数十项神煞、四柱合参、主事人生辰）。
产品输出时会同时给出这句声明，不做"黄历宜忌"的冒充。

作者：虫志龙 <47190078@qq.com>
"""

from datetime import date, timedelta

import calendar_core as cc
import astro

JIANCHU = ["建", "除", "满", "平", "定", "执", "破", "危", "成", "收", "开", "闭"]

HUANGDAO12 = ["青龙", "明堂", "天刑", "朱雀", "金匮", "天德", "白虎", "玉堂", "天牢", "玄武", "司命", "勾陈"]
HUANGDAO_GUARD = {"青龙", "明堂", "金匮", "天德", "玉堂", "司命"}

# 黄道十二神起例：地支 -> 青龙所临之支（日级按月支、时级按日支，同一张表）
QINGLONG_START = {"子": "申", "午": "申", "丑": "戌", "未": "戌", "寅": "子", "申": "子",
                  "卯": "寅", "酉": "寅", "辰": "辰", "戌": "辰", "巳": "午", "亥": "午"}

XIU = ["角", "亢", "氐", "房", "心", "尾", "箕", "斗", "牛", "女", "虚", "危",
       "室", "壁", "奎", "娄", "胃", "昴", "毕", "觜", "参", "井", "鬼", "柳",
       "星", "张", "翼", "轸"]
XIU_ANIMAL = ["蛟", "龙", "貉", "兔", "狐", "虎", "豹", "獬", "牛", "蝠", "鼠", "燕",
              "猪", "貐", "狼", "狗", "雉", "鸡", "乌", "猴", "猿", "犴", "羊", "獐",
              "马", "鹿", "蛇", "蚓"]
XIU_LUCK = {"角": "吉", "亢": "凶", "氐": "凶", "房": "吉", "心": "凶", "尾": "吉", "箕": "吉",
            "斗": "吉", "牛": "凶", "女": "凶", "虚": "凶", "危": "凶", "室": "吉", "壁": "吉",
            "奎": "凶", "娄": "吉", "胃": "吉", "昴": "凶", "毕": "吉", "觜": "凶", "参": "吉",
            "井": "吉", "鬼": "凶", "柳": "凶", "星": "凶", "张": "吉", "翼": "凶", "轸": "吉"}
# 二十八宿值日锚点：2026-10-26 为危宿（与公开黄历一致），由此外推
_XIU_ANCHOR_ZHI = 11

SHA_FANG = {"申子辰": "南", "寅午戌": "北", "亥卯未": "西", "巳酉丑": "东"}
CAISHEN = {"甲": "东北", "乙": "东北", "丙": "西南", "丁": "西南", "戊": "正北",
           "己": "正北", "庚": "正东", "辛": "正东", "壬": "正南", "癸": "正南"}
XISHEN = {"甲": "东北", "己": "东北", "乙": "西北", "庚": "西北", "丙": "西南", "辛": "西南",
          "丁": "正南", "壬": "正南", "戊": "东南", "癸": "东南"}

PENGZU_GAN = {
    "甲": "甲不开仓财物耗散", "乙": "乙不栽植千株不长", "丙": "丙不修灶必见灾殃",
    "丁": "丁不剃头头必生疮", "戊": "戊不受田田主不祥", "己": "己不破券二比并亡",
    "庚": "庚不经络织机虚张", "辛": "辛不合酱主人不尝", "壬": "壬不汲水更难提防",
    "癸": "癸不词讼理弱敌强",
}
PENGZU_ZHI = {
    "子": "子不问卜自惹祸殃", "丑": "丑不冠带主不还乡", "寅": "寅不祭祀神鬼不尝",
    "卯": "卯不穿井水泉不香", "辰": "辰不哭泣必主重丧", "巳": "巳不远行财物伏藏",
    "午": "午不苫盖屋主更张", "未": "未不服药毒气入肠", "申": "申不安床鬼祟入房",
    "酉": "酉不会客醉坐颠狂", "戌": "戌不吃犬作怪上床", "亥": "亥不嫁娶不利新郎",
}

# 建除十二神传统宜/忌（简化版，各家略有出入）
JIANCHU_YIJI = {
    "建": (["出行", "赴任", "会友", "上书", "见工"], ["动土", "开仓", "嫁娶", "安葬"]),
    "除": (["除旧", "扫舍", "疗病", "拆卸"], ["求财", "嫁娶", "远行"]),
    "满": (["祈福", "结亲", "开市", "立契"], ["服药", "栽种", "安葬"]),
    "平": (["修墙", "平路", "涂泥"], ["开渠", "栽种", "乘船"]),
    "定": (["宴会", "协议", "交易", "纳财"], ["诉讼", "远行", "搬迁"]),
    "执": (["捕捉", "纳畜", "造屋", "嫁娶"], ["开市", "求财", "远行"]),
    "破": (["破屋", "坏垣", "求医"], ["嫁娶", "开市", "动土", "安葬"]),
    "危": (["祭祀", "祈福", "安床"], ["登高", "行船", "远行", "嫁娶"]),
    "成": (["开市", "嫁娶", "入宅", "动土", "入学"], ["诉讼"]),
    "收": (["纳财", "收账", "捕捉", "进人口"], ["开市", "安葬", "远行"]),
    "开": (["开市", "交易", "嫁娶", "入学", "出行"], ["安葬", "动土"]),
    "闭": (["筑堤", "修屋", "安葬"], ["开市", "出行", "求医", "赴任"]),
}

# 用途 -> 优先建除、次选建除、避开建除
PURPOSE_MAP = {
    "嫁娶": (["成", "满", "定"], ["开", "除"], ["破", "危", "闭", "平"]),
    "开市": (["成", "开", "满"], ["定"], ["破", "危", "闭"]),
    "搬家": (["成", "开"], ["满", "定"], ["破", "危", "闭"]),
    "签约": (["成", "定", "满"], ["开"], ["破", "危"]),
    "出行": (["建", "开", "成"], ["定"], ["破", "危", "闭"]),
    "动土": (["成", "开"], ["建"], ["破", "危", "闭", "平"]),
    "入学": (["成", "开"], ["定"], ["破", "危"]),
    "求医": (["除", "破"], ["成"], ["满", "闭"]),
    "安葬": (["闭", "成"], ["除"], ["破", "满", "开"]),
    "通用": ([], [], []),
}


def huangdao_god(key_zhi, target_zhi):
    """黄道黑道十二神。

    日级：key_zhi 传月支，target_zhi 传日支；
    时级：key_zhi 传日支，target_zhi 传时支。
    """
    start = cc.ZHI.index(QINGLONG_START[key_zhi])
    return HUANGDAO12[(cc.ZHI.index(target_zhi) - start) % 12]


def jianchu_of(month_zhi, day_zhi):
    idx = (cc.ZHI.index(day_zhi) - cc.ZHI.index(month_zhi)) % 12
    return JIANCHU[idx]


def xiu_of(d):
    """二十八宿值日：以 2026-10-26 为危宿（与公开黄历对齐）外推。"""
    jdn = cc.jdn_local(d)
    return XIU[(jdn + 11) % 28]


def day_info(d):
    """单日详情。"""
    gz_index = cc.day_ganzhi_index(d)
    gz = cc.ganzhi(gz_index)
    g, z = gz[0], gz[1]
    mzhi, jie, jie_t = cc.month_zhi_of(
        __import__("datetime").datetime(d.year, d.month, d.day, 12, tzinfo=astro.CST))
    jc = jianchu_of(cc.ZHI[mzhi], z)
    yi, ji = JIANCHU_YIJI[jc]
    chong_gz = cc.ganzhi(gz_index - 6)
    sha = SHA_FANG.get(next((k for k in SHA_FANG if z in k), ""), "—")
    god = huangdao_god(cc.ZHI[mzhi], z)

    hours = []
    start = cc.ZHI.index(QINGLONG_START[z])
    for k in range(12):
        hz = (start + k) % 12
        hgod = HUANGDAO12[k]
        hours.append({
            "zhi": cc.ZHI[hz],
            "range": cc.shichen_range(hz),
            "god": hgod,
            "luck": "吉" if hgod in HUANGDAO_GUARD else "凶",
        })
    hours.sort(key=lambda x: cc.ZHI.index(x["zhi"]))

    x = xiu_of(d)
    xiu_full = "%s%s%s" % ("北方" if XIU.index(x) in (7, 8, 9, 10, 11, 12, 13) else
                           "东方" if XIU.index(x) in (0, 1, 2, 3, 4, 5, 6) else
                           "西方" if XIU.index(x) in (14, 15, 16, 17, 18, 19, 20) else
                           "南方", XIU_ANIMAL[XIU.index(x)], x)

    return {
        "date": str(d),
        "weekday": "一二三四五六日"[d.weekday()],
        "lunar": cc.lunar_text(d),
        "ganzhi": gz,
        "nayin": cc.nayin(gz_index),
        "month_jie": jie,
        "jianchu": jc,
        "day_god": god,
        "day_god_luck": "黄道" if god in HUANGDAO_GUARD else "黑道",
        "xiu": xiu_full,
        "xiu_luck": XIU_LUCK[x],
        "chong": chong_gz + "（%s）" % cc.SHENGXIAO[cc.ZHI.index(chong_gz[1])],
        "sha_direction": sha,
        "xunkong": cc.xunkong(gz_index),
        "caishen": CAISHEN[g],
        "xishen": XISHEN[g],
        "pengzu": [PENGZU_GAN[g], PENGZU_ZHI[z]],
        "yi": yi,
        "ji": ji,
        "good_hours": [h for h in hours if h["luck"] == "吉"],
        "hours": hours,
        "note": "本日宜忌为建除十二神层面的简化参考，非完整黄历。",
    }


def pick_days(start_date, end_date, purpose="通用", avoid_zhi=None, limit=None):
    """按用途给日期打分排序。avoid_zhi 可传冲忌生肖对应的地支。"""
    first, second, bad = PURPOSE_MAP.get(purpose, PURPOSE_MAP["通用"])
    rows = []
    d = start_date
    while d <= end_date:
        info = day_info(d)
        score = 0
        reasons = []
        if info["jianchu"] in first:
            score += 3
            reasons.append("建除「%s」合%s之用" % (info["jianchu"], purpose))
        elif info["jianchu"] in second:
            score += 1
            reasons.append("建除「%s」可作次选" % info["jianchu"])
        if info["jianchu"] in bad:
            score -= 3
            reasons.append("建除「%s」不宜%s" % (info["jianchu"], purpose))
        if info["day_god_luck"] == "黄道":
            score += 2
            reasons.append("值神%s（黄道）" % info["day_god"])
        else:
            score -= 1
            reasons.append("值神%s（黑道）" % info["day_god"])
        if info["xiu_luck"] == "吉":
            score += 1
            reasons.append("宿%s吉" % info["xiu"])
        else:
            score -= 1
            reasons.append("宿%s凶" % info["xiu"])
        if avoid_zhi and info["chong"][1] == avoid_zhi:
            score -= 4
            reasons.append("日冲本命生肖，回避")
        rows.append({"date": info["date"], "ganzhi": info["ganzhi"], "lunar": info["lunar"],
                     "jianchu": info["jianchu"], "day_god": info["day_god"],
                     "xiu": info["xiu"], "score": score, "reasons": reasons,
                     "good_hours": [h["zhi"] + "时" for h in info["good_hours"]]})
        d += timedelta(days=1)
    rows.sort(key=lambda r: (-r["score"], r["date"]))
    if limit:
        rows = rows[:limit]
    return {
        "purpose": purpose,
        "range": [str(start_date), str(end_date)],
        "candidates": rows,
        "note": "评分为四层加权（建除 3 分、值神 2 分、宿 1 分、日冲 -4 分）的相对排序，"
                "只用于缩小候选范围，最终以主事人生辰合参与现实条件为准。",
    }
