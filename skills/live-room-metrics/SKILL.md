---
name: live-room-metrics
description: "Livestream session arithmetic and funnel diagnosis. Computes entry rate, watch time, engagement, product click rate, pay conversion, GPM, UV value, refund rate, ad ROI and CPA from one session's raw numbers; builds a unit-economics model and breakeven ROI; back-solves required traffic and ad budget from a target GMV; and locates the leaking funnel layer against stage-based reference lines. Use whenever a livestream decision needs a number behind it."
---

# 直播指标计算与漏斗诊断

这个技能只做一件事：**把一场直播的原始数字变成能用来做决定的数字**，并且保证算出来的每个数都能被人用纸笔复核。

三个命令，一个自检：

| 命令 | 用途 | 什么时候调 |
|---|---|---|
| `session` | 一场直播的指标 + 五层漏斗诊断 | 播完复盘、开播前定基线 |
| `breakeven` | 单件经济模型 + 保本 ROI / 保本 CPA | 任何涉及投放、定价、选品的讨论之前 |
| `plan` | 从目标 GMV 反推所需点击、进房、曝光、预算 | 定目标的时候，判断目标现不现实 |
| `selftest` | 22 项公式校验 | 改动脚本后、或怀疑脚本算错时 |

脚本位置：`scripts/live_metrics.py`。纯标准库，Python 3.8+，无网络依赖，不写任何文件。

---

## 调用方式

```bash
# 1. 场次指标 + 诊断（口径: 付款口径 GMV、进房人次口径）
python scripts/live_metrics.py session \
  --impressions 180000 --entries 12600 --watch 41 \
  --likes 3200 --comments 640 --follows 180 \
  --clicks 880 --orders 42 --paid-orders 31 \
  --gmv 3069 --refund-gmv 210 \
  --ad-cost 1800 --ad-entries 6300 --stage cold

# 2. 保本测算（做投放前必跑）
python scripts/live_metrics.py breakeven \
  --price 129 --cost 41 --fulfillment 7 \
  --return-rate 0.22 --commission 0.05 --payment-fee 0.006 \
  --return-logistics 9 --fixed-cost 1200

# 3. 目标反推
python scripts/live_metrics.py plan \
  --target-gmv 50000 --aov 99 --pay-rate 0.03 \
  --click-rate 0.10 --entry-rate 0.08 --target-roi 2.5 \
  --entries-per-hour 3200
```

所有命令都支持 `--json`，便于二次处理；不加 `--json` 时输出给人看的表格。

---

## 输出契约

调用方（主 Agent）拿到结果后必须遵守：

1. **数字必须带口径。** 引用 GPM 时写"GPM 243.57（付款口径成交额 / 千进房人次）"，不写"GPM 偏低"。
2. **只报脚本算出来的数，不手工估。** 少一个参数就向用户要，或者明确标注"该值未提供，相关指标跳过"。
3. **诊断结论里"第一个漏点"优先。** 脚本按 曝光→进房→停留→互动→点击→付款 的顺序找第一个低于参考线的层，因为上层漏了，下层的数据本身就被污染。
4. **参考线不是平台标准。** 输出时必须说明这是经验参考区间，不同类目差异很大（见 `references/metric-definitions.md` 的类目修正）。
5. **样本不足要说不。** 单场付款单量低于 20 时，支付转化率的波动极大，不能据此下结论，只能作为方向。

---

## 阈值表（经验参考，非平台官方）

| 指标 | 冷启动 | 成长期 | 成熟期 | 说明 |
|---|---|---|---|---|
| 进房率 | 6% | 8% | 10% | 进房人次/曝光次数，推荐流为主 |
| 平均停留 | 45 秒 | 55 秒 | 60 秒 | 低于 45 秒基本留不住成交 |
| 互动率 | 4% | 5% | 5% | (点赞+评论)/进房人次 |
| 商品点击率 | 8% | 10% | 12% | 点击/进房人次 |
| 支付转化率 | 2.0% | 3.0% | 3.5% | 已付款/商品点击 |
| GPM | 500 | 700 | 900 | 元/千进房人次 |

这些数的作用是**给一个可比的锚**，不是判分。低客单价快消与高客单价家居的 GPM 能差五倍，看的是同一账号的纵向变化，不是横向排行榜。

---

## 常见错误（脚本会主动提醒的错误）

| 错误 | 后果 | 脚本如何处理 |
|---|---|---|
| GMV 用下单口径，转化率用付款口径 | 两个指标的分子不是同一批人 | 分别输出下单转化率与支付转化率 |
| 观看人次当成观看人数 | 停留和互动率被系统性低估 | 参数名强制区分 `--entries`（人次） |
| 下单数 < 付款数 | 口径填反 | 触发警告 |
| 广告花费大于成交额 | 多场花费混进单场 | 触发警告 |
| 用 GMV 同比不同流量结构的场次 | 得出"话术变好了"的错误结论 | 强制输出自然/付费进房占比 |
| 单件净毛利为负还建议放量 | 卖一件亏一件 | `breakeven` 直接拒绝给保本 ROI 并说明 |

---

## 不做什么

- 不做数据抓取，不连平台后台。所有数字由用户提供。
- 不做预测模型。样本量级不够，任何"预测下场 GMV"都是编的。
- 不判断平台规则。涉及违规、限流、处罚，一律建议查官方后台或问平台客服。
