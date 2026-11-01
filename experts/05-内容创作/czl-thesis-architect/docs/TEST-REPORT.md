# 功能测试报告（2.0.0）

项目：`czl-thesis-architect`（文衡 / Paperwright）　版本：2.0.0
测试日期：2026-10-26　执行人：虫志龙

> 只记录**实际执行过**的测试与真实输出。未执行的项在第五节列出，不标记为通过。

---

## 一、结果总览

| 测试类型 | 方法 | 结果 |
|---|---|---|
| 单元测试 | `unittest`，逐工具行为验证 | **54 个用例全部通过** |
| 端到端 | 六个工具在示例论文上串联跑通 | **通过**，各自命中设计好的问题 |
| CLI 实跑 | 六条命令对夹具实际执行 | **通过**，问题可指回行号 |
| JSON 契约 | 六个工具 `--json` 输出结构一致性 | **通过**（tool / issues / summary 齐备） |
| 平台格式校验 | `validate_expert.py` | 见第 4.7 节 |
| 打包完整性 | 解压后从副本重跑测试 | 见第 4.8 节 |

## 二、环境

| 项 | 值 |
|---|---|
| 操作系统 | Windows（win32） |
| Python | 3.13.14 |
| 第三方 Python 包 | 无（仅标准库） |
| 网络 | 全程离线，工具无网络调用 |
| 测试入口 | `python scripts/run_tests.py` |

## 三、用例清单

| 文件 | 用例数 | 覆盖点 |
|---|---|---|
| `test_wordstat.py` | 8 | 章识别（含"第 1 章"与 `#` 前缀）、前置部分、总字数等于各章之和、目标偏差、失衡章节、图表计数、JSON、缺文件 |
| `test_abstract_check.py` | 9 | 中英摘要提取、五要素判定、字数下限、缺要素、中英数字不一致、禁用关键词、无摘要、JSON、缺文件 |
| `test_style_lint.py` | 8 | 套话密度、干净文本不误报、长句比例、连续短句、连接词连用、英文被动、JSON、缺文件 |
| `test_cite_format.py` | 12 | 条目切分、编号跳号、专著缺出版地、电子资源缺引用日期、期刊缺页码、重复条目、同号重复为阻断、APA/IEEE/GB 转换、转换输出与人工提示、缺文件 |
| `test_dup_scan.py` | 6 | 重合段识别、行号定位、无重合不误报、JSON、源目录为空、缺文件 |
| `test_figtable.py` | 9 | 悬挂引用、题注未被引用、编号重复、跳号、风格混用、正文句子不误判为题注、干净文档、退出码、缺文件 |
| `test_pipeline_e2e.py` | 2 | 六工具串联命中、JSON 契约一致 |

夹具：`tests/fixtures/sample-thesis.md`（1800 字示例论文，含六章 + 摘要 + 文献表，数据与文献均虚构）、
`tests/fixtures/source-text.md`（含一段与论文重复的源文本，用于 dup_scan）。

## 四、实际输出（原样粘贴）

### 4.1 测试套件

```
$ python scripts/run_tests.py
...
Ran 54 tests in 0.045s

OK

用例：54 个｜失败 0｜错误 0
```

### 4.2 `wordstat.py`

```
$ python scripts/wordstat.py tests/fixtures/sample-thesis.md --target 3000
=== wordstat ===
文件：sample-thesis.md
字数：中文 1781 字 + 西文 78 词 = 1859
章数：7｜目标 3000 字

| 章 | 字数 | 占比 | 段数 | 图 | 表 |
|---|---|---|---|---|---|
| （前置：题目/摘要） | 212 | 11.4% | 5 | 0 | 0 |
| 第 1 章 引言 | 414 | 22.3% | 4 | 0 | 0 |
| 第 2 章 文献综述 | 286 | 15.4% | 3 | 0 | 0 |
| 第 3 章 研究设计 | 265 | 14.3% | 4 | 0 | 0 |
| 第 4 章 结果 | 148 | 8.0% | 11 | 1 | 1 |
| 第 5 章 讨论 | 259 | 13.9% | 4 | 0 | 0 |
| 第 6 章 结论 | 275 | 14.8% | 9 | 0 | 0 |
| **合计** | **1859** | 100% | — | — | — |

问题：BLOCKER 0 / MAJOR 1 / MINOR 0
- MAJOR WS002 总字数 1859，比目标 3000 少 38%
```

### 4.3 `abstract_check.py`

```
$ python scripts/abstract_check.py tests/fixtures/sample-thesis.md
=== abstract_check ===
文件：sample-thesis.md
中文摘要：108 字｜英文摘要：46 词
五要素：目的✓；方法✓；结果✓；结论✓；边界✓
关键词：5 个（课后服务；参与率；通勤时间；县域初中；教育公平）

问题：BLOCKER 0 / MAJOR 1 / MINOR 3
- MAJOR AB002 中文摘要 108 字，不在建议区间 200—800 字
- MINOR AB003 英文摘要 46 词，不在建议区间 120—400 词
- MINOR AB006 摘要含空转表达：越来越
- MINOR AB010 英文摘要缺少中文里出现的数字：['33', '64.5']
```

### 4.4 `style_lint.py`

```
$ python scripts/style_lint.py tests/fixtures/sample-thesis.md
=== style_lint ===
文件：sample-thesis.md
句子：92 句，平均 20.8 字，长句占 0%
套话/空转：8 处（4.2/千字）
连续短句：0 处｜连接词连用段：0 处｜英文被动：0%

问题：BLOCKER 0 / MAJOR 0 / MINOR 2
- MINOR SL003 [第17行] 套话/空转表达 8 处（4.2/千字，阈值 2.0）
    命中：第17行「随着社会经济的不断发展」；「具有重要的理论意义」；
    第69行「起到了积极的推动作用」；「奠定了基础」；「综上所述」
- MINOR SL007 高频重复词：参与（30 次）、服务（24 次）、研究（22 次）
```

### 4.5 `figtable.py`

```
$ python scripts/figtable.py tests/fixtures/sample-thesis.md
=== figtable ===
文件：sample-thesis.md
图 1 个｜表 1 个｜正文引用 2 处
识别到的题注：表4-1（第47行）三校课后服务参与情况；图4-1（第59行）三校课后服务参与率对比（%）

问题：BLOCKER 1 / MAJOR 1 / MINOR 0
- BLOCKER FT006 [第61行] 正文引用 表 5-1，但不存在该编号的题注
- MAJOR FT005 [第47行] 表 4-1 在正文中未被引用
EXIT=1
```

### 4.6 `dup_scan.py`

```
$ python scripts/dup_scan.py tests/fixtures/sample-thesis.md --sources tests/fixtures/source-text.md
=== dup_scan ===
文件：sample-thesis.md｜源文本 1 份｜比对长度 13 字
重合段：3 处｜覆盖率 4.6%

| 行号 | 长度 | 命中来源 | 片段开头 |
|---|---|---|---|
| 31—31 | 62 | source-text.md | 课后服务通过延长学生在校时间减少了学生参加校外培训的机会… |
| 27—27 | 33 | source-text.md | 关于课后服务与学业成绩的关系已有研究结论并不一致支持方多报告正相关… |
| 27—27 | 19 | source-text.md | 反对方则指出控制背景后关联大幅减弱… |

- MAJOR DS002 [第31行] 1 处 40—200 字的重合（最长 62 字，第 31 行，命中 source-text.md）
```

### 4.7 `cite_format.py`（APA 转换）

```
$ python scripts/cite_format.py tests/fixtures/sample-thesis.md --to apa
[1] 陈某, & 王某 (2022). 县域课后服务参与率调查. *教育研究*, *43*(5), 45-52.
[2] 王某 (2021). *通勤时间与课后服务选择* [Doctoral dissertation]. 华东师范大学, 上海.
[3] 李某 (2020). *课后服务的国际比较*. 〔待补：出版地〕: 〔待补：出版者〕.
[4] 教育部 (〔待补：年份〕). 关于做好课后服务工作的通知. http://example.org/policy.html.
[5] 王某 (2020). 课后服务效果的再检验. *教育经济*, *12*(3), 33-40.
[6] 张某 (2021). 课后服务研究综述. *〔待补：刊名〕*.
[8] 陈某 (2022). 县域课后服务参与率调查. *教育研究*, *43*(5), 45-52.

需人工调整（7 条）：姓名需人工转拼音并调序；刊名需人工译为英文或按缩写表处理

问题：BLOCKER 0 / MAJOR 5 / MINOR 0
- MAJOR CF002 [第87行] 编号不连续：第 7 条为 [8]，应为 [7]
- MAJOR CF004 [第86行] 期刊论文缺起止页码
- MAJOR CF005 [第83行] 专著缺出版地或出版者
- MAJOR CF007 [第84行] 电子资源缺引用日期
- MAJOR CF009 [第87行] 疑似重复条目：与第 81 行题名相同
```

## 五、未执行 / 未验证（不计入通过）

| 项 | 原因 | 建议 |
|---|---|---|
| 客户端内对话效果 | 开发环境无法模拟市场安装后的运行时 | 注册后手动走一轮：写方法章、改摘要、转引用、答辩 PPT |
| 撰写质量的盲评 | 无外部评审人 | 找 2—3 位真实用户各写一章，收集"能不能直接用"的反馈 |
| 平台审核与分成政策 | 无后台权限、无政策文档 | 按风险清单第四节逐项确认 |
| macOS / Linux | 仅在 Windows 实测 | 无平台相关代码，仍建议各跑一次 `run_tests.py` |
| 真实论文全流程压测 | 不代写，也不宜用他人材料 | 用自己一篇旧稿从摘要到答辩走一遍 |
| 中文姓名拼音化 | 明确不实现（需专名库） | 输出已逐条标注"需人工调整" |
| 图像生成服务商用条款 | 无法核实原文 | 见风险清单 R2 |

## 六、复现步骤

```bash
cd <专家包>/skills/thesis-architect

# 全部用例
python scripts/run_tests.py

# 逐个工具
python scripts/wordstat.py tests/fixtures/sample-thesis.md --target 3000
python scripts/abstract_check.py tests/fixtures/sample-thesis.md
python scripts/style_lint.py tests/fixtures/sample-thesis.md
python scripts/cite_format.py tests/fixtures/sample-thesis.md --to apa
python scripts/dup_scan.py tests/fixtures/sample-thesis.md --sources tests/fixtures/source-text.md
python scripts/figtable.py tests/fixtures/sample-thesis.md
```

## 七、首轮失败与修复

第一轮 11 个用例失败，代表性问题三例（详见 `docs/DEVLOG.md` 第四节）：

1. `cite_format.py` 把整篇文档吃成一条文献（正文被当第 0 条）→ 改为从首个编号条目开始解析。
2. `abstract_check.py` 抓不到 `## Abstract`（井号 + 大小写）→ 剥井号 + 忽略大小写。
3. `wordstat.py` 认不出"第 1 章"（只认中文数字）→ 正则允许阿拉伯数字。

修复后 54/54 通过，并从夹具实跑确认输出可读。
