---
name: funnel-review
description: "Fifth gate. Decomposes a net GMV change into UV, conversion rate, AOV and refund rate using sequential substitution so the four contributions add up exactly to the total, then ranks the drivers and states what can and cannot be said. Starts by checking whether the two periods are even comparable (tracking version, campaign timing, refund attribution). Use for 'why did it drop', monthly reviews, campaign post-mortems, or when two people quote different numbers for the same week."
---

# 复盘：先拆数，再解释

## 什么时候用

- "这个月为什么掉了"
- 月度/大促复盘
- 两个部门报的数不一样
- 涨了但利润没涨

## 拆解公式

```
净成交额 = UV × 转化率 × 客单价 × (1 − 退款率)
```

四项依次替换，每换一项算一次净成交额，差值就是这一项的贡献。四项之和精确等于总变化（工具会打印残差，正常为 0）。

**为什么用逐项替换而不是简单乘比例**：比例法在多项同时变化时无法加总，最后总是"还有一部分解释不了"。逐项替换的代价是交叉项被先替换的一项吃掉，所以顺序固定写上。

## 操作

```bash
python scripts/funnel_check.py decompose \
  --p1-uv 120000 --p1-cvr 0.031 --p1-aov 168 --p1-refund 0.14 \
  --p2-uv 98000  --p2-cvr 0.028 --p2-aov 181 --p2-refund 0.19
```

## 先查口径，再谈归因

拆数之前必须过四问。任一问答"变了"，就先断开趋势线，不要往归因走：

1. 埋点或报表逻辑，两期之间改过吗？
2. 系统迁移过吗？（换后台、换服务商、换统计口径）
3. 退款算在哪一期？（下单期 / 退款发生期，两者完全不同）
4. 活动有没有错位？（去年大促在 11 月 1 日，今年在 10 月 31 日）

**在排除这四条之前讨论"为什么掉了"，是浪费会议时间。**

## 输出

1. 两期四项指标对比表
2. 四项贡献额 + 占总降幅/增幅比例 + 主因排序
3. **可以说 / 不能说**两句话——这是最重要的部分

例：

- 可以说：净成交额下降 25.1%，其中流量减少贡献 72.9%，转化率下降贡献 31.4%，退款率上升抵掉 18.4%，客单价上升对冲 22.7%。
- 不能说：因为竞品降价所以流量掉了。—— 这句话需要竞品价格监测数据支撑，现在没有。

## 归因候选表（别急着下结论）

| 候选 | 若要成立，应看到 | 现在的证据 | 状态 |
|---|---|---|---|
| 流量结构变化 | 付费占比上升、自然下降 | 未查 | 待查 |
| 竞品分流 | 流失人群与竞品重合 | 无 | 无证据 |
| 埋点漏报 | 受影响集中在某版本/某端 | 未查 | 待查 |
| 活动错位 | 去年同期有活动 | 去年同期有满减 | 部分支持 |
| 季节性 | 去年同期同向下降 | 去年降 6% | 支持 |
| 正常波动 | 在历史波动带内 | 超出 | 排除 |

**"待查""无证据""排除"都要写。** 只写支持结论的那一行，是选择性举证。

## 异常

| 情况 | 处理 |
|---|---|
| 用户只给了一个总数 | 只能给结论句 + 需要补的四个数，不做拆解 |
| 四项之和与总变化对不上 | 说明还有别的口径差（运费、优惠、跨期），先查口径 |
| 用户已经写好了归因 | 把他的单一归因放进候选表对比，不要直接推翻 |
| 退款率突然跳变 | 先看是不是某个 SKU 或某批货的质量问题，再看整体 |
| 用户要"预测下个月" | 不给点预测。给区间 + 假设 + 假设失效的信号 |
| 样本很小（周销几十单） | 不做百分比拆解，只给绝对数 |

## 与其他技能的关系

- 上游：`sku-margin`（把 GMV 拆解落到毛利）
- 下游：`campaign-runbook`（下一次怎么改）
- 口径定义卡：`references/metric-definitions.md`
