# 制图宗师 · 全栈图表设计与渲染专家

把口述的流程、架构、表结构、数据，编译成**可以直接交付的图表文件**。

- 开发者：虫志龙（47190078@qq.com）
- 版本：1.0.0
- 类型：Agent 型单专家
- 分类：产品设计

## 它解决什么问题

让大模型"画张图"，通常得到三段文字：一段 Mermaid 代码、一句"你可以用 XX 渲染"、外加一堆需要自己补的细节。真正卡人的地方在于：代码可能有语法错、节点一多就糊成一团、配色全凭感觉、最后还得自己找工具导出。

这个专家把流程拆成三段，每段都有可执行的校验：

```
结构描述 ──→ 模型(model.json) ──→ 体检(check/review) ──→ 渲染(render) ──→ 交付文件
```

产出的是**文件**，不是"你可以这样画"。

## 核心能力

| 能力 | 说明 |
|---|---|
| 11 类图表 | 流程图、状态图、类图、ER 图、时序图、甘特图、思维导图、时间轴、饼图、四象限、柱线图 |
| 12 套主题 | 6 浅色 + 6 深色，切换主题不重排 |
| 4 种输出 | SVG（矢量）、HTML（交互预览）、Mermaid（可再编辑）、ASCII（终端） |
| 语法体检 | 对任意 Mermaid 源码做静态检查，精确到行号 |
| 质量评分 | 100 分制，每条扣分都对应一个具体可读性问题 |
| 完全离线 | 零第三方依赖，不联网、不装包 |

## 安装与自检

专家包已放入 WorkBuddy 专家目录，在「专家中心 - 我的专家」中即可选择。

首次使用建议跑一次自检，确认文件完整：

```bash
node skills/diagram-forge/scripts/tools/selftest.mjs
```

预期输出：`共 86 项检查，通过 86 项，失败 0 项`。

环境要求：Node.js ≥ 18（只用标准库）。

## 快速上手

```bash
# 看一份模板
node skills/diagram-forge/scripts/dg.mjs new flow

# 校验 → 评分 → 渲染
node skills/diagram-forge/scripts/dg.mjs check my.json
node skills/diagram-forge/scripts/dg.mjs review my.json
node skills/diagram-forge/scripts/dg.mjs render my.json --out out --theme graphite --format svg,html,mmd
```

更完整的用法见 [USAGE.md](./USAGE.md)，字段规范见 `skills/diagram-forge/references/model-schema.md`。

## 目录结构

```
czl-diagram-forge/
├── .codebuddy-plugin/plugin.json     专家元数据
├── agents/czl-diagram-forge.md       专家提示词（六条工作流）
├── skills/diagram-forge/
│   ├── SKILL.md                      技能说明
│   ├── references/                   模型规范 / 语法速查 / 主题 / CLI / 评分细则
│   ├── scripts/
│   │   ├── dg.mjs                    命令行入口
│   │   ├── lib/                      渲染引擎（13 个模块）
│   │   └── tools/                    自检脚本 / 头像体检
│   └── templates/                    11 份可运行模板
├── avatars/expert.png                原创头像 512×512
├── docs/                             产品规格 / 工作流 / 测试报告 / 风险清单
├── README.md
├── USAGE.md
├── CHANGELOG.md
├── LICENSE
└── NOTICE.md
```

## 渲染引擎

自研实现，不依赖任何第三方渲染库：

- **布局**：分层有向图（环检测 → 最长路径分层 → 重心法排序 → 正交路由），支持 TB/LR/BT/RL 四向变换
- **排版**：中日韩文字宽度按全角计量，西文按字符类别加权，换行时中文按字断、西文按词断
- **绘制**：场景图（Scene）中间层，一次布局可序列化为 SVG / HTML / ASCII
- **主题**：语义令牌 + 7 色角色板，节点填充由底色与角色色混合得出

## 已知边界

- 不支持从 `.mmd` 文件反向重建模型（可做语法体检与风格建议）
- 时序图不支持激活条与嵌套 fragment
- 思维导图不支持环形/双向布局
- ASCII 输出仅覆盖流程图、状态图、类图、ER、时序、甘特、思维导图与简单列表

## 许可

代码与文档：MIT，见 [LICENSE](./LICENSE)。
第三方组件：无捆绑，见 [NOTICE.md](./NOTICE.md)。
