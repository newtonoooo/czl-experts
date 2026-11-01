#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""确定性多因子打分引擎（仅标准库，无第三方依赖）。

输入：一个 JSON 文件，结构见 references/field-dictionary.md。
输出：风险闸门淘汰表 + 五维加权榜单（JSON 或 Markdown）。

设计原则
--------
1. 纯函数式：同一输入必然得到同一输出，不含随机数、不含当前时间。
2. 缺失即缺失：某维度全字段缺失时该维度记为 None，权重在可用维度间
   等比例放大，绝不按 0 分计入。
3. 打分规则全部落在 references/scoring-rubric.md，本文件是它的可执行版本，
   两者不一致时以 rubric 为准并同步修改本文件。

用法
----
    python rank_universe.py input.json
    python rank_universe.py input.json --format json --top 10
    python rank_universe.py --selftest
"""

import json
import sys

# ---------------------------------------------------------------- 权重与常量

DEFAULT_WEIGHTS = {
    'fundamental': 25.0,
    'technical': 25.0,
    'capital': 20.0,
    'valuation': 15.0,
    'event': 15.0,
}

# 用途为短线观察时的权重调整（技术面 +5，基本面 -5）
SHORT_TERM_WEIGHTS = {
    'fundamental': 20.0,
    'technical': 30.0,
    'capital': 20.0,
    'valuation': 15.0,
    'event': 15.0,
}

DEFAULT_MIN_AMOUNT = 5.0e7      # 近20日均成交额下限（元）
DEFAULT_MAX_LIMIT_UP = 3        # 连续涨停达到该值即触发闸门
DEFAULT_MAX_MISSING = 2         # 关键字段缺失数达到该值即不参与排序
DEFAULT_MIN_COVERAGE = 0.50     # 维度覆盖率下限，低于此值视为"数据不足"

# 关键字段：缺失计数用
KEY_FIELDS = ('price', 'market_cap', 'roe', 'pe_ttm')

ALIASES = {
    'pe': 'pe_ttm', 'pe_ttm': 'pe_ttm', '市盈率': 'pe_ttm',
    'pb': 'pb', '市净率': 'pb',
    'roe': 'roe', '净资产收益率': 'roe',
    'market_cap': 'market_cap', '总市值': 'market_cap', '市值': 'market_cap',
    'revenue_yoy': 'revenue_yoy', '营收增速': 'revenue_yoy',
    'profit_yoy': 'profit_yoy', '净利增速': 'profit_yoy', '净利润增速': 'profit_yoy',
    'gross_margin': 'gross_margin', '毛利率': 'gross_margin',
    'debt_ratio': 'debt_ratio', '资产负债率': 'debt_ratio',
    'dividend_yield': 'dividend_yield', '股息率': 'dividend_yield',
    'pct_from_high_250': 'pct_from_high_250', '距高点': 'pct_from_high_250',
    'vol_ratio': 'vol_ratio', '量比': 'vol_ratio',
    'rsi14': 'rsi14', 'rsi': 'rsi14',
    'ma20': 'ma20', 'ma60': 'ma60',
    'main_net_inflow_1d': 'main_net_inflow_1d', '主力净流入1日': 'main_net_inflow_1d',
    'main_net_inflow_5d': 'main_net_inflow_5d', '主力净流入5日': 'main_net_inflow_5d',
    'turnover': 'turnover', '换手率': 'turnover',
    'amount': 'amount', '成交额': 'amount',
    'limit_up_days': 'limit_up_days', '连板': 'limit_up_days',
    'is_st': 'is_st', 'st': 'is_st',
    'suspended': 'suspended', '停牌': 'suspended',
    'event_score': 'event_score', '事件分': 'event_score',
    'code': 'code', '代码': 'code',
    'name': 'name', '名称': 'name',
    'price': 'price', '现价': 'price', '最新价': 'price',
    'pct_chg': 'pct_chg', '涨跌幅': 'pct_chg',
}


# ---------------------------------------------------------------- 工具函数

def lerp(x, x0, y0, x1, y1):
    """线性插值到 [0,1]，超出区间按端点截断。"""
    if x is None:
        return None
    if x1 == x0:
        return y1
    t = (x - x0) / float(x1 - x0)
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    return y0 + (y1 - y0) * t


def piecewise(x, points):
    """分段线性：points 为 (x, y) 升序列表。"""
    if x is None:
        return None
    pts = sorted(points)
    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        if x0 <= x <= x1:
            return lerp(x, x0, y0, x1, y1)
    return pts[-1][1]


def wavg(pairs):
    """加权平均，自动忽略 None；权重合计为 0 时返回 None。"""
    total_w = 0.0
    acc = 0.0
    for value, weight in pairs:
        if value is None:
            continue
        acc += value * weight
        total_w += weight
    if total_w <= 0:
        return None
    return acc / total_w


def num(v):
    """把输入转成 float；空串/None/无法解析一律返回 None（不猜）。"""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(',', '')
    if not s or s in ('-', '--', 'N/A', 'NA', 'null', 'None'):
        return None
    mult = 1.0
    if s.endswith('亿'):
        mult, s = 1e8, s[:-1]
    elif s.endswith('万'):
        mult, s = 1e4, s[:-1]
    elif s.endswith('%'):
        mult, s = 1.0, s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return None


def norm_stock(raw):
    """把各种写法的字段名归一到标准字段。"""
    out = {}
    for k, v in raw.items():
        key = ALIASES.get(str(k).strip(), str(k).strip())
        out[key] = v
    return out


# ---------------------------------------------------------------- 五个维度

def score_fundamental(s):
    roe = num(s.get('roe'))
    profit_yoy = num(s.get('profit_yoy'))
    revenue_yoy = num(s.get('revenue_yoy'))
    gross_margin = num(s.get('gross_margin'))
    debt_ratio = num(s.get('debt_ratio'))

    roe_v = piecewise(roe, [(0, 0.0), (5, 0.25), (10, 0.55), (15, 0.80), (20, 1.0)])
    profit_v = piecewise(profit_yoy, [(-20, 0.0), (0, 0.30), (15, 0.65), (40, 1.0)])
    revenue_v = piecewise(revenue_yoy, [(-10, 0.0), (0, 0.30), (15, 0.70), (30, 1.0)])
    margin_v = piecewise(gross_margin, [(5, 0.15), (20, 0.50), (50, 1.0)])
    debt_v = piecewise(debt_ratio, [(20, 1.0), (50, 0.65), (70, 0.30), (85, 0.0)])

    return wavg([(roe_v, 0.40), (profit_v, 0.25), (revenue_v, 0.15),
                 (margin_v, 0.10), (debt_v, 0.10)])


def score_technical(s):
    price = num(s.get('price'))
    ma20 = num(s.get('ma20'))
    ma60 = num(s.get('ma60'))
    pct_high = num(s.get('pct_from_high_250'))
    vol_ratio = num(s.get('vol_ratio'))
    rsi = num(s.get('rsi14'))

    if price is None or (ma20 is None and ma60 is None):
        ma_v = None
    elif ma20 is not None and ma60 is not None:
        if price > ma20 > ma60:
            ma_v = 1.0
        elif price > ma20:
            ma_v = 0.70
        elif price > ma60:
            ma_v = 0.40
        else:
            ma_v = 0.15
    elif ma20 is not None:
        ma_v = 0.70 if price > ma20 else 0.20
    else:
        ma_v = 0.40 if price > ma60 else 0.20

    high_v = piecewise(pct_high, [(-70, 0.15), (-50, 0.35), (-30, 0.70),
                                  (-15, 1.0), (-5, 0.55), (0, 0.20)])
    vol_v = piecewise(vol_ratio, [(0.5, 0.15), (1.0, 0.35), (1.5, 0.75),
                                  (2.5, 1.0), (4.0, 0.60), (6.0, 0.30)])
    rsi_v = piecewise(rsi, [(20, 0.20), (30, 0.60), (45, 1.0),
                            (60, 0.80), (70, 0.40), (80, 0.15)])

    return wavg([(ma_v, 0.30), (high_v, 0.25), (vol_v, 0.15), (rsi_v, 0.30)])


def score_capital(s):
    flow5 = num(s.get('main_net_inflow_5d'))
    flow1 = num(s.get('main_net_inflow_1d'))
    turnover = num(s.get('turnover'))
    mcap = num(s.get('market_cap'))

    # 5日主力净流入占市值比例（市值单位：亿元）
    flow5_v = None
    if flow5 is not None and mcap:
        ratio = flow5 / (mcap * 1e8) * 100.0        # 百分比
        flow5_v = piecewise(ratio, [(-1.0, 0.0), (0, 0.30), (0.5, 0.80), (1.5, 1.0)])
    turn_v = piecewise(turnover, [(0.3, 0.15), (1.0, 0.35), (3.0, 0.80),
                                  (8.0, 1.0), (15.0, 0.60), (25.0, 0.20)])
    flow1_v = None
    if flow1 is not None:
        flow1_v = 0.80 if flow1 > 0 else (0.35 if flow1 == 0 else 0.15)

    return wavg([(flow5_v, 0.55), (turn_v, 0.25), (flow1_v, 0.20)])


def score_valuation(s):
    pe = num(s.get('pe_ttm'))
    pb = num(s.get('pb'))
    dy = num(s.get('dividend_yield'))

    if pe is None:
        pe_v = None
    elif pe <= 0:
        pe_v = 0.05
    else:
        pe_v = piecewise(pe, [(5, 1.0), (15, 0.95), (25, 0.70),
                              (40, 0.40), (60, 0.18), (100, 0.05)])
    pb_v = piecewise(pb, [(0.5, 1.0), (1.5, 0.85), (3.0, 0.55),
                          (5.0, 0.30), (8.0, 0.10)])
    dy_v = piecewise(dy, [(0, 0.20), (1.5, 0.60), (3.0, 0.90), (5.0, 1.0)])

    return wavg([(pe_v, 0.45), (pb_v, 0.30), (dy_v, 0.25)])


def score_event(s):
    es = num(s.get('event_score'))
    if es is None:
        return None
    if es > 1.0:
        es = es / 100.0
    return max(0.0, min(1.0, es))


DIMENSIONS = (
    ('fundamental', '基本面', score_fundamental),
    ('technical', '技术面', score_technical),
    ('capital', '资金面', score_capital),
    ('valuation', '估值', score_valuation),
    ('event', '事件', score_event),
)


def grade(v):
    if v is None:
        return 'N/A'
    if v >= 0.70:
        return '强'
    if v >= 0.45:
        return '中性'
    return '弱'


# ---------------------------------------------------------------- 风险闸门

def run_gate(s, cfg, coverage=None):
    """返回 (是否淘汰, 原因列表)。淘汰即不参与排序。"""
    reasons = []
    if s.get('is_st') in (True, 'true', '1', 1, '是', 'ST'):
        reasons.append('ST/退市风险')
    if s.get('suspended') in (True, 'true', '1', 1, '是'):
        reasons.append('停牌')
    amount = num(s.get('amount'))
    min_amount = cfg.get('min_amount', DEFAULT_MIN_AMOUNT)
    if amount is not None and amount < min_amount:
        reasons.append('成交额 %s元 低于下限 %s元' % (fmt_num(amount), fmt_num(min_amount)))
    lud = num(s.get('limit_up_days'))
    max_lu = cfg.get('max_limit_up', DEFAULT_MAX_LIMIT_UP)
    if lud is not None and lud >= max_lu:
        reasons.append('连续涨停 %d 日' % int(lud))

    missing = [f for f in KEY_FIELDS if num(s.get(f)) is None]
    if len(missing) >= cfg.get('max_missing', DEFAULT_MAX_MISSING):
        reasons.append('关键字段缺失：%s' % '、'.join(missing))
    min_cov = cfg.get('min_coverage', DEFAULT_MIN_COVERAGE)
    if coverage is not None and coverage < min_cov:
        reasons.append('维度覆盖率 %.0f%% 低于下限 %.0f%%' % (coverage * 100, min_cov * 100))
    return (len(reasons) > 0), reasons


def fmt_num(v):
    if v is None:
        return 'N/A'
    if abs(v) >= 1e8:
        return '%.2f亿' % (v / 1e8)
    if abs(v) >= 1e4:
        return '%.2f万' % (v / 1e4)
    return '%.2f' % v


def compute_warnings(s):
    """风险标注（不淘汰，只提示），对应 S3 的"降级并标注"。"""
    warns = []
    pct_high = num(s.get('pct_from_high_250'))
    rsi = num(s.get('rsi14'))
    pe = num(s.get('pe_ttm'))
    lud = num(s.get('limit_up_days'))
    amount = num(s.get('amount'))
    if pct_high is not None and pct_high > -3:
        warns.append('贴近250日高点（%.1f%%）' % pct_high)
    if rsi is not None and rsi >= 75:
        warns.append('RSI %.0f 偏热' % rsi)
    if pe is not None and pe > 60:
        warns.append('PE-TTM %.1f 偏高' % pe)
    if lud is not None and lud > 0:
        warns.append('近期有 %d 个涨停' % int(lud))
    if amount is not None and amount < 1.5e8:
        warns.append('成交额 %s 偏低' % fmt_num(amount))
    return warns


# ---------------------------------------------------------------- 主流程

def rank(payload, top=None):
    cfg = dict(payload.get('settings') or {})
    purpose = payload.get('purpose') or cfg.get('purpose') or 'mid_term_tracking'
    weights = cfg.get('weights') or (SHORT_TERM_WEIGHTS if purpose == 'short_term'
                                     else DEFAULT_WEIGHTS)
    total_w = sum(weights.get(k, 0) for k, _, _ in DIMENSIONS)
    if total_w <= 0:
        raise ValueError('weights 合计必须大于 0')

    passed, gated = [], []
    for raw in payload.get('stocks', []):
        s = norm_stock(raw)
        dims = {}
        for key, _label, fn in DIMENSIONS:
            dims[key] = fn(s)
        available_w = sum(weights.get(k, 0) for k in dims if dims[k] is not None)
        coverage = available_w / total_w
        dead, reasons = run_gate(s, cfg, coverage)
        if available_w <= 0:
            score = None
        else:
            acc = sum(dims[k] * weights.get(k, 0) for k in dims if dims[k] is not None)
            score = acc / available_w * 100.0
        row = {
            'code': s.get('code'),
            'name': s.get('name'),
            'price': num(s.get('price')),
            'pct_chg': num(s.get('pct_chg')),
            'score': None if score is None else round(score, 2),
            'coverage': round(coverage, 4),
            'dims': {k: (None if dims[k] is None else round(dims[k], 4)) for k in dims},
            'dims_score': {k: (None if dims[k] is None
                               else round(dims[k] * weights.get(k, 0), 2)) for k in dims},
            'grades': {k: grade(dims[k]) for k in dims},
            'available': {k: (dims[k] is not None) for k in dims},
            'gate_reasons': reasons,
            'warnings': compute_warnings(s),
        }
        if dead:
            gated.append(row)
        else:
            passed.append(row)

    # 排序：总分降序 → 资金面 → 距高点回撤（越接近高点越靠后）
    def sort_key(r):
        pct_high = num(norm_stock_by_code(payload, r['code']).get('pct_from_high_250'))
        return (-(r['score'] if r['score'] is not None else -1),
                -(r['dims']['capital'] or 0),
                -(pct_high if pct_high is not None else -999))

    passed.sort(key=sort_key)
    gated.sort(key=lambda r: r['score'] if r['score'] is not None else -1, reverse=True)
    for i, r in enumerate(passed, 1):
        r['rank'] = i
    if top:
        passed = passed[:top]

    return {
        'as_of': payload.get('as_of'),
        'source': payload.get('source'),
        'purpose': purpose,
        'weights': weights,
        'counts': {'input': len(payload.get('stocks', [])),
                   'gated': len(gated), 'ranked': len(passed)},
        'ranked': passed,
        'gated': gated,
    }


def norm_stock_by_code(payload, code):
    for raw in payload.get('stocks', []):
        s = norm_stock(raw)
        if s.get('code') == code:
            return s
    return {}


# ---------------------------------------------------------------- 输出

def to_markdown(res):
    L = []
    L.append('### 漏斗台账')
    c = res['counts']
    L.append('候选人 %d → 闸门淘汰 %d → 参与排序 %d' % (c['input'], c['gated'], c['ranked']))
    L.append('')
    L.append('### 榜单（权重 %s）' % ', '.join('%s %g' % (k, v) for k, v in res['weights'].items()))
    L.append('')
    L.append('| 位次 | 代码 | 名称 | 现价 | 涨跌 | 总分 | 基本面 | 技术面 | 资金面 | 估值 | 事件 | 覆盖 |')
    L.append('|---|---|---|---|---|---|---|---|---|---|---|---|')
    for r in res['ranked']:
        dp = r['dims_score']
        L.append('| %d | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %.0f%% |' % (
            r['rank'], r['code'], r['name'],
            '-' if r['price'] is None else '%.2f' % r['price'],
            '-' if r['pct_chg'] is None else '%+.2f%%' % r['pct_chg'],
            '-' if r['score'] is None else '%.2f' % r['score'],
            '-' if dp['fundamental'] is None else '%.1f' % dp['fundamental'],
            '-' if dp['technical'] is None else '%.1f' % dp['technical'],
            '-' if dp['capital'] is None else '%.1f' % dp['capital'],
            '-' if dp['valuation'] is None else '%.1f' % dp['valuation'],
            '-' if dp['event'] is None else '%.1f' % dp['event'],
            r['coverage'] * 100))
    warn_rows = [r for r in res['ranked'] if r.get('warnings')]
    if warn_rows:
        L.append('')
        L.append('### 风险标注（不淘汰，仅提示）')
        for r in warn_rows:
            L.append('- %s %s：%s' % (r['code'], r['name'], '、'.join(r['warnings'])))
    if res['gated']:
        L.append('')
        L.append('### 闸门淘汰表')
        L.append('')
        L.append('| 代码 | 名称 | 原因 |')
        L.append('|---|---|---|')
        for r in res['gated']:
            L.append('| %s | %s | %s |' % (r['code'], r['name'], '；'.join(r['gate_reasons'])))
    return '\n'.join(L)


# ---------------------------------------------------------------- 自检

def selftest():
    sample = {
        'as_of': '2026-10-28',
        'source': 'selftest',
        'purpose': 'mid_term_tracking',
        'stocks': [
            {'code': '000001', 'name': '质量优选', 'price': 20.0, 'pct_chg': 1.5,
             'market_cap': 400, 'pe_ttm': 18.0, 'pb': 2.0, 'roe': 18.0,
             'revenue_yoy': 20.0, 'profit_yoy': 25.0, 'gross_margin': 45.0,
             'debt_ratio': 35.0, 'dividend_yield': 2.0, 'ma20': 19.5, 'ma60': 18.6,
             'pct_from_high_250': -15.0, 'vol_ratio': 1.6, 'rsi14': 48,
             'main_net_inflow_5d': 2.0e8, 'main_net_inflow_1d': 5.0e7,
             'turnover': 3.5, 'amount': 8.0e8, 'limit_up_days': 0,
             'is_st': False, 'suspended': False, 'event_score': 60},
            {'code': '000002', 'name': '高位过热', 'price': 50.0, 'pct_chg': 9.9,
             'market_cap': 300, 'pe_ttm': 75.0, 'pb': 9.0, 'roe': 6.0,
             'revenue_yoy': 2.0, 'profit_yoy': -5.0, 'gross_margin': 18.0,
             'debt_ratio': 68.0, 'dividend_yield': 0.2, 'ma20': 45.0, 'ma60': 40.0,
             'pct_from_high_250': -1.0, 'vol_ratio': 5.0, 'rsi14': 82,
             'main_net_inflow_5d': -1.0e8, 'main_net_inflow_1d': -2.0e7,
             'turnover': 18.0, 'amount': 9.0e8, 'limit_up_days': 4,
             'is_st': False, 'suspended': False, 'event_score': 90},
            {'code': '000003', 'name': 'ST风险', 'price': 3.0, 'pct_chg': 2.0,
             'market_cap': 30, 'pe_ttm': -8.0, 'pb': 1.2, 'roe': -12.0,
             'amount': 2.0e7, 'is_st': True, 'suspended': False},
            {'code': '000004', 'name': '数据不全', 'price': 12.0,
             'pct_chg': 0.5, 'turnover': 2.0},
            {'code': '000005', 'name': '中性样本', 'price': 15.0, 'pct_chg': -0.8,
             'market_cap': 180, 'pe_ttm': 28.0, 'pb': 3.0, 'roe': 10.0,
             'revenue_yoy': 8.0, 'profit_yoy': 6.0, 'gross_margin': 25.0,
             'debt_ratio': 52.0, 'dividend_yield': 1.0, 'ma20': 15.2, 'ma60': 15.0,
             'pct_from_high_250': -35.0, 'vol_ratio': 1.0, 'rsi14': 38,
             'main_net_inflow_5d': 1.0e7, 'main_net_inflow_1d': -3.0e6,
             'turnover': 1.5, 'amount': 3.0e8, 'limit_up_days': 0,
             'is_st': False, 'suspended': False},
        ],
    }
    ok = True
    r1 = rank(json.loads(json.dumps(sample)))
    r2 = rank(json.loads(json.dumps(sample)))

    def check(cond, msg):
        nonlocal ok
        print(('PASS  ' if cond else 'FAIL  ') + msg)
        if not cond:
            ok = False

    # 权重合计
    check(abs(sum(DEFAULT_WEIGHTS.values()) - 100.0) < 1e-9, '默认权重合计 = 100')

    # 确定性
    check(json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True), '两次运行结果完全一致')

    # 闸门
    gated_codes = sorted(x['code'] for x in r1['gated'])
    check(gated_codes == ['000002', '000003', '000004'],
          '闸门淘汰 000002(连板)/000003(ST+低成交)/000004(缺字段+覆盖率)，实际 %s' % gated_codes)

    # 覆盖率闸门
    r4 = [x for x in r1['gated'] if x['code'] == '000004'][0]
    check(any('覆盖率' in s for s in r4['gate_reasons']),
          '低覆盖率标的被覆盖率闸门拦下，原因：%s' % '；'.join(r4['gate_reasons']))

    # 排序合理：质量优选 应高于 中性样本
    codes = [x['code'] for x in r1['ranked']]
    check(codes == ['000001', '000005'], '排序为 000001 > 000005，实际 %s' % codes)

    # 缺失维度不补零：000005 无 event_score，事件维应为 None 且覆盖率 < 1
    r5 = [x for x in r1['ranked'] if x['code'] == '000005'][0]
    check(r5['dims']['event'] is None, '事件维缺失记为 None（未补 0）')
    check(abs(r5['coverage'] - 0.85) < 1e-6, '权重按可用维度重分配，覆盖率 = 0.85，实际 %.4f' % r5['coverage'])

    # 分数区间
    check(all(0 <= x['score'] <= 100 for x in r1['ranked'] if x['score'] is not None),
          '所有分数落在 0—100')

    # 单位解析
    check(num('3.5亿') == 3.5e8 and num('1200万') == 1.2e7 and num('--') is None,
          '单位解析：亿/万/占位符')

    # 短线权重切换
    short = json.loads(json.dumps(sample))
    short['purpose'] = 'short_term'
    r3 = rank(short)
    check(r3['weights']['technical'] == 30.0 and r3['weights']['fundamental'] == 20.0,
          '短线模式权重切换（技术 30 / 基本面 20）')

    print('')
    print('SELFTEST ' + ('PASSED' if ok else 'FAILED'))
    return 0 if ok else 1


# ---------------------------------------------------------------- 入口

def main():
    args = sys.argv[1:]
    if '--selftest' in args:
        return selftest()
    if not args:
        print(__doc__)
        return 2
    path = args[0]
    fmt = 'md'
    top = None
    i = 1
    while i < len(args):
        if args[i] == '--format':
            fmt = args[i + 1]
            i += 2
        elif args[i] == '--top':
            top = int(args[i + 1])
            i += 2
        else:
            i += 1
    payload = json.load(open(path, encoding='utf-8'))
    res = rank(payload, top=top)
    if fmt == 'json':
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(to_markdown(res))
    return 0


if __name__ == '__main__':
    sys.exit(main())
