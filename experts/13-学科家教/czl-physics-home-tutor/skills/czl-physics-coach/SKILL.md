---
name: czl-physics-coach
description: Operating kit for senior-high physics home tutoring. Load when you need the sticking-point probes, the 12-model atlas, process slicing rules, the law-selection decision tree, the error-code table, the exam scoring positions, experiment and graph procedures, parent scripts, textbook-version mapping, formula sheets, or the review schedule. Also load before running the bundled checkers that verify numbers and generate variant problems.
---

# 高中物理家教操作台

这是一套给"家庭辅导"场景用的工作手册，不是知识百科。它的目的是让一次辅导有固定骨架：先判断卡在哪，再按段讲，最后留下可复查的痕迹。

## 一、什么时候加载

- 孩子做不出多过程题、电磁综合题，需要拆开讲；
- 家长想弄清"到底卡在哪"，而不是再听一遍完整解答；
- 错题本越抄越厚但分数不动；
- 实验题、图像题只能靠背；
- 需要出同类变式题、核对答案数值。

## 二、主干流程（三诊六段）

**三诊**：诉求分诊 → 卡点定位 → 学情与版本核对。
**六段**：翻译题面 → 圈对象 → 切时间 → 挑工具 → 按点写 → 换皮再做。

每一段都有可见产出，没有产出不许进下一段。段的详细动作写在主 Agent 提示词里，这里只负责给"怎么做"的具体材料和判据。

## 三、按问题找文件

| 你现在的困难 | 打开 |
|---|---|
| 不知道孩子卡在哪，问不出所以然 | `references/01-卡点诊断与探测题.md` |
| 题目认不出是哪个模型 | `references/02-模型图谱.md` |
| 知道要分段，但切不准、衔接量老丢 | `references/03-过程切分与衔接量.md` |
| 牛顿、动能定理、动量守恒不知道挑哪个 | `references/04-规律选择决策树.md` |
| 复盘时只会说"粗心" | `references/05-错因码表与补救动作.md` |
| 会做但拿不到分 | `references/06-计算题评分点与落笔规范.md` |
| 实验题靠背，数据处理不会写 | `references/07-实验流程与数据处理.md` |
| 图像题读不出信息 | `references/08-图像题读图五问.md` |
| 家长一开口就吵起来 | `references/09-家长陪练话术卡.md` |
| 不知道这章在哪个版本的第几册 | `references/10-教材版本与选科对照.md` |
| 要查公式、单位、量纲 | `references/11-公式与单位速查.md` |
| 要排考前计划、定回访节奏 | `references/12-复习排程与回访节奏.md` |
| 要说明资料从哪来、哪些不能用 | `references/00-资料索引与引用边界.md` |

模板在 `templates/`：讲义、错因卡、周计划、家长陪练单。要交付成文件时用它们，不要每次现编格式。

## 四、脚本

两个脚本都在 `scripts/`，纯标准库，无需安装依赖。

```bash
# 数值复核：算一遍，同时给公式、代入过程和常见错法提醒
python scripts/physics_check.py incline --m 2 --theta 30 --mu 0.2
python scripts/physics_check.py projectile --v0 20 --angle 45
python scripts/physics_check.py collision --m1 2 --u1 6 --m2 4 --u2 0 --kind elastic
python scripts/physics_check.py induction --B 0.5 --L 1 --v 2 --R 0.4

# 变式题生成：题干与答案同时生成，答案由程序计算，不会算错
python scripts/variant_gen.py --model incline --seed 7 --n 2
python scripts/variant_gen.py --list

# 自测：确认脚本本身没坏
python scripts/self_test.py
```

规则：
1. **凡是要给具体数值答案，先跑 `physics_check.py`**。算不出来就说明缺哪个量。
2. 出变式题一律用 `variant_gen.py`，不要手编数字——手编的数字经常出现"答案不整、物理不合理"。
3. 脚本只做高中范围内的模型，超范围会直接报错，不会给一个似是而非的数。

## 五、输出契约

一次辅导至少留下三样东西，缺一样就算没做完：

1. **分段讲解**：段号 + 每段对象/规律/方程；关键行标出这是哪个得分位。
2. **两道变式**：一道换数字，一道换情境；附答案与评分点。
3. **一条错因卡**：错因码 + 证据 + 补救动作 + 回访日期（3/7/15 天）。

给家长看的版本压在 400 字内，只写"做什么"，不写推导。

## 六、质量红线

- 不给整份作业或试卷的答案；只讲方法、批步骤、出同类题。
- 不猜题、不承诺提分数字。
- 条件不足时明确说缺什么，不替题面补假设。
- 教材版本、选科、考试地区不清时先问，不默认。
- 涉及"这题答案是不是错了"时，先用脚本复核再下结论；脚本也判不了就说"这需要看原题和评分标准"。

## 七、引用与版权

本技能内所有讲解文字、模型卡、错因码、模板均为本项目原创编写。教材目录、课程标准只引用名称与结构，不复制原文。需要教材原文时，引导用户到官方平台自行获取，见 `references/00-资料索引与引用边界.md`。
