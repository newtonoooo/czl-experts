# 语言准确性自查清单（Language QA）

> 用法：所有含英文的成品在交付前逐条过一遍。能用脚本的部分用 `scripts/qa_check.py`，语义类必须人工看。

## 一、语法高频错（教师最容易漏看的）

| # | 检查点 | 错误示例 | 正确 |
|---|---|---|---|
| 1 | 主谓一致（集合名词/就近原则） | The number of students are rising. | The number of students is rising. |
| 2 | 时态一致（叙事文中突然跳现在时） | She walked in and sees a letter. | She walked in and saw a letter. |
| 3 | 现在完成 vs 一般过去 | I have seen him yesterday. | I saw him yesterday. |
| 4 | 非谓语逻辑主语 | Walking in the park, the flowers looked beautiful. | Walking in the park, I found the flowers beautiful. |
| 5 | 定语从句关系词 | This is the house which he lives. | This is the house where he lives. |
| 6 | 冠词（可数单数必带冠词） | He is teacher. | He is a teacher. |
| 7 | 介词搭配 | discuss about the plan | discuss the plan |
| 8 | 比较级对象一致 | His English is better than me. | His English is better than mine. |
| 9 | 虚拟语气 | If I was you, I would go. | If I were you, I would go. |
| 10 | 倒装（否定词提前） | Never I have seen such a thing. | Never have I seen such a thing. |
| 11 | 平行结构 | She likes reading, swimming and to run. | She likes reading, swimming and running. |
| 12 | 代词指代一致 | Everyone should bring their book.（正式书面语中） | Everyone should bring his or her book. / All students should bring their books. |

## 二、中式英语（Chinglish）高频对照

| 学生写法 | 问题 | 建议 |
|---|---|---|
| I very like it. | 程度副词不能直接修饰动词 | I like it very much. |
| open the light | 搭配错 | turn on the light |
| learn knowledge | 搭配错 | acquire / gain knowledge |
| my English level has improved | 搭配生硬 | my English has improved |
| with the development of society | 套话 | 改成具体现象 |
| As we all know that... | 句法冗余 | As we all know, ... |
| There have many people. | 存在句误用 | There are many people. |
| I think it is not good. | 否定前移更自然 | I don't think it is good. |

## 三、答案与题干一致性

- [ ] 选择题答案数量 = 题目数量（含七选五 5 空）。
- [ ] 每个选项字母 A–D 都存在，无重复、无空项。
- [ ] 答案与解析给出的选项一致（不能答案写 B、解析说 C）。
- [ ] 语法填空答案与语篇语法一致（时态、单复数、大小写）。
- [ ] 完形答案代入后整段可读通。
- [ ] 写作题要点数 = 评分时对照的要点数。

## 四、格式与排版

- [ ] 题号连续，无跳号、无重号。
- [ ] 卷头分值合计 = 各题分值之和。
- [ ] 选项标点统一（A. / A) 不混用）。
- [ ] 英文标点用半角，中文标点用全角，不混排。
- [ ] 首行缩进/段间距统一。
- [ ] 听力材料标注"仅文本，无音频"。

## 五、占位符与残留

- [ ] 无 `[TODO]`、`XX`、`待补`、`（略）`、`……（自行补充）`。
- [ ] 无模板说明文字残留（如"此处写教学目标"）。
- [ ] 无重复段落（复制粘贴痕迹）。
- [ ] 文件名与内容一致（不出现"未命名""副本"）。

## 六、隐私与合规

- [ ] 无学生真实姓名、学号、身份证号、手机号。
- [ ] 无真实学校全称 + 具体班级 + 成绩的组合（可识别个人）。
- [ ] 语篇中无真实未成年人可识别信息。
- [ ] 引用外部材料注明来源；未整段复制受版权保护内容。
- [ ] 不含"官方命题""内部消息"等误导性表述。

## 七、语义合理性（脚本查不了，必须人看）

1. 阅读题的正确答案是否真的唯一？把四个选项逐个代回原文验证。
2. 干扰项是否有"其实也对"的情况？
3. 写作题的要点是否都在情境中能自然引出？
4. 续写前文是否真的留了可接的伏笔？没有就补。
5. 教案的活动时间加起来是否超课时？
6. 分层作业是否三层指向同一目标？

## 八、交付前最后一问

> 如果另一位同层次教师拿到这份材料，不改一个字能不能直接上课/直接印？不能的话，缺的那一块就是没做完。
