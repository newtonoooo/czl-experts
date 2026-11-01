#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""紫微斗数 ziwei.py

排盘顺序：农历生辰 → 命宫/身宫 → 命宫天干（五虎遁）→ 五行局（纳音）→
紫微星落宫 → 天府星对称定位 → 十四主星 → 生年四化 → 十二宫 → 大限 / 流年。

宫位编号统一为 0=寅、1=卯 … 11=丑（地支顺时针序列）。
主星位置用相对偏移计算，便于自检：十四主星必须各落一宫、不重不漏。

作者：虫志龙 <47190078@qq.com>
"""

import calendar_core as cc

PALACE_NAMES = ["命宫", "兄弟", "夫妻", "子女", "财帛", "疾厄",
                "迁移", "交友", "官禄", "田宅", "福德", "父母"]

JU_SHIFT = {"水": 2, "木": 3, "金": 4, "土": 5, "火": 6}
JU_NAME = {2: "水二局", 3: "木三局", 4: "金四局", 5: "土五局", 6: "火六局"}

# 紫微系：以紫微为基准的逆行偏移
ZIWEI_GROUP = [("紫微", 0), ("天机", -1), ("太阳", -3), ("武曲", -4), ("天同", -5), ("廉贞", -8)]
# 天府系：以天府为基准的顺行偏移
TIANFU_GROUP = [("天府", 0), ("太阴", 1), ("贪狼", 2), ("巨门", 3), ("天相", 4),
                ("天梁", 5), ("七杀", 6), ("破军", 10)]

SIHUA = {
    "甲": {"禄": "廉贞", "权": "破军", "科": "武曲", "忌": "太阳"},
    "乙": {"禄": "天机", "权": "天梁", "科": "紫微", "忌": "太阴"},
    "丙": {"禄": "天同", "权": "天机", "科": "文昌", "忌": "廉贞"},
    "丁": {"禄": "太阴", "权": "天同", "科": "天机", "忌": "巨门"},
    "戊": {"禄": "贪狼", "权": "太阴", "科": "右弼", "忌": "天机"},
    "己": {"禄": "武曲", "权": "贪狼", "科": "天梁", "忌": "文曲"},
    "庚": {"禄": "太阳", "权": "武曲", "科": "太阴", "忌": "天同"},
    "辛": {"禄": "巨门", "权": "太阳", "科": "文曲", "忌": "文昌"},
    "壬": {"禄": "天梁", "权": "紫微", "科": "左辅", "忌": "武曲"},
    "癸": {"禄": "破军", "权": "巨门", "科": "太阴", "忌": "贪狼"},
}

STAR_NOTE = {
    "紫微": "主导与格局", "天机": "思虑与变通", "太阳": "外显与担当", "武曲": "执行与财",
    "天同": "安逸与情绪", "廉贞": "边界与张力", "天府": "库藏与稳守", "太阴": "内在与积累",
    "贪狼": "欲望与交际", "巨门": "言语与是非", "天相": "辅佐与形象", "天梁": "规则与庇护",
    "七杀": "决断与冲劲", "破军": "破旧与重启",
}


def _palace_index_of_zhi(zhi):
    return (cc.ZHI.index(zhi) - 2) % 12


def _zhi_of_palace(index):
    return cc.ZHI[(index + 2) % 12]


def _tianfu_index(ziwei_index):
    return (12 - ziwei_index) % 12


def _ziwei_index(day, ju):
    """紫微星落宫：以局数除日，余数补足后按奇逆偶顺进退。"""
    n = (ju - day % ju) % ju
    quotient = (day + n) // ju
    base = (quotient - 1) % 12
    if n == 0:
        return base
    return (base - n) % 12 if n % 2 == 1 else (base + n) % 12


def chart(solar_dt, gender, longitude=None):
    """紫微盘。solar_dt 为东八区带时区 datetime。"""
    import astro
    fp = cc.four_pillars(solar_dt, longitude=longitude)
    year_gan = fp["pillars"]["year"][0]
    year_zhi_i = cc.ZHI.index(fp["pillars"]["year"][1])

    lunar_date = solar_dt.date()
    if longitude is not None:
        lunar_date = cc.true_solar_time(solar_dt, longitude)[0].date()
        if lunar_date != solar_dt.date():
            fp = cc.four_pillars(solar_dt, longitude=longitude)
            year_gan = fp["pillars"]["year"][0]
            year_zhi_i = cc.ZHI.index(fp["pillars"]["year"][1])
    ly, lm, ld, leap = cc.solar_to_lunar(lunar_date)
    hour_zhi_i = cc.hour_zhi_of(
        cc.true_solar_time(solar_dt, longitude)[0].hour if longitude is not None else solar_dt.hour)

    ming = (lm - 1 - hour_zhi_i) % 12
    shen = (lm - 1 + hour_zhi_i) % 12

    yin_gan = (2 + 2 * (cc.GAN.index(year_gan) % 5)) % 10
    palace_gan = {i: (yin_gan + i) % 10 for i in range(12)}

    ming_ganzhi_idx = cc.ganzhi_index(cc.GAN[palace_gan[ming]], _zhi_of_palace(ming))
    ju = JU_SHIFT[cc.nayin(ming_ganzhi_idx)[-1]]
    ziwei = _ziwei_index(ld, ju)
    tianfu = _tianfu_index(ziwei)

    stars = {i: [] for i in range(12)}
    for name, off in ZIWEI_GROUP:
        stars[(ziwei + off) % 12].append(name)
    for name, off in TIANFU_GROUP:
        stars[(tianfu + off) % 12].append(name)

    # 自检：十四主星各一
    flat = [s for v in stars.values() for s in v]
    assert len(flat) == 14 and len(set(flat)) == 14, "十四主星排布自检失败"

    sihua = SIHUA[year_gan]
    hua_of = {}
    for kind, star in sihua.items():
        hua_of.setdefault(star, []).append(kind)

    palaces = []
    for k in range(12):
        idx = (ming - k) % 12
        stars_here = stars[idx]
        palaces.append({
            "order": k,
            "palace": PALACE_NAMES[k],
            "palace_zhi": _zhi_of_palace(idx),
            "palace_gan": cc.GAN[palace_gan[idx]],
            "ganzhi": cc.GAN[palace_gan[idx]] + _zhi_of_palace(idx),
            "is_ming": idx == ming,
            "is_shen": idx == shen,
            "stars": [{"name": s, "note": STAR_NOTE.get(s, ""),
                       "sihua": hua_of.get(s, [])} for s in stars_here],
            "empty": not stars_here,
        })

    # 大限：顺行按 命→兄弟→夫妻 走（宫位递减），逆行按 命→父母→福德 走（宫位递增）
    yang_year = cc.GAN.index(year_gan) % 2 == 0
    forward = (yang_year and gender == "男") or ((not yang_year) and gender == "女")
    dayun = []
    for k in range(12):
        start = ju + k * 10
        if forward:
            pos = (ming - k) % 12
            pname = PALACE_NAMES[k]
        else:
            pos = (ming + k) % 12
            pname = PALACE_NAMES[(12 - k) % 12]
        dayun.append({
            "palace": pname,
            "palace_zhi": _zhi_of_palace(pos),
            "age_range": "%d–%d" % (start, start + 9),
            "is_current": False,
        })

    return {
        "system": "紫微斗数",
        "solar": solar_dt.strftime("%Y-%m-%d %H:%M"),
        "lunar": "%s年%s%s" % (cc.ganzhi((ly - 4) % 60), cc.lunar_month_name(lm, leap),
                               cc.lunar_day_name(ld)),
        "lunar_raw": {"year": ly, "month": lm, "day": ld, "leap": leap},
        "hour_zhi": cc.ZHI[hour_zhi_i],
        "gender": gender,
        "year_ganzhi": fp["pillars"]["year"],
        "ming_palace": {"zhi": _zhi_of_palace(ming), "ganzhi": cc.GAN[palace_gan[ming]] + _zhi_of_palace(ming)},
        "shen_palace": {"zhi": _zhi_of_palace(shen)},
        "ju": {"name": JU_NAME[ju], "number": ju},
        "ziwei": {"zhi": _zhi_of_palace(ziwei)},
        "tianfu": {"zhi": _zhi_of_palace(tianfu)},
        "sihua": sihua,
        "palaces": palaces,
        "dayun": {"forward": forward, "list": dayun,
                  "note": "大限自命宫起，每宫十年，起运虚岁等于五行局数。"},
        "flow_year_branch": cc.ZHI[year_zhi_i],
    }


def flow_year(chart_data, target_year):
    """某公历年的流年落宫与虚岁。"""
    ly = chart_data["lunar_raw"]["year"]
    xu = target_year - ly + 1
    zhi = cc.ZHI[(target_year - 4) % 12]
    idx = _palace_index_of_zhi(zhi)
    for p in chart_data["palaces"]:
        if p["palace_zhi"] == zhi:
            return {"year": target_year, "xu_sui": xu, "zhi": zhi,
                    "palace": p["palace"], "ganzhi": cc.ganzhi((target_year - 4) % 60)}
    return {"year": target_year, "xu_sui": xu, "zhi": zhi, "palace": None}
