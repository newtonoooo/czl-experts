#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卦象模块 divination.py

包含两套体例，各自独立的起卦与装卦规则：
  1. 梅花易数：时间/数字/方位起卦，体用生克，本卦—互卦—变卦
  2. 六爻纳甲：三钱摇卦或时间取数，京房八宫定宫与世应，纳甲、六亲、六神

两套体系的判断逻辑完全不共用，输出结构也不合并——合并会掩盖体例差异。

作者：虫志龙 <47190078@qq.com>
"""

import secrets
from datetime import datetime

import calendar_core as cc

# 八卦：爻由下至上，(初,中,上)，1 为阳
TRIGRAM_BITS = {
    "乾": (1, 1, 1), "兑": (1, 1, 0), "离": (1, 0, 1), "震": (1, 0, 0),
    "巽": (0, 1, 1), "坎": (0, 1, 0), "艮": (0, 0, 1), "坤": (0, 0, 0),
}
BITS_TRIGRAM = {v: k for k, v in TRIGRAM_BITS.items()}
TRIGRAM_NUMBER = {"乾": 1, "兑": 2, "离": 3, "震": 4, "巽": 5, "坎": 6, "艮": 7, "坤": 8}
TRIGRAM_ELEMENT = {"乾": "金", "兑": "金", "离": "火", "震": "木",
                   "巽": "木", "坎": "水", "艮": "土", "坤": "土"}
TRIGRAM_NATURE = {"乾": "天", "兑": "泽", "离": "火", "震": "雷",
                  "巽": "风", "坎": "水", "艮": "山", "坤": "地"}

# 六十四卦：上卦 -> [(下卦, 卦名, 核心意象)]
_HEX_TABLE = {
    "乾": [("乾", "乾为天", "纯阳刚健，行健不息"), ("兑", "天泽履", "如履虎尾，慎行得吉"),
           ("离", "天火同人", "与人同心，公开则通"), ("震", "天雷无妄", "不妄为则无灾"),
           ("巽", "天风姤", "不期而遇，慎防蔓延"), ("坎", "天水讼", "争而不决，退让为上"),
           ("艮", "天山遁", "时不可为，退避保身"), ("坤", "天地否", "上下不交，闭塞待时")],
    "兑": [("乾", "泽天夬", "决断去疑，光明正大"), ("兑", "兑为泽", "和悦相说，以柔取胜"),
           ("离", "泽火革", "顺时而变，革故鼎新"), ("震", "泽雷随", "随时而动，择善而从"),
           ("巽", "泽风大过", "负重过甚，栋桡宜扶"), ("坎", "泽水困", "困而不失其所亨"),
           ("艮", "泽山咸", "感应相通，以虚受人"), ("坤", "泽地萃", "聚而不散，防聚而生乱")],
    "离": [("乾", "火天大有", "所有丰盛，守成在德"), ("兑", "火泽睽", "同中见异，小事可成"),
           ("离", "离为火", "附丽而明，柔顺守中"), ("震", "火雷噬嗑", "去梗除阻，明断是非"),
           ("巽", "火风鼎", "鼎新养贤，稳中求变"), ("坎", "火水未济", "事未竟成，慎终如始"),
           ("艮", "火山旅", "旅居在外，柔顺自处"), ("坤", "火地晋", "光明渐进，顺势上行")],
    "震": [("乾", "雷天大壮", "壮而有节，不可恃力"), ("兑", "雷泽归妹", "急于所归，位不当则凶"),
           ("离", "雷火丰", "盛极宜忧，日中则昃"), ("震", "震为雷", "震动惊惧，敬而无失"),
           ("巽", "雷风恒", "守常有恒，不易其方"), ("坎", "雷水解", "解难缓困，宜速不宜迟"),
           ("艮", "雷山小过", "小事可为，大事勿越"), ("坤", "雷地豫", "豫备而乐，防乐极生悲")],
    "巽": [("乾", "风天小畜", "小有积蓄，密云不雨"), ("兑", "风泽中孚", "诚信及物，中虚乃孚"),
           ("离", "风火家人", "内治有序，先齐其家"), ("震", "风雷益", "损上益下，见善则迁"),
           ("巽", "巽为风", "柔顺而入，随风渐进"), ("坎", "风水涣", "涣散宜聚，聚则成事"),
           ("艮", "风山渐", "循序渐进，女归吉"), ("坤", "风地观", "观仰示范，静而察之")],
    "坎": [("乾", "水天需", "待时而动，险在前也"), ("兑", "水泽节", "节而有度，苦节不可贞"),
           ("离", "水火既济", "事已成，守成防乱"), ("震", "水雷屯", "初生艰难，宜建侯"),
           ("巽", "水风井", "养而不穷，井道常通"), ("坎", "坎为水", "重险习坎，行险而不失信"),
           ("艮", "水山蹇", "见险而止，反身修德"), ("坤", "水地比", "亲比相辅，择善而从")],
    "艮": [("乾", "山天大畜", "大有蓄积，止健养贤"), ("兑", "山泽损", "损下益上，损而有孚"),
           ("离", "山火贲", "文饰之美，白贲无咎"), ("震", "山雷颐", "养正则吉，观其所养"),
           ("巽", "山风蛊", "积弊待治，先甲后甲"), ("坎", "山水蒙", "蒙昧求明，童蒙求我"),
           ("艮", "艮为山", "止其所止，不获其身"), ("坤", "山地剥", "剥落将尽，顺时而止")],
    "坤": [("乾", "地天泰", "上下交泰，小往大来"), ("兑", "地泽临", "临事以宽，教思无穷"),
           ("离", "地火明夷", "明入地中，晦其明以自守"), ("震", "地雷复", "一阳来复，七日来复"),
           ("巽", "地风升", "积小成高，柔以时升"), ("坎", "地水师", "用众以正，师出有名"),
           ("艮", "地山谦", "谦而有终，卑以自牧"), ("坤", "坤为地", "纯阴厚载，利牝马之贞")],
}

HEX_NAME = {}
for _up, _rows in _HEX_TABLE.items():
    for _low, _name, _gloss in _rows:
        HEX_NAME[(_up, _low)] = (_name, _gloss)

# 京房八宫
PALACES = [("乾", (1, 1, 1, 1, 1, 1)), ("兑", (1, 1, 0, 1, 1, 0)), ("离", (1, 0, 1, 1, 0, 1)),
           ("震", (1, 0, 0, 1, 0, 0)), ("巽", (0, 1, 1, 0, 1, 1)), ("坎", (0, 1, 0, 0, 1, 0)),
           ("艮", (0, 0, 1, 0, 0, 1)), ("坤", (0, 0, 0, 0, 0, 0))]
PALACE_ELEMENT = {"乾": "金", "兑": "金", "离": "火", "震": "木",
                  "巽": "木", "坎": "水", "艮": "土", "坤": "土"}
SHI_POSITION = [6, 1, 2, 3, 4, 5, 4, 3]  # 本宫、一世…五世、游魂、归魂
STEP_NAMES = ["本宫", "一世", "二世", "三世", "四世", "五世", "游魂", "归魂"]

# 纳甲：内卦三爻 / 外卦三爻 的地支（自初爻起）
NAJIA_ZHI = {
    "乾": (["子", "寅", "辰"], ["午", "申", "戌"]),
    "坎": (["寅", "辰", "午"], ["申", "戌", "子"]),
    "艮": (["辰", "午", "申"], ["戌", "子", "寅"]),
    "震": (["子", "寅", "辰"], ["午", "申", "戌"]),
    "巽": (["丑", "亥", "酉"], ["未", "巳", "卯"]),
    "离": (["卯", "丑", "亥"], ["酉", "未", "巳"]),
    "坤": (["未", "巳", "卯"], ["丑", "亥", "酉"]),
    "兑": (["巳", "卯", "丑"], ["亥", "酉", "未"]),
}
NAJIA_GAN = {"乾": ("甲", "壬"), "坤": ("乙", "癸"), "震": ("庚", "庚"), "巽": ("辛", "辛"),
             "坎": ("戊", "戊"), "离": ("己", "己"), "艮": ("丙", "丙"), "兑": ("丁", "丁")}

LIUSHEN = ["青龙", "朱雀", "勾陈", "螣蛇", "白虎", "玄武"]
LIUSHEN_START = {"甲": 0, "乙": 0, "丙": 1, "丁": 1, "戊": 2, "己": 3, "庚": 4, "辛": 4, "壬": 5, "癸": 5}

WUXING_SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
WUXING_KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}


def _hexagram_name(lines):
    """返回 (卦名, 意象, 上卦, 下卦)。"""
    lower = BITS_TRIGRAM[tuple(lines[0:3])]
    upper = BITS_TRIGRAM[tuple(lines[3:6])]
    name, gloss = HEX_NAME[(upper, lower)]
    return name, gloss, upper, lower


def _liuqin(palace_el, yao_el):
    if yao_el == palace_el:
        return "兄弟"
    if WUXING_SHENG[yao_el] == palace_el:
        return "父母"
    if WUXING_SHENG[palace_el] == yao_el:
        return "子孙"
    if WUXING_KE[palace_el] == yao_el:
        return "妻财"
    return "官鬼"


# ---------------------------------------------------------------- 梅花易数

def meihua_by_time(dt=None):
    """时间起卦：以农历年月日数与时支数取卦。"""
    dt = dt or datetime.now(astro_tz())
    d = dt.date()
    ly, lm, ld, leap = cc.solar_to_lunar(d)
    yz = (ly - 4) % 12 + 1                      # 年支序数（子=1）
    hz = cc.hour_zhi_of(dt.hour) + 1            # 时支序数（子=1）

    upper_n = (yz + lm + ld) % 8 or 8
    lower_n = (yz + lm + ld + hz) % 8 or 8
    moving = (yz + lm + ld + hz) % 6 or 6

    return _meihua_core(upper_n, lower_n, moving, {
        "method": "时间起卦",
        "basis": "农历 %s年%s%s 日，%s时" % (cc.ganzhi((ly - 4) % 60),
                                         cc.lunar_month_name(lm, leap),
                                         cc.lunar_day_name(ld), cc.ZHI[hz - 1]),
        "numbers": {"year_branch": yz, "month": lm, "day": ld, "hour_branch": hz},
        "time": dt.strftime("%Y-%m-%d %H:%M"),
    })


def meihua_by_numbers(a, b, note=""):
    """数字起卦：两数分别取上下卦，两数之和取动爻。"""
    upper_n = a % 8 or 8
    lower_n = b % 8 or 8
    moving = (a + b) % 6 or 6
    return _meihua_core(upper_n, lower_n, moving, {
        "method": "数字起卦", "basis": note or "取数 %d、%d" % (a, b),
        "numbers": {"a": a, "b": b}, "time": datetime.now(astro_tz()).strftime("%Y-%m-%d %H:%M"),
    })


def astro_tz():
    import astro
    return astro.CST


def _trigram_by_number(n):
    for name, num in TRIGRAM_NUMBER.items():
        if num == n:
            return name
    raise ValueError("卦数越界")


def _meihua_core(upper_n, lower_n, moving, meta):
    upper = _trigram_by_number(upper_n)
    lower = _trigram_by_number(lower_n)
    lines = list(TRIGRAM_BITS[lower]) + list(TRIGRAM_BITS[upper])   # 初爻在前
    ben_name, ben_gloss, _, _ = _hexagram_name(lines)

    # 互卦：二三四爻为下互，三四五爻为上互
    hu_lines = [lines[1], lines[2], lines[3], lines[2], lines[3], lines[4]]
    hu_name, hu_gloss, hu_up, hu_low = _hexagram_name(hu_lines)

    # 变卦：动爻取反
    bian_lines = list(lines)
    bian_lines[moving - 1] ^= 1
    bian_name, bian_gloss, bian_up, bian_low = _hexagram_name(bian_lines)

    # 体用：动爻所在之卦为用，另一卦为体
    if moving <= 3:
        yong, ti = lower, upper
        yong_pos = "下卦"
    else:
        yong, ti = upper, lower
        yong_pos = "上卦"

    ti_el = TRIGRAM_ELEMENT[ti]
    yong_el = TRIGRAM_ELEMENT[yong]
    if ti_el == yong_el:
        relation, verdict = "比和", "体用比和，事多顺遂，各得其分"
    elif WUXING_SHENG[yong_el] == ti_el:
        relation, verdict = "用生体", "用生体，得外力相助，进则有得"
    elif WUXING_SHENG[ti_el] == yong_el:
        relation, verdict = "体生用", "体生用，我耗于外，宜节力勿贪"
    elif WUXING_KE[yong_el] == ti_el:
        relation, verdict = "用克体", "用克体，外压临身，宜守不宜进"
    else:
        relation, verdict = "体克用", "体克用，我能制事，然劳心费手"

    return {
        "system": "梅花易数",
        "meta": meta,
        "ben": {"name": ben_name, "upper": upper, "lower": lower,
                "gloss": ben_gloss,
                "lines": [_line_text(l) for l in lines]},
        "hu": {"name": hu_name, "upper": hu_up, "lower": hu_low, "gloss": hu_gloss},
        "bian": {"name": bian_name, "lines": [_line_text(l) for l in bian_lines],
                 "gloss": bian_gloss, "upper": bian_up, "lower": bian_low},
        "moving_line": moving,
        "moving_pos": yong_pos,
        "ti_yong": {
            "ti": {"trigram": ti, "element": ti_el, "nature": TRIGRAM_NATURE[ti]},
            "yong": {"trigram": yong, "element": yong_el, "nature": TRIGRAM_NATURE[yong]},
            "relation": relation,
            "verdict": verdict,
        },
        "reading_order": ["先看体用生克定大势", "再看互卦看过程", "末看变卦看落点"],
    }


def _line_text(v):
    return "阳" if v else "阴"


# ---------------------------------------------------------------- 六爻纳甲

def _palace_of(lines):
    """京房八宫：返回 (宫, 宫五行, 第几步, 世爻位)。"""
    key = tuple(lines)
    for pname, head in PALACES:
        seq = _palace_sequence(head)
        for step, (lv, shi) in enumerate(seq):
            if lv == key:
                return pname, PALACE_ELEMENT[pname], STEP_NAMES[step], shi
    raise ValueError("未找到所属宫")


def _palace_sequence(head):
    out = [(head, 6)]
    base = list(head)
    for k in range(1, 6):
        lv = list(base)
        for i in range(k):
            lv[i] ^= 1
        out.append((tuple(lv), SHI_POSITION[k]))
    you = list(base)
    for i in range(5):
        you[i] ^= 1
    you[3] ^= 1
    out.append((tuple(you), 4))
    gui = list(you)
    for i in range(3):
        gui[i] = base[i]
    out.append((tuple(gui), 3))
    return out


def liuyao_toss(seed_note=""):
    """三钱摇卦：字为阴、背为阳，三背为老阳、三字为老阴。"""
    lines, moving = [], []
    detail = []
    for i in range(6):
        coins = [secrets.randbelow(2) for _ in range(3)]   # 1=背(阳面)
        backs = sum(coins)
        if backs == 0:
            v, mv, label = 0, True, "老阴（三字）"
        elif backs == 1:
            v, mv, label = 1, False, "少阳（一背）"
        elif backs == 2:
            v, mv, label = 0, False, "少阴（二背）"
        else:
            v, mv, label = 1, True, "老阳（三背）"
        lines.append(v)
        if mv:
            moving.append(i + 1)
        detail.append({"yao": i + 1, "coins": coins, "label": label,
                       "value": v, "moving": mv})
    return _liuyao_core(lines, moving, detail, seed_note)


def liuyao_by_numbers(numbers, seed_note=""):
    """数字起卦（六爻）：每个数字的奇偶定阴阳，能被 3 整除者作动爻。"""
    lines, moving = [], []
    for i, n in enumerate(numbers[:6]):
        v = n % 2
        lines.append(v)
        if n % 3 == 0:
            moving.append(i + 1)
    detail = [{"yao": i + 1, "number": numbers[i], "value": lines[i],
               "moving": (i + 1) in moving} for i in range(6)]
    return _liuyao_core(lines, moving, detail, seed_note)


def _liuyao_core(lines, moving, detail, note):
    import astro
    now = datetime.now(astro.CST)
    day_idx = cc.day_ganzhi_index(now.date())
    day_gan = cc.ganzhi(day_idx)[0]

    ben_name, ben_gloss, upper, lower = _hexagram_name(lines)
    palace, palace_el, step, shi = _palace_of(lines)
    ying = (shi - 1 + 3) % 6 + 1

    yao_list = []
    gan_in, gan_out = NAJIA_GAN[lower][0], NAJIA_GAN[upper][1]
    zhi_in, zhi_out = NAJIA_ZHI[lower][0], NAJIA_ZHI[upper][1]
    start = LIUSHEN_START[day_gan]
    for i in range(6):
        gan = gan_in if i < 3 else gan_out
        zhi = zhi_in[i] if i < 3 else zhi_out[i - 3]
        el = cc.ZHI_WUXING[cc.ZHI.index(zhi)]
        yao_list.append({
            "position": i + 1,
            "yin_yang": "阳" if lines[i] else "阴",
            "moving": (i + 1) in moving,
            "gan": gan, "zhi": zhi, "element": el,
            "liuqin": _liuqin(palace_el, el),
            "liushen": LIUSHEN[(start + i) % 6],
            "shi_ying": "世" if (i + 1) == shi else ("应" if (i + 1) == ying else ""),
            "kong": zhi in cc.xunkong(day_idx),
        })

    if moving:
        bian_lines = list(lines)
        for p in moving:
            bian_lines[p - 1] ^= 1
        bian_name, bian_gloss, bian_up, bian_low = _hexagram_name(bian_lines)
        bian_yao = []
        for i in range(6):
            if (i + 1) not in moving:
                continue
            zhi = (NAJIA_ZHI[bian_low][0] if i < 3 else NAJIA_ZHI[bian_up][1])[i if i < 3 else i - 3]
            el = cc.ZHI_WUXING[cc.ZHI.index(zhi)]
            bian_yao.append({"position": i + 1, "zhi": zhi, "element": el,
                             "liuqin": _liuqin(palace_el, el)})
        bian = {"name": bian_name, "upper": bian_up, "lower": bian_low,
                "gloss": bian_gloss, "yao": bian_yao}
    else:
        bian = {"name": None, "note": "六爻皆静，无变卦", "yao": []}

    return {
        "system": "六爻纳甲",
        "cast_time": now.strftime("%Y-%m-%d %H:%M"),
        "day_ganzhi": cc.ganzhi(day_idx),
        "xunkong": cc.xunkong(day_idx),
        "note": note,
        "detail": detail,
        "ben": {"name": ben_name, "upper": upper, "lower": lower,
                "gloss": ben_gloss},
        "palace": {"name": palace + "宫", "element": palace_el, "step": step,
                   "shi": shi, "ying": ying},
        "yao": yao_list,
        "moving": moving,
        "bian": bian,
    }
