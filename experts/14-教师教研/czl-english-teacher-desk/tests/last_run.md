# 回归测试记录（2026-11-01 10:43:12）

- 运行环境：Python 3.13.14 / win32
- 结果：**13/13 通过**

| 用例 | 命令 | 结果 | 说明 |
|---|---|---|---|
| T01 细目表生成（正常配置） | `scripts/blueprint.py --spec C:\Users\丛自龙\.workbuddy\plugins\marketplaces\my-experts\plugins\czl-english-teacher-desk\tests\fixtures\spec.json --out C:\Users\丛自龙\AppData\Local\Temp\etd_test_puhkpm9b\blueprint.md` | PASS | exit=0（期望 0）；输出含 ['已生成']：是 |
| T01b 细目表内容校验 | `-` | PASS | 总分行：True；题量行：True |
| T02 分值不一致应告警 | `scripts/blueprint.py --spec C:\Users\丛自龙\AppData\Local\Temp\etd_test_puhkpm9b\spec_bad.json --out C:\Users\丛自龙\AppData\Local\Temp\etd_test_puhkpm9b\bp_bad.md` | PASS | exit=0（期望 0）；stderr 含 ['WARN']：是 |
| T03 空 sections 应报错 | `scripts/blueprint.py --spec C:\Users\丛自龙\AppData\Local\Temp\etd_test_puhkpm9b\spec_empty.json` | PASS | exit=2（期望 2） |
| T04 成绩统计生成 | `scripts/item_stats.py --csv C:\Users\丛自龙\.workbuddy\plugins\marketplaces\my-experts\plugins\czl-english-teacher-desk\tests\fixtures\scores.csv --full C:\Users\丛自龙\.workbuddy\plugins\marketplaces\my-experts\plugins\czl-english-teacher-desk\tests\fixtures\full.json --out C:\Users\丛自龙\AppData\Local\Temp\etd_test_puhkpm9b\stats.md` | PASS | exit=0（期望 0）；输出含 ['已生成']：是 |
| T04b 统计报告字段完整 | `-` | PASS | 含参考人数与得分率 |
| T05 缺考行被排除（12 行 → 11 人） | `-` | PASS | 统计到 11 人且提示缺考 |
| T06 列名不匹配应报错 | `scripts/item_stats.py --csv C:\Users\丛自龙\.workbuddy\plugins\marketplaces\my-experts\plugins\czl-english-teacher-desk\tests\fixtures\scores.csv --full C:\Users\丛自龙\AppData\Local\Temp\etd_test_puhkpm9b\full_bad.json` | PASS | exit=2（期望 2） |
| T07 读后续写折算 | `scripts/essay_score.py --type continuation --content 4 --language 4 --structure 3 --cohesion 3` | PASS | exit=0（期望 0）；输出含 ['第四档', '18.5']：是 |
| T08 应用文满分需复核 | `scripts/essay_score.py --type app --content 5 --language 5 --structure 5 --cohesion 5` | PASS | exit=0（期望 0）；输出含 ['第五档', '需复核']：是 |
| T09 维度越界应报错 | `scripts/essay_score.py --type app --content 9 --language 4 --structure 3 --cohesion 3` | PASS | exit=2（期望 2） |
| T10 合格样卷自检通过 | `scripts/qa_check.py --paper C:\Users\丛自龙\.workbuddy\plugins\marketplaces\my-experts\plugins\czl-english-teacher-desk\tests\fixtures\paper.md --answers C:\Users\丛自龙\.workbuddy\plugins\marketplaces\my-experts\plugins\czl-english-teacher-desk\tests\fixtures\answers.md` | PASS | exit=0（期望 0）；输出含 ['未发现占位符', '结论：FAIL 0 项']：是 |
| T11 缺陷样卷应报错 | `scripts/qa_check.py --paper C:\Users\丛自龙\.workbuddy\plugins\marketplaces\my-experts\plugins\czl-english-teacher-desk\tests\fixtures\paper_bad.md` | PASS | exit=1（期望 1）；输出含 ['占位符', '缺号']：是 |
