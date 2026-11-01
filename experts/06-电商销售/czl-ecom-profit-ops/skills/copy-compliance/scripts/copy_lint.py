#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""copy_lint.py - 商品标题与详情文案的合规体检（纯标准库）。

检查六类风险，每类给替换写法，不只标红：
  绝对化用语 / 功效越界 / 价格与比价 / 诱导交易 / 站外导流 / 标题结构

用法
----
    python copy_lint.py --file detail.txt
    python copy_lint.py --text "全网最低 宝宝专用保温杯"
    python copy_lint.py --text "..." --title --limit 30
    python copy_lint.py --file detail.txt --json

退出码：0 = 无高风险；1 = 存在高风险命中；2 = 输入错误。

说明：词表是**风险提示**，不是法律意见。词表外的表达同样可能违规；判定以平台规则与
《广告法》《反不正当竞争法》《明码标价和禁止价格欺诈规定》等现行文本为准。
"""

from __future__ import annotations

import argparse
import json
import re
import sys

HIGH, MID, LOW = "高", "中", "低"

# term, category, risk, suggestion
TERMS = [
    # ---- 绝对化用语（《广告法》第九条明确禁止"国家级""最高级""最佳"等）
    ("最佳", "绝对化用语", HIGH, "去掉，改为可验证的具体描述（如「实测保温 6 小时」）"),
    ("最好", "绝对化用语", HIGH, "去掉，改为具体指标或使用场景"),
    ("最强", "绝对化用语", HIGH, "去掉，改为功能事实"),
    ("最优", "绝对化用语", HIGH, "去掉，改为可比较的具体参数"),
    ("最高级", "绝对化用语", HIGH, "去掉"),
    ("最先进", "绝对化用语", HIGH, "改为具体技术参数"),
    ("最高端", "绝对化用语", HIGH, "改为材质、工艺等可核对信息"),
    ("第一品牌", "绝对化用语", HIGH, "去掉；如需背书，写清第三方机构名称与统计口径"),
    ("全国第一", "绝对化用语", HIGH, "去掉，除非能出示统计机构、口径、期间"),
    ("全球第一", "绝对化用语", HIGH, "去掉，除非能出示统计机构、口径、期间"),
    ("销量第一", "绝对化用语", HIGH, "去掉，或改为「本店近 30 天售出 X 件」"),
    ("行业第一", "绝对化用语", HIGH, "去掉，或改为可核对的排名来源"),
    ("排名第一", "绝对化用语", HIGH, "去掉，或注明榜单名称与期次"),
    ("唯一", "绝对化用语", HIGH, "改为「少见」「少有」等非排他表述"),
    ("独家", "绝对化用语", HIGH, "去掉，除非有独家授权文件"),
    ("顶级", "绝对化用语", HIGH, "改为具体材质或等级"),
    ("极致", "绝对化用语", HIGH, "改为具体体验描述"),
    ("国家级", "绝对化用语", HIGH, "去掉；资质类表述须与证书原文一致"),
    ("世界级", "绝对化用语", HIGH, "去掉"),
    ("绝对", "绝对化用语", HIGH, "去掉"),
    ("万能", "绝对化用语", HIGH, "改为适用场景清单"),
    ("百分百", "绝对化用语", HIGH, "改为实测数据"),
    ("最好的", "绝对化用语", HIGH, "去掉，改为具体指标"),
    ("驰名商标", "绝对化用语", HIGH, "《商标法》禁止将「驰名商标」用于广告宣传，删除"),
    ("国家免检", "绝对化用语", HIGH, "该评选已取消，删除"),
    ("央视上榜", "绝对化用语", HIGH, "无授权不得使用，删除"),
    ("永久", "绝对化用语", HIGH, "改为质保期限（如「质保 2 年」）"),
    ("100%", "绝对化用语", MID, "改为实测数据并注明样本与方法；「100% 棉」这类成分表述须与检测一致"),


    # ---- 功效越界
    ("治疗", "功效越界", HIGH, "删除；非药品不得使用医疗用语"),
    ("治愈", "功效越界", HIGH, "删除"),
    ("根治", "功效越界", HIGH, "删除"),
    ("药到病除", "功效越界", HIGH, "删除"),
    ("包治", "功效越界", HIGH, "删除"),
    ("消炎", "功效越界", HIGH, "删除；非药品不得宣称"),
    ("抗病毒", "功效越界", HIGH, "删除，除非产品注册类别允许"),
    ("降血压", "功效越界", HIGH, "删除"),
    ("降血糖", "功效越界", HIGH, "删除"),
    ("降血脂", "功效越界", HIGH, "删除"),
    ("抗癌", "功效越界", HIGH, "删除"),
    ("防癌", "功效越界", HIGH, "删除"),
    ("排毒", "功效越界", HIGH, "删除，改为成分与工艺描述"),
    ("丰胸", "功效越界", HIGH, "删除"),
    ("壮阳", "功效越界", HIGH, "删除"),
    ("生发", "功效越界", HIGH, "删除；特殊化妆品须按注册功效表述"),
    ("减肥不反弹", "功效越界", HIGH, "删除承诺，改为使用方式说明"),
    ("无副作用", "功效越界", HIGH, "删除"),
    ("杀菌", "功效越界", MID, "仅消毒类产品且持卫生许可时可宣称，须标杀菌率与检测报告"),
    ("纯天然", "功效越界", MID, "改为具体成分表；「纯天然」缺乏统一判定标准"),
    ("无添加", "功效越界", MID, "改为「未添加 XX」，并与配料表一致"),
    ("零添加", "功效越界", MID, "改为「未添加 XX」，并与配料表一致"),
    ("无刺激", "功效越界", MID, "改为「经斑贴测试」，并保留测试报告"),

    ("医用级", "功效越界", MID, "无医疗器械注册证不得使用"),
    ("食品级", "功效越界", MID, "改为「符合 GB 4806 食品接触用材料标准」等具体标准号"),
    ("可食用", "功效越界", MID, "非食品类删除"),
    ("宝宝专用", "功效越界", LOW, "改为「适合 6 个月以上婴幼儿使用」，并确保有相应检测依据"),

    # ---- 价格与比价
    ("原价", "价格与比价", HIGH, "改为「日常价」并确保有促销前成交记录；折价基准须真实"),
    ("专柜价", "价格与比价", HIGH, "删除，或提供专柜价凭证与同款对应关系"),
    ("市场价", "价格与比价", MID, "改为「参考价」并注明来源"),
    ("划线价", "价格与比价", HIGH, "须有真实成交依据，否则删除"),
    ("吊牌价", "价格与比价", MID, "须为该商品真实吊牌价，保留凭证"),
    ("清仓价", "价格与比价", MID, "改为具体促销价，不暗示理由"),
    ("跳楼价", "价格与比价", HIGH, "改为具体价格"),
    ("亏本", "价格与比价", HIGH, "删除"),
    ("全网最低", "价格与比价", HIGH, "删除；无依据的价格比较属价格欺诈风险"),
    ("史上最低", "价格与比价", HIGH, "删除"),
    ("假一赔十", "价格与比价", MID, "作为承诺须可履行，否则改为「支持正品验货」"),
    ("买贵退差价", "价格与比价", MID, "写清对比渠道、时限与凭证要求"),

    # ---- 诱导交易
    ("好评返现", "诱导交易", HIGH, "删除；属诱导评价，平台明确禁止"),
    ("五星好评", "诱导交易", HIGH, "删除，改为「如有问题请联系客服」"),
    ("刷单", "诱导交易", HIGH, "删除"),
    ("删差评", "诱导交易", HIGH, "删除"),
    ("改评价", "诱导交易", HIGH, "删除"),
    ("仅剩", "诱导交易", MID, "改为真实库存数，或删除"),
    ("最后一天", "诱导交易", MID, "须与实际活动期一致"),
    ("最后3小时", "诱导交易", MID, "须与实际活动期一致"),
    ("抢完即止", "诱导交易", LOW, "改为「数量有限」并确保描述真实"),
    ("手慢无", "诱导交易", LOW, "改为「库存有限」"),

    # ---- 站外导流
    ("加微信", "站外导流", MID, "删除；平台禁止引导站外交易"),
    ("微信号", "站外导流", MID, "删除"),
    ("私聊", "站外导流", LOW, "改为「咨询客服」"),
    ("二维码", "站外导流", MID, "删除站外二维码"),
]

BAD_SYMBOLS = ["★", "☆", "◆", "■", "▶", "※", "!!!", "！！！", "【", "】"]

# 「最 + 形容词」的组合千变万化，用模式兜住；已由字面表命中的区间不再重复计。
REGEX_TERMS = [
    (
        r"最(安全|好|佳|强|优|低价|便宜|高端|高级|先进|火|值得|专业|正宗|耐用|舒适|舒服|健康|营养|实惠|划算|抢手|热销|受欢迎|有效|放心|靠谱|牛)",
        "绝对化用语",
        HIGH,
        "去掉「最」字，改成可验证的具体指标或使用场景",
    ),
    (
        r"第[一二三四五六七八九十]品牌",
        "绝对化用语",
        HIGH,
        "改为具体品牌事实，删除排名表述",
    ),
]


def lint_text(text, title_mode=False, limit=0):
    hits = []
    spans = []
    for term, cat, risk, tip in TERMS:
        start = 0
        while True:
            idx = text.find(term, start)
            if idx < 0:
                break
            ctx = text[max(0, idx - 10): idx + len(term) + 10].replace("\n", " ")
            hits.append({
                "term": term,
                "category": cat,
                "risk": risk,
                "index": idx,
                "context": ctx,
                "suggestion": tip,
            })
            spans.append((idx, idx + len(term)))
            start = idx + len(term)

    for pattern, cat, risk, tip in REGEX_TERMS:
        for m in re.finditer(pattern, text):
            a, b = m.span()
            if any(a < s_end and b > s_start for s_start, s_end in spans):
                continue
            ctx = text[max(0, a - 10): b + 10].replace("\n", " ")
            hits.append({
                "term": m.group(0),
                "category": cat,
                "risk": risk,
                "index": a,
                "context": ctx,
                "suggestion": tip,
            })
            spans.append((a, b))

    structure = []
    if title_mode and limit > 0 and len(text) > limit:
        structure.append({
            "item": "标题超长",
            "risk": MID,
            "detail": f"当前 {len(text)} 字，上限 {limit} 字，超出 {len(text) - limit} 字",
            "suggestion": "删掉与核心词无关的修饰词，保留品牌+核心词+属性+场景",
        })

    for sym in BAD_SYMBOLS:
        if sym in text:
            structure.append({
                "item": f"特殊符号 {sym}",
                "risk": LOW,
                "detail": "部分平台限制标题使用装饰符号",
                "suggestion": "改为空格或直接删除",
            })

    tokens = re.findall(r"[\u4e00-\u9fa5]{2,}", text)
    counts = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
    for t, c in counts.items():
        if c >= 3:
            structure.append({
                "item": f"关键词堆砌「{t}」",
                "risk": MID,
                "detail": f"出现 {c} 次",
                "suggestion": "保留 1–2 次，其余换成属性词或场景词",
            })

    return hits, structure


def print_report(hits, structure, text):
    high = [h for h in hits if h["risk"] == HIGH]
    mid = [h for h in hits if h["risk"] == MID]
    low = [h for h in hits if h["risk"] == LOW]
    print(f"## 文案合规体检（{len(text)} 字）")
    print()
    if hits:
        print("| 风险 | 类别 | 命中词 | 上下文 | 改法 |")
        print("|---|---|---|---|---|")
        for h in sorted(hits, key=lambda x: ({HIGH: 0, MID: 1, LOW: 2}[x["risk"]], x["category"])):
            print(f"| {h['risk']} | {h['category']} | {h['term']} | …{h['context']}… | {h['suggestion']} |")
        print()
    if structure:
        print("结构问题：")
        for s in structure:
            print(f"- [{s['risk']}] {s['item']}：{s['detail']} → {s['suggestion']}")
        print()
    print(f"汇总：高风险 {len(high)} 处，中风险 {len(mid)} 处，低风险 {len(low)} 处。")
    if high:
        print("判定：不可直接上架。高风险项属《广告法》绝对化用语或功效越界，须逐条改写。")
    elif mid:
        print("判定：可改后上架。中风险项需要凭证或限定条件，拿不出凭证就删。")
    elif hits or structure:
        print("判定：低风险。逐条确认后可上架。")
    else:
        print("判定：未命中词表。词表不等于法律意见，发布前仍需人工复核。")


def main(argv=None):
    ap = argparse.ArgumentParser(description="商品文案合规体检")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", help="直接传入文案")
    src.add_argument("--file", help="从文本文件读取")
    ap.add_argument("--title", action="store_true", help="按标题口径检查（配合 --limit 查超长）")
    ap.add_argument("--limit", type=int, default=0, help="标题字数上限，0 = 不检查长度")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if a.file:
        try:
            with open(a.file, encoding="utf-8-sig") as fh:
                text = fh.read()
        except FileNotFoundError:
            print(f"输入错误：找不到文件 {a.file}", file=sys.stderr)
            return 2
        except UnicodeDecodeError:
            print("输入错误：文件不是 UTF-8 编码", file=sys.stderr)
            return 2
    else:
        text = a.text

    if not text or not text.strip():
        print("输入错误：文案为空", file=sys.stderr)
        return 2

    hits, structure = lint_text(text, a.title, a.limit)
    if a.json:
        payload = {
            "length": len(text),
            "hits": hits,
            "structure": structure,
            "counts": {
                "high": sum(1 for h in hits if h["risk"] == HIGH),
                "mid": sum(1 for h in hits if h["risk"] == MID),
                "low": sum(1 for h in hits if h["risk"] == LOW),
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_report(hits, structure, text)
    return 1 if any(h["risk"] == HIGH for h in hits) else 0


if __name__ == "__main__":
    sys.exit(main())
