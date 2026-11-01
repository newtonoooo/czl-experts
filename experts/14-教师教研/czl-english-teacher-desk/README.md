# 卓识教育-高中英语老师助手

> 六段闭环的高中英语教学工作台：学情定位 → 单元与课时设计 → 命题组卷 → 批改与错误台账 → 讲评与迁移 → 周期复盘。
> 开发者：虫志龙｜邮箱：47190078@qq.com｜版本：1.0.0｜标识：`czl-english-teacher-desk`

## 它解决什么问题

一线英语教师的时间不是花在"不会写教案"，而是花在**重复描述背景**和**把零散材料拼成能用的东西**上：这节课的目标要和上次考试暴露的缺口对上，这套卷子要和刚教过的范围对上，这次批改要和下节课的讲评对上。

本产品把这条链固定成六段，每段有准入条件、交付物和质检单，上一段的产物直接成为下一段的输入。教师只需给最少的信息（教材单元、课型、班级层次；或一份成绩表、一篇学生作文），就能拿到可直接上课、直接印、直接讲的东西。

## 六段能力

| 段 | 产出 | 典型说法 |
|---|---|---|
| W1 学情定位台 | 学情诊断单（分布、板块得分率、失分点 Top3–5、错因分布） | "我班这次考得不好，问题在哪" |
| W2 单元与课时设计台 | 单元整体设计 + 课时教案 + 分层作业 + 评价量表 | "明天要上必修一 Unit 3 阅读课" |
| W3 命题组卷台 | 双向细目表 + 原创试卷 + 答案与解析 + 质检单 | "出一套单元测，100 分" |
| W4 批改与错误台账 | 批改单（四维证据 + 改句示范）+ 班级错误台账 | "批一下这 30 篇读后续写" |
| W5 讲评与迁移台 | 讲评课教案 + 变式题组 + 当堂检测 | "这题总错，讲评课怎么上" |
| W6 周期复盘台 | 复盘报告（动作—结果对照、三层归因、三个决策） | "这个月到底有没有效果" |

## 四个可运行脚本

| 脚本 | 作用 |
|---|---|
| `scripts/blueprint.py` | 由 JSON 配置生成双向细目表，校验题量、分值、难度配比、考点集中度 |
| `scripts/item_stats.py` | 成绩 CSV → 均分、标准差、分数段、板块得分率、失分贡献率、失分点排序 |
| `scripts/essay_score.py` | 写作四维分 → 加权总分、档次建议、一致性告警 |
| `scripts/qa_check.py` | 试卷/答案自检：占位符、题号连续、选项完整、分值合计、答案数量、隐私字段 |

仅依赖 Python 3 标准库，不联网。运行示例：

```bash
python scripts/blueprint.py --spec tests/fixtures/spec.json --out 细目表.md
python scripts/item_stats.py --csv tests/fixtures/scores.csv --full tests/fixtures/full.json --out 学情.md
python scripts/essay_score.py --type continuation --content 4 --language 4 --structure 3 --cohesion 3
python scripts/qa_check.py --paper tests/fixtures/paper.md --answers tests/fixtures/answers.md
```

## 目录结构

```
czl-english-teacher-desk/
├── .codebuddy-plugin/plugin.json   专家元数据（展示字段、头像、知识库清单）
├── agents/                         主提示词（路由、纪律、契约、边界）
├── workflows/W1–W6                 六段工作流规格（职责/输入/步骤/判断/输出/异常/依赖）
├── references/                     10 份知识库（课标口径、卷面结构、课型模型、命题规范、评分框架、错因、指标、质检、交付、素材合规）
├── scripts/                        4 个可运行脚本
├── bin/make_avatar.py              头像裁剪缩放工具（纯标准库）
├── tests/                          回归测试（13 个用例 + fixtures + 最近一次运行记录）
├── docs/                           产品规格、工作流设计、使用说明、开发记录、测试报告、风险清单、展示文案、图标诊断
├── avatars/expert.png              512×512 原创头像
├── LICENSE                         许可条款
└── CHANGELOG.md                    版本记录
```

## 使用示例

- 人教版必修一 Unit 3 的阅读课，做成一份明天就能上的教案，含分层作业
- 这是我班月考英语成绩表，算出各板块得分率，找出失分点前三，再配一节讲评课
- 这是学生的读后续写，按评分维度批改，挑两个最值得改的问题，只示范改两句

## 边界

不做整卷真题复制、不做教材原文转录、不代替教师定等、不收集学生身份信息、不出听力音频、不做代写与成绩造假。

## 安装

专家目录（WorkBuddy）：

```
%USERPROFILE%\.workbuddy\plugins\marketplaces\my-experts\plugins\czl-english-teacher-desk\
```

注册到市场列表：

```bash
python scripts/register_expert.py "<expert-dir>"
```

> 脚本位于 WorkBuddy 内置的 expert-manager 技能目录，不在本包内。

## 头像

`avatars/expert.png`，512×512，PNG，约 218 KB。替换要求：PNG/JPG、512×512、≤500 KB、文件名保持 `expert.png`。

## 许可

见 `LICENSE`。第三方依赖：仅 Python 标准库，无第三方代码、无外部素材。
