---
name: czl-math-ledger
description: 错题台账与间隔复现工作流。当用户说"错题本抄了没用""整理错题""复习计划""上次讲过的又错"时加载。用 1/3/7/21/45 天阶梯安排复现，产出到期清单与周报。Use when the user wants wrong answers organised, a review schedule, or a weekly report on what keeps coming back.
---

# 复盘：让同一道题在快忘的时候再见一次

## 职责边界

只负责记账、排期、出周报。不在这一环讲题（转 `czl-math-decompose`），不重新诊断（转 `czl-math-diagnose`）。

**不做**：不做"错题本美化"、不要求抄原题、不按科目/章节建文件夹。台账只回答一个问题：**今天该看哪几条。**

## 输入参数

| 参数 | 必需 | 说明 |
|---|---|---|
| 错题 | 是 | 至少一类：题号+得分、错题照片、或"哪几道不会"的口述 |
| 知识点 | 是 | 每条一个，取"失分发生的那个知识点" |
| 错因主码 | 是 | C/M/A/W/R 之一；定不出来先留空，别硬填 |
| 正确入口 | 是 | 一句话：这题应该从哪句条件切进去。**不是答案** |
| 台账文件路径 | 建议 | 默认工作目录下 `math-error-ledger.csv` |

**关键字段是"正确入口"**。台账里如果只存题目和答案，复现时学生只是在背答案，练不到任何动作。

## 执行步骤

### 步骤 1：建账

```bash
python scripts/ledger.py add --csv math-error-ledger.csv --source 周测三 \
  --item "导数单调性|M|已知 f(x)=x^3-3ax 讨论单调性|先求导，再看参数在二次项还是常数项"
```

一条一行，`知识点|码|题目摘要|正确入口`。题目摘要写 20 字以内，写不下就说明这题该拆成两题记。

判断条件：如果一条错题说不出"正确入口"，说明这题当时也没弄懂，直接转 `czl-math-decompose`，拆完再入账。

### 步骤 2：排期

阶梯固定：**1 → 3 → 7 → 21 → 45 天**。答对进一级，答错退回第 0 级（明天再来），并累计 `lapses`。

判断条件：同一条 `lapses ≥ 3`，不再按记忆问题处理，标明"概念缺口"，回拆题重讲一遍再回炉。

### 步骤 3：每日到期

```bash
python scripts/ledger.py due --csv math-error-ledger.csv
```

输出按逾期天数排序的清单，带"该从哪里切入"。

判断条件：单日到期超过 8 条时，只做逾期最久的 8 条，其余顺延——一次看太多等于没看。

### 步骤 4：复现后记录

```bash
python scripts/ledger.py review --csv math-error-ledger.csv --id 3 --result wrong
```

**必须真的先做一遍再看答案。** 直接看答案然后标"会了"，是把台账变成摆设的最快方式。

### 步骤 5：周报

```bash
python scripts/ledger.py stats --csv math-error-ledger.csv
```

周报回答三件事：这周该清哪些、哪些卡了三次以上、按码看这周的训练是不是打偏了。

判断条件：如果周报显示 A 码（运算）占比连续两周超过 50%，说明问题不在方法，在计算习惯，训练处方整体改为限时计算。

## 输出格式

- 每日清单：`templates/daily-due.md`（表格：id / 逾期 / 知识点 / 码 / 正确入口）
- 周报：`templates/weekly-review.md`（五段：总量 / 按码 / 卡三次 / 这周动作 / 下周不做什么）

## 异常处理

| 异常 | 处理 |
|---|---|
| 台账文件不存在 | 直接新建，不要报错要求用户先建 |
| CSV 被 Excel 改坏（列错位） | 读表头做列映射，缺列时明确报缺哪一列，不要静默丢数据 |
| 用户一次给 40 道错题 | 只入账前 10 条（按失分排序），其余让他下周再给。一次入 40 条，一条都不会复现 |
| 用户只想"整理"不想"复现" | 说清：只整理不复现，两周后等于没记。仍可整理，但要写明这个后果 |
| 日期跨月/跨年 | 用 ISO 日期（YYYY-MM-DD），不写"下周三"这种相对说法 |

## 必要依赖

- `scripts/ledger.py` — 台账增删查、排期、周报（纯标准库，CSV 可直接用 Excel 打开）
- `templates/daily-due.md`、`templates/weekly-review.md`
- `materials/error-taxonomy.md` — 码的判据

## 与其他工作流的关系

```
decompose / drill ──错题──▶ ledger ──到期──▶ 学生自己做 ──错──▶ decompose
                              │
                              └──周报──▶ diagnose（重定码）
```

- 上游：`czl-math-decompose` 拆过的题、`czl-math-drill` 练错的题。
- 下游：到期复现由学生独立完成；复现失败且卡三次以上，回拆题。
- 反向：周报是诊断的输入之一，两周一次把周报喂回 `czl-math-diagnose` 校准。
