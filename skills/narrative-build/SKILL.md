---
name: narrative-build
description: Build the executive summary first, then the three-act body. Produces a five-part summary (situation, tension, thesis, proof, end state) within 700 characters and a section order derived from the scoring matrix, then lints the summary for length, paragraph count, numeric density, empty adjectives and cliche openings. Use when the user asks for an executive summary, a proposal structure, or says the draft reads flat.
description_zh: 成篇关。先写五段式执行摘要（≤700 字），再按评分矩阵排章节，并用脚本体检结构与数字密度。
---

# 成篇关 · 叙事与执行摘要

## 为什么先写摘要

执行摘要写不顺，说明立意还没想清楚。此时写正文只是把糊涂放大到三十页。所以顺序是：先摘要，摘要过了再展开正文。

摘要不是全文缩写，是**放在最前面的结论**。很多评委只看这一页。

## 五段结构

| 段 | 写什么 | 长度 | 常见错误 |
|---|---|---|---|
| 1 处境 | 客户现在的样子，用他们的话 | 2–3 句 | 先介绍自己公司 |
| 2 张力 | 不做会怎样，带数字 | 1–2 句 | 只说"很重要" |
| 3 主张 | 我们怎么解决，主题在此出现 | 2–3 句 | 罗列功能 |
| 4 证据 | 一个够硬的案例或数据 | 1–2 句 | 说"经验丰富" |
| 5 终局 | 交付后能验收的样子 | 2 句 | 抒情升华 |

全文控制在 700 字内。

## 命令

```bash
python scripts/summary_lint.py 执行摘要.md --anchor 客户全称
```

七项检查：字数、段落数（4–8）、首段是否出现客户锚点、数字密度（≥2）、空词、开场套话、单段是否超过 260 字。退出码 1 表示未通过。

`samples/summary-good.md` 是通过的样子，`samples/summary-draft.md` 是典型套话稿，可对照看差在哪。

## 正文三段

1. **懂你的活**：复述客户的约束（工期、现网、合规、政治现实），证明我们做过功课。这一节最容易省，也最容易丢分。
2. **我们怎么干**：按评分矩阵的顺序展开，每节开头两句要能单独读懂（评委会跳读）。做法写成动作序列，不写成名词堆。
3. **你会变成什么样**：可验收的状态、里程碑、度量口径。

## 判据

- 摘要能单独抽出来当一页纸发出去，不需要正文解释。
- 每章开头两句话能回答"这章解决评分表哪一项"。
- 全文没有一段是为了"看起来完整"而写的。

## 输出

执行摘要（Markdown）+ 章节骨架（标题 + 每节两句话要点 + 对应得分点）。骨架先给客户确认，再写正文——顺序反了会返工。

## 异常处理

- **数字凑不出来**：说明证据不足，先回 `evidence-ledger` 补证；不要编数。
- **客户要求写得"大气"**：大气通常指模糊。改成"具体到让对手没法抄"，并给一版对照示例。
- **篇幅被限制在 20 页内**：优先砍"我们是谁"和"公司简介"，保留评分矩阵对应章节与执行摘要。

## 与其他技能的关系

主题从 `win-theme-forge` 来，章节顺序从 `rfp-decode` 的矩阵来，数字口径从 `evidence-ledger` 与 `price-story` 来。四者用的是同一套事实。
