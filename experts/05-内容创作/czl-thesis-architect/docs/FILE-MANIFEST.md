# 文件清单（2.0.0）

项目：`czl-thesis-architect`（文衡 / Paperwright）　版本：2.0.0
生成时间：2026-10-26　共 60 个文件，约 570 KB

> `__pycache__/` 为 Python 运行缓存，不列入清单，打包自动排除。

## 一、元数据与外观

| 路径 | 大小 | 职责 |
|---|---|---|
| `.codebuddy-plugin/plugin.json` | 2.7 KB | 唯一元数据：标识、版本、作者、展示字段、分类、标签、示例问法、头像与资源路径 |
| `agents/czl-thesis-architect.md` | 10.4 KB | 主提示词：写手型定位、六条铁律、12 模块矩阵、写作执行规范、输出格式、工具调度、边界 |
| `avatars/expert.png` | 261 KB | 原创符号型头像 512×512（页面网格 + 垂线 + 标尺梁） |
| `avatars/.gitkeep` | 0 B | 占位，保证空目录可版本管理 |

## 二、文档

| 路径 | 大小 | 职责 |
|---|---|---|
| `README.md` | 7.1 KB | 使用说明：12 模块表、安装、用法示例、工具命令、目录结构、写作规矩、已知局限 |
| `CHANGELOG.md` | 3.0 KB | 版本日志：2.0.0 全量条目（新增/移除/变更/限制）+ 1.0.0 说明 |
| `LICENSE` | 2.8 KB | 许可声明：允许/禁止用途、第三方组件、标准引用边界、免责、商业授权 |
| `docs/PRODUCT-SPEC.md` | 9.0 KB | 产品规格：用户、51 项功能矩阵、输入输出、工具接口、质量要求、非目标、验收标准 |
| `docs/DEVLOG.md` | 6.9 KB | 开发记录：为什么重做、实现路径、手册写法、11 个失败用例与修法、设计取舍、原创性说明 |
| `docs/TEST-REPORT.md` | 9.2 KB | 测试报告：54 用例、六个工具真实输出、未验证清单、复现步骤 |
| `docs/RISK-REGISTER.md` | 9.2 KB | 风险清单：五项核查、11 条风险（R1—R11）、需你决定的 6 项 |
| `docs/STORE-LISTING.md` | 4.9 KB | 展示文案：名称、简介、标签、示例问法、详情页长文案、关键词、使用提示 |
| `docs/FILE-MANIFEST.md` | 本文件 | 文件清单与职责 |

## 三、工作流技能

| 路径 | 大小 | 职责 |
|---|---|---|
| `skills/thesis-architect/SKILL.md` | 4.4 KB | 路由入口：怎么用这本手册、12 模块表、通用写作流程、各模块产出要求、硬约束 |
| `skills/thesis-architect/manifest.yaml` | 4.5 KB | W1—W12 模块路由（触发词 + 手册 + 模板）、文体判断、句子库入口、6 个工具索引、13 个模板索引 |

### 3.1 references（15 份写作手册，约 1916 行）

| 路径 | 大小 | 写什么 |
|---|---|---|
| `00-writing-principles.md` | 6.0 KB | 总则：三条标准、五种段型配方、时态人称、hedging 分级、引用嵌入、图表规矩、十条空转句式 |
| `01-topic-and-proposal.md` | 5.6 KB | 选题：题目结构、候选评估表、研究问题写法、开题报告七节配方、五个被打回原因 |
| `02-literature-review.md` | 6.3 KB | 综述：概念块检索式、矩阵、三种组织方式、示范段落、句式库（20+）、五个常见错误 |
| `03-structure-and-outline.md` | 3.9 KB | 提纲：主线、标准结构、每章六格、标题写法、字数预算算法、结构自检四问、六种结构病 |
| `04-abstract-and-keywords.md` | 5.6 KB | 摘要：五要素、中文示范（300 字）、英文示范与改写要点、关键词标准、六个错误 |
| `05-introduction.md` | 7.0 KB | 引言：四段配方、逐段写法、700 字完整示范、句式库、五个常见错误 |
| `06-methods.md` | 6.7 KB | 方法章：六节配方、设计/抽样/工具/分析写法、示范段落、必报项清单、三条效度威胁、伦理 |
| `07-results-and-figures.md` | 5.3 KB | 结果：只报事实、四种统计叙述句、质性主题写法、三线表规范、图注、六个错误 |
| `08-discussion-conclusion.md` | 6.5 KB | 讨论：四段配方、文献对话三种动作、机制三件套、局限写法、结论与分层建议、句式库 |
| `09-language-zh.md` | 6.7 KB | 中文润色：四步顺序、**30 组高频病句对照**、句长控制、衔接表、学术化改写、改稿交付格式 |
| `10-language-en.md` | 8.1 KB | 英文润色：八病、动词要实、连接词精简、hedging、中译英五动作、**15 组对照**、示范段落 |
| `11-dedup-and-similarity.md` | 6.0 KB | 降重：报告四指标、正当/不当、逐类处置、改写四步与示范、明确不做的五件事、AIGC |
| `12-citation-and-format.md` | 6.3 KB | 引用：以谁为准、类型标识、五类条目要素、四种格式对照、十条高频错误、图表与版式、核对流程 |
| `13-defense-and-submission.md` | 6.5 KB | 答辩投稿：逐页 PPT、讲稿写法、五类问答、期刊矩阵、投稿信四段、逐点回复、致谢、附录 |
| `14-genre-methods.md` | 5.7 KB | 文体：七类论文（人文/质性/量化/实验/工程/算法/综述）的方法章与结果章差异、报告下限、雷区 |

### 3.2 templates（13 份写作模板，约 948 行）

| 路径 | 大小 | 填什么 |
|---|---|---|
| `title-candidates.md` | 1.4 KB | 题目候选表、五维评分、定题检查、中英题目、题目—问题—方法一致性 |
| `proposal.md` | 2.5 KB | 开题报告七节 + 技术路线 + 进度表 + 预判问题 |
| `lit-matrix.md` | 1.4 KB | 文献矩阵 8 列 + 按主题重排 + 缺口定位 |
| `abstract.md` | 2.2 KB | 中英摘要槽位模板 + 关键词 + 五要素核对 |
| `chapter-cards.md` | 3.0 KB | 六章写作卡（要回答/字数/结构/不许写/自查） |
| `sentence-bank-zh.md` | 5.2 KB | **中文学术句式库 54 条**，按起段/立论/分歧/评价/收口/报数据/机制/限制/引用分类 |
| `sentence-bank-en.md` | 4.6 KB | **英文学术句式库 47 条** + hedging 阶梯 + 禁用表达 |
| `polish-pairs.md` | 1.9 KB | 润色对照表 + 八种改写类型 + 三档改动强度 + 不许改的四样 |
| `dedup-plan.md` | 2.0 KB | 查重整改表 + 逐段处置 + 改写记录 + 复检 + 不做的事 |
| `format-checklist.md` | 2.2 KB | 格式核对清单（六大类 40 项）+ 自动检查 + 人工必核 |
| `defense-script.md` | 3.5 KB | 答辩页序 + 逐页讲稿示范 + 15 问 + 备用页 + 当天检查 |
| `cover-letter.md` | 2.2 KB | 投稿信三场景模板 + 四条禁忌 + 材料清单 |
| `response-letter.md` | 2.7 KB | 审稿回复三段式 + 不采纳写法 + 中文版 + 位置表 + 五个禁忌 |

## 四、工具与测试

### 4.1 scripts（8 个文件，约 1539 行）

| 路径 | 大小 | 职责 | 退出码 |
|---|---|---|---|
| `_common.py` | 4.1 KB | 公共模块：编码安全读取、问题记录、中英文字数、段落句切分、统一报告 | — |
| `wordstat.py` | 6.3 KB | 按章字数/占比/段落/图表 + 目标偏差 + 失衡章节 | 0 / 2 |
| `abstract_check.py` | 8.7 KB | 摘要字数、五要素、关键词质量、中英数字一致性 | 0 / 1 / 2 |
| `style_lint.py` | 9.2 KB | 套话密度、长句、连续短句、连接词连用、段首雷同、英文被动、重复词 | 0 / 1 / 2 |
| `cite_format.py` | 13.4 KB | 参考文献检查 + GB/T 7714 ↔ APA ↔ MLA ↔ IEEE 转换 | 0 / 1 / 2 |
| `dup_scan.py` | 6.3 KB | 与源文本 n-gram 重合比对，定位未标注重复 | 0 / 1 / 2 |
| `figtable.py` | 6.9 KB | 图表编号重复/跳号/风格混用、题注未引用、悬挂引用 | 0 / 1 / 2 |
| `run_tests.py` | 1.0 KB | 测试入口 | 0 / 1 |

### 4.2 tests（7 个测试文件 + 2 份夹具，约 523 行）

| 路径 | 大小 | 覆盖 |
|---|---|---|
| `test_wordstat.py` | 2.3 KB | 8 个用例 |
| `test_abstract_check.py` | 3.7 KB | 9 个用例 |
| `test_style_lint.py` | 2.7 KB | 8 个用例 |
| `test_cite_format.py` | 3.1 KB | 12 个用例 |
| `test_dup_scan.py` | 2.5 KB | 6 个用例 |
| `test_figtable.py` | 2.4 KB | 9 个用例 |
| `test_pipeline_e2e.py` | 2.2 KB | 2 个端到端用例 |
| `fixtures/sample-thesis.md` | 7.1 KB | 1800 字示例论文（六章 + 摘要 + 文献表，数据虚构） |
| `fixtures/source-text.md` | 0.7 KB | 含与论文重复段落的对照源文本 |

## 五、完整性检查

| 检查项 | 方法 | 结果 |
|---|---|---|
| `plugin.json` 的 `agents` 路径存在 | `validate_expert.py` | 通过 |
| `plugin.json` 的 `skills` 路径含 `SKILL.md` | `validate_expert.py` | 通过 |
| `plugin.json` 的 `avatar` 路径存在 | 手工 + 校验脚本 | 通过 |
| `references/` 与 `manifest.yaml` 双向一致 | 脚本比对 15 个文件名 | 无缺失、无孤儿 |
| `templates/` 与 `manifest.yaml` 双向一致 | 脚本比对 13 个文件名 | 无缺失、无孤儿 |
| 7 个脚本存在且被文档引用 | 脚本比对 | 全部符合 |
| 测试可从发布包解压副本运行 | 解压后 `run_tests.py` | 全部通过 |
