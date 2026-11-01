---
name: czl-physics-desk
description: Operating kit for a senior-high physics teacher's desk. Load when you need to anchor a lesson to curriculum standards, draft lesson plans and worksheets, build item blueprints, papers and scoring rubrics, grade by scoring points, compute difficulty and discrimination from score sheets, map error codes to remedies, design a review lesson, or export print-ready docx. Also load before running the bundled scripts (blueprint, rubric, item analysis, formula check, docx export).
---

# 高中物理教师工作台

这是给一线高中物理教师用的操作手册，不是知识百科，也不是学生讲义。它只解决一件事：**把课上完、把卷子出完、把分数看懂，并且留下能复用的东西。**

## 一、什么时候加载

- 要备一节课（新授/实验/复习/习题），需要教案、学案、板书、作业；
- 要出一份卷子，需要细目表、评分细则、答案；
- 考完了要看数据：难度、区分度、分数段、班级共性错因；
- 要上一节讲评课，需要选题、流程、变式、当堂检测；
- 要把一次教研做成可分享的一页纸；
- 要跑本技能里的脚本（细目表校验、评分细则生成、成绩分析、数值核对、docx 导出）。

学生个人辅导场景不加载本技能，改用学习辅导类专家。

## 二、文件地图

| 文件 | 里面有什么 | 什么时候读 |
|---|---|---|
| `references/00-索引与引用边界.md` | 全套文件索引、引用规范、数据隐私 | 第一次用、要引用课标/教材/真题时 |
| `references/01-课标与考向.md` | 四素养落点、模块结构、题型与分值、难度预设、命题趋势 | W1 定标、W3 命题 |
| `references/02-知识结构与公式.md` | 分模块公式表：表达式、适用条件、高频易错 | 任何涉及公式与判据的场合 |
| `references/03-命题规范.md` | 细目表做法、难度控制、题干与选项规则、四查清单 | W3 命题 |
| `references/04-评分与错因.md` | 错因码表 E01–E20、三步赋分、讲评优先级 | W4 诊断、W5 复盘、批改 |
| `references/05-实验清单.md` | 12 个教材实验的原理、器材、易错、误差、数据处理 | 实验课、实验题 |
| `references/06-讲评与补救.md` | 45 分钟讲评课结构、三选三不选、变式三维度、跟踪表 | W5 复盘 |
| `references/07-版本课时与板书.md` | 四版教材模块对照、课时建议、板书三栏、课件规范 | W2 设计、做课件 |
| `references/08-开放资源与引用边界.md` | 可商用/不可商用的外部资源清单、下载与引用规则 | 要找外部素材时 |
| `references/09-工作流规范.md` | 六个工作流的完整定义（输入/步骤/判断/输出/异常/依赖/关系） | 接手复杂任务、判断该走哪条线 |
| `templates/` | 教案、学案、细目表、试卷评分细则、学情报告、讲评课、教研记录 | 出成品时套结构，不套措辞 |
| `scripts/` | 五个可执行脚本 + 自检 | 涉及计算、统计、导出时 |

## 三、最短路径

老师只说一句话时，按这个顺序处理：

1. **认任务**：备课 / 命题 / 批改分析 / 讲评 / 教研 → 对应 W1–W6（见 `09-工作流规范.md`）。
2. **补最小输入**：一次只问 1–3 项，缺什么问什么，不要抛清单。
3. **先给骨架再给内容**：正式卷先给细目表；教案先给目标与时间轴；学情先给统计表。骨架确认后再展开。
4. **跑工具**：涉及数值 → `physics_calc.py`；出卷 → `blueprint.py` + `rubric_builder.py`；成绩 → `item_analysis.py`。
5. **出打印版**：`docx_lite.py` 生成 A4 .docx，和正文一起交付。
6. **收尾三件事**：需教师确认项（重难点/学情/课时器材）、文件命名、下一步建议（一句话）。

## 四、质量闸门

交付前逐条过，过不了就改：

- [ ] 每个公式都带适用条件，矢量题先定正方向；
- [ ] 计算题答案能由所列式子逐步推出，单位和有效数字对得上；
- [ ] 试卷四件套齐全（细目表、试题、答案、评分细则），总分与时长自洽；
- [ ] 学情结论有数据支撑，样本量与局限写清楚；
- [ ] 真题标注年份与卷别，教材原文没有整段照抄；
- [ ] 打印版能直接印：A4、不跨页、页眉页脚齐全；
- [ ] 末尾有「需您确认」，且只写该老师决定的事。

## 五、边界

- 只做高中物理（含新高考选择性必修），不做大学物理与竞赛超纲题；
- 不做学生作业代写、替考、押题卖题；
- 不伪造真题、不虚构数据、不编造教材页码；
- 学生姓名等个人信息不索取、不落盘，成绩表按学号处理。

## 六、脚本速查

```bash
python scripts/blueprint.py --in 细目表.csv --out 细目表.md      # 校验总分/难度/配比
python scripts/rubric_builder.py --in 步骤.csv --out 评分细则.md  # 生成评分细则
python scripts/item_analysis.py --scores 成绩.csv --full 满分.csv --out 学情.md
python scripts/physics_calc.py --list                            # 看可用公式
python scripts/physics_calc.py --formula kinematics.v --args v0=0,a=2,t=3
python scripts/docx_lite.py --in 教案.md --out 教案.docx --title "牛顿第二定律" --meta "高二·人教2019"
python scripts/self_test.py                                      # 全量自检
```

脚本只用标准库，不需要联网、不需要 pip 安装。
