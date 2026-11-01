---
name: diagram-forge
description: |
  图表工坊 —— 把结构描述编译成可交付图表。模型驱动，离线渲染 SVG / 交互式 HTML / Mermaid 源码 / 终端 ASCII，内置语法体检与质量评分。
  触发词：画图、流程图、架构图、时序图、状态机、ER 图、甘特图、思维导图、时间轴、饼图、四象限、柱状图、折线图、图表美化、图表体检、SVG 渲染
---

# 图表工坊

## 这个技能解决什么问题

大模型直接"写 Mermaid 代码"有三个通病：语法偶尔写错、节点一多就糊、配色全靠猜。
本技能把流程拆成 **模型 → 体检 → 渲染** 三段，每一段都有可执行的校验，产出的是文件而不是文本。

- 不联网、不安装依赖、不调用外部渲染服务
- 11 类图表、12 套主题、4 种输出格式
- 结构问题在渲染前就被拦住（`check` + `review`）
- 同一份模型可反复导出不同格式与配色

## 什么时候用

| 场景 | 用不用 |
|---|---|
| 要把口述流程/架构/数据变成图片文件 | ✅ 用 |
| 要检查一段 Mermaid 源码有没有语法问题 | ✅ 用（只跑 `check`） |
| 要在文档、PPT、README 里嵌矢量图 | ✅ 用 |
| 要画人物插画、照片级示意图 | ❌ 不用 |
| 要把已有 `.mmd` 原样重排版成图片 | ⚠️ 只能做语法体检与建议；重建需按模型重新描述结构 |

## 核心概念：模型即图纸

`model.json` 是唯一事实来源。所有输出都由它派生：

```
model.json ──┬─→ .svg   矢量图（文档 / PPT）
             ├─→ .html  交互预览（主题切换 + 缩放平移）
             ├─→ .mmd   Mermaid 源码（二次编辑 / 平台兼容）
             ├─→ .txt   终端 ASCII（代码注释 / 聊天）
             └─→ .model.json  规范化后的模型（便于版本管理）
```

字段全表见 `references/model-schema.md`。快速上手：`dg new flow` 打印一份可跑的模板。

## 快速开始

```bash
# 1. 看一份模板长什么样
node skills/diagram-forge/scripts/dg.mjs new flow

# 2. 写自己的模型，保存为 my.json，然后校验
node skills/diagram-forge/scripts/dg.mjs check my.json

# 3. 打分，看结构有没有硬伤
node skills/diagram-forge/scripts/dg.mjs review my.json

# 4. 渲染全部格式
node skills/diagram-forge/scripts/dg.mjs render my.json --out out --theme graphite --format svg,html,mmd
```

## 命令一览

| 命令 | 作用 | 退出码 |
|---|---|---|
| `render <model.json>` | 生成图表文件 | 0 成功 / 2 模型不合法 |
| `check <file>` | 校验模型或 Mermaid 源码 | 0 通过 / 1 语法错误 / 2 模型错误 |
| `review <model.json>` | 质量评分与改进项 | 0 / 2 |
| `themes` | 列出 12 套主题 | 0 |
| `new <kind>` | 打印该类型的模板 | 0 |
| `spec` | 打印模型字段规范 | 0 |

`render` 参数：`--out` 输出目录、`--theme` 主题名、`--format` 格式列表（`svg,html,mmd,ascii,model`）、`--name` 文件名、`--all-themes` HTML 内嵌全部主题。

## 11 类图表与选型

| kind | 中文 | 什么时候选它 |
|---|---|---|
| `flow` | 流程图 | 有先后顺序与分支判断的业务流程 |
| `state` | 状态图 | 一个对象在多个状态间迁移（订单、工单、账号） |
| `class` | 类图 | 代码结构、接口与实现关系 |
| `er` | ER 图 | 数据库表结构与表间关系 |
| `sequence` | 时序图 | 多方调用的先后顺序（接口链路、协议交互） |
| `gantt` | 甘特图 | 有开始时间与工期的排期 |
| `mindmap` | 思维导图 | 一个主题向下发散的信息树 |
| `timeline` | 时间轴 | 按时间排列的里程碑 |
| `pie` | 饼图 | 构成占比（≤8 项） |
| `quadrant` | 四象限 | 双维度评估（成本/价值、紧急/重要） |
| `xy` | 柱线图 | 分类数值对比与趋势 |

选型拿不准时，按「有没有先后 → 有没有状态 → 有没有实体属性 → 有没有多方交互 → 有没有时间/占比/双维度」的顺序问一遍。

## 输出格式选择

- **要放进 Word / PPT / 网页** → SVG（矢量，放大不糊）
- **要发给同事看、还要能切主题** → HTML（单文件，离线可用）
- **要在支持 Mermaid 的平台里继续编辑** → MMD
- **要贴进代码注释、终端、聊天窗口** → ASCII
- **要进版本库做 diff** → `.model.json`

## 主题选择

6 浅色：`graphite`（通用文档）、`paper`（打印/暖调）、`ocean`（技术文档）、`mint`（数据类）、`sand`（报告）、`sakura`（创意）
6 深色：`midnight`（默认深色）、`carbon`（高对比）、`nordic`（IDE 风格）、`forest`、`plum`、`slate`

配色细节与自定义方法见 `references/themes.md`。

## 质量门槛

渲染前必须满足：

1. `check` 无 error
2. `review` 分数 ≥ 78 且无 high 级问题
3. 节点 ≤ 30
4. 判断节点出边 ≥ 2 且带条件标签

评分细则见 `references/quality-rubric.md`。

## 异常处理

| 现象 | 原因 | 处理 |
|---|---|---|
| `未知主题 "xxx"` | 主题名拼错 | 跑 `themes` 取准确名 |
| `模型校验未通过` | 字段缺失 / 悬空边 / 类型不符 | 按提示的字段路径逐条修 |
| `括号未闭合`（检查 .mmd） | 源码语法错误 | 定位到行号修括号或引号 |
| 图很宽/很高 | 方向与结构不匹配 | 改 `direction` 为 `LR` 或 `TB` |
| 节点文字被换行挤成多行 | 标签过长 | 标签压到 12 字内，细节放 `note` |

## 环境要求

- Node.js ≥ 18（仅用标准库，无需 `npm install`）
- 无网络依赖，可在离线环境运行
- 头像体检工具需要 Python 3.8+（可选）

## 自检

```bash
node skills/diagram-forge/scripts/tools/selftest.mjs
```

逐类型跑模型校验、渲染、导出、评分共 86 项检查，用于确认安装完整。
