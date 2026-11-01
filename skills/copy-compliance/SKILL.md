---
name: copy-compliance
description: "Sixth gate. Lints product titles and detail copy against six risk classes - absolute claims, out-of-scope efficacy, price comparison, review inducement, off-platform diversion, and title structure - and returns a replacement for every hit rather than just a red flag. Also checks title length against a configurable platform limit, keyword stuffing and decorative symbols, and points to the category licence check for food, health food, cosmetics, medical devices, toys and 3C. Use before publishing any listing, main image, detail page or live-commerce script."
---

# 合规：先把会被罚的句子挑出来

## 什么时候用

- 上架前、改标题前、改详情前
- 大促主图和直播话术定稿前
- 被平台提示"极限词"或被投诉后
- 进入新类目前（先查资质，再写文案）

## 六类风险

| 类别 | 典型表达 | 风险 | 依据方向 |
|---|---|---|---|
| 绝对化用语 | 最好、最强、国家级、唯一、销量第一 | 高 | 《广告法》禁止"国家级""最高级""最佳"等用语 |
| 功效越界 | 治疗、消炎、降血压、减肥不反弹 | 高 | 非药品/非医疗器械不得宣称疾病治疗功能 |
| 价格与比价 | 原价、专柜价、全网最低、划线价 | 高 | 虚假折价、虚假价格比较属价格欺诈 |
| 诱导交易 | 好评返现、刷单、删差评、仅剩 3 件 | 高/中 | 平台规则禁止；虚假紧迫涉虚假宣传 |
| 站外导流 | 加微信、二维码 | 中 | 平台规则禁止引导站外交易 |
| 标题结构 | 超长、关键词堆砌、装饰符号 | 中/低 | 平台发布规范 |

## 操作

```bash
# 详情页整段体检
python scripts/copy_lint.py --file detail.txt

# 标题体检（按 30 字上限，上限以平台当期规范为准）
python scripts/copy_lint.py --text "316不锈钢儿童保温杯 6小时保温 400ml" --title --limit 30

# 机器可读输出
python scripts/copy_lint.py --text "..." --json
```

退出码 1 表示存在高风险命中，可直接接进发布前的检查脚本。

## 处理原则

1. **每一处命中都要给替换写法**，不能只标红。只标红的检查表没人会用第二次。
2. **能给出证据的表述可以保留**。"销量第一"不行；"本店近 30 天售出 1.2 万件"可以（前提是真实）。
3. **拿不出凭证就删**，不要改成"据称""据说"——这类转述同样构成虚假宣传风险。
4. **资质先于文案**。类目资质不全时，文案写得再干净也没用，先解决资质（见 `references/category-licenses.md`）。

## 改写示例

| 原文 | 风险 | 改写 |
|---|---|---|
| 最安全的儿童保温杯 | 绝对化用语 | 316 不锈钢内胆，符合 GB 4806 食品接触用材料标准 |
| 食品级材质 | 依据不足 | 内胆材质 316 不锈钢，检测报告编号 XXX |
| 全网最低价 | 虚假比价 | 到手价 69 元（活动期 10.20–11.11） |
| 治疗口腔溃疡 | 功效越界 | 不涉及（删除；非药品不得宣称） |
| 宝宝专用 | 依据不足 | 适合 6 个月以上婴幼儿使用（附适用说明） |
| 好评返现 5 元 | 诱导评价 | 删除；改为"如有问题请联系客服" |
| 仅剩最后 3 件 | 虚假紧迫 | 库存 128 件（真实库存） |

## 异常

| 情况 | 处理 |
|---|---|
| 用户说"同行都这么写" | 同行违法不等于你可以。给一句：被投诉时按你的链接处罚，不按同行的 |
| 用户说"我确实是最好的" | 主观优劣不能作为绝对化用语的抗辩。改成可验证的事实 |
| 词表没命中但用户仍担心 | 词表只覆盖常见表达，人工再看一遍主图、直播口播、客服话术 |
| 是保健食品/化妆品 | 只能按批准或备案的功效表述，不得扩展。先取得批准文件原文 |
| 涉及疾病名、药品名 | 一律不用，除非是药品广告且已取得广告审查批准 |
| 直播口播稿 | 按同一套词表检查，口播违规同样被处罚且更难撤证 |

## 与其他技能的关系

- 上游：无（可独立使用）
- 下游：`campaign-runbook`（大促素材定稿前必过）
- 词表与依据：`references/banned-claims.md`
- 类目资质：`references/category-licenses.md`
