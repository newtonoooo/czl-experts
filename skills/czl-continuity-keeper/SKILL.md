---
name: czl-continuity-keeper
description: 长篇档案与连续性管理。当用户要建项目、提交章节入档、接管旧稿、查看进度、登记或回收伏笔、检查缺章与称号漂移、导出全本时加载。回答"写到哪、欠什么、下一步动哪里"。Use when the user needs project setup, chapter archiving, progress reporting, foreshadowing tracking, or continuity checks on a long serial.
---

# 台账：档案与连续性

## 职责边界

只做一件事：让"这本书现在处于什么状态"变成可读的数据，而不是靠回忆。

**不做**：不写正文、不改设定。发现冲突只报告，不擅自决定以谁为准。

## 为什么必须有这一环

写到三十章以后，靠记忆必然出现三类错：人物称法换了、能力上限飘了、伏笔埋了没回收。这三类错读者会当场抓出来。台账的作用不是"记录"，是**在写下一章之前拦住它**。

## 输入

- 作品目录（首次由 `init` 创建）
- 每章正文文件
- 体检报告（来自 `czl-voice-tune`）

## 步骤

### 第 1 步：建项目

```bash
python skills/czl-continuity-keeper/scripts/nproj.py init \
  --dir "作品目录" --title "书名" --target 1000000 --chapter-words 3000
```

生成：

```
作品目录/
  .nproj/state.json     项目状态（章节、字数、伏笔、待办、待复核）
  chapters/             正文
  qc/                   体检报告
  export/               导出版本
```

`bible.json`（规则表、人物卡、称号表）由 `czl-story-architect` 产出后放进 `.nproj/`。

### 第 2 步：每章的顺序，一步不能换

```
写正文 → 体检(voice_scan 出 json) → 提交入档(commit) → 结构核查(lint)
```

**必须先有体检报告再提交。** 没有 `qc/ch-XXX.report.json`，`commit` 会把这章记为 `missing` 并把档案标为待复核。

```bash
python skills/czl-voice-tune/scripts/voice_scan.py chapters/ch-001.md \
  --json qc/ch-001.report.json --quiet

python skills/czl-continuity-keeper/scripts/nproj.py commit \
  --dir . --chapter 1 --file chapters/ch-001.md --title "章名" --summary "一句话"
```

### 第 3 步：伏笔登记（埋的时候就登记，不许事后补）

```bash
nproj.py thread --dir . add --id t1 --content "剪刀是谁的" --planted 1 --due 12
nproj.py thread --dir . resolve --id t1 --chapter 11
nproj.py thread --dir . drop --id t2 --note "改成支线，不再回收"
```

三条纪律：
1. **埋的时候同时写到期章。** 写不出到期章就别埋。
2. **回收必须有正文章节号。** 口头说"收了"不算。
3. **放弃要留痕。** 不许默默消失——读者记得，作者忘了，就是坑。

### 第 4 步：结构核查（每章入档后跑一次）

```bash
python skills/czl-continuity-keeper/scripts/lint_project.py --dir . --json qc/lint.json
```

七项检查：

| 代码 | 检查 | 级别 |
|---|---|---|
| L1 | 缺章 | 阻断 |
| L2 | 单章字数越界 | 提示 |
| L3 | 体检缺失或未过 | 阻断 |
| L4 | 伏笔到期未收 | 阻断（临近到期为提示） |
| L5 | 称号漂移（同章多种称法） | 提示 |
| L6 | 档案待复核 | 阻断 |
| L7 | 登记与磁盘文件不一致 | 阻断/提示 |

有阻断项，**不许写下一章**。

### 第 5 步：回答"我现在到哪了"

```bash
nproj.py status --dir .
```

输出五件事：写到第几章、总字数与目标占比、缺章、体检未过、未回收伏笔与已到期项、下一步。**这就是用户隔三天回来要的那一句话。**

## 接管旧稿（重点场景）

用户拿一叠旧稿来，不要一上来就读全文。

1. 按章拆文件，命名 `ch-001.md`、`ch-002.md`……
2. `init` 建项目，`--target` 按用户说的全书字数，`--chapter-words` 按现有章节的实际均值
3. 逐章 `commit`，**先不强求体检**（旧稿体检会大面积 FAIL，先建档）
4. 从正文反推 `bible.json`：人名与称法、能力与上限、时间线锚点。**反推不出来的，标"未知"，不许编**
5. 跑 `lint`，把缺章、字数异常章、称法混用列给用户
6. 跑一次 `voice_scan` 抽样 3 章，给整体人味分区间
7. 给用户一页接管报告：现状、欠什么、建议从哪一章开始动

**接管时不许声称"我记得前文"。** 所有"记得"必须来自档案。

## 判断条件

| 情况 | 处理 |
|---|---|
| 用户要求跳过体检直接入档 | 拒绝。说明代价（后面每一章的对照基线都是脏的） |
| 用户说"这两章顺序反了" | 改章节号并重跑 lint，不许留两个 ch-005 |
| 用户改了已入档的正文 | 重新 commit 该章（会覆盖并更新指纹），然后重跑 lint 看有没有连带冲突 |
| 伏笔到期但剧情确实用不上 | 走 `drop`，并建议在正文里给一句交代 |
| 用户只想看进度 | 只跑 `status`，不写任何文件 |

## 输出

```
.nproj/state.json       项目状态（脚本维护，不要手改）
qc/ch-XXX.report.json   每章体检
qc/lint.json            结构核查
export/<书名>-vN.md     导出版本
（对话中）状态一句话 + 阻断项清单
```

## 异常处理

- **没有 Python**：明确说"无法建可校验的档案"，改为交付一份结构化交接包（章节清单、字数、伏笔表、待办），并标注"未落盘校验"。
- **state.json 被手改坏**：`json` 解析失败会报错。不要静默重建，先备份坏文件再重建。
- **章节号冲突**：同号章会被后提交的覆盖。覆盖前打印提示，用户确认后再提交。
- **导出时缺章**：导出会在文内留空并提示缺章号，不假装完整。

## 依赖

`scripts/nproj.py`（建档/提交/伏笔/导出）、`scripts/lint_project.py`（七项核查）。纯标准库。

## 与其他工作流的关系

上游：`czl-chapter-forge`（正文）、`czl-voice-tune`（体检报告）、`czl-story-architect`（bible.json）。
下游：`czl-delivery-pack`（导出与投稿）、`czl-data-doctor`（进度与数据对照）。

## 脚本

三个脚本，`nproj.py` 的子命令新增 `verify`：

```bash
# 校验正文与档案是否一致、依赖链是否完整
python scripts/nproj.py verify --dir .
```

`commit` 时会给每章记两个指纹：本章 SHA-256，以及**前一章的 SHA-256**。`verify` 据此查两件事：

1. 磁盘上的正文有没有被手改（与入档指纹不符）
2. 依赖链断没断（本章记录的前章指纹 ≠ 前章当前指纹）

**边界要说清**：这是完整性校验，不是防篡改签名。它能发现"悄悄改了但没重新提交"，挡不住刻意伪造——要防伪造得引入密钥，那超出这个产品的范围。

改稿后必须重跑 `commit`，否则 `verify` 一定报不一致。这是设计如此，不是 bug。
