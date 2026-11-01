---
name: price-story
description: Build the value case before naming a price. Computes the cost of inaction, total cost of ownership, net benefit, ROI and payback, then structures two or three price tiers that differ by scope rather than by discount, and flags the structural problems that make a price table unconvincing. Use when the user asks how to present pricing, whether to discount, or how to justify a higher price than a competitor.
description_zh: 报价关。先算不做的代价、TCO、ROI 与回本周期，再用三档配置差代替折扣，并检查报价结构问题。
---

# 报价关 · 价值先于价格

## 原则

先建立"不做会损失多少"，价格才有参照物。没有参照物的报价，客户只能拿对手的数字来比，而数字永远有更低的。

顺序固定：**代价 → 投入 → 回报 → 三档 → 让价换条件**。任何一步跳到价格，前面的工作就白做了。

## 命令

```bash
python scripts/value_case.py samples/case.json --md 价格叙事.md
```

输出：不做的代价（按年与累计）、TCO（一次性 + 年运营 × 年数）、净收益、ROI、回本周期、三档差价表、讲述顺序。

脚本会检查四类结构问题：档位少于 2 档、价格未升序、回本周期超过测算期、推荐档是最低价。

## 三档怎么设

| 档 | 定位 | 内容原则 |
|---|---|---|
| 保底 | 满足全部硬性要求的最低价 | 不多给，也不缺项，避免被废标 |
| 推荐 | 我方希望成交的配置 | 把差异化做实的地方放这里 |
| 进取 | 含增值项 | 用来锚定，让推荐档显得合理 |

档位之间要能一句话说清"多了什么"，而不是"贵了多少"。

## 判据

- 回本周期 ≤ 测算期，否则客户会问"凭什么投"。
- 每档的服务范围写得下三行，写不下说明还没想清楚边界。
- 任何折扣都必须换回至少一项条件：付款周期、合同年限、范围收缩、案例授权、预付款比例。

## 输出

价格叙事底稿（内部用）+ 对外报价页（只留代价、回报、三档，不留内部测算过程）。

## 异常处理

- **客户只给一个预算数字**：反推该预算下能做到什么、做不到什么，把"做不到"写成三期路线图，而不是硬压范围。
- **对手报价明显低于成本**：不要在价格上跟。改讲交付风险与变更成本，并给出"低价方案在第 8 个月会发生什么"的具体推演。
- **客户要求先降价再谈**：先要条件，再给价格。无条件降价会让后面每一次谈判都从更低点开始。
- **年损失无法估算**：用"每停一小时门诊损失多少挂号量"这类可观察的量做替代口径，并标 E4。

## 与其他技能的关系

代价与回报的数字来自 `evidence-ledger` 的 E1/E2 证据；报价章节的位置由 `rfp-decode` 的矩阵决定；红队阶段用 `bid-redteam` 检查报价项得分是否被低估。
