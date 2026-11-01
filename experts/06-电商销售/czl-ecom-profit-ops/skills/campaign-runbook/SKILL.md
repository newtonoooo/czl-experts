---
name: campaign-runbook
description: "Fourth gate, second half. Builds a T-60 campaign runbook organised around decision deadlines rather than task lists: enrolment cut-off, price verification, asset lock, stock commitment, price-protection window, war-room cadence, and the post-event return wave. Splits budget across warm-up, burst and comeback phases, and defines the abort criteria for each phase. Use 45-60 days before 618, Double 11, Double 12, CNY or any platform mega-sale."
---

# 大促倒排：按决策点排，不按任务清单排

## 什么时候用

- 618 / 双 11 / 双 12 / 年货节前 45–60 天
- 平台临时大促（提前 14 天内的版本，见文末"短周期版"）
- 活动复盘后要改下一次的打法

## 为什么按决策点排

任务清单谁都会写，问题是**任务没有截止时间**。倒排表真正的作用是把"过了这个点就做不了"的事情标出来：

- 报名截止了，价格再算得漂亮也进不去
- 素材定稿晚了，主图来不及测
- 价格校验没做，活动期被系统判价格力不足，流量进不来
- 价保窗口没算，返场降价把利润再吐一遍

所以这张表每一行都必须有**日期 + 决策 + 不做的后果**。

## 三个阶段与预算分配

| 阶段 | 时间 | 目标 | 预算占比 | 判据 |
|---|---|---|---|---|
| 蓄水 | T-14 到 T-1 | 加购、领券、收藏、种草 | 25% | 加购量 / 领券量 |
| 爆发 | T 日 | 成交 | 60% | 实时 ROI 与库存 |
| 返场 | T+1 到 T+3 | 捡漏、清尾货、承接未付款 | 15% | 转化率与退款率 |

**爆发期的预算不要一次投满**，留 30% 给当天下午根据实时数据加投。上午的数据只代表上午。

## 操作要点

1. 先用 `promo-math` 算出机制叠加后的实收和保本实收，**再决定报不报名**。报名后再算，只能接受结果。
2. 用 `promo-math stock` 算备货与现金峰值，把采购决策放进 T-25 之前——晚了供应商排产排不进去。
3. 用 `sku-margin` 复核活动价下的单均贡献毛利，负数就改机制（减一层优惠 / 换赠品 / 提客单），不要硬报。
4. 备货优先级按 `assortment-roles` 的角色排：利润款优先，引流款按保守量，清货款不补。

## 输出

一张倒排表（谁、哪天、做什么决定、不做会怎样）+ 三段预算金额 + 每阶段的放弃条件。

例：

| 日期 | 决策 | 负责人 | 不做的后果 |
|---|---|---|---|
| T-52 | 报名哪些场次 | 运营 | 错过报名，无会场流量 |
| T-45 | 活动价与机制定稿 | 老板 | 后面所有素材和备货都建立在错的价上 |
| T-25 | 采购下单 | 供应链 | 排产来不及，只能空运补货，成本翻倍 |

## 异常

| 情况 | 处理 |
|---|---|
| 距活动不到 30 天 | 用"短周期版"（见 reference），砍掉素材 A/B 和达人种草，只保价格、备货、客服 |
| 平台规则还没公布 | 按去年规则搭骨架，把所有依赖规则的日期标"待确认"，规则公布当天重排 |
| 库存已在路上，来不及改 | 不设备货决策，改设备货后的处理方案：返场价、搭赠、跨平台分流 |
| 用户只想做"活动当天" | 说明只做当天的结果通常是：价格没优势、库存不准、客服崩。给最小可行版（价格+库存+客服三件事） |
| 多平台同时做 | 每个平台单独一张倒排表，共用一份库存表；冲突时按毛利高者优先 |
| 去年活动亏了 | 复盘先做归因（`funnel-review`），再排今年。不复盘就排，是重复去年的错 |

## 与其他技能的关系

- 上游：`promo-math`（机制与备货）、`sku-margin`（活动价毛利）、`assortment-roles`（备货优先级）
- 下游：`funnel-review`（活动后拆解）、`copy-compliance`（大促话术与主图文案体检）
- 倒排细则：`references/t60-timeline.md`
