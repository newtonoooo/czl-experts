"""style_lint 行为测试。"""

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import style_lint

FIX = Path(__file__).resolve().parent / "fixtures"


def codes(issues):
    return {i.code for i in issues}


class TestStyleLint(unittest.TestCase):
    def test_fixture_formulaic(self):
        text = (FIX / "sample-thesis.md").read_text(encoding="utf-8")
        metrics, issues = style_lint.lint(text)
        self.assertGreaterEqual(metrics["formulaic_hits"], 6)
        self.assertIn("SL003", codes(issues))

    def test_clean_text_no_formulaic_issue(self):
        text = "三校参与率分别为 82.1%、64.5% 与 48.7%。通勤时间每增加 30 分钟，周参与时长减少 0.7 小时。" * 6
        _, issues = style_lint.lint(text)
        self.assertNotIn("SL003", codes(issues))

    def test_long_sentence(self):
        sentence = "本研究通过对三所县域初中为期一学年的参与数据进行收集整理并在此基础上结合问卷与访谈两类材料的交叉验证进一步考察了通勤时间与家庭收入两类因素对参与率的独立影响。"
        text = sentence * 25
        metrics, issues = style_lint.lint(text)
        self.assertGreater(metrics["long_sentence_ratio"], 0.25)
        self.assertIn("SL001", codes(issues))

    def test_short_sentence_runs(self):
        text = "数据显示差异。差异很明显。三校不同。差距很大。值得关注。还需要检验。" * 5
        _, issues = style_lint.lint(text)
        self.assertIn("SL002", codes(issues))

    def test_connective_abuse(self):
        text = "首先，要说明样本。其次，要说明工具。再次，要说明程序。最后，要说明分析。" * 3
        _, issues = style_lint.lint(text)
        self.assertIn("SL004", codes(issues))

    def test_english_passive(self):
        text = "The data were collected by teachers. The survey was distributed in three schools. " \
               "The results were analysed by SPSS. The sample was selected by stratum. " \
               "The questionnaire was designed by the author. The interviews were recorded by two assistants. " * 3
        metrics, issues = style_lint.lint(text)
        self.assertGreater(metrics["passive_ratio"], 0.5)
        self.assertIn("SL006", codes(issues))

    def test_main_json(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = style_lint.main([str(FIX / "sample-thesis.md"), "--json"])
        self.assertIn(code, (0, 1))
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["tool"], "style_lint")

    def test_missing_file(self):
        self.assertEqual(style_lint.main(["无此.md"]), 2)


if __name__ == "__main__":
    unittest.main()
