#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""子平八字 bazi.py

职责：在四柱之上补齐十神、藏干、五行力量、纳音、空亡、神煞、大运、流年。
不做吉凶断语——断语属于解读层，本文件只给结构化事实与可复核的量化口径。

量化口径说明（产品自定，非古典定论，输出中会一并披露）：
  - 五行力量：天干 1.0；地支藏干按本气 1.0 / 中气 0.4 / 余气 0.2 折算；月支整体 ×1.5
  - 旺衰：以「得令 / 得地 / 得势」三项计分，仅作强弱粗判

作者：虫志龙 <47190078@qq.com>
"""

from datetime import datetime, timedelta

import calendar_core as cc
import astro

# 地支藏干：本气、中气、余气
CANG_GAN = {
    "子": ["癸"], "丑": ["己", "癸", "辛"], "寅": ["甲", "丙", "戊"], "卯": ["乙"],
    "辰": ["戊", "乙", "癸"], "巳": ["丙", "戊", "庚"], "午": ["丁", "己"],
    "未": ["己", "丁", "乙"], "申": ["庚", "壬", "戊"], "酉": ["辛"],
    "戌": ["戊", "辛", "丁"], "亥": ["壬", "甲"],
}
CANG_WEIGHT = [1.0, 0.4, 0.2]

ELEMENTS = ["木", "火", "土", "金", "水"]

# 十二长生
CHANGSHENG_ORDER = ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"]
CHANGSHENG_START = {"甲": "亥", "乙": "午", "丙": "寅", "丁": "酉", "戊": "寅",
                    "己": "酉", "庚": "巳", "辛": "子", "壬": "申", "癸": "卯"}

TIANYI = {"甲": "丑未", "戊": "丑未", "庚": "丑未", "乙": "子申", "己": "子申",
          "丙": "亥酉", "丁": "亥酉", "壬": "卯巳", "癸": "卯巳", "辛": "午寅"}
WENCHANG = {"甲": "巳", "乙": "午", "丙": "申", "戊": "申", "丁": "酉", "己": "酉",
            "庚": "亥", "辛": "子", "壬": "寅", "癸": "卯"}
LUSHEN = {"甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳",
          "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子"}
YANGREN = {"甲": "卯", "丙": "午", "戊": "午", "庚": "酉", "壬": "子"}  # 仅列阳干，阴干羊刃分歧大，不作判断

SANHE = [("申", "子", "辰"), ("寅", "午", "戌"), ("巳", "酉", "丑"), ("亥", "卯", "未")]
LIUHE = [("子", "丑"), ("寅", "亥"), ("卯", "戌"), ("辰", "酉"), ("巳", "申"), ("午", "未")]
LIUCHONG = [("子", "午"), ("丑", "未"), ("寅", "申"), ("卯", "酉"), ("辰", "戌"), ("巳", "亥")]
LIUHAI = [("子", "未"), ("丑", "午"), ("寅", "巳"), ("卯", "辰"), ("申", "亥"), ("酉", "戌")]
SANXING = [("寅", "巳", "申"), ("丑", "戌", "未"), ("子", "卯")]


def element_of_gan(gan):
    return ELEMENTS[cc.GAN.index(gan) // 2]


def element_of_zhi(zhi):
    return cc.ZHI_WUXING[cc.ZHI.index(zhi)]


def shishen(day_gan, other_gan):
    """以日干为我，判十神。"""
    me = cc.GAN.index(day_gan)
    ot = cc.GAN.index(other_gan)
    same_polarity = (me % 2) == (ot % 2)
    wo = me // 2
    it = ot // 2
    if it == wo:
        return "比肩" if same_polarity else "劫财"
    if it == (wo + 1) % 5:
        return "食神" if same_polarity else "伤官"
    if it == (wo - 1) % 5:
        return "偏印" if same_polarity else "正印"
    if it == (wo + 2) % 5:
        return "偏财" if same_polarity else "正财"
    return "七杀" if same_polarity else "正官"


def changsheng(gan, zhi):
    start = cc.ZHI.index(CHANGSHENG_START[gan])
    step = 1 if cc.GAN.index(gan) % 2 == 0 else -1
    offset = (cc.ZHI.index(zhi) - start) * step % 12
    return CHANGSHENG_ORDER[offset]


xunkong = cc.xunkong


def _zhi_relations(zhis):
    found = []
    pool = list(zhis)
    for group in SANHE:
        if all(z in pool for z in group):
            found.append({"type": "三合", "members": list(group)})
    for a, b in LIUHE:
        if a in pool and b in pool:
            found.append({"type": "六合", "members": [a, b]})
    for a, b in LIUCHONG:
        if a in pool and b in pool:
            found.append({"type": "六冲", "members": [a, b]})
    for a, b in LIUHAI:
        if a in pool and b in pool:
            found.append({"type": "相害", "members": [a, b]})
    for group in SANXING:
        if all(z in pool for z in group):
            found.append({"type": "相刑", "members": list(group)})
    return found


def _shensha(pillars, day_gan, year_zhi, day_zhi, zhis):
    hits = []

    tianyi = list(TIANYI[day_gan])
    hits.append({"name": "天乙贵人", "hit": [z for z in zhis if z in tianyi], "rule": "以日干查"})
    hits.append({"name": "文昌", "hit": [z for z in zhis if z == WENCHANG[day_gan]], "rule": "以日干查"})
    hits.append({"name": "禄神", "hit": [z for z in zhis if z == LUSHEN[day_gan]], "rule": "以日干查"})

    if day_gan in YANGREN:
        hits.append({"name": "羊刃", "hit": [z for z in zhis if z == YANGREN[day_gan]],
                     "rule": "仅阳干取帝旺位"})

    def sanhe_group(z):
        for g in SANHE:
            if z in g:
                return g
        return None

    for label, base, target in (("桃花", year_zhi, {"申子辰": "酉", "寅午戌": "卯",
                                                    "巳酉丑": "午", "亥卯未": "子"}),
                                ("驿马", year_zhi, {"申子辰": "寅", "寅午戌": "申",
                                                    "巳酉丑": "亥", "亥卯未": "巳"}),
                                ("华盖", year_zhi, {"申子辰": "辰", "寅午戌": "戌",
                                                    "巳酉丑": "丑", "亥卯未": "未"}),
                                ("将星", year_zhi, {"申子辰": "子", "寅午戌": "午",
                                                    "巳酉丑": "酉", "亥卯未": "卯"})):
        g = sanhe_group(base)
        if g:
            key = "".join(g)
            z = target.get(key)
            if z:
                hits.append({"name": label, "hit": [x for x in zhis if x == z],
                             "rule": "以年支三合局查"})
    return [h for h in hits if h["hit"]]


def wuxing_strength(pillars):
    """五行力量：天干计 1.0，地支藏干按 1.0/0.4/0.2 折算，月支整体 ×1.5。"""
    score = {e: 0.0 for e in ELEMENTS}
    detail = []
    for pos in ("year", "month", "day", "hour"):
        gz = pillars[pos]
        g, z = gz[0], gz[1]
        score[element_of_gan(g)] += 1.0
        detail.append({"pos": pos, "gan": g, "element": element_of_gan(g), "weight": 1.0})
        factor = 1.5 if pos == "month" else 1.0
        for i, cg in enumerate(CANG_GAN[z]):
            w = CANG_WEIGHT[i] * factor
            score[element_of_gan(cg)] += w
    total = sum(score.values())
    pct = {e: round(score[e] / total * 100, 1) for e in ELEMENTS}
    return {"raw": {e: round(v, 2) for e, v in score.items()}, "percent": pct, "total": round(total, 2)}


def strength_verdict(pillars, day_gan, wuxing_percent):
    """旺衰粗判：以五行力量占比为主口径，得令/得地/得势为旁证。

    主口径：日主及其印星（生我）合计占比。
    这样与页面上展示的五行柱状图同源，用户能自己对上账。
    """
    me = element_of_gan(day_gan)
    me_idx = ELEMENTS.index(me)
    support = [ELEMENTS[me_idx], ELEMENTS[(me_idx - 1) % 5]]
    support_pct = round(sum(wuxing_percent[e] for e in support), 1)

    if support_pct >= 55:
        level = "偏强"
    elif support_pct >= 47:
        level = "中和偏强"
    elif support_pct >= 40:
        level = "中和"
    elif support_pct >= 33:
        level = "中和偏弱"
    else:
        level = "偏弱"

    month_zhi = pillars["month"][1]
    month_el = element_of_zhi(month_zhi)
    deling = month_el in support

    dedi = 0
    for pos in ("year", "month", "day", "hour"):
        z = pillars[pos][1]
        if any(element_of_gan(cg) in support for cg in CANG_GAN[z]):
            dedi += 1

    deshi = sum(1 for pos in ("year", "month", "hour")
                if element_of_gan(pillars[pos][0]) in support)

    notes = [
        "月令%s（%s）%s" % (month_zhi, month_el, "助我，得令" if deling else "不助我，失令"),
        "地支 %d 支藏同类或印星（得地）" % dedi,
        "天干 %d 个比劫或印星（得势）" % deshi,
        "同类与印星合计 %.1f%%（主口径）" % support_pct,
    ]
    return {
        "level": level,
        "support_percent": support_pct,
        "support_elements": support,
        "deling": deling,
        "dedi": dedi,
        "deshi": deshi,
        "notes": notes,
        "basis": "以同类+印星占五行总力的比例为主口径，得令/得地/得势仅作旁证",
    }


def start_age_of_dayun(pillars, year_gan, gender, birth_dt):
    """起运：阳年男 / 阴年女 顺行，取出生后下一个节；反之逆行取上一个节。"""
    yang_year = cc.GAN.index(year_gan) % 2 == 0
    forward = (yang_year and gender == "男") or ((not yang_year) and gender == "女")
    tl = cc._jie_timeline(birth_dt.year)
    if forward:
        target = next(t for t, _n, _z in tl if t > birth_dt)
        delta = (target - birth_dt).total_seconds() / 86400.0
    else:
        target = max(t for t, _n, _z in tl if t <= birth_dt)
        delta = (birth_dt - target).total_seconds() / 86400.0

    years = int(delta // 3)
    rem_days = delta - years * 3
    months = int(rem_days * 4)
    days = round((rem_days * 4 - months) * 30)
    return {
        "forward": forward,
        "reference_term": target.strftime("%Y-%m-%d %H:%M"),
        "days_to_term": round(delta, 2),
        "start_age": round(delta / 3.0, 2),
        "start_age_text": "%d 年 %d 个月 %d 天" % (years, months, days),
    }


def dayun_sequence(month_index, forward, count=9):
    out = []
    for i in range(1, count + 1):
        idx = (month_index + i) % 60 if forward else (month_index - i) % 60
        out.append(cc.ganzhi(idx))
    return out


def liunian(year, count):
    out = []
    for y in range(year, year + count):
        idx = (y - 4) % 60
        out.append({"year": y, "ganzhi": cc.ganzhi(idx),
                    "age_note": "立春起算"})
    return out


def liuyue(liunian_gan_index, year):
    """某个流年的十二个月柱（五虎遁）。"""
    out = []
    for k in range(12):
        mzhi = (2 + k) % 12
        idx = cc.month_ganzhi_index(liunian_gan_index % 10, mzhi)
        out.append({"month_zhi": cc.ZHI[mzhi], "ganzhi": cc.ganzhi(idx)})
    return out


def chart(birth_dt, gender, longitude=None, day_boundary="23:00", liunian_years=8):
    """完整八字盘。birth_dt 为东八区带时区 datetime。"""
    fp = cc.four_pillars(birth_dt, longitude=longitude, day_boundary=day_boundary)
    p = fp["pillars"]
    idx = fp["indices"]
    day_gan = p["day"][0]

    pillars_detail = {}
    for pos, label in (("year", "年柱"), ("month", "月柱"), ("day", "日柱"), ("hour", "时柱")):
        gz = p[pos]
        g, z = gz[0], gz[1]
        cang = [{"gan": cg, "shishen": shishen(day_gan, cg),
                 "weight": CANG_WEIGHT[i]} for i, cg in enumerate(CANG_GAN[z])]
        pillars_detail[pos] = {
            "label": label,
            "ganzhi": gz,
            "gan": g,
            "zhi": z,
            "gan_element": element_of_gan(g),
            "zhi_element": element_of_zhi(z),
            "gan_shishen": "日主" if pos == "day" else shishen(day_gan, g),
            "cang_gan": cang,
            "nayin": cc.nayin(idx[pos]),
            "changsheng": changsheng(day_gan, z),
        }

    zhis = [p[k][1] for k in ("year", "month", "day", "hour")]
    lns = liunian(birth_dt.year, liunian_years)
    for item in lns:
        gi = cc.ganzhi_index(item["ganzhi"][0], item["ganzhi"][1])
        item["shishen"] = shishen(day_gan, item["ganzhi"][0])
        item["age"] = item["year"] - birth_dt.year
        item["liuyue"] = liuyue(gi % 10, item["year"])

    start = start_age_of_dayun(p, p["year"][0], gender, birth_dt)
    seq = dayun_sequence(idx["month"], start["forward"])
    dayun = []
    for i, gz in enumerate(seq):
        dayun.append({
            "step": i + 1,
            "ganzhi": gz,
            "start_age": round(start["start_age"] + i * 10, 2),
            "end_age": round(start["start_age"] + (i + 1) * 10, 2),
            "shishen": shishen(day_gan, gz[0]),
            "nayin": cc.nayin(cc.ganzhi_index(gz[0], gz[1])),
        })

    return {
        "gender": gender,
        "solar": fp["input_time"],
        "true_solar_time": fp["true_solar_time"],
        "lunar": cc.lunar_text(datetime.strptime(fp["true_solar_time"][:10], "%Y-%m-%d").date()),
        "shengxiao": fp["shengxiao"],
        "pillars": p,
        "indices": idx,
        "pillars_detail": pillars_detail,
        "day_master": {
            "gan": day_gan,
            "element": element_of_gan(day_gan),
            "polarity": "阳" if cc.GAN.index(day_gan) % 2 == 0 else "阴",
            "changsheng_in_month": changsheng(day_gan, p["month"][1]),
        },
        "wuxing": wuxing_strength(p),
        "strength": strength_verdict(p, day_gan, wuxing_strength(p)["percent"]),
        "xunkong": {"day": xunkong(idx["day"]), "year": xunkong(idx["year"])},
        "zhi_relations": _zhi_relations(zhis),
        "shensha": _shensha(p, day_gan, p["year"][1], p["day"][1], zhis),
        "dayun": {"meta": start, "list": dayun},
        "liunian": lns,
        "month_jie": {"name": fp["month_jie"], "time": fp["month_jie_time"]},
        "nearby_terms": fp["nearby_terms"],
        "correction": {
            "longitude": fp["longitude"],
            "longitude_offset_minutes": fp["longitude_offset_minutes"],
            "equation_of_time_minutes": fp["equation_of_time_minutes"],
            "day_boundary": day_boundary,
        },
        "quant_note": "五行力量与旺衰为本产品的量化口径，非古典定论，仅供横向比较。",
    }
