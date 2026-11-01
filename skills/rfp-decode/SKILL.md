---
name: rfp-decode
description: Decode a tender document into a working scoring matrix and a disqualification list. Turns the scoring method into scoring points with weight, evidence, target section and owner, ranks them by writing order, and scans the tender text for disqualification and hard-requirement sentences. Use when the user asks how to read a tender, how to break down the scoring table, or what could get the bid rejected.
description_zh: 读标关。把评分办法拆成得分点矩阵并按投入产出排序，同时抽出否决项与硬性要求。
---

# 读标关 · 评分表倒推

## 什么时候用

- 拿到招标文件，第一件事就是拆评分办法。
- 客户问"重点写哪几章""哪几项容易废标"。
- 方案写到一半，想回头核对有没有漏项。

## 输入

1. 评分办法原文（分值、权重、评分细则）。
2. 投标人须知（资格、密封、份数、签字要求）。
3. 技术需求（用于判断得分点对应章节）。

没有评分办法时，按通用假设（技术 40 / 商务 30 / 价格 30）推进，并在产物第一行标注"假设，待客户确认"。

## 两步走

### 第一步：矩阵（得分点）

把评分表抄成 CSV，五列：`item,score,evidence,section,owner`。

```bash
python scripts/rfp_matrix.py matrix items.csv --md 得分点矩阵.md
```

脚本会按分值降序排出写作顺序，算证据覆盖率与落章率，并标出"占比 ≥10% 却没有证据"的高风险项。这类项要么补证据，要么战略性放弃——不要用形容词填。

### 第二步：否决项

```bash
python scripts/rfp_matrix.py scan rfp.txt --md 否决项清单.md
```

按"否决/无效/废标/不予受理/不接受/不得/拒绝"抽句，另按"必须/应当/须提供/加盖/密封/原件"抽硬性要求。

**脚本输出只是候选清单，不能替代逐条核对原文。** 抽取靠关键词，会漏也会多；最终清单要人工过一遍，控制在十项以内，按"会不会直接死"排序。

## 判据

- 证据覆盖率 <60%：先补证据再动笔，否则写出来的都是形容词。
- 有 ≥10% 分值的项既无证据也无落章：列为"战略放弃"或"必须补齐"，二选一，不许悬着。
- 否决项清单没做完：不许进成篇关。这一条没有例外。

## 输出

一份矩阵（Markdown + CSV）+ 一份否决项清单。矩阵要给责任人，否则没人认领的得分点等于零分。

## 异常处理

- **评分办法只有总分没有细则**：按行业常规拆，标注"推定"，并要求客户向招标代理确认。
- **CSV 里有合并单元格导致的错行**：先在 Excel 里拆平再跑脚本，不要指望脚本猜。
- **否决项抽出来 30 条以上**：说明文件本身苛刻，先评估是否值得投（回 `bid-gatekeeper` 复评）。
- **同一得分点出现两次不同分值**：以最新版澄清文件为准，并在矩阵里留一行备注。

## 与其他技能的关系

矩阵是后面所有环节的地基：`win-theme-forge` 按高分项立意，`narrative-build` 按矩阵顺序排章节，`bid-redteam` 用同一张表打分。三处用的必须是同一份矩阵，不要各写一份。
