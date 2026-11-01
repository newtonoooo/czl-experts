---
name: czl-triprism-playbook
description: "Method pack for the TriPrism data team. references/ holds six method notes: how to write a metric contract, the evidence grading and recheck standard, chart and layout rules, ten common analysis traps, privacy and compliance limits, and which deliverable to use when. templates/ holds the task brief and the cross-examination minute. scripts/triad.py is a thin launcher for the bundled toolchain in tools/. Load one or two notes on demand; never read the whole pack into context."
version: 1.0.0
---

# 三棱镜 · 方法包

这个包解决的是「**同一个动作，每次都要做得一样**」的问题。

分析可以有不同的判断，但**流程不能每次凭感觉**：体检怎么做、口径怎么写、结论怎么标等级、报告怎么排版，都写死在这里。

```
czl-triprism-playbook/
├── SKILL.md
├── references/
│   ├── 01-口径怎么写.md
│   ├── 02-证据分级与复算标准.md
│   ├── 03-图表与排版规范.md
│   ├── 04-十个常见误判.md
│   ├── 05-隐私与合规底线.md
│   └── 06-交付物选用指南.md
├── templates/
│   ├── T1-任务书.md
│   └── T2-质证纪要.md
└── scripts/
    └── triad.py            工具链启动器（真正的实现在 <包根>/tools/）
```

---

## 什么时候加载哪一份

| 你在做什么 | 读这份 |
|---|---|
| 用户口径含糊，要写清指标定义 | `references/01-口径怎么写.md` |
| 要给结论标 A/B/C/D，或复算没过 | `references/02-证据分级与复算标准.md` |
| 要出图、要排版、要交给老板看 | `references/03-图表与排版规范.md` |
| 结论"看起来对"但心里没底 | `references/04-十个常见误判.md` |
| 表里有姓名、手机号、工资、身份证 | `references/05-隐私与合规底线.md` |
| 不确定该给网页/一页纸/幻灯片/Excel | `references/06-交付物选用指南.md` |
| 开工前要和用户对齐范围 | `templates/T1-任务书.md` |
| 三路结论打架，需要留痕 | `templates/T2-质证纪要.md` |

**一次只读一到两份。** 全量读进来只会把上下文塞满，不会让分析变准。

---

## 四条硬规则（不看参考文档也必须遵守）

1. **没体检不分析。** 体检闸门 `block` 就直接停，不产出任何结论。
2. **没口径不出数。** 分母、粒度、过滤条件没写清，算出来的百分比没有意义。
3. **没复算不进正文。** 每条结论都要能被同一份源数据重算出来；算不出来的，标"未复算"或删掉。
4. **数据不出本地。** 不调用任何需要上传原始表格的服务。

---

## 工具链怎么调

工具在包根的 `tools/` 下，全部纯标准库，不需要装任何东西。

```bash
# 方式一：直接用启动器（自动定位包根）
python <SKILL_DIR>/scripts/triad.py run --path data.xlsx --outdir out --title "经营会诊"

# 方式二：直接调工具
python <PACKAGE_ROOT>/tools/triad_cli.py run --path data.xlsx --outdir out
```

`<PACKAGE_ROOT>` 一般是：

```
~/.workbuddy-ai/plugins/marketplaces/my-experts/plugins/czl-triprism-data-team
```

找不到就搜一下：

```bash
find ~ -maxdepth 8 -type d -name "czl-triprism-data-team" 2>/dev/null
```

---

## 常用子命令

| 命令 | 干什么 | 什么时候用 |
|---|---|---|
| `profile --path X --brief` | 只体检，输出给模型看的摘要 | 每次开工第一步 |
| `analyze --path X --contract C --lanes course` | 单跑一条分析线 | 分派给成员时 |
| `verify --path X --bundle B` | 复算全部结论 | 三路回传之后 |
| `run --path X --outdir O` | 一条龙出四件套 | 主理人交付时 |

退出码：`0` 成功 / `2` 输入错误 / `3` 体检拦截 / `4` 复算失败。
**看到 3 或 4，不要绕过，按提示处理。**
