# 来源与第三方说明（NOTICE）

本文件说明本专家包内每一类内容的来源，便于平台审核与后续维护时核对。

## 1. 自主开发内容（本包主体）

以下内容由虫志龙为本次发布从头编写，未复制任何现有专家包的提示词、工作流文档、代码或模板：

| 内容 | 文件 | 说明 |
|---|---|---|
| 主提示词与工作流定义 | `agents/czl-pro-backtest-desk.md` | 五工作流（WF-01..05）结构、铁律、六段式回复 |
| 五个技能文档 | `skills/*/SKILL.md` 及 `references/` | 口径卡、体检单、审计单、报告契约等均为自定义结构 |
| 回测内核 | `kit/btcore.py` | 撮合、费用、手数、T+1、指标、事件研究、参数扫描 |
| 报告引擎 | `kit/btreport.py` | 载荷组装与模板渲染 |
| 报告模板 | `kit/template/report.tpl.html` | 版式、配色、SVG 绘制逻辑均为自行设计 |
| 工具脚本 | `tools/*.py`、`tools/*.js` | 自检、渲染检查、格式转换、头像体检与缩放、演示数据生成 |
| 头像 | `avatars/avatar.png` | 2026-10-28 使用 WorkBuddy 内置图像生成能力按本产品定位生成的原创图；已裁去生成工具水印并缩放至 512×512 |
| 演示数据 | `data/demo_bars*.csv` | 由 `tools/gen_demo_bars.py` 用固定随机种子合成，**不是真实行情** |
| 文档 | `README/USAGE/SPEC/CHANGELOG/docs/*` | 原创撰写 |

## 2. 运行时依赖

| 依赖 | 是否随包分发 | 许可 / 说明 |
|---|---|---|
| Python 3.9+ 标准库 | 否（系统自带） | PSF License，仅调用 `csv/json/math/statistics/datetime/argparse/zlib/struct` 等 |
| Node.js（可选） | 否 | 仅 `tools/check_report.js` 报告自检需要；不装不影响回测与报告生成 |
| 行情命令行工具（可选，如 `westock-data`、`westock-tool`） | **否** | 仅在用户环境已安装时调用其公开命令接口；本包不包含、不再分发其任何文件。相关命令写法见 `skills/bt-datafeeds/references/westock-cli.md` |

**本包不含任何第三方 Python 包、前端框架、CDN 资源、字体文件或图标库。**
报告模板为单文件自包含 HTML，使用系统字体栈（-apple-system / PingFang SC / Microsoft YaHei 等），不加载外部字体。

## 3. 未使用的内容

为避免权利瑕疵，本次开发明确**未**采用以下内容：

- 任何现有专家包的提示词原文、工作流命名与章节结构
- 任何现有专家包的回测脚本、示例代码、HTML 模板与 CSS
- 任何现有专家包的头像、品牌图与宣传文案
- 任何第三方回测框架（backtrader / vectorbt / zipline 等）的代码

方法论层面参考了公开的量化研究与软件工程实践（如信号与成交分离、样本外验证、审计清单），这些属于通用技术思想，不构成对具体表达的复制。

## 4. 数据与商标

- 文中出现的标的代码（如 510300.SH、600519.SH）仅作示例，不构成推荐。
- "WorkBuddy" 为腾讯公司产品名称，本包仅在"运行平台"意义上提及，与 platform 方无隶属或代理关系，也未获得其背书。

## 5. 维护

- 开发者：虫志龙
- 联系：47190078@qq.com
- 版本：1.0.0（2026-10-28）
