---
name: screening-method
description: Method library for A-share multi-factor screening — the authoritative scoring rubric, field dictionary, delivery templates and compliance guardrails that back the czl-ashare-screener expert. Load when computing five-dimension scores, normalising user data, or assembling the nine-section screening brief.
---

# 选股方法库（screening-method）

本技能是「专业级A股选股引擎」的方法层。专家本体负责对话与编排，本技能负责**口径**：分数怎么算、字段怎么认、报告怎么排、哪些话不能说。口径统一，结果才可复核。

## 什么时候加载

| 触发场景 | 需要的文件 |
|----------|-----------|
| 要把用户数据归一成标准字段 | `references/field-dictionary.md` |
| 要算分、判档、解释某个分数 | `references/scoring-rubric.md` + `scripts/rank_universe.py` |
| 要出交付报告（九段式） | `references/output-templates.md` |
| 要检查措辞是否越界 | `references/compliance-guardrails.md` |

## 快速开始

1. **归一数据**：把不同来源的字段按 `field-dictionary.md` 的别名表映射成标准字段，写成一份 JSON。
2. **跑引擎**（推荐，确定性）：

```bash
python scripts/rank_universe.py <input.json>              # Markdown 榜单
python scripts/rank_universe.py <input.json> --format json
python scripts/rank_universe.py <input.json> --top 10
python scripts/rank_universe.py --selftest                 # 自检，10 项断言
```

3. **组装报告**：按 `output-templates.md` 填九段，逐条过 `compliance-guardrails.md` 的自检清单。

## 目录

```
screening-method/
├── SKILL.md                       # 本文件：何时用、怎么用
├── references/
│   ├── field-dictionary.md        # 标准字段、别名、单位、取数模板
│   ├── scoring-rubric.md          # 五维评分卡（与脚本一一对应）
│   ├── output-templates.md        # 九段式交付模板 + 单票卡
│   └── compliance-guardrails.md    # 禁用词、免责声明、发布前自检
├── scripts/
│   └── rank_universe.py           # 确定性打分引擎（仅标准库）
└── examples/
    └── sample_universe.json       # 输入格式示例（虚构数据）
```

## 三条不可违背的口径

1. **缺失不等于 0**：字段缺失记 `N/A`，该维度退出加权，剩余维度权重等比例放大；覆盖率低于 50% 的标的直接判"数据不足"，不进榜单。
2. **闸门先于打分**：ST、停牌、流动性不足、连续涨停、数据不足，一律在打分之前淘汰，且必须单独列表说明原因。
3. **脚本优先于心算**：有权重、有分段函数的地方一律交给 `rank_universe.py`。手算必须在交付中声明"可能有人工误差"。

## 输入最小集

一份可算分的输入至少需要：`code`、`name`、`price`、`market_cap`、`pe_ttm`、`roe`，以及技术面 `ma20`/`ma60`/`pct_from_high_250`/`rsi14` 中的任意两项。低于这个密度就进入"合约模式"，只交付条件与取数清单，不出榜单。
