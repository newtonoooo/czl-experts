---
name: quality-gate
description: "AI-trace quality gate for Chinese WeChat Official Account drafts. Runs a quantitative script over a draft to measure sentence-length rhythm, boilerplate phrasing, meta-narration, structural sameness, paragraph function density, metaphor density, life markers and concrete information, then returns per-dimension scores, hard-fail items with locations, and targeted fix suggestions. Also scores title candidates across six dimensions and ranks them. Use when a draft must be checked before publishing, when a piece reads flat or machine-written, or when titles need objective comparison."
version: 1.0.0
---

# 质量闸门（quality-gate）

## 这个技能解决什么

写稿的人最难判断的不是"写得好不好"，而是"哪里不对"。凭感觉改，改十遍还在原地。

这个技能把"不对"拆成八项可测量的东西，用脚本量出来，再回到具体句子去改。

## 什么时候用

| 场景 | 用法 |
|---|---|
| 稿子写完，准备发 | 跑 `quality_gate.py`，过了线再发 |
| 稿子读着像 AI 写的，说不清哪里 | 跑 `quality_gate.py`，看硬伤清单 |
| 改完想知道有没有变好 | 同一稿跑两次，比数字 |
| 标题有五个候选，选不出来 | 跑 `title_score.py` 排序 |
| 要给团队定交付标准 | 把 75 分作为通过线写进规范 |

## 执行步骤

1. **拿全文**：稿件保存为 `.md` 或 `.txt`（UTF-8）。没有文件就把全文写到临时文件，不要用"我读了"代替真实运行。
2. **跑体检**：
   ```bash
   python scripts/quality_gate.py draft.md
   python scripts/quality_gate.py draft.md --json     # 需要二次处理时
   ```
3. **读报告**：先看结论（可发 / 需修 / 建议重写），再看硬伤，最后看命中位置。**不要跳过硬伤直接看总分。**
4. **定点修改**：每一条硬伤都要给出"改前 → 改后 → 为什么"。修改原则见 `references/fix-library.md`。
5. **重跑**：改完必须重跑，把两次的总分和分项并排给用户。**没有第二次运行数字的交付不算完成。**
6. **标题**（如果用户需要）：
   ```bash
   python scripts/title_score.py --file titles.txt
   python scripts/title_score.py "标题A" "标题B" --top 3
   ```

## 八项指标与阈值

| 指标 | 满分 | 量什么 | 常见病灶 |
|---|---|---|---|
| 节奏变化 | 20 | 句长变异系数（标准差/均值） | 满篇 20 字左右的句子，读起来打点 |
| 套话控制 | 20 | 每千字命中套话词数 | "首先/其次/最后""形成闭环""持续发力" |
| 元叙述 | 15 | 作者跳出来提示读者怎么读 | "这才是全文最要紧的""请注意""多说一句" |
| 句式变化 | 15 | 三句以上同构短句、对仗排比 | "第一步…第二步…第三步…" |
| 段落功能 | 10 | 首尾被过渡句占用的段落比 | 每段开头"因此""所以"，结尾"总之" |
| 比喻密度 | 5 | 平均每段比喻数 | 一段一个比喻，读着累 |
| 生活痕迹 | 10 | 口语词、引语、具体时刻 | 全是判断，没有一个时间地点 |
| 具体信息 | 5 | 数字、量词、专名密度 | 通篇没有能被核对的数字 |

**硬伤判定**（任一命中即判"需修"，不看总分）：
- 元叙述 ≥ 1 处
- 总结句标签 ≥ 1 处
- 套话 > 3 处
- 三句以上同构短句 ≥ 1 处
- "不是…而是" > 2 处
- 比喻密度 > 0.6 / 段

## 标题六维与阈值

| 维度 | 满分 | 看重什么 |
|---|---|---|
| 具体锚点 | 20 | 数字、量词、地名校名、引号内的专名 |
| 反差张力 | 15 | 转折词、两个数量级差、同一前提下的对立 |
| 留白 | 20 | 有没有把结论写进标题；问句是否自答 |
| 长度 | 15 | 主标 10—24 字，整体 ≤ 34 字 |
| 抽象程度 | 10 | "底层逻辑/认知/本质/价值"这类词越少越好 |
| 合规风险 | 20 | "震惊/必看/第一/绝对"等标题党词 |

评分 ≥ 80 可发；65—79 需改一处；< 65 换掉。

## 脚本能力边界（必须向用户说明）

脚本只量**机械特征**。以下三件事脚本判断不了，必须由你用语义判断补上：

1. **歧义**：标题里有没有一个读者会误解的词（尤其官方文件专门澄清过的词）。脚本会给高分，读者会读错。
2. **真伪**：标题里的数字对不对、有没有夸大。脚本只数数字，不核对。
3. **信息量**：一条建议换到别的话题里还成不成立。成立就是泛化建议，脚本量不出来。

所以在给出最终建议前，对排第一的标题必须额外回答一句：**这个标题里哪个词可能被读者理解成另一个意思？**

## 输入输出

- **输入**：稿件文件（UTF-8）或标题列表
- **输出**：
  - 终端报告（可直接截图给用户）
  - `--json` 结构化结果，便于接入自动化
  - 退出码：`0` 通过 / `1` 未通过 / `2` 输入错误

## 依赖

- Python 3.8+，仅标准库（`re`、`json`、`math`、`dataclasses`、`argparse`）
- 无需联网，不上传文本

## 异常处理

| 情况 | 处理 |
|---|---|
| 稿件不足 300 字 | 报告会附"样本偏小"提示，结论仅供参考，建议对完整稿重跑 |
| 文件编码不是 UTF-8 | 先转码；转不了就手动粘贴到新文件 |
| 报告命中位置不准确 | 词表是启发式，命中位置用于定位，最终判断以人工复读为准 |
| 用户坚持要发未过线的稿 | 记录在交付物里："已告知 X 项硬伤未处理，用户决定发布"，不代为其背书 |

## References

- `references/rules.md` — 八项指标的完整定义、计算公式与调参方法
- `references/fix-library.md` — 常见病灶的改法库（改前/改后对照）
