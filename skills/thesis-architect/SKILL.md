---
name: thesis-architect
description: 论文写作全流程手册集：选题开题、文献综述、结构提纲、摘要关键词、引言、方法、结果图表、讨论结论、语言润色、降重查重、引用格式、答辩投稿，另附中文与英文句子库。Use when the user needs thesis text written, rewritten, shortened, polished, formatted or prepared for defense and submission.
---

# 论文写作全流程

## 怎么用这本手册

不是先读全套再动手。**用户点哪个模块，只读那个模块的手册，写完就交。**

- 要写引言 → 读 `references/05-introduction.md`
- 要改摘要 → 读 `references/04-abstract-and-keywords.md`
- 要润色 → 读 `references/09-language-zh.md` 或 `10-language-en.md`
- 不确定文体怎么写 → 读 `references/14-genre-methods.md`

每份手册都给四样东西：**段落配方 → 句式库 → 示范段落 → 常见错误对照**。
句式库是取材用的，不是抄的：取一句的骨架，换成你的内容，别整段搬。

## 十二个写作模块

| 编号 | 模块 | 手册 | 一句判断 |
|---|---|---|---|
| W1 | 选题与开题 | `01-topic-and-proposal.md` | 题目不定，后面全是白写 |
| W2 | 文献与综述 | `02-literature-review.md` | 综述不是读书笔记，是按争议组织 |
| W3 | 结构与提纲 | `03-structure-and-outline.md` | 每章都要有不可替代的职责 |
| W4 | 摘要与关键词 | `04-abstract-and-keywords.md` | 摘要是全文的压缩，不是导语 |
| W5 | 引言 | `05-introduction.md` | 四段：背景→缺口→问题→贡献 |
| W6 | 方法章 | `06-methods.md` | 别人照着你写的能重做一遍 |
| W7 | 结果与图表 | `07-results-and-figures.md` | 结果只报事实，解释留给讨论 |
| W8 | 讨论与结论 | `08-discussion-conclusion.md` | 讨论要对话，结论要收口 |
| W9 | 语言润色 | `09-language-zh.md` / `10-language-en.md` | 清晰优先于漂亮 |
| W10 | 降重与查重 | `11-dedup-and-similarity.md` | 换骨架，不是换同义词 |
| W11 | 引用与格式 | `12-citation-and-format.md` | 格式错会被认为引用不实 |
| W12 | 答辩与投稿 | `13-defense-and-submission.md` | 一页一件事，讲稿不念 PPT |

文体判断 → `14-genre-methods.md`。句子取材 → `templates/sentence-bank-zh.md`、`sentence-bank-en.md`。

## 写作通用流程

1. **定位**：这一章/这一段要回答什么问题、多少字、给谁看。
2. **配方**：列出每段干什么（立论/举证/反驳/过渡/收束），先定骨架再落笔。
3. **起稿**：按配方逐段写，一段一个动作，段首给判断句。
4. **核验**：字数、引用位置、术语一致、占位符列全。
5. **自查**：跑对应脚本（字数、摘要、语言、图表、引用、重复），按报告回原文定位。

## 各模块的产出要求

| 模块 | 必须给到的产出 | 不许只给 |
|---|---|---|
| W1 | 3—5 个题目候选 + 评估 + 收敛题目 + 研究问题 + 开题报告全稿 | 一堆方向让你自己选 |
| W2 | 检索式 + 综述正文（带出处占位）+ 段落衔接 | 文献清单 |
| W3 | 三级提纲 + 字数预算 + 每章任务 | 只有章名 |
| W4 | 中文摘要 + 英文摘要 + 关键词 | 摘要的写作要点 |
| W5 | 四段式引言正文 | 引言该写什么 |
| W6 | 方法章正文（含样本、工具、程序、分析、效度） | 方法章目录 |
| W7 | 结果叙述句 + 三线表 + 图注 | 建议你自己画表 |
| W8 | 讨论正文（发现/对比/机制/边界）+ 结论 + 分层建议 | 讨论要点 |
| W9 | 改后全文 + 对照表 | 只说哪里有语病 |
| W10 | 逐段改写 + 引用补标位置 | 让你自己换词 |
| W11 | 排好格式的参考文献表 + 核对清单 | 格式要求罗列 |
| W12 | 逐页 PPT + 讲稿 + 问答 + 信件全文 | PPT 大纲 |

## 硬约束

不编造文献/数据/批注/规定；缺材料用 `〔待补：缺什么｜从哪拿〕`；推断用 `〔核验：…〕` 标注；
不承诺通过、录用、查重率；不代检索付费库；不提供规避查重与 AI 检测的方法；
伦理审批未完成不做实施性建议。

## 工具

`scripts/` 下六个写作工具：`wordstat.py`（字数结构）、`cite_format.py`（引用转换与检查）、
`abstract_check.py`（摘要）、`style_lint.py`（语言）、`dup_scan.py`（重复比对）、`figtable.py`（图表）。
用法见 `manifest.yaml` 的 tools 段与各脚本 `--help`。
