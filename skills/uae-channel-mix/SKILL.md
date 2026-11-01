---
name: uae-channel-mix
description: |
  阿联酋渠道配比与预算建模：把预算、目标、人群层、行业、城市转成可执行的渠道分配表，含曝光/触达区间、素材要求与 KPI 形态。配套确定性计算脚本，分配结果精确等于预算。
  触发词：预算分配、渠道配比、投放比例、媒体计划、media plan、CPM、触达估算、多少预算投哪里。
description_en: |
  UAE channel mix and budget modelling: turn budget, objective, audience tier, sector and city into an executable allocation table with impression/reach ranges, creative requirements and KPI shapes. Backed by a deterministic script whose allocation sums exactly to the budget.
---

# 渠道配比与预算建模

## 何时用

- W3 Spend architecture 全段。
- 用户问"钱怎么分""投哪个渠道""这个预算够不够"。
- 需要给客户一份能直接进排期表的媒体计划。

## 核心脚本

`bin/uae_plan.py`（位于专家包根目录）

```bash
python bin/uae_plan.py \
  --budget 300000 \
  --objective awareness \
  --audience core \
  --sector beauty \
  --market uae_wide \
  --format markdown
```

| 参数 | 取值 | 说明 |
|------|------|------|
| `--budget` | 整数 AED | 总预算，含制作费时需先扣除 |
| `--objective` | `awareness` / `consideration` / `conversion` / `retention` | 决定信任层/发现层/转化层的预算权重 |
| `--audience` | `core` / `expand` / `opportunity` / `mixed` | 来自 W2 的分层结论 |
| `--sector` | 行业 id | 见 `intel_query.py list-sectors` |
| `--market` | `dubai` / `abu_dhabi` / `sharjah` / `uae_wide` | 影响户外、KOL、零售媒体的权重 |
| `--reserve` | 0~1，默认 0.10 | 测试预留比例 |
| `--format` | `markdown` / `json` | JSON 用于二次加工 |

## 脚本内置的四条硬规则

1. **分配精确**：整数分配之和恒等于 `预算 − 测试预留`，无四舍五入漂移。脚本自带断言，漂移会直接报错退出。
2. **预算分层封顶**：< 5 万 AED 最多 2 个渠道；5~30 万最多 4 个；> 30 万最多 6 个。小预算不铺开。
3. **角色覆盖**：5 万 AED 以上必须有信任层渠道；转化目标必须保留转化层；声量目标必须有发现层。
4. **两级分配**：先按目标决定三类角色的预算权重，再在角色内部按渠道适配度分。所以渠道占比反映的是策略，不是排序巧合。

## 你必须补的四件事（脚本算不出来）

| 缺口 | 你要做什么 |
|------|-----------|
| 创意产能 | 预算够但只有 2 条素材 → 短视频渠道会被素材量卡死，必须提示先扩素材 |
| 归因现实 | 说清能测到什么（平台内转化、优惠码核销）、测不到什么（跨设备、线下到店） |
| 渠道可行性 | 高客单 B2B 不该重仓 TikTok；奢侈品不该进零售媒体比价 |
| 采买现实 | CPM 区间是假设，必须写"以平台实时报价校准" |

## 三档敏感性

用户预算未定时，跑三次不同预算（低/中/高），输出结构对比，而不是给一个假的精确答案。

```bash
for b in 50000 150000 300000; do
  python bin/uae_plan.py --budget $b --objective conversion \
    --audience mixed --sector ecommerce --format markdown
done
```

## 输出交付格式

```markdown
## 渠道配比（预算 X AED）
| 渠道 | 角色 | 预算 | 占比 | 预估曝光 | 预估触达 | 采买口径 |

**为什么这样分**：{三条理由，对应人群层、渠道角色、节点}

**素材清单**：{按渠道列，含比例与语言版本}

**衡量方式**：{能测什么/测不到什么/怎么验证}

> 假设：{CPM 区间、频次、点击率、未去重说明}
```

## 异常处理

| 情况 | 处理 |
|------|------|
| 预算 < 最低渠道门槛（约 1 万 AED） | 明确说"只够单点测试"，给单渠道方案 + 预期上限 |
| 脚本报 `no channel fits this budget` | 降低 `--reserve`、换更低价渠道、或建议提高预算 |
| 行业 id 不存在 | 跑 `intel_query.py list-sectors` 取合法值，不要猜 |
| 用户要求固定百分比 | 按用户比例执行，但标注"该配比偏离基线，风险是 X" |

## 与其他工作流的关系

- **上游**：W2 的分层结论（决定 `--audience`）。
- **下游**：W4 用这里的渠道清单排时间轴；W5 用渠道清单确定文案规格（比例、语言、时长）。
- **依赖**：`skills/uae-market-intel` 的渠道目录与行业备注。
