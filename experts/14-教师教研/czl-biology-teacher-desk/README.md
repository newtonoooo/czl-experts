# 卓识教育 · 高中生物老师助手

> 一个从备课到评价的高中生物教师工作台。给一节课、一个单元、一份卷子、一叠答题卡或一张成绩表，返回可以直接进课堂、直接印发的东西。

- **包名**：`czl-biology-teacher-desk`
- **版本**：1.0.0
- **开发者**：虫志龙（47190078@qq.com）
- **类型**：Agent 型专家（单角色）
- **分类**：06-ContentCreative（平台校验器支持的 12 类之一；若你的市场支持教育分类，可改为 15-Education，见风险清单第 2 条）

## 它解决什么问题

高中生物老师的时间，大量耗在四件重复又必须准确的事上：

1. 备课要写目标、配活动、算时间，还得保证目标和评价对得上；
2. 出卷要先想清楚考什么、考到什么程度，出完还要写评分细则；
3. 批完要能说清"他到底卡在哪一步"，而不是只打个分；
4. 考完要决定下周教什么，而不是只报个均分。

这个专家把四件事串成一条流水线：**先定边界 → 再出内容 → 回收数据 → 统一定稿**。

## 八个工作流

| 编号 | 名称 | 触发场景 | 交付物 |
|---|---|---|---|
| W1 | 任务受理与边界确认 | 任何任务的第一步 | 任务卡 |
| W2 | 单元架构 | 单元规划、课时不够 | 概念依赖图 + 课时表 + 单元评价 |
| W3 | 课时设计 | 备新课、复习课、讲评课 | 三对齐表 + 教案 + 板书 + 分层作业 |
| W4 | 命题与组卷 | 单元卷、月考、专项 | 双向细目表 + 试卷 + 答案 + 评分细则 |
| W5 | 批阅与反馈 | 答题卡、长句题、实验报告 | 采分点打勾表 + 错因归类 + 批语 |
| W6 | 学情诊断与分层 | 考后分析 | 统计表 + Top 失分点 + A/B/C 处方 |
| W7 | 实验课设计 | 学生实验、材料受限 | 变量表 + 安全须知 + 预实验清单 + 失败预案 |
| W8 | 交付打包 | 成品交付前 | 打印版 docx + 课件大纲 + 复核清单 |

工作流之间是串联的，每个文件都写了输入、步骤、判断条件、输出、异常处理、依赖和上下游关系。

## 三对齐：本产品的核心方法

任何一节课、任何一份卷子，先摆一张"目标—活动—证据"表。目标必须可测，每个目标必须有评价证据，认知层级要铺开（默认 记忆:理解:应用:分析 ≈ 2:4:3:1）。找不到证据的目标，删掉；分值不闭合的细目表，重做。

## 随包工具（纯标准库，离线可跑）

| 脚本 | 作用 | 典型命令 |
|---|---|---|
| `skills/czl-bio-teacher-kit/scripts/score_report.py` | 成绩统计、板块得分率、难度与区分度 | `python score_report.py -i scores.csv -f 2,2,4,6 -o report.md` |
| `skills/czl-bio-teacher-kit/scripts/blueprint_check.py` | 双向细目表校验 | `python blueprint_check.py -i blueprint.csv --total 100 --profile unit` |
| `skills/czl-bio-teacher-kit/scripts/make_docx.py` | Markdown → A4 打印版 docx | `python make_docx.py -i 教案.md -o 教案.docx` |
| `bin/validate_package.py` | 专家包自检（路径、头像、引用） | `python bin/validate_package.py .` |
| `bin/set_local_avatar.py` | 本地导入时让头像显示出来 | `python bin/set_local_avatar.py --expert-dir .` |
| `bin/image_square.py` | PNG 正方形裁剪缩放（无第三方依赖） | `python bin/image_square.py -i a.png -o b.png --size 512` |

## 目录结构

```
czl-biology-teacher-desk/
├── .codebuddy-plugin/plugin.json   专家清单
├── agents/                         Agent 主提示词
├── workflows/                      W1–W8 工作流
├── references/                     六份原创学科资料
├── materials/                      可直接印发的表单模板
├── skills/czl-bio-teacher-kit/     工具脚本与模板
├── bin/                            打包与运维脚本
├── avatars/expert.png              原创头像
├── docs/                           规格、说明、测试、风险、清单
├── tests/                          自动化测试与样例数据
├── README.md / CHANGELOG.md / LICENSE
```

## 安装 / 导入

**方式一（推荐）**：把 `dist/czl-biology-teacher-desk.zip` 导入 WorkBuddy 专家中心。

**方式二（本机开发）**：把整个目录放到
`~/.workbuddy/plugins/marketplaces/my-experts/plugins/`，再运行平台注册脚本。

导入后如果列表里显示的是首字色块而不是头像，见 `docs/02-使用说明.md` 第 4 节：这是相对路径头像在本地未上传时的正常回退，可用 `bin/set_local_avatar.py` 临时内嵌头像。

## 边界

- 不替学生写作业、不押题、不承诺分数。
- 只做教材标准实验的教学指导，不做危险操作。
- 不打包教材原文、教辅扫描件、真题成卷；引用的真题标注年份与卷别。
- 学情只处理分数本身，不收集学生姓名。

## 版权与许可

本包内全部提示词、工作流、参考资料、脚本、头像均由虫志龙独立编写与制作，未复制第三方受版权保护的表达。许可条款见 `LICENSE`。

## 更新

见 `CHANGELOG.md`。
