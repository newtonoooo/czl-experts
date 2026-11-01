---
name: listing-ops-kit
description: "Working kit for writing one Amazon listing that can actually be submitted. Six gate playbooks (intake, keyword budget, copy build, compliance release, AI-readiness score, appeal) each with inputs, steps, pass conditions, output artifact, failure handling and neighbours. One standard-library audit engine with five subcommands: lint measures title, bullet, description and back-end search-term budgets against per-marketplace limits and flags all-caps, symbol noise, stuffing, duplicate phrases and thin bullets; compliance turns claim patterns, category prerequisites and market obligations into BLOCK, CONDITION and INFO findings and returns GO, CONDITIONAL or BLOCKED with a named blocking list; score rates seven weighted dimensions into a 0-100 AI-readiness figure with every deduction itemised and the unanswered buyer questions listed; keywords de-duplicates a keyword pool, groups terms by token overlap and assigns each group to title, bullets, description or back-end search terms against a character budget; report merges all four into one Markdown file. Reference packs cover marketplace character baselines, the compliance matrix by market and category, original copy patterns, and the scoring rubric. Load one gate playbook at a time."
version: 1.0.1
---

# Listing 作业套件（listing-ops-kit）

> 这不是文案灵感库，是**施工图 + 量具**：六道门怎么过，四个量具怎么读。
> 读法：只看当前卡住的那道门，不要一次读完。

---

## 一、套件目录

```
listing-ops-kit/
├── SKILL.md                       # 本文件：总纲、闸门速查、纪律
├── workflows/                     # 六道闸门（按需取一份）
│   ├── 00-输入体检.md
│   ├── 01-关键词预算.md
│   ├── 02-文案构建.md
│   ├── 03-合规放行.md
│   ├── 04-AI就绪度.md
│   └── 05-申诉框架.md
├── references/
│   ├── marketplace-rules.json     # 站点字符基线 + 文案检查参数
│   ├── compliance-matrix.json     # 宣称规则 + 类目门槛 + 市场义务
│   ├── copy-patterns.md           # 标题/五点/描述骨架
│   └── score-rubric.md            # 七维评分口径
└── scripts/
    ├── listing_audit.py           # 审计引擎（纯标准库）
    └── fixtures/                  # 四个测试样本
```

## 二、六道闸门速查

| 门 | 一句话职责 | 过门条件 | 产物 |
|---|---|---|---|
| G0 输入体检 | 把"一款产品"变成结构化输入卡 | 站点、类目、产品本体、≥1 主词齐备 | 输入卡 + 缺失项 |
| G1 关键词预算 | 把词池分到固定位置，先算预算再写 | 每个词有唯一归属，标题不超预算 | 分配表 |
| G2 文案构建 | 标题 / 五点 / 描述 / 后台词 | 每条卖点含利益 + 证据 + 场景 | 可复制文案块 |
| G3 合规放行 | 词层 + 类目层 + 市场层 | 无 BLOCK | GO / CONDITIONAL / BLOCKED |
| G4 AI 就绪度 | 七维打分 + 问答缺口 | 扣分项都有改写动作 | 0–100 分 + 缺口清单 |
| G5 申诉框架 | 被压/下架后的四段式 | 每段有可执行动作 | 根因/纠正/预防/证据 |

**顺序纪律**：G3 没出判定，不许说"可以上"；G2 没跑 lint，不许交文案。

## 三、量具速查

```bash
S=scripts/listing_audit.py
python $S lint       --listing x.json --market US
python $S compliance --listing x.json --market DE --category juvenile_products
python $S score      --listing x.json
python $S keywords   --listing x.json --market US
python $S report     --listing x.json --market US --category general --out report.md
```

退出码：`0` 通过 / `1` 有警告 / `2` 有阻断。加 `--json` 拿机器可读结果。

### 输入文件格式

```json
{
  "market": "US",
  "category": "food_contact",
  "brand": "NORDVIK",
  "title": "…",
  "bullets": ["…", "…", "…", "…", "…"],
  "description": "…",
  "search_terms": "…",
  "attributes": {
    "material": "…", "color": "…", "size": "…", "weight": "…",
    "quantity": "…", "audience": "…", "style": "…", "care": "…"
  },
  "keywords": {
    "primary": ["…"], "secondary": ["…"], "long_tail": ["…"]
  },
  "competitor_titles": ["…"]
}
```

只有 `title` 是必需的，其余缺失会被记为扣分项而不是报错——这样可以在只有标题时先体检标题。

### 可用类目键

`electronics` `juvenile_products` `food_contact` `textiles` `toys` `battery_products` `general`

类目键填错不会报错，但类目层门槛会静默跳过——`compliance` 返回里的 `category_known` 为 `false` 时，说明你填了一个没覆盖的类目，此时判定只覆盖了词层与市场层。**看到 `category_known: false` 必须告诉用户"类目门槛未核对"**。

## 四、四条硬纪律

1. **不编费率**。佣金、FBA 费用、广告费没有来源就标"未提供，未计入"。
2. **不给结论不给清单**。任何放行判定都要带阻断项/条件项条目。
3. **不交未检文案**。交付前必须跑一次 `lint`，把退出码和命中项一起给用户。
4. **不承诺排名**。分数是结构完整度，不是销量预测。

## 五、规则包是基线，不是法律

`marketplace-rules.json` 与 `compliance-matrix.json` 里的上限与义务是**写作期自查基线**。亚马逊会按类目模板调整限制，各地法规也在变。

处理冲突的顺序：**用户后台显示 > 当地法规原文 > 本规则包**。发现不一致时，以更高优先级为准，并把差异告诉用户。

## 六、样本说明

`fixtures/` 四个样本用于自测与演示，产品与品牌均为虚构：

| 文件 | 用途 | 预期 |
|---|---|---|
| `cup_us_good.json` | 七维满分锚点 | lint PASS / 合规 GO / 100 分 |
| `earbuds_us_bad.json` | 违规项覆盖 | lint FAIL（3 阻断）/ 合规 BLOCKED |
| `chair_de.json` | 德语站 + 欧盟义务 | 合规 BLOCKED（GPSR、LUCID） |
| `blouse_us_partial.json` | 信息量不足 | 28 分左右，D1/D5 大幅扣分 |

改规则包后先跑这四个样本，确认预期没被改坏，再去写真实 Listing。
