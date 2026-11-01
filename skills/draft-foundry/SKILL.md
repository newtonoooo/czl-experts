---
name: draft-foundry
description: "Outline-first drafting for Chinese WeChat Official Account articles, taking a confirmed topic (usually chosen from topic-radar's five candidates) and turning it into a load-bearing skeleton and a publishable draft. Builds a load-bearing skeleton (5-9 nodes, each with an explicit 'what the reader takes away' line), validates it with a script, then writes the draft against five reusable structural patterns and a library of opening moves. Enforces write-rough-not-full rules so the draft does not self-summarize. Use when producing an article from a topic, when an article keeps collapsing mid-way, when an opening is weak, or when a writer needs a reusable structure instead of a blank page."
version: 1.0.0
---

# 初稿工坊（draft-foundry）

## 这个技能解决什么

写不出来的最大原因不是没灵感，是**没有骨架就开始写**。写到第三段发现和第五段说的是同一件事，然后开始糊。

这座工坊的顺序是死的：**先骨架，验过再写**。骨架的唯一标准是每个节点都能用一句话说清"这一段读者会得到什么"。说不出来，这个节点就不该存在。

## 什么时候用

- 用户给了选题，要一篇稿子
- 用户写了一半卡住
- 用户的开头总是留不住人
- 用户要一套能反复用的结构，不想每次从零想

**不适用**：还没选题 → 先走 `topic-radar`；稿子已经写完要体检 → `quality-gate`。

## 执行步骤

### 第零步：先确认账号，再接选题

动笔前必须知道自己**替谁写**：公众号名称（落款用）+ 账号方向（写给谁、写什么领域）。
这两个都只能来自用户，**没有任何默认值**——不许默认教育、不许默认某个城市、不许默认某类读者。

用户没说方向就先问一句；没说账号名就让落款留空（渲染时整块不输出），**不要编一个像真的号名**。

### 第一步：接选题

上游通常来自 `topic-radar` 的 5 选 1。接过来先确认三件事，不要重新讨论选题：

- 角度是什么（事实/影响/反常识/方法/判断）——它决定骨架长相
- 类型是什么（热点/常销/争议/骨架）——它决定寿命与语气
- 素材够了没有——不够就先列缺什么

如果用户是直接给题（没走过选题），补一句"这篇从哪个角度切"，不要默认他会说。

### 第二步：确认三件事（一句话，别展开）

1. 这篇给谁看（具体到一个人）
2. 他看完会做什么（一个动作或一个判断）
3. 篇幅多少（决定节点数：1500 字约 4—5 节点，2500 字约 6—7 节点）

三件事没确认就开写，写出来的东西八成要重来。

### 第三步：选骨架模式

从 `references/skeletons.md` 选一个，不要混用两种。五种常用模式：

| 模式 | 适合 | 骨架长相 |
|---|---|---|
| **现场递进** | 观察、访谈、亲历 | 场面 → 反常 → 追因 → 另一面 → 收在动作 |
| **判断+三证** | 观点、评论 | 判断 → 证据1 → 证据2 → 反例 → 适用边界 |
| **流程拆解** | 方法、攻略 | 错误做法 → 为什么错 → 正确做法 → 步骤 → 常见卡点 |
| **对比双轨** | 选择困难类 | A 做法 → B 做法 → 分水岭 → 你属于哪种 → 试错成本 |
| **时间线** | 事件复盘、政策变化 | 起点 → 转折 → 当下 → 三种走向 → 现在该做什么 |

### 第四步：写骨架并跑检查

```bash
python scripts/outline_check.py 大纲.md
```

检查三件事：每个节点有没有「读者得到」、节点数是否在 5—9、结尾是不是"总结"。
**不通过不许开写。** 脚本给出的每条"必须修"都要处理掉。

### 第五步：写初稿（三条硬规则）

1. **允许写糙，不允许写满。** 每段先把事实、场面、对话写出来，不写总结句。
2. **不许边写边收。** 段落结尾不要"这就是为什么……"，让下一段接上。
3. **每段至少一个可核对的东西**：一个数、一个时间、一句原话、一个动作。三个都没有，这段是空的。

### 第六步：自查后交付

写完先自己过一遍，再交给用户：

```bash
# 用 quality-gate 的脚本自查，别用感觉判断
python ../quality-gate/scripts/quality_gate.py 初稿.md
```

把脚本数字和初稿一起交付。有硬伤就自己改完再交，不要交付"我知道有问题但先给你看"的稿子。

## 输出规范

- **骨架和初稿分开交付**，不要一次给一整篇。骨架确认后再写，能省掉一半返工。
- 初稿附一行说明：字数、节点数、用了哪个骨架模式。
- 缺素材的地方写 `【待补：需要什么】`，不要用臆造细节填空。用户在交付时能一眼看到你还缺什么。
- 保留用户的原话。用户口述里的土话、比喻、骂人的话，是这篇稿子最值钱的部分，不要"优化"掉。

## 依赖

- Python 3.8+，仅标准库
- `quality-gate` 技能（初稿自查），可选 `voiceprint-lab`（按作者指纹写）

## 异常处理

| 情况 | 处理 |
|---|---|
| 用户催着要整篇，不肯确认骨架 | 先给骨架（5 分钟的事），说明"骨架你看一眼，不对现在改成本最低" |
| 素材明显不够 | 列出缺的 3 样东西，先写能写的部分，缺的段落留占位 |
| 用户要写的题自己不熟 | 要求提供事实来源；没有来源就改成"我不懂这块，只能帮你组织，内容得你给" |
| 写着写着发现骨架不对 | 停下来改骨架，不要在错的骨架上继续写。改骨架 10 分钟，改稿子 2 小时 |

## References

- `references/skeletons.md` — 五种骨架模式的完整展开与选用判断
- `references/opening-patterns.md` — 开头写法库（含反例）
- `templates/outline-template.md` — 骨架文件模板（脚本可直接检查）
