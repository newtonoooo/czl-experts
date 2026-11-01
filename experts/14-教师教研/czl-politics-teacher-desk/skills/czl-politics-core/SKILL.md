---
name: czl-politics-core
description: "Core knowledge and production rules for the senior-high politics teacher workbench: curriculum map, concept clinic, lesson frames, exam blueprint, score diagnosis, current-affairs sourcing protocol, delivery spec, plus workflow files, document templates and two lint scripts. Load when producing or checking any politics teaching deliverable (unit plan, lesson plan, slide outline, exam item, review lesson, revision plan)."
---

# 高中政治备课核心库

这是「卓识教育-高中政治老师助手」的作业底稿。它解决一件事：**让每一份产出有依据、有结构、能被别人接手。**

## 什么时候用

只要产出下列任何一类东西，先读本文件，再按需读对应参考：

- 单元/学期/复习专题规划
- 课时教学设计（新授、复习、讲评、习题、公开课）
- 课件分页框架、板书设计
- 作业、试题、评分细则、双向细目表
- 成绩分析与学情诊断报告
- 时政素材的教学化改造

## 目录索引

### references/（知识底稿）

| 文件 | 解决什么问题 | 什么时候读 |
|---|---|---|
| `curriculum-map.md` | 七册教材的模块—主题群—核心概念地图、素养落点、常见考法 | 任何涉及"这个内容在哪本书、考什么"的时候 |
| `concept-clinic.md` | 40 组高频易混概念的区分、判断口诀、典型设问 | 设计辨析环节、解释学生错因、命制干扰项时 |
| `lesson-frames.md` | 五种课型的课堂结构、议题式教学四要素、问题链规则、常见失败模式 | 设计任何一节课之前 |
| `exam-blueprint.md` | 命题蓝图、能力层级、情境类型、设问动词、评分细则写法、12 条命题硬伤 | 出题、改题、审题时 |
| `grading-diagnosis.md` | 得分率与区分度读法、五类错因、临界生、教学归因 | 拿到分数数据之后 |
| `current-affairs-protocol.md` | 素材来源分级、五步核验、素材卡字段、教学转化路径、引用与边界 | 用任何时政材料之前 |
| `delivery-spec.md` | 五类交付物的字段、版式、命名、长度上限 | 定稿排版时 |
| `source-index.md` | 权威来源清单、检索式、引用格式 | 需要核实事实时 |

### templates/（成品骨架）

| 模板 | 对应产出 |
|---|---|
| `unit-plan.md` | 单元整体规划 |
| `lesson-plan.md` | 课时教学设计 |
| `slide-outline.md` | 分页课件框架 + 板书 |
| `exam-item.md` | 单题（选择/主观）与评分细则 |
| `review-lesson.md` | 试卷讲评课设计 |

模板里的 `{{字段}}` 必须全部替换，不允许留存占位符。定稿前用 `scripts/lesson_lint.py` 扫一遍。

### workflows/（八条工作流）

`W1-intake` → `W2-unit-plan` → `W3-lesson-design` → `W4-slides-board` → `W5-assessment` → `W6-grading-diagnosis` → `W7-review-lesson` → `W8-quality-gate`

工作流文件在专家包根目录的 `workflows/` 下。每条工作流都写了：职责、输入参数、执行步骤、判断条件、输出格式、异常处理、依赖、上下游关系。**按需读，不要一次全读。**

### scripts/（两个检查器，纯标准库，无需安装依赖）

```bash
python scripts/lesson_lint.py <交付文件.md>
python scripts/item_lint.py <试题文件.md>
```

- `lesson_lint.py`：检查教案/规划/讲评稿的必备章节、占位符残留、时间加总、目标—评价对齐数量、禁用表述。
- `item_lint.py`：检查试题文件的题干要素、选项数量、答案与解析是否齐全、评分标准是否有分档、是否出现"略""言之有理即可"这类空答案。

两个脚本都只做机械检查，**结论不等于合格**：人的判断仍然要做，脚本只负责把低级错误挡在门外。

## 生产流程（默认路径）

1. **判任务**：读 `workflows/W1-intake.md`，把用户的话拆成"模块 + 课型 + 课时 + 产出清单"。
2. **找底稿**：按任务类型读 1—2 个 reference，不要全读。
3. **套骨架**：从 `templates/` 取对应模板，先搭空架子再填内容。
4. **填内容**：遵循 `agents/czl-politics-teacher-desk.md` 第六节的输出规范。
5. **过闸**：按五道质量闸自查（事实、对齐、可教、可评、可核）。
6. **跑脚本**：`lesson_lint.py` 或 `item_lint.py`。
7. **写备注**：交付物末尾的"教师备注"三段不能省。

## 三条容易翻车的地方

1. **把"议题"写成"话题"**。议题必须是一个有张力的判断问题（"该不该""值不值""哪一种更可取"），不是一个名词（"谈创新""说民主"）。名词开头的一定要改。
2. **目标写素养、活动做填空**。政治认同、科学精神不是靠念出来的，是靠学生在情境里做判断做出来的。活动里没有"学生要做出一个判断并说明理由"，这条目标就是空的。
3. **评分标准写成"意思对即可"**。分档标准必须能回答："这个学生得了 6 分而不是 4 分，差在哪句话？"答不上来就是没写标准。

## 与其他组件的关系

- 人设、路由、红线在 `agents/czl-politics-teacher-desk.md`，本文件不重复。
- 本库只装"知识 + 骨架 + 检查器"，不装人设。
- 新增内容时，reference 放判据，template 放格式，workflow 放流程，三者不混写。
