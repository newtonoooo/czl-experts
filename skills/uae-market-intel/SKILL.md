---
name: uae-market-intel
description: |
  阿联酋市场情报底座：人群分层画像、渠道能力目录、行业合规偏置三份结构化知识库，配套查询脚本。用于在给出任何营销建议前先锁定人群层、渠道可行性与行业敏感点。
  触发词：阿联酋人群、迪拜消费者、外籍居民、渠道渗透率、CPM、行业合规、市场情报。
description_en: |
  UAE market intelligence base: three structured knowledge files (audience segments, channel catalog, sector compliance bias) plus a query script. Use before giving any UAE marketing recommendation to lock down the audience tier, channel feasibility and sector sensitivity.
---

# 阿联酋市场情报底座

## 何时用

- W2 人群分层：需要把"阿联酋消费者"拆成可投放的层。
- W3 渠道建模：需要判断某渠道在特定行业是否可行、采买成本量级。
- W5 合规审查：需要知道该行业的敏感点在哪。

**不要在没读本技能的情况下直接凭印象写渠道建议。** 这里的数字是采买基线，不是装饰。

## 三份知识库

| 文件 | 内容 | 主要用途 |
|------|------|---------|
| `data/audience_segments.json` | 五个人群的画像、语言、主媒介、决策驱动、敏感点、预算指数 | W2 |
| `data/channel_catalog.json` | 渠道角色、优势、限制、CPM/CPC 区间、素材要求、最低预算 | W3 |
| `data/sector_notes.json` | 十二个行业的渠道偏置与合规红线 | W3 / W5 |

## 查询方式

脚本只做检索与摘要，不做判断。判断留给你。

```bash
# 列出全部人群层
python skills/uae-market-intel/scripts/intel_query.py segments

# 看单个渠道的采买参数
python skills/uae-market-intel/scripts/intel_query.py channel --id tiktok

# 看某行业该用什么渠道、避什么坑
python skills/uae-market-intel/scripts/intel_query.py sector --id beauty

# 按行业筛可行渠道（按适配度排序）
python skills/uae-market-intel/scripts/intel_query.py channels-for --sector beauty
```

也可以直接 `Read` 对应的 JSON 文件。

## 数据口径纪律（重要）

三份文件里每个数值都带 `basis` 字段，只有四种取值：

| basis | 含义 | 使用方式 |
|-------|------|---------|
| `official-stat` | 官方统计口径（人口、国籍构成等） | 可直接引用，注明来源机构与年份 |
| `industry-report` | 行业报告区间 | 引用区间，注明报告类型与年份 |
| `platform-stated` | 平台自述数据 | 标注"平台自述"，视为上限而非实测 |
| `planning-range` | 采买经验区间 | **不得对外作为事实陈述**，只能作为建模假设 |

**硬规则：**

1. `planning-range` 的数字进交付物时，必须写成"假设区间"，并附一句"需以平台实际报价校准"。
2. 任何超过 12 个月的数值，输出时标 `需复核`。
3. 用户要对外发布的市场规模/渗透率结论，一律先在线检索核实再落笔。
4. 数据缺口就写"该维度无可靠公开数据"，并给出获取路径（平台后台、行业协会、客户自有数据）。

## 与其他工作流的关系

- 被 **W2** 调用 → 输出人群分层表。
- 被 **W3** 调用 → 提供 `uae-channel-mix` 建模所需的渠道可行性输入。
- 被 **W5** 调用 → 提供行业敏感点，交给 `uae-brand-safety` 做扫描。
- 本技能**不产出最终文案**，只产出判断依据。
