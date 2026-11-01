---
name: win-theme-forge
description: Forge and stress-test win themes. Turns buyer pain into three to five theme cards, each carrying the buyer's own words, our move, an evidence level, target sections and clone risk, then lints every card for empty adjectives, missing evidence tags and missing buyer anchors. Use when the user asks what makes us win, how to distil highlights, or why the proposal reads like a capability brochure.
description_zh: 立意关。把买方痛点锻造成 3–5 张赢标主题卡，并逐条检查空词、证据等级与客户锚点。
---

# 立意关 · 赢标主题

## 什么时候用

- 客户问"我们凭什么赢""亮点怎么提炼"。
- 方案写完自己读着像"能力说明书"：每章都在讲我们有什么，没讲客户能得到什么。
- 评审反馈"没有记忆点""看完记不住"。

## 核心判据：三问过堂

每条主题必须同时过三关，任何一关不过就重写：

1. **只对这家客户成立吗？** 把客户名换成别家还成立 → 太泛。
2. **有证据吗？** E1（客户侧数据）或 E2（同类项目实证）才算硬证据。只有 E3（方法）和 E4（假设），说明还只是想法。
3. **对手照抄会不会露馅？** 会露馅＝有壁垒；照抄也成立＝不是差异化。

## 一条主题的构成

| 部分 | 写什么 | 反例 |
|---|---|---|
| 主题句 | 一句话，含客户与结果 | "提供优质服务" |
| 客户原话痛点 | 客户自己说过的麻烦，最好带数字 | "客户很重视质量" |
| 我们的做法 | 三个以内具体动作 | "采用先进技术" |
| 证据 | E 级 + 一句可核实的事实 | "经验丰富" |
| 落章 | 出现在哪几节 | 空着 |
| 照抄风险 | low / medium / high | 不填 |

## 命令

把主题写成 JSON（结构见 `samples/themes.json`），然后：

```bash
python scripts/theme_check.py samples/themes.json --md 主题卡体检.md
```

脚本检查：主题句长度、空词命中、证据是否标 E 级、是否落章、是否出现客户锚点、易被照抄却只有弱证据。

退出码 1 表示有主题 FAIL，改完再跑。`samples/themes-bad.json` 是一份典型的空话主题，可以用来看脚本报什么。

## 数量与排序

一般 3–5 条，按分值权重排序，第一条必须是最能打动评委的那条（通常与最高分值项对应）。超过 5 条说明还没想清楚主次。

## 输出

主题卡表 + 一段话说明"如果只让评委记住一句，是哪一句"。后者往往比表格更有用——评委真正记住的通常只有一句。

## 异常处理

- **客户坚持要"行业领先"这类表述**：可以留在封面语，但不能作为主题句；主题句必须能被证据支撑。
- **一条主题都写不出来**：回到 `rfp-decode`，多半是没找到高分项对应的真实优势，或者根本没有优势需要换打法。
- **主题互相重叠**：合并。评委记不住三条意思一样的话。

## 与其他技能的关系

主题卡是执行摘要的骨架（`narrative-build`），也是证据账本的索引（`evidence-ledger`）：每条主题至少挂一条 E1/E2 证据，账本里要能找到对应材料。
