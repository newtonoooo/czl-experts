#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""listing_audit.py — 亚马逊 Listing 审计引擎（纯标准库，零第三方依赖）

五个子命令：
    lint        文案体检：字符预算、全大写、符号、堆砌、重复
    compliance  合规放行：词层 + 类目层 + 市场层，输出 GO / CONDITIONAL / BLOCKED
    score       AI 推荐就绪度：七维加权 0-100，逐项扣分
    keywords    关键词预算：去重、分组、按位置分配字符预算
    report      以上四项合并为一份 Markdown 报告

退出码：0 = 通过；1 = 有警告；2 = 有阻断。

用法示例：
    python listing_audit.py lint --listing x.json --market US
    python listing_audit.py compliance --listing x.json --market DE --category juvenile_products
    python listing_audit.py report --listing x.json --market US --category electronics --out r.md

本工具是写作期自查工具，不构成法律意见，也不是对平台规则的官方解释。
"""

import argparse
import json
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REF_DIR = os.path.join(os.path.dirname(BASE_DIR), 'references')

# 允许出现的全大写缩写（不视为"全大写滥用"）
ACRONYMS = {
    'USB', 'LED', 'LCD', 'ABS', 'PVC', 'PET', 'PP', 'PE', 'PU', 'TPU', 'EVA', 'PS',
    'BPA', 'GPS', 'FCC', 'CE', 'UKCA', 'ROHS', 'REACH', 'LFGB', 'FDA', 'CPSC',
    'UV', 'SPF', 'XL', 'XXL', 'XXXL', 'CM', 'MM', 'ML', 'KG', 'OZ', 'LB', 'FT',
    'IP', 'IPX', 'PD', 'QC', 'TWS', 'ANC', 'HD', 'RGB', 'DC', 'AC', 'BT', 'NFC',
    'PSE', 'RCM', 'WEEE', 'GPSR', 'EPR', 'UIN', 'ASTM', 'EN', 'ISO', 'MSDS',
    'OEM', 'ODM', 'SKU', 'ASIN', 'FAQ', 'DIY', 'SPF', 'TBD', 'AUX', 'HDMI',
}

STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'for', 'with', 'of', 'to', 'in', 'on', 'at',
    'by', 'from', 'is', 'are', 'be', 'as', 'it', 'its', 'this', 'that', 'your',
    'you', 'our', 'we', 'not', 'no', 'all', 'can', 'will', 'has', 'have',
    'der', 'die', 'das', 'und', 'oder', 'für', 'mit', 'von', 'zu', 'im', 'in',
    'le', 'la', 'les', 'et', 'ou', 'pour', 'avec', 'de', 'du', 'des',
    'el', 'los', 'las', 'y', 'o', 'para', 'con', 'del',
}


# ---------------------------------------------------------------- 基础工具

def read_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_rules():
    return read_json(os.path.join(REF_DIR, 'marketplace-rules.json'))


def load_matrix():
    return read_json(os.path.join(REF_DIR, 'compliance-matrix.json'))


def load_listing(path):
    data = read_json(path)
    if not isinstance(data, dict):
        raise SystemExit('listing 文件必须是 JSON 对象')
    data.setdefault('title', '')
    data.setdefault('bullets', [])
    data.setdefault('description', '')
    data.setdefault('search_terms', '')
    data.setdefault('attributes', {})
    data.setdefault('keywords', {})
    if not isinstance(data['bullets'], list):
        raise SystemExit('bullets 必须是数组')
    return data


def byte_len(text):
    return len(text.encode('utf-8'))


def norm_words(text):
    """小写、去标点、切词（保留数字与连字符内部结构）。"""
    text = text.lower()
    text = re.sub(r'[^\w\u4e00-\u9fff]+', ' ', text)
    return [w for w in text.split() if w]


def finding(level, code, where, msg, fix=''):
    return {'level': level, 'code': code, 'where': where, 'msg': msg, 'fix': fix}


def worst_level(findings):
    if any(f['level'] == 'BLOCK' for f in findings):
        return 'BLOCK'
    if any(f['level'] == 'WARN' for f in findings):
        return 'WARN'
    if any(f['level'] == 'INFO' for f in findings):
        return 'INFO'
    return 'PASS'


def exit_code(findings):
    w = worst_level(findings)
    return {'BLOCK': 2, 'WARN': 1, 'INFO': 0, 'PASS': 0}[w]


# ---------------------------------------------------------------- lint

def _title_allcaps(title, min_len, ratio_max, brand=''):
    """全大写词检测。品牌名本身常为全大写，按惯例豁免。"""
    words = re.findall(r"[A-Za-z][A-Za-z'\-]*", title)
    if not words:
        return [], 0.0
    brand_low = brand.strip().lower()
    caps = []
    for w in words:
        core = w.replace('-', '').replace("'", '')
        if len(core) < min_len:
            continue
        if brand_low and core.lower() == brand_low:
            continue
        if core.upper() == core and core.lower() != core:
            if core.upper() not in ACRONYMS:
                caps.append(w)
    ratio = len(caps) / float(len(words))
    return caps, ratio


def _duplicate_phrases(texts, n=3, limit=4, min_count=4):
    """重复 n-gram 检测。阈值 4 次：关键词在标题+五点+描述各出现一次属正常落位，
    达到 4 次才具备堆砌特征。"""
    tokens = []
    for t in texts:
        tokens.extend(norm_words(t))
    grams = {}
    for i in range(len(tokens) - n + 1):
        g = ' '.join(tokens[i:i + n])
        grams[g] = grams.get(g, 0) + 1
    dup = [(g, c) for g, c in grams.items() if c >= min_count]
    dup.sort(key=lambda x: (-x[1], -len(x[0])))
    return dup[:limit]


def lint(listing, market):
    rules = load_rules()
    mk = rules['marketplaces'].get(market)
    if not mk:
        raise SystemExit('未知站点 %s，可用：%s' % (market, ', '.join(rules['marketplaces'])))
    chk = rules['copy_checks']
    out = []

    title = listing['title']
    bullets = listing['bullets']
    desc = listing['description']
    st = listing['search_terms']

    # 标题长度
    t_max = mk['title']['hard_max']
    t_soft = mk['title']['soft_max']
    n = len(title)
    if n > t_max:
        out.append(finding('BLOCK', 'TITLE_OVER_HARD', 'title',
                           '标题 %d 字符，超过 %s 站硬上限 %d，会被截断或压制' % (n, market, t_max),
                           '删掉重复属性词，把超出部分移到五点或后台搜索词'))
    elif n > t_soft:
        out.append(finding('INFO', 'TITLE_OVER_SOFT', 'title',
                           '标题 %d 字符，超过移动端完整显示阈值 %d' % (n, t_soft),
                           '若非类目模板要求，建议压到 %d 以内' % t_soft))

    # 全大写
    caps, ratio = _title_allcaps(title, chk['all_caps_word_min_len'],
                                 chk['all_caps_ratio_max'],
                                 listing.get('brand') or '')
    if caps:
        out.append(finding('WARN', 'TITLE_ALL_CAPS', 'title',
                           '标题含全大写单词：%s（占比 %.0f%%）' % (', '.join(caps[:5]), ratio * 100),
                           '改为首字母大写；缩写若为通用写法请确认在白名单内'))

    # 符号
    hits = [s for s in chk['banned_symbols'] if s in title or s in desc
            or any(s in b for b in bullets)]
    if hits:
        out.append(finding('WARN', 'COPY_SYMBOL', 'title/bullets/description',
                           '含非标准字符：%s' % ' '.join(hits),
                           '删除装饰性符号，规格信息用文字表达'))

    # 五点
    cnt = len(bullets)
    if cnt != mk['bullets']['count']:
        out.append(finding('INFO', 'BULLET_COUNT', 'bullets',
                           '五点数量为 %d，标准位为 %d' % (cnt, mk['bullets']['count']),
                           '补齐或合并到标准条数'))
    for i, b in enumerate(bullets, 1):
        if len(b) > mk['bullets']['max_chars']:
            out.append(finding('BLOCK', 'BULLET_OVER', 'bullets[%d]' % i,
                               '第 %d 条 %d 字符，超过上限 %d' % (i, len(b), mk['bullets']['max_chars']),
                               '拆成两条或删掉重复证据'))
        elif len(b) < mk['bullets']['min_chars']:
            out.append(finding('INFO', 'BULLET_THIN', 'bullets[%d]' % i,
                               '第 %d 条仅 %d 字符，信息量偏低' % (i, len(b)),
                               '补一个带单位的证据或一个具体场景'))

    # 描述
    if len(desc) > mk['description']['max_chars']:
        out.append(finding('BLOCK', 'DESC_OVER', 'description',
                           '描述 %d 字符，超过上限 %d' % (len(desc), mk['description']['max_chars']),
                           '压缩使用步骤或移入 A+ 模块'))

    # 后台搜索词
    st_bytes = byte_len(st)
    if st_bytes > mk['search_terms']['max_bytes']:
        out.append(finding('BLOCK', 'SEARCH_TERMS_OVER', 'search_terms',
                           '后台搜索词 %d 字节，超过上限 %d' % (st_bytes, mk['search_terms']['max_bytes']),
                           '删掉与标题重复的词，优先保留长尾词'))

    # 重复短语
    dup = _duplicate_phrases([title] + bullets + [desc])
    if dup:
        out.append(finding('WARN', 'COPY_DUPLICATE', 'title/bullets/description',
                           '重复短语：%s' % '；'.join('%s ×%d' % (g, c) for g, c in dup),
                           '同一短语只保留一处，重复会稀释关键词权重'))

    # 标题词频堆砌
    if title:
        freq = {}
        for w in norm_words(title):
            if len(w) >= 3 and w not in STOPWORDS:
                freq[w] = freq.get(w, 0) + 1
        top = sorted(freq.items(), key=lambda x: -x[1])[:3]
        over = [x for x in top if x[1] > chk['stuffing_repeat_max']]
        if over:
            out.append(finding('WARN', 'TITLE_STUFFING', 'title',
                               '标题词频偏高：%s' % '，'.join('%s ×%d' % x for x in over),
                               '同义词堆砌会被判为关键词滥用，保留最常用的那个'))

    # 标题缺规格数字
    if not re.search(r'\d', title):
        out.append(finding('INFO', 'TITLE_NO_SPEC', 'title',
                           '标题没有任何数字规格',
                           '补一个买家最关心的规格（容量/尺寸/数量/功率）'))

    # 标题格式细节
    if title.strip().endswith('.'):
        out.append(finding('INFO', 'TITLE_PERIOD', 'title', '标题以句号结尾', '删除结尾标点'))
    if '  ' in title:
        out.append(finding('INFO', 'TITLE_SPACES', 'title', '标题含连续空格', '清理多余空格'))

    # 品牌位
    brand = (listing.get('brand') or '').strip()
    if not brand:
        out.append(finding('INFO', 'NO_BRAND', 'brand',
                           '未提供品牌，标题品牌位留空',
                           '无品牌就留空，不要编造品牌名'))

    if any(f['level'] == 'BLOCK' for f in out):
        verdict = 'FAIL'
    elif any(f['level'] == 'WARN' for f in out):
        verdict = 'WARN'
    else:
        verdict = 'PASS'
    return {
        'check': 'lint',
        'market': market,
        'metrics': {
            'title_chars': len(title),
            'title_hard_max': t_max,
            'title_soft_max': t_soft,
            'bullet_count': cnt,
            'bullet_chars': [len(b) for b in bullets],
            'description_chars': len(desc),
            'search_terms_bytes': st_bytes,
        },
        'verdict': verdict,
        'findings': out,
        'exit_code': exit_code(out),
    }


# ---------------------------------------------------------------- compliance

def _scan_claims(text, claims):
    hits = []
    for rule in claims:
        for pat in rule['patterns']:
            try:
                for m in re.finditer(pat, text, re.IGNORECASE):
                    frag = m.group(0)
                    if not frag.strip():
                        continue
                    hits.append({
                        'level': rule['severity'],
                        'code': rule['id'],
                        'label': rule['label'],
                        'matched': frag,
                        'why': rule['why'],
                        'fix': rule['fix'],
                    })
                    break
            except re.error:
                continue
    return hits


def _dedupe_items(items):
    """同一义务可能同时出现在类目层与市场层（如 GPSR），按 dedupe 键或标签前缀合并。"""
    out = []
    seen = set()
    for it in items:
        key = it.get('dedupe') or it['label'][:6].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def compliance(listing, market, category):
    matrix = load_matrix()
    text = ' \n '.join([listing['title']] + list(listing['bullets'])
                       + [listing['description'], listing['search_terms']])

    claim_hits = _scan_claims(text, matrix['claims'])

    # 同类规则去重（同 code 只报一次，保留首个命中）
    seen = set()
    deduped = []
    for h in claim_hits:
        if h['code'] in seen:
            continue
        seen.add(h['code'])
        deduped.append(h)

    items = []
    cat = matrix['categories'].get(category)
    if cat:
        for req in cat['requires'].get(market, []):
            items.append({
                'level': req['severity'],
                'code': 'CAT-%s-%s' % (category.upper(), market),
                'label': req['item'],
                'matched': '-',
                'why': req['why'],
                'fix': req['fix'],
                'dedupe': req.get('dedupe'),
            })
    mk = matrix['markets'].get(market)
    if mk:
        for ob in mk['obligations']:
            items.append({
                'level': ob['severity'],
                'code': 'MKT-%s' % market,
                'label': ob['item'],
                'matched': '-',
                'why': ob['why'],
                'fix': ob['fix'],
                'dedupe': ob.get('dedupe'),
            })

    all_items = deduped + _dedupe_items(items)
    blocks = [x for x in all_items if x['level'] == 'BLOCK']
    conds = [x for x in all_items if x['level'] == 'CONDITION']
    infos = [x for x in all_items if x['level'] == 'INFO']

    if blocks:
        verdict = 'BLOCKED'
    elif conds:
        verdict = 'CONDITIONAL'
    else:
        verdict = 'GO'

    return {
        'check': 'compliance',
        'market': market,
        'category': category,
        'category_known': bool(cat),
        'verdict': verdict,
        'counts': {'BLOCK': len(blocks), 'CONDITION': len(conds), 'INFO': len(infos)},
        'blocking': blocks,
        'conditional': conds,
        'informational': infos,
        'exit_code': 2 if blocks else (1 if conds else 0),
        'disclaimer': '本判定基于配置规则与所提供文本，不构成法律意见，最终以亚马逊后台与当地法规为准。',
    }


# ---------------------------------------------------------------- score

SCENARIO_BANK = {
    'indoor': ['indoor', 'home', 'office', 'kitchen', '室内', '家用', '办公室', '厨房'],
    'outdoor': ['outdoor', 'camping', 'hiking', 'beach', 'garden', '户外', '露营', '徒步'],
    'travel': ['travel', 'commute', 'commuter', 'trip', 'car', 'portable', '旅行', '通勤', '车载', '便携'],
    'gym': ['gym', 'workout', 'fitness', 'running', '健身', '运动', '跑步'],
    'gift': ['gift', 'present', 'christmas', 'birthday', '礼物', '送礼'],
}

AUDIENCE_BANK = {
    'baby': ['baby', 'infant', 'newborn', '婴儿', '宝宝'],
    'kids': ['kid', 'kids', 'child', 'children', 'toddler', '儿童', '孩子'],
    'adult': ['adult', 'men', 'women', 'unisex', '成人', '男士', '女士'],
    'senior': ['senior', 'elderly', '老人', '老年'],
    'pet': ['pet', 'dog', 'cat', '宠物', '猫', '狗'],
}

QUESTION_PROBES = [
    ('尺寸多大', ['cm', 'mm', 'inch', 'inches', '尺寸', '长', '宽', '高', 'dimension']),
    ('什么材质', ['silicone', 'cotton', 'abs', 'stainless', 'steel', 'aluminum', 'nylon',
                  'polyester', 'leather', 'glass', 'silk', '硅胶', '棉', '不锈钢', '材质']),
    ('多重/容量', ['ml', 'oz', 'kg', 'gram', ' lb', 'l ', 'liter', 'litre', '重量', '容量', '克']),
    ('怎么清洁', ['wash', 'clean', 'dishwasher', 'wipe', '清洗', '水洗', '机洗', '清洁']),
    ('适合谁', ['for kids', 'for adults', 'for women', 'for men', 'for people',
                  'for anyone', 'designed for', '适合', '适用人群']),
    ('包装里有什么', ['includes', 'package', 'pack of', '1 x', '2 x', '含', '配件', '套装']),
    ('兼容什么', ['compatible', 'fits', 'works with', '适用', '兼容', '适配']),
    ('安全吗', ['safe', 'safety', 'rounded', 'non-toxic', 'bpa', '安全', '圆角', '无毒']),
    ('怎么用', ['step', 'how to', 'install', 'assembly', '使用步骤', '安装']),
    ('耐用吗', ['durable', 'tear', 'scratch', 'lifetime', 'warranty', '耐用', '耐磨', '保修']),
]

UNIT_RE = re.compile(r'\d+(?:\.\d+)?\s*(?:cm|mm|inch|inches|in\b|ml|oz|g\b|kg|lb|lbs|l\b|w\b|mah|ft)', re.I)

MATERIAL_WORDS = [
    'silicone', 'cotton', 'abs', 'stainless', 'steel', 'aluminum', 'nylon',
    'polyester', 'leather', 'glass', 'silk', 'bamboo', 'ceramic', 'wool',
    '硅胶', '棉', '不锈钢', '真丝', '竹', '陶瓷', '羊毛',
]

EVIDENCE_WORDS = [
    'tested', 'certified', 'standard', 'en 71', 'astm', 'fda', 'lfgb',
    'double wall', 'double-wall', 'reinforced', 'food grade', 'food-grade',
    '测试', '认证', '食品级', '双层',
]


def _has_any(text_low, words):
    return any(w in text_low for w in words)


def score(listing):
    title = listing['title']
    bullets = listing['bullets']
    desc = listing['description']
    attrs = listing.get('attributes') or {}
    body = ' \n '.join(bullets + [desc])
    body_low = body.lower()
    all_low = (title + ' \n ' + body).lower()

    dims = []
    deductions = []

    # D1 属性完整度 20
    slots = ['material', 'color', 'size', 'weight', 'quantity', 'audience', 'style', 'care']
    filled = []
    for s in slots:
        v = attrs.get(s)
        if isinstance(v, str) and v.strip() and v.strip().lower() not in ('n/a', 'none', '无', '其他', '标准'):
            filled.append(s)
    d1 = round(len(filled) / 8.0 * 20, 1)
    dims.append(('D1 属性完整度', 20, d1))
    if len(filled) < 8:
        missing = [s for s in slots if s not in filled]
        deductions.append(('D1', '属性缺 %d 项：%s' % (len(missing), '、'.join(missing)),
                           '在后台属性栏补齐，或在五点中用一句带数值的话覆盖'))

    # D2 场景与人群 15
    scen = [k for k, ws in SCENARIO_BANK.items() if _has_any(all_low, ws)]
    aud = [k for k, ws in AUDIENCE_BANK.items() if _has_any(all_low, ws)]
    hits2 = len(scen) + len(aud)
    d2 = 0 if hits2 == 0 else (6 if hits2 == 1 else (10 if hits2 == 2 else 15))
    dims.append(('D2 场景与人群覆盖', 15, d2))
    if d2 < 15:
        deductions.append(('D2', '仅覆盖 %d 类场景/人群（%s）' % (hits2, '、'.join(scen + aud) or '无'),
                           '补一句「谁在什么场合用」，用具体场景词而非形容词'))

    # D3 问答覆盖 15
    answered, unanswered = [], []
    for q, toks in QUESTION_PROBES:
        if _has_any(all_low, toks):
            answered.append(q)
        else:
            unanswered.append(q)
    d3 = round(len(answered) / 10.0 * 15, 1)
    dims.append(('D3 问答覆盖', 15, d3))
    if unanswered:
        deductions.append(('D3', '未回答：%s' % '、'.join(unanswered),
                           '每条未答问题补一个短句，优先补前三条'))

    # D4 实体一致性 15
    title_specs = set(m.group(0).lower().replace(' ', '') for m in UNIT_RE.finditer(title))
    body_specs = set(m.group(0).lower().replace(' ', '') for m in UNIT_RE.finditer(body))
    if title_specs:
        ratio = len(title_specs & body_specs) / float(len(title_specs))
    else:
        ratio = 0.0
    d4a = round(ratio * 10, 1)

    tw = [w for w in norm_words(title) if len(w) >= 3 and w not in STOPWORDS]
    head = tw[:3]
    if head:
        present = [w for w in head if w in norm_words(body)]
        d4b = round(len(present) / float(len(head)) * 5, 1)
    else:
        d4b = 0.0
    d4 = round(d4a + d4b, 1)
    dims.append(('D4 实体一致性', 15, d4))
    if d4 < 15:
        if title_specs and ratio < 1.0:
            missing_specs = title_specs - body_specs
            deductions.append(('D4', '标题规格未在正文复现：%s' % '、'.join(sorted(missing_specs)),
                               '在五点里复述同一规格，不要换单位或改数值'))
        if d4b < 5:
            deductions.append(('D4', '标题前三个实词未在正文出现',
                               '让五点和描述使用与标题一致的产品名'))

    # D5 结构化程度 15
    d5 = 0.0
    c = len(bullets)
    d5 += 5 if c == 5 else (3 if c in (4, 6) else 0)
    anchored = sum(1 for b in bullets if re.match(r'^\s*(\*\*[^*]+\*\*|【[^】]+】)', b))
    d5 += min(4.0, anchored * 0.8)
    d5 += 3 if desc.count('\n\n') >= 2 else 0
    d5 += 3 if 400 <= len(desc) <= 2000 else 0
    d5 = round(min(15.0, d5), 1)
    dims.append(('D5 结构化程度', 15, d5))
    if d5 < 15:
        if anchored < 5:
            deductions.append(('D5', '仅 %d/%d 条五点有加粗锚点' % (anchored, c),
                               '每条开头加 2–4 词加粗短语，作为该条的主题标签'))
        if desc.count('\n\n') < 2:
            deductions.append(('D5', '描述段落少于 3 段', '按「是什么 / 怎么用 / 不适合什么 / 包装与维护」分段'))
        if not (400 <= len(desc) <= 2000):
            deductions.append(('D5', '描述长度 %d 字符，不在 400–2000 区间' % len(desc),
                               '过短补使用步骤，过长压缩重复内容'))

    # D6 差异化证据 10
    unit_hits = len(UNIT_RE.findall(' \n '.join(bullets)))
    d6 = 7 if unit_hits >= 3 else (4 if unit_hits >= 1 else 0)
    if _has_any(body_low, MATERIAL_WORDS):
        d6 += 2
    if _has_any(body_low, EVIDENCE_WORDS):
        d6 += 1
    d6 = min(10.0, float(d6))
    dims.append(('D6 差异化证据', 10, d6))
    if d6 < 10:
        deductions.append(('D6', '五点中带单位数字 %d 个' % unit_hits,
                           '每个卖点至少给一个数字：容量、尺寸、承重、层数、时长'))

    # D7 关键词自然度 10
    primary = ''
    kw = listing.get('keywords') or {}
    if isinstance(kw.get('primary'), list) and kw['primary']:
        primary = str(kw['primary'][0]).strip()
    d7 = 0.0
    if primary:
        if primary.lower() in title.lower():
            d7 += 4
        if any(primary.lower() in b.lower() for b in bullets):
            d7 += 3
    else:
        d7 += 7  # 未声明主词，不计入此项扣分
    freq = {}
    for w in norm_words(title):
        if len(w) >= 3 and w not in STOPWORDS:
            freq[w] = freq.get(w, 0) + 1
    top_n = max(freq.values()) if freq else 0
    d7 += 3 if top_n <= 3 else (1 if top_n == 4 else 0)
    d7 = round(min(10.0, d7), 1)
    dims.append(('D7 关键词自然度', 10, d7))
    if primary and primary.lower() not in title.lower():
        deductions.append(('D7', '主词「%s」未出现在标题' % primary, '把主词放进标题前 5 个词内'))
    if primary and not any(primary.lower() in b.lower() for b in bullets):
        deductions.append(('D7', '主词「%s」未出现在五点' % primary, '至少一条五点自然包含主词'))
    if top_n > 3:
        deductions.append(('D7', '标题最高频实词出现 %d 次' % top_n, '删掉重复词，换成同义的属性描述'))

    total = round(sum(d[2] for d in dims), 1)
    if total >= 85:
        band = '结构完整，可被稳定引用'
        action = '保持结构，把精力转到主图与评论'
    elif total >= 70:
        band = '有明确缺口'
        action = '按扣分项逐条补，通常先补 D1 与 D3 收益最大'
    elif total >= 50:
        band = '只能回答基础问题'
        action = '重写五点结构，同时补齐属性栏'
    else:
        band = '基本无法被结构化召回'
        action = '整体重写，不做局部修补'

    return {
        'check': 'score',
        'total': total,
        'band': band,
        'action': action,
        'dimensions': [{'name': n, 'weight': w, 'score': s} for n, w, s in dims],
        'deductions': [{'dim': d, 'issue': i, 'action': a} for d, i, a in deductions],
        'unanswered': unanswered,
        'exit_code': 0,
    }


# ---------------------------------------------------------------- keywords

def _singular(w):
    if len(w) > 4 and w.endswith('ies'):
        return w[:-3] + 'y'
    if len(w) > 3 and w.endswith('s') and not w.endswith('ss'):
        return w[:-1]
    return w


def keywords(listing, market):
    rules = load_rules()
    mk = rules['marketplaces'].get(market)
    if not mk:
        raise SystemExit('未知站点 %s' % market)

    kw = listing.get('keywords') or {}
    pool = []
    for k in ('primary', 'secondary', 'long_tail'):
        v = kw.get(k)
        if isinstance(v, list):
            for t in v:
                if isinstance(t, str) and t.strip():
                    pool.append({'term': t.strip(), 'source': k})
    for ct in (listing.get('competitor_titles') or []):
        if isinstance(ct, str):
            for w in norm_words(ct):
                if len(w) >= 4 and w not in STOPWORDS:
                    pool.append({'term': w, 'source': 'competitor'})

    # 去重
    seen = {}
    for item in pool:
        key = ' '.join(_singular(w) for w in norm_words(item['term']))
        if not key:
            continue
        if key in seen:
            seen[key]['dup'] += 1
            continue
        seen[key] = {'term': item['term'], 'key': key, 'source': item['source'], 'dup': 0}

    terms = list(seen.values())

    # 分组：共享任一 token 即同组
    groups = []
    for t in terms:
        toks = set(t['key'].split())
        placed = False
        for g in groups:
            if g['tokens'] & toks:
                g['tokens'] |= toks
                g['terms'].append(t)
                placed = True
                break
        if not placed:
            groups.append({'tokens': set(toks), 'terms': [t]})

    brand = (listing.get('brand') or '').strip()
    budget = mk['title']['hard_max'] - len(brand) - 2

    assignments = []
    used_title = 0
    for g in groups:
        head = g['terms'][0]
        ntok = len(head['key'].split())
        if head['source'] == 'primary' and used_title + len(head['term']) + 1 <= budget:
            slot = 'title'
            used_title += len(head['term']) + 1
            reason = '主词组：标题只放主词本身，组内其余词分到五点或后台词'
        elif ntok >= 3:
            slot = 'search_terms'
            reason = '长尾词（≥3 词），标题放不下，进后台搜索词'
        elif any(t['key'] in MATERIAL_WORDS for t in g['terms']) or ntok == 1:
            slot = 'title/bullets'
            reason = '单属性词，用于标题规格段或五点证据句'
        else:
            slot = 'bullets'
            reason = '场景/属性组合，进五点做具体化'
        assignments.append({
            'group': ' / '.join(t['term'] for t in g['terms'][:4]),
            'size': len(g['terms']),
            'slot': slot,
            'reason': reason,
        })

    assignments.sort(key=lambda x: (x['slot'] != 'title', -x['size']))
    slots_count = {}
    for a in assignments:
        slots_count[a['slot']] = slots_count.get(a['slot'], 0) + 1

    return {
        'check': 'keywords',
        'market': market,
        'input_terms': len(pool),
        'unique_terms': len(terms),
        'duplicates_removed': len(pool) - len(terms),
        'groups': len(groups),
        'title_budget_chars': budget,
        'title_used_chars': used_title,
        'slot_distribution': slots_count,
        'assignments': assignments,
        'exit_code': 0,
    }


# ---------------------------------------------------------------- 输出

def print_human(result):
    check = result['check']
    if check == 'lint':
        print('== 文案体检 · %s ==' % result['market'])
        m = result['metrics']
        print('标题 %d/%d 字符 | 五点 %d 条 | 描述 %d 字符 | 后台词 %d 字节'
              % (m['title_chars'], m['title_hard_max'], m['bullet_count'],
                 m['description_chars'], m['search_terms_bytes']))
        print('判定：%s' % result['verdict'])
        for f in result['findings']:
            print('  [%s] %s @ %s — %s' % (f['level'], f['code'], f['where'], f['msg']))
            if f['fix']:
                print('        改法：%s' % f['fix'])
        if not result['findings']:
            print('  无问题项。')

    elif check == 'compliance':
        print('== 合规放行 · %s / %s ==' % (result['market'], result['category']))
        print('判定：%s  阻断 %d / 条件 %d / 提示 %d'
              % (result['verdict'], result['counts']['BLOCK'],
                 result['counts']['CONDITION'], result['counts']['INFO']))
        for title, key in (('阻断项', 'blocking'), ('条件项', 'conditional'), ('提示项', 'informational')):
            if result[key]:
                print('-- %s --' % title)
                for it in result[key]:
                    print('  [%s] %s' % (it['level'], it['label']))
                    if it.get('matched') and it['matched'] != '-':
                        print('        命中原文：%s' % it['matched'])
                    print('        原因：%s' % it['why'])
                    print('        改法：%s' % it['fix'])
        print('注：%s' % result['disclaimer'])

    elif check == 'score':
        print('== AI 推荐就绪度 ==')
        print('总分：%s / 100 — %s' % (result['total'], result['band']))
        print('建议：%s' % result['action'])
        for d in result['dimensions']:
            print('  %-16s %5s / %d' % (d['name'], d['score'], d['weight']))
        if result['deductions']:
            print('-- 扣分明细 --')
            for d in result['deductions']:
                print('  [%s] %s' % (d['dim'], d['issue']))
                print('        动作：%s' % d['action'])

    elif check == 'keywords':
        print('== 关键词预算 · %s ==' % result['market'])
        print('输入 %d 词 → 去重后 %d 词（去掉 %d 个重复），分 %d 组'
              % (result['input_terms'], result['unique_terms'],
                 result['duplicates_removed'], result['groups']))
        print('标题预算 %d 字符，已分配 %d' % (result['title_budget_chars'], result['title_used_chars']))
        for a in result['assignments']:
            print('  → %-14s %s  (组内 %d 词) %s' % (a['slot'], a['group'], a['size'], a['reason']))


def _report_exit(listing, market, category):
    """报告落盘成功也要把判定带进退出码，便于串进自动化流程。"""
    lr = lint(listing, market)
    cr = compliance(listing, market, category)
    return max(lr['exit_code'], cr['exit_code'])


def build_report(listing, market, category):
    lr = lint(listing, market)
    cr = compliance(listing, market, category)
    sr = score(listing)
    kr = keywords(listing, market)

    lines = []
    lines.append('# Listing 审计报告')
    lines.append('')
    lines.append('- 站点：%s' % market)
    lines.append('- 类目：%s' % category)
    lines.append('- 标题字符：%d' % lr['metrics']['title_chars'])
    lines.append('')
    lines.append('## 一、放行判定')
    lines.append('')
    lines.append('| 项目 | 结果 |')
    lines.append('|---|---|')
    lines.append('| 文案体检 | %s |' % lr['verdict'])
    lines.append('| 合规判定 | %s |' % cr['verdict'])
    lines.append('| AI 就绪度 | %s / 100（%s） |' % (sr['total'], sr['band']))
    lines.append('')
    lines.append('## 二、文案体检')
    lines.append('')
    if lr['findings']:
        lines.append('| 级别 | 代码 | 位置 | 问题 | 改法 |')
        lines.append('|---|---|---|---|---|')
        for f in lr['findings']:
            lines.append('| %s | %s | %s | %s | %s |'
                         % (f['level'], f['code'], f['where'],
                            f['msg'].replace('|', '/'), f['fix'].replace('|', '/')))
    else:
        lines.append('无问题项。')
    lines.append('')
    lines.append('## 三、合规清单')
    lines.append('')
    for title, key in (('阻断项', 'blocking'), ('条件项', 'conditional'), ('提示项', 'informational')):
        lines.append('### %s' % title)
        lines.append('')
        if not cr[key]:
            lines.append('无。')
        else:
            for it in cr[key]:
                lines.append('- **%s**' % it['label'])
                if it.get('matched') and it['matched'] != '-':
                    lines.append('  - 命中原文：`%s`' % it['matched'])
                lines.append('  - 原因：%s' % it['why'])
                lines.append('  - 改法：%s' % it['fix'])
        lines.append('')
    lines.append('> %s' % cr['disclaimer'])
    lines.append('')
    lines.append('## 四、AI 推荐就绪度')
    lines.append('')
    lines.append('| 维度 | 得分 | 权重 |')
    lines.append('|---|---|---|')
    for d in sr['dimensions']:
        lines.append('| %s | %s | %d |' % (d['name'], d['score'], d['weight']))
    lines.append('')
    lines.append('**总分 %s / 100** — %s' % (sr['total'], sr['band']))
    lines.append('')
    if sr['deductions']:
        lines.append('扣分明细：')
        lines.append('')
        for d in sr['deductions']:
            lines.append('- `%s` %s → %s' % (d['dim'], d['issue'], d['action']))
        lines.append('')
    if sr['unanswered']:
        lines.append('未回答的买家问题：%s' % '、'.join(sr['unanswered']))
        lines.append('')
    lines.append('## 五、关键词预算')
    lines.append('')
    lines.append('输入 %d 词，去重后 %d 词，分 %d 组。标题预算 %d 字符，已分配 %d。'
                 % (kr['input_terms'], kr['unique_terms'], kr['groups'],
                    kr['title_budget_chars'], kr['title_used_chars']))
    lines.append('')
    lines.append('| 词组 | 词数 | 建议位置 | 理由 |')
    lines.append('|---|---|---|---|')
    for a in kr['assignments']:
        lines.append('| %s | %d | %s | %s |' % (a['group'], a['size'], a['slot'], a['reason']))
    lines.append('')
    return '\n'.join(lines)


# ---------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(
        prog='listing_audit.py',
        description='亚马逊 Listing 审计引擎（文案体检 / 合规放行 / AI 就绪度 / 关键词预算）')
    sub = ap.add_subparsers(dest='cmd', required=True)

    for name in ('lint', 'compliance', 'score', 'keywords', 'report'):
        p = sub.add_parser(name)
        p.add_argument('--listing', required=True, help='listing JSON 文件路径')
        p.add_argument('--market', default='US', help='站点代码，默认 US')
        p.add_argument('--category', default='general', help='类目键，默认 general')
        p.add_argument('--out', help='report 子命令的输出文件')
        p.add_argument('--json', action='store_true', help='以 JSON 输出')

    args = ap.parse_args(argv)
    listing = load_listing(args.listing)

    if args.cmd == 'lint':
        r = lint(listing, args.market)
    elif args.cmd == 'compliance':
        r = compliance(listing, args.market, args.category)
    elif args.cmd == 'score':
        r = score(listing)
    elif args.cmd == 'keywords':
        r = keywords(listing, args.market)
    elif args.cmd == 'report':
        md = build_report(listing, args.market, args.category)
        if args.out:
            with open(args.out, 'w', encoding='utf-8') as f:
                f.write(md)
            print('报告已写入 %s（%d 字符）' % (args.out, len(md)))
        else:
            print(md)
        return _report_exit(listing, args.market, args.category)
    else:
        ap.error('未知子命令')

    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print_human(r)
    return r['exit_code']


if __name__ == '__main__':
    sys.exit(main())
