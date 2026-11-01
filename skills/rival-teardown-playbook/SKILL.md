---
name: rival-teardown-playbook
description: |
  Five-layer competitor teardown playbook for Amazon sellers. Converts a rival ASIN, listing URL, pasted page content or screenshots into a graded evidence ledger, a five-layer dissection (demand positioning / message / visuals / voice-of-customer / arena), a reproducible strength score, and a differentiation playbook with copy seeds, visual briefs, review-risk actions and validation metrics.
  Trigger phrases: 竞品拆解、竞品分析、对手为什么卖得好、差异化打法、listing 反向拆解、review 挖掘、对手强在哪。
version: 1.0.0
license: See LICENSE in the expert package root
---

# 竞品拆解作战手册（rival-teardown-playbook）

这套手册解决一个问题：**把「对手卖得好」这个模糊感受，变成可以照着做的动作。**

它由四部分组成：

| 组成 | 作用 | 位置 |
|---|---|---|
| 五层拆解框架 | 决定「看什么、怎么看出选择与代价」 | `references/framework.md` |
| 证据规则 | 决定「什么能写进结论、什么只能待验证」 | `references/evidence-rules.md` |
| 输出契约 | 决定「交付什么文件、章节顺序、质检门槛」 | `references/output-contract.md` |
| 切口模式库 | 决定「差异化从哪几个方向找」 | `references/playbook-patterns.md` |

配套工具：`scripts/teardown_toolkit.py`（零依赖，只用 Python 标准库）。

## 一、执行顺序（六步，不可跳步）

### 第 1 步 输入体检 `intake`

```bash
python3 scripts/teardown_toolkit.py parse "<用户给的原始输入>"
```

输出：ASIN、站点、规范化链接、输入类型（asin / url / short-link / text）、缺失字段清单。

判定规则：

- 拿到 ASIN 或可抓链接 → 继续第 2 步
- 只有文本/截图 → 记录为「用户供给」通道，缺失字段写进台账
- 什么都没给 → 一次性问 3 个问题（竞品标识、我方产品、本次目标），问完开工

### 第 2 步 建台账 `ledger`

```bash
python3 scripts/teardown_toolkit.py ledger --asin B0XXXXXXXX --out 证据台账-B0XXXXXXXX-2026-10-28.csv
```

台账字段固定：`字段, 值, 来源, 等级, 采集时间, 备注`。

采集时边拿边填，等级只能是 E1 / E2 / E3 / U（定义见 `references/evidence-rules.md`）。
拿不到的字段写「未获取」，不许留空，也不许写 0。

### 第 3 步 五层拆解

按 `references/framework.md` 逐层执行。每层三个必答项：**做了什么选择 / 服务谁 / 代价是什么**。

每层结尾一行结论，格式固定：

```
本层结论：<一句话> [E1-03][E2-07] 置信度：中
```

### 第 4 步 评分 `score`

```bash
python3 scripts/teardown_toolkit.py score --positioning 78 --message 85 --visual 90 --voice 72 --arena 65
```

输出加权总分、强度档位、建议打法（正面压 / 单点突破 / 侧翼 / 换战场）。
权重固定 20/20/20/25/15，不接受临时改权重——改权重会让不同竞品的分数失去可比性。

### 第 5 步 出报告 `scaffold` + 填充

```bash
python3 scripts/teardown_toolkit.py scaffold --asin B0XXXXXXXX --date 2026-10-28 --out ./竞品拆解-B0XXXXXXXX-2026-10-28.md
```

先用模板生成骨架，再按章节填充。骨架里的 `<!-- FILL -->` 全部替换掉才算完成。

### 第 6 步 质检 `check`

```bash
python3 scripts/teardown_toolkit.py check ./竞品拆解-B0XXXXXXXX-2026-10-28.md
```

质检项：必需章节齐全、无残留占位符、结论带证据编号、含样本量披露、含数据缺口表、含合规红线小节。
任一项失败 → 修到通过 → 再交付。

## 二、五层拆解一览

| 层 | 核心问题 | 典型证据 | 常见误判 |
|---|---|---|---|
| L1 需求定位 | 他在服务哪个具体场景里的哪类人 | 标题主语、场景词、变体结构、QA 提问方式 | 把「品类」当「场景」，结论落不到动作 |
| L2 表达 | 他用什么叙事结构说服人 | 标题句式、五点顺序、A+ 分段逻辑、关键词位置 | 只数关键词，不看关键词的排列顺序 |
| L3 视觉 | 他用什么视觉动线制造第一眼优势 | 主图构图、副图顺序、对比图、信息图密度 | 把「好看」当「有效」，说不出转化理由 |
| L4 口碑 | 用户为什么买、为什么退 | 好评聚类、差评穿透、QA 心理防线 | 只读差评，忽略好评里被反复确认的购买理由 |
| L5 格局 | 他在价格带和流量结构里占了什么位置 | 价格、变体、捆绑、优惠、类目排名、广告位 | 只看自己类目，忽略相邻类目的替代品 |

## 三、交付物

| 文件 | 内容 | 谁看 |
|---|---|---|
| `竞品拆解-{ASIN}-{date}.md` | 完整五层拆解 + 评分 + 打法 | 运营负责人 |
| `打法卡-{ASIN}-{date}.md` | 一页纸：主攻方向 + 5 条动作 | 老板 / 跨部门 |
| `文案种子-{ASIN}-{date}.md` | 3 个角度的标题与五点草稿 | 文案 /  listing 执行 |
| `证据台账-{ASIN}-{date}.csv` | 字段级来源与等级 | 复核 / 存档 |

## 四、质检门槛（交付前自检）

1. 每条结论后面有证据编号；没有编号的结论要么补证据，要么降级为「待验证」。
2. 口碑层写清样本量（「分析了前 40 条，其中 1-3 星 11 条」），不写「大量评论显示」。
3. 数据缺口表至少 1 行；如果真的一项不缺，写「无」，并说明采集覆盖范围。
4. 合规红线小节必须存在；没有风险就写「本报告未发现明显合规风险点」。
5. 打法动作必须带验证指标和验证周期；写不出指标的动作用「探索性动作」标注，不与已验证动作混排。
6. 报告里不出现「最」「第一」「唯一」这类绝对化表述去描述竞品或我方产品。

## 五、依赖与边界

- **依赖**：Python 3.8+ 标准库。无第三方包、无 API Key、无网络请求。
- **数据来源**：宿主环境提供的抓取能力 / 电商数据工具 / 用户提供内容，三者任一即可跑通。
- **不做的事**：不抓取非公开数据、不绕过登录与验证码、不代写侵权文案、不承诺销量预测精度。
- **失败降级**：任一层数据缺失只降该层置信度，不阻断整份报告；连续两层无证据时，先交付「部分拆解 + 缺口说明」，再与用户确认是否补数。
