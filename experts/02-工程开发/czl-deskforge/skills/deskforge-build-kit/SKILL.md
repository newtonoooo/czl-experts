---
name: deskforge-build-kit
description: "Build kit for assembling single-file personal workbenches. Contains five stage playbooks — scope compression, data modelling, assembly, factory inspection and release — each specifying inputs, steps, pass conditions, output format, failure handling, dependencies and neighbours. Provides five card primitives (list, matrix, form, metric, time) with parameters and inline-SVG drawing recipes, a storage namespace and seed-data convention, a mobile sizing checklist, and three pure-standard-library checkers: a compliance lint for external references, emoji-as-icon, input font size, hit-target size, storage prefixes, block count and file weight; a DOM prober for missing element ids, undefined handlers and cyclic render calls; and a scope-card generator that rejects more than four blocks. Load the stage playbook you need, one at a time, rather than the whole kit."
version: 1.0.0
---

# 桌匠装配套件（deskforge-build-kit）

> 这套东西不是知识库，是**加工图纸 + 量具**：五道工序的画法，加三个能跑的检查工具。
> 读法：按当前进度取一份工序文件，不要一次全读。

---

## 一、套件目录

```
deskforge-build-kit/
├── SKILL.md                      # 本文件：总纲、卡片速查、判定阈值
├── workflows/                    # 五道工序（按需取一份）
│   ├── 01-收束.md
│   ├── 02-建模.md
│   ├── 03-装配.md
│   ├── 04-体检.md
│   └── 05-上线.md
├── references/                   # 参数表与清单
│   ├── card-primitives.md        # 五种卡片的参数、字段与 SVG 画法
│   ├── data-namespace.md         # 键名规范、字段类型、种子数据、导入导出、迁移
│   └── qc-checklist.md           # 出厂体检清单（脚本项 + 人工项 + 常见翻车）
└── scripts/                      # 三个纯标准库检查/生成工具
    ├── blueprint_lint.py
    ├── dom_probe.py
    └── spec_card.py
```

---

## 二、五道工序速查

| 工序 | 一句话职责 | 产出 | 文件 |
|---|---|---|---|
| ① 收束 | 口语需求 → 模块表 + 字段表，压到 4 块以内 | 收束卡 | `workflows/01-收束.md` |
| ② 建模 | 字段、键名、种子数据、备份路径定死 | 数据账 | `workflows/02-建模.md` |
| ③ 装配 | 先骨架，再一块一块填，保持可运行 | 单文件 HTML | `workflows/03-装配.md` |
| ④ 体检 | 两个脚本 + 人工四项，出出厂单 | 出厂单 | `workflows/04-体检.md` |
| ⑤ 上线 | 给链接或给文件 + 备份说明 | 链接 / 文件 | `workflows/05-上线.md` |

**单向依赖**：①→②→③→④→⑤。允许跳步，但跳了必须在交付里写明"未做前置，本次结论以此为限"。

---

## 三、五种卡片速查

| 原语 | 主参数 | 不适用的信号 |
|---|---|---|
| `list` 清单卡 | 行字段、排序键、状态枚举、可勾选 | 一行里要塞 8 个以上字段（该拆成表单 + 详情） |
| `matrix` 矩阵卡 | 行维度、列维度、取值函数、色阶阈值 | 维度不是稳定的集合（会每天新增列） |
| `form` 表单卡 | 字段与校验、默认值、落库位置 | 只有一个布尔值（用勾选即可，别做表单） |
| `metric` 指标卡 | 口径、对比基准、图形类型（环/柱/折线） | 口径说不清（先定义清楚再画） |
| `time` 时间卡 | 起止、分组粒度、未完成是否顺延 | 只是显示一个日期（写进标题即可） |

参数、字段结构与 SVG 画法见 `references/card-primitives.md`。

---

## 四、判定阈值

| 项 | 线 | 越线怎么办 |
|---|---|---|
| 模块数 | ≤4 | 出分期表，本期只做 3 块 |
| 单文件体积 | ≤300 KB（硬上限 600 KB） | 压缩 SVG 精度、示例数据减半、长列表改折叠 |
| 输入框字号 | ≥16px | 改 CSS，不许用 `transform: scale` |
| 触控目标 | ≥44px（儿童向 ≥50px） | 加 `min-height` 与 `padding` |
| 外链数量 | 0 | 全部内联；确需联网的能力改为可选适配层 |
| emoji 当图标 | 0 处 | 换成内联 SVG path |
| 存储键前缀 | 全部 `czl_desk_` | 改键名，并写迁移 |
| 脚本 error | 0 | 改代码，不许改阈值 |
| 示例数据 | 3–5 条，含 1 条逾期/异常 | 补种子 |
| 首屏 | 必须有"今天要处理" | 加到所有模块之上 |

---

## 五、脚本

三个脚本都不联网、不引第三方库、不上传任何数据。

```bash
# 合规体检（退出码 0 通过 / 1 有警告 / 2 有错误）
python scripts/blueprint_lint.py --file 台子.html --prefix czl_desk_

# 结构与调用体检
python scripts/dom_probe.py --file 台子.html

# 收束卡生成（模块 >4 直接拒绝）
python scripts/spec_card.py --input 需求.json --out 收束卡.md
```

| 脚本 | 默认阈值（可调，但**不建议调**） |
|---|---|
| `blueprint_lint.py` | 体积 ≤600KB 报错；输入字号 <16px 报错；按钮 <44px 报错；发现 https/http 资源引用报错；发现 emoji 图标报错；模块 >4 报错；无 `viewport` 报错；无安全区 padding 警告 |
| `dom_probe.py` | `getElementById('x')` 无对应 `id` 报错；渲染函数成环报错；初始化入口多于 1 个警告；疑似未定义调用警告 |
| `spec_card.py` | 模块 >4 报错；字段缺类型报错；字段缺示例警告 |

---

## 六、使用纪律

1. **一次只读一份工序文件**。五份全读会把判断标准混在一起。
2. **先量后切**：没收束卡不许写 HTML；没数据账不许写存储代码。
3. **骨架先跑通**：空白页能打开、控制台无报错、`refreshAll()` 能跑，再填第一块。
4. **一块一交付**：每填完一块就是一个可运行版本，随时能停。
5. **体检结果原文附进出厂单**，不许只写"检查通过"。
6. **阈值不许为了通过而改动**；确实业务需要放宽的，在出厂单里写明理由与影响面。
7. **旧台子优先沿用**：原配色、原键名、原结构能留就留，只加不改。
8. **示例数据只能是假数据**，交付物可能被公开访问。

---

## 七、与专家提示词的分工

- `agents/czl-deskforge.md` 定**身份、边界、语气、总规矩**；
- 本套件定**画法、参数、阈值、工具**；
- 两者冲突时，以专家提示词的身份与边界为准，以本套件的技术参数为准（例如具体像素值）。

---

*© 2026 虫志龙 · 版权所有 ｜ 独立撰写，未使用任何第三方专家包内容*
