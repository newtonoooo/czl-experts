#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""历法核心 calendar_core.py

职责：
  - 干支纪年/月/日/时的换算
  - 农历（定朔定气法）与公历互转，含闰月
  - 真太阳时校正
  - 四柱（年月日时）定位

本文件只做"时间到干支"的换算，不做吉凶判断。吉凶与解读属于上层模块。
实现依据为公开的历法规则（干支纪日、五虎遁、五鼠遁、定朔定气置闰），
代码独立编写。

作者：虫志龙 <47190078@qq.com>
"""

import math
from datetime import datetime, date, timedelta

import astro

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
SHENGXIAO = "鼠牛虎兔龙蛇马羊猴鸡狗猪"
WUXING = "木木火火土土金金水水"          # 天干五行
ZHI_WUXING = "水土木木土火火土金金土水"    # 地支五行
GAN_YINYANG = "阳阴" * 5
ZHI_YINYANG = "阳阴阳阴阳阴阳阴阳阴阳阴"

# 十二节 -> 所起月支
JIE_TO_ZHI = {
    "立春": 2, "惊蛰": 3, "清明": 4, "立夏": 5, "芒种": 6, "小暑": 7,
    "立秋": 8, "白露": 9, "寒露": 10, "立冬": 11, "大雪": 0, "小寒": 1,
}


def ganzhi(index):
    """0 -> 甲子，59 -> 癸亥。"""
    i = index % 60
    return GAN[i % 10] + ZHI[i % 12]


def ganzhi_index(gan, zhi):
    """由天干地支反查六十甲子序号。"""
    g = GAN.index(gan)
    z = ZHI.index(zhi)
    for i in range(60):
        if i % 10 == g and i % 12 == z:
            return i
    raise ValueError("干支不匹配")


def xunkong(ganzhi_index):
    """旬空（空亡）两地支。"""
    xun = (ganzhi_index % 60) // 10
    start = (10 - 2 * xun) % 12
    return ZHI[start] + ZHI[(start + 1) % 12]


def nayin(index):
    """六十甲子纳音。"""
    table = [
        "海中金", "炉中火", "大林木", "路旁土", "剑锋金", "山头火",
        "涧下水", "城头土", "白蜡金", "杨柳木", "泉中水", "屋上土",
        "霹雳火", "松柏木", "长流水", "沙中金", "山下火", "平地木",
        "壁上土", "金箔金", "覆灯火", "天河水", "大驿土", "钗钏金",
        "桑柘木", "大溪水", "沙中土", "天上火", "石榴木", "大海水",
    ]
    return table[(index % 60) // 2]


# ---------------------------------------------------------------- 日柱

def jdn_local(d):
    """当地日期（东八区）正午所落的儒略日数（整日数，JD 的 .5 边界已对齐）。"""
    jd = astro.jd_from_datetime(datetime(d.year, d.month, d.day, 12, tzinfo=astro.CST))
    return int(math.floor(jd + 0.5))


def day_ganzhi_index(d):
    """某日的日干支序号。基准经多方历表核对：1949-10-01 为甲子日（序号 0）。"""
    return (jdn_local(d) + 49) % 60


def day_ganzhi(d):
    return ganzhi(day_ganzhi_index(d))


# ---------------------------------------------------------------- 节气与月柱

def _jie_timeline(year):
    """覆盖 year 前后的十二节时间轴：[(datetime, '节名', 月支序号)] 升序。"""
    items = []
    for y in (year - 1, year, year + 1):
        for name, zhi in JIE_TO_ZHI.items():
            items.append((astro.solar_term_time(y, name), name, zhi))
    items.sort(key=lambda x: x[0])
    return items


def month_zhi_of(dt):
    """按节气定月支：返回 (月支序号, 所属节的名称, 该节交节时刻)。"""
    tl = _jie_timeline(dt.year)
    cur = tl[0]
    for item in tl:
        if item[0] <= dt:
            cur = item
        else:
            break
    return cur[2], cur[1], cur[0]


def year_ganzhi_index_by_lichun(dt):
    """以立春为界定年干支序号。"""
    lichun = astro.solar_term_time(dt.year, "立春")
    y = dt.year if dt >= lichun else dt.year - 1
    return (y - 4) % 60


def month_ganzhi_index(year_gan_index, month_zhi):
    """五虎遁：由年干与月支定月干。"""
    order = (month_zhi - 2) % 12          # 寅=0
    gan = (2 + 2 * (year_gan_index % 5) + order) % 10
    for i in range(60):
        if i % 10 == gan and i % 12 == month_zhi:
            return i
    raise ValueError("月柱推算失败")


def hour_zhi_of(hour):
    """23:00–00:59 为子时。"""
    return ((hour + 1) // 2) % 12


def hour_ganzhi_index(day_gan_index, hour_zhi):
    """五鼠遁：由日干与时辰定 时干。"""
    gan = (2 * (day_gan_index % 5) + hour_zhi) % 10
    for i in range(60):
        if i % 10 == gan and i % 12 == hour_zhi:
            return i
    raise ValueError("时柱推算失败")


# ---------------------------------------------------------------- 真太阳时

def true_solar_time(dt, longitude):
    """把东八区标准时换算为出生地真太阳时。

    longitude 为东经度数；为 None 时不做经度校正（按 120°E 计）。
    """
    offset_min = 0.0 if longitude is None else (longitude - 120.0) * 4.0
    mean = dt + timedelta(minutes=offset_min)
    eot = astro.equation_of_time_minutes(astro.jd_from_datetime(mean))
    return mean + timedelta(minutes=eot), offset_min, eot


# ---------------------------------------------------------------- 四柱

def four_pillars(dt_local, longitude=None, day_boundary="23:00"):
    """给定东八区标准时间，返回四柱及其判定依据。

    day_boundary: "23:00" 表示晚子时（23 点后日柱进次日，传统子时换日）；
                  "00:00" 表示以午夜换日。
    """
    correction = None
    if longitude is not None:
        ts, offset_min, eot = true_solar_time(dt_local, longitude)
    else:
        ts, offset_min, eot = dt_local, 0.0, astro.equation_of_time_minutes(
            astro.jd_from_datetime(dt_local))

    solar_date = ts.date()
    effective_date = solar_date
    if day_boundary == "23:00" and ts.hour >= 23:
        effective_date = solar_date + timedelta(days=1)

    year_idx = year_ganzhi_index_by_lichun(ts)
    mzhi, jie_name, jie_dt = month_zhi_of(ts)
    month_idx = month_ganzhi_index(year_idx % 10, mzhi)
    day_idx = day_ganzhi_index(effective_date)
    hzhi = hour_zhi_of(ts.hour)
    hour_idx = hour_ganzhi_index(day_idx % 10, hzhi)

    # 距交节时长，供"交界提示"使用
    nearby = []
    for name, t in astro.solar_terms_of_year(ts.year):
        gap = abs((ts - t).total_seconds()) / 60.0
        if gap <= 60:
            nearby.append({"term": name, "time": t.strftime("%Y-%m-%d %H:%M"),
                           "gap_minutes": round((ts - t).total_seconds() / 60.0, 1)})

    return {
        "input_time": dt_local.strftime("%Y-%m-%d %H:%M"),
        "true_solar_time": ts.strftime("%Y-%m-%d %H:%M"),
        "longitude": longitude,
        "longitude_offset_minutes": round(offset_min, 2),
        "equation_of_time_minutes": round(eot, 2),
        "day_boundary": day_boundary,
        "pillars": {
            "year": ganzhi(year_idx),
            "month": ganzhi(month_idx),
            "day": ganzhi(day_idx),
            "hour": ganzhi(hour_idx),
        },
        "indices": {
            "year": year_idx, "month": month_idx, "day": day_idx, "hour": hour_idx,
        },
        "month_jie": jie_name,
        "month_jie_time": jie_dt.strftime("%Y-%m-%d %H:%M"),
        "shengxiao": SHENGXIAO[year_idx % 12],
        "nearby_terms": nearby,
    }


# ---------------------------------------------------------------- 农历

def _dongzhi(year):
    return astro.solar_term_time(year, "冬至")


def _mid_term_times(year):
    return [astro.solar_term_time(year, n) for n in astro.MID_TERMS]


def _has_zhongqi(start_date, end_date, mid_times):
    for t in mid_times:
        if start_date <= t.date() < end_date:
            return True
    return False


_CYCLE_CACHE = {}
_YEAR_CACHE = {}


def _cycle(year):
    """以「含冬至之月为十一月」为锚，返回 [十一月(year), 十一月(year+1)) 的月序。

    闰月只在周期内部判定：周期内有 13 个月时，取第一个不含中气的月为闰月。
    这是 2033 年"闰十一月"这类边界情形能被正确处理的关键——若按上一年周期
    判闰，冬至就落不到十一月里，编号会整体错位。
    """
    if year in _CYCLE_CACHE:
        return _CYCLE_CACHE[year]

    dz0 = _dongzhi(year)
    dz1 = _dongzhi(year + 1)
    moons = astro.new_moons_between(astro.jd_from_datetime(dz0) - 40,
                                    astro.jd_from_datetime(dz1) + 20)
    i0 = max(i for i, m in enumerate(moons) if m.date() <= dz0.date())
    i1 = max(i for i, m in enumerate(moons) if m.date() <= dz1.date())
    starts = moons[i0:i1]
    n = len(starts)

    mid_times = []
    for y in (year - 1, year, year + 1, year + 2):
        mid_times.extend(_mid_term_times(y))
    mid_times.sort()

    leap_pos = None
    if n == 13:
        for i in range(1, n):
            start = starts[i].date()
            end = starts[i + 1].date() if i + 1 < n else dz1.date()
            if not _has_zhongqi(start, end, mid_times):
                leap_pos = i
                break
        if leap_pos is None:
            leap_pos = 1

    months = []
    num = 11
    for i in range(n):
        if i == leap_pos:
            months.append((starts[i].date(), num, True))
        else:
            if i > 0:
                num = num % 12 + 1
            months.append((starts[i].date(), num, False))

    _CYCLE_CACHE[year] = months
    return months


def lunar_year_months(lunar_year):
    """农历某年的月序：[(初一日 date, 月序 1..12, 是否闰月)]，按时间升序。

    农历年 = 从本年的正月初一到下一年的正月初一。其中正月至十月来自上一周期，
    十一月至十二月来自本周期（可能含闰十一月、闰十二月）。
    """
    if lunar_year in _YEAR_CACHE:
        return _YEAR_CACHE[lunar_year]

    prev = _cycle(lunar_year - 1)
    cur = _cycle(lunar_year)

    start_idx = None
    for i, (_, num, leap) in enumerate(prev):
        if num == 1 and not leap:
            start_idx = i
            break
    if start_idx is None:
        raise ValueError("上一年度周期内缺正月：%d" % (lunar_year - 1))

    months = list(prev[start_idx:])
    for item in cur:
        if item[1] == 1 and not item[2]:
            break
        months.append(item)

    _YEAR_CACHE[lunar_year] = months
    return months


def _lunar_year_start(lunar_year):
    months = lunar_year_months(lunar_year)
    for i, (start, num, leap) in enumerate(months):
        if num == 1 and not leap:
            return start
    # 理论上不会发生；兜底取正月所在的下一年度首月
    raise ValueError("农历年缺正月：%d" % lunar_year)


def solar_to_lunar(d):
    """公历 date -> (农历年, 月, 日, 是否闰月)。"""
    for ly in (d.year, d.year - 1):
        months = lunar_year_months(ly)
        start0 = _lunar_year_start(ly)
        end = _lunar_year_start(ly + 1)
        if start0 <= d < end:
            pick = months[0]
            for i, item in enumerate(months):
                nxt = months[i + 1][0] if i + 1 < len(months) else end
                if item[0] <= d < nxt:
                    day = (d - item[0]).days + 1
                    return ly, item[1], day, item[2]
    raise ValueError("农历换算失败：%s" % d)


def lunar_to_solar(lunar_year, month, day, is_leap=False):
    """农历 -> 公历 date。"""
    months = lunar_year_months(lunar_year)
    target = None
    for start, num, leap in months:
        if num == month and leap == is_leap:
            target = start
            break
    if target is None:
        raise ValueError("该年无此月：%d 年 %s%d 月" % (lunar_year, "闰" if is_leap else "", month))
    return target + timedelta(days=day - 1)


def lunar_month_name(month, is_leap):
    names = ["正", "二", "三", "四", "五", "六", "七", "八", "九", "十", "冬", "腊"]
    return ("闰" if is_leap else "") + names[(month - 1) % 12] + "月"


def lunar_day_name(day):
    if day <= 10:
        return "初" + "一二三四五六七八九十"[day - 1]
    if day < 20:
        return "十" + "一二三四五六七八九"[day - 11]
    if day == 20:
        return "二十"
    if day < 30:
        return "廿" + "一二三四五六七八九"[day - 21]
    return "三十"


def lunar_text(d):
    ly, m, dd, leap = solar_to_lunar(d)
    return "%s%s%s" % (ganzhi((ly - 4) % 60), lunar_month_name(m, leap), lunar_day_name(dd))


# ---------------------------------------------------------------- 时辰辅助

def shichen_range(hour_zhi):
    """时辰对应的钟点区间文本（东八区标准时，未做真太阳时校正）。"""
    start = (hour_zhi * 2 - 1) % 24
    end = (start + 2) % 24
    return "%02d:00–%02d:00" % (start, end)


def wuxing_of_gan(gan):
    return WUXING[GAN.index(gan)]


def wuxing_of_zhi(zhi):
    return ZHI_WUXING[ZHI.index(zhi)]
