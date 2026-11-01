---
name: promo-math
description: "Fourth gate, first half. Stacks item discount, member discount, store coupon and cross-store spend-and-save in a fixed order, then reports the merchant's real received amount, margin per unit, breakeven received amount and which layer gave the most away. Also sizes campaign stock from daily sales, uplift, lead time and safety stock, and returns purchase amount, cash-occupancy days and stockout / overstock exposure across five sell-through scenarios. Use before submitting any campaign enrolment, before setting a promo price, and before committing a purchase order."
---

# 大促机制算账：先算后报

## 什么时候用

- 报活动前：这个价能不能报
- 设计优惠结构：满减、店铺券、会员折扣、赠品怎么搭
- 备货前：备多少、压多少钱、断货和滞销各有多大风险
- 活动结束后：实际毛利和预估差多少（用同一套成本行复核）

## 为什么必须先算

大促最常见的亏法不是"折扣太大"，是**折扣叠在一起没人算过**。

单品打 9 折、会员再 95 折、店铺券满 199 减 20、跨店满 300 减 50 按金额占比分摊——单看每一层都"还行"，叠完实收只有原价的 70%，而成本一点没变。

更隐蔽的一种：**店铺券门槛按优惠后金额判定**。用户把活动价打完折发现差 1 块钱没到门槛，券不生效，你以为让利 20 元，实际一分没让，但你已经按"让了 20"去算利润了。工具会明确标"未达门槛"。

## 叠加顺序（固定）

```
活动前成交价
 → 单品折扣
 → 会员折扣
 → 店铺券 / 店铺满减（按优惠后金额判门槛）
 → 跨店满减（按本商品占整单金额的比例分摊）
 = 商家实收
```

**为什么顺序必须写死**：顺序变了结果会变。跨店满减如果按原价占比分摊，本商品承担的比例会不同。平台真实顺序可能不一样，交付时必须写一句"以活动规则页为准"，并说明顺序假设。

## 操作

```bash
# 机制叠加账本
python scripts/promo_math.py stack \
  --price 199 --cost 62 --ship 8 --commission 0.05 --payment 0.006 \
  --item-discount 0.9 --member 0.95 \
  --store-threshold 199 --store-coupon 20 \
  --cross-threshold 300 --cross-off 50

# 备货与现金占用
python scripts/promo_math.py stock \
  --daily 20 --uplift 3 --days 3 --lead-days 10 \
  --current 100 --moq 50 --unit-cost 62 --settle-days 15
```

## 输出怎么读

`stack` 给三样：

1. **逐层让利表**——哪一层让得最多。多数时候排名第一的是跨店满减，因为它是按整单分摊的隐性成本。
2. **保本实收**——毛利归零的实收金额。当前实收比它高多少，就是你的余量。
3. **判定**——亏损 / 薄利（毛利率 < 8%）/ 健康。

`stock` 给五档达成率（60%/80%/100%/120%/150%）下的期末库存、断货量、占用资金。

判断标准很土：**现金峰值超过你手头能动的钱，就先减备货量，不要靠账期硬扛。**

## 备货公式

```
活动期需求 = 日常日销 × 活动倍数 × 活动天数 + 日常日销 × 备货提前期
安全库存   = 日常日销 × 活动倍数 × 安全天数
建议采购   = 上限(活动期需求 + 安全库存 − 现有库存)，按起订量取整
现金占用天数 = 提前期 + 活动天数 + 结算周期 − 供应商账期
```

活动倍数不要拍脑袋：取去年同场活动/日常的比，没有历史就用近 30 天最好那天的倍数打折。

## 异常

| 情况 | 处理 |
|---|---|
| 不知道平台佣金和费率 | 用后台费率页；不确定就按两档算，结论取差的 |
| 跨店满减规则今年改了 | 以活动规则页为准，重新算；不要沿用去年的分摊方式 |
| 赠品是自己产品 | 按成本计入 `--gift-cost`，不要按售价计 |
| 有平台补贴（平台承担部分让利） | 从让利里扣掉平台承担部分，只算商家实际承担 |
| 用户要"冲销量，不赚钱也行" | 要求写下亏多少、亏多久、亏完之后靠什么赚回来（复购/连带/排名）。写不出来就是在赌 |
| 用户给的销量预测是"感觉能卖 500 单" | 换成三档：保守 60%、基准 100%、乐观 150%，按保守档备首批货 |
| 库存是一次性买断不能退 | 备货量按保守档，滞销风险单独写进操盘单 |

## 与其他技能的关系

- 上游：`sku-margin`（同一套成本行，别用两套数）
- 下游：`campaign-runbook`（把算出来的量填进倒排表）
- 机制细节与坑：`references/promo-mechanics.md`
