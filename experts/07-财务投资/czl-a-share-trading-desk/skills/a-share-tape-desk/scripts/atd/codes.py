"""股票代码解析与交易规则。

只接受沪深 A 股：60/68 开头归沪市，00/30 开头归深市。
北交所（8/4/920 开头）、港股、美股一律拒绝，并给出明确原因。
"""

import re

MARKET_SH = "SH"
MARKET_SZ = "SZ"

BOARD_MAIN = "主板"
BOARD_GEM = "创业板"      # 300 / 301
BOARD_STAR = "科创板"      # 688 / 689


class CodeError(ValueError):
    """代码不在服务范围内。"""


def _to_prefixed(digits, market):
    return ("sh" if market == MARKET_SH else "sz") + digits


def parse(raw):
    """把用户输入解析成结构化代码对象。

    返回 dict：
        code      6 位数字
        market    SH / SZ
        board     主板 / 创业板 / 科创板
        prefixed  带交易所前缀的小写代码，如 sh600519
        secid     东方财富风格 secid，如 1.600519
        limit_pct 涨跌幅限制比例（未考虑 ST，ST 需调用 limit_ratio）
    """
    if raw is None:
        raise CodeError("代码为空")
    text = str(raw).strip().upper()
    text = text.replace("．", ".").replace(" ", "")

    # 显式境外市场：直接拒绝，不做猜测
    if ".HK" in text or ".US" in text or text.startswith("HK") or re.match(r"^[A-Z]{2,6}$", text):
        raise CodeError("仅支持沪深A股，港股与美股不在服务范围")

    m = re.search(r"(\d{6})", text)
    if not m:
        raise CodeError("无法识别6位股票代码：%s" % raw)
    digits = m.group(1)

    if digits.startswith(("60", "68")):
        market = MARKET_SH
        secid_prefix = "1"
    elif digits.startswith(("00", "30")):
        market = MARKET_SZ
        secid_prefix = "0"
    elif digits.startswith(("8", "4", "92")):
        raise CodeError("北交所代码 %s 不在服务范围（仅沪深A股）" % digits)
    else:
        raise CodeError("代码 %s 不属于沪深A股（需 60/68/00/30 开头）" % digits)

    if digits.startswith("68"):
        board = BOARD_STAR
    elif digits.startswith("30"):
        board = BOARD_GEM
    else:
        board = BOARD_MAIN

    return {
        "code": digits,
        "market": market,
        "board": board,
        "prefixed": _to_prefixed(digits, market),
        "secid": "%s.%s" % (secid_prefix, digits),
        "limit_pct": 0.20 if board in (BOARD_GEM, BOARD_STAR) else 0.10,
    }


def is_st(name):
    """名称是否含风险警示标记。"""
    if not name:
        return False
    upper = str(name).upper().replace(" ", "")
    return ("ST" in upper) or ("退" in upper) or ("PT" in upper)


def limit_ratio(info, name=None):
    """涨跌幅限制比例（小数）。

    主板 10%，创业板/科创板 20%；主板 ST 为 5%，创业板/科创板 ST 仍为 20%。
    """
    if is_st(name) and info["board"] == BOARD_MAIN:
        return 0.05
    return info["limit_pct"]


def round_price(value):
    """A股报价四舍五入到分。"""
    return float(int(round(float(value) * 100 + 1e-9))) / 100.0


def limit_prices(prev_close, ratio):
    """按昨收与限制比例计算涨停价、跌停价。"""
    prev = float(prev_close)
    up = round_price(prev * (1 + ratio))
    down = round_price(prev * (1 - ratio))
    return up, down


def describe(info, name=None):
    """一行中文描述，用于报告表头。"""
    ratio = limit_ratio(info, name)
    tag = "ST" if is_st(name) else "普通"
    return "%s（%s·%s·%s·涨跌幅±%d%%）" % (
        name or "",
        info["code"],
        info["market"],
        info["board"] + tag,
        int(round(ratio * 100)),
    )
