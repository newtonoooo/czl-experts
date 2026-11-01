"""abstract_check 行为测试。"""

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import abstract_check

FIX = Path(__file__).resolve().parent / "fixtures"


def codes(issues):
    return {i.code for i in issues}


GOOD = """摘要：本研究以县域三所初中为对象，采用问卷与访谈相结合的方法，共回收有效问卷 312 份。结果显示，三校参与率分别为 82.1%、64.5% 与 48.7%。研究认为，通勤时间是主要解释变量。受横截面设计限制，本研究不作因果推断。

关键词：课后服务；参与率；通勤时间；县域初中

## Abstract

Drawing on 312 parent surveys from three junior high schools, this study examines participation. Rates ranged from 48.7% to 82.1%. The findings suggest that commuting time shapes participation. The cross-sectional design limits causal inference.

Keywords: after-school programs; participation rate; commuting time
"""


class TestAbstractCheck(unittest.TestCase):
    def test_fixture_parsed(self):
        text = (FIX / "sample-thesis.md").read_text(encoding="utf-8")
        metrics, issues = abstract_check.analyze(text)
        self.assertGreater(metrics["zh_chars"], 100)
        self.assertGreater(metrics["en_words"], 20)
        self.assertEqual(metrics["keyword_count"], 5)
        self.assertNotIn("AB001", codes(issues))

    def test_elements_detected(self):
        metrics, _ = abstract_check.analyze(GOOD)
        self.assertTrue(all(metrics["elements"].values()), metrics["elements"])

    def test_missing_result_element(self):
        text = "摘要：本研究以三所初中为对象，采用问卷方法。研究认为该问题值得关注。\n\n关键词：课后服务；参与率；通勤时间\n"
        _, issues = abstract_check.analyze(text)
        self.assertIn("AB004", codes(issues))

    def test_too_short(self):
        text = "摘要：本研究讨论课后服务。\n\n关键词：课后服务；参与率；通勤时间\n"
        _, issues = abstract_check.analyze(text)
        self.assertIn("AB002", codes(issues))

    def test_number_mismatch(self):
        text = (
            "摘要：本研究回收有效问卷 312 份，参与率为 82.1%。结果显示差异明显。研究认为通勤时间是主要因素。"
            "受样本限制，结论仅适用于本县。\n\n关键词：课后服务；参与率；通勤时间\n\n## Abstract\n\n"
            "Drawing on 250 surveys, this study finds a rate of 61.4%. Results show clear differences. "
            "The findings suggest commuting time matters. The sample limits generalisation.\n"
        )
        _, issues = abstract_check.analyze(text)
        self.assertIn("AB009", codes(issues))

    def test_banned_keyword(self):
        text = "摘要：本研究回收问卷 312 份，采用问卷方法，结果显示差异存在，研究认为通勤时间重要，受样本限制。\n\n关键词：课后服务；研究；分析；对策\n"
        _, issues = abstract_check.analyze(text)
        self.assertIn("AB008", codes(issues))

    def test_no_abstract(self):
        _, issues = abstract_check.analyze("# 第一章\n\n正文没有摘要。\n")
        self.assertIn("AB001", codes(issues))

    def test_main_json(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = abstract_check.main([str(FIX / "sample-thesis.md"), "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["tool"], "abstract_check")

    def test_missing_file(self):
        self.assertEqual(abstract_check.main(["无此.md"]), 2)


if __name__ == "__main__":
    unittest.main()
