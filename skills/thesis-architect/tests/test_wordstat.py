"""wordstat 行为测试。"""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import wordstat

FIX = Path(__file__).resolve().parent / "fixtures"


def codes(issues):
    return {i.code for i in issues}


class TestWordstat(unittest.TestCase):
    def setUp(self):
        self.text = (FIX / "sample-thesis.md").read_text(encoding="utf-8")

    def test_chapters_detected(self):
        data, _ = wordstat.analyze(self.text)
        titles = [c["title"] for c in data["chapters"]]
        self.assertEqual(len([t for t in titles if t.startswith("第")]), 6)
        self.assertTrue(any("前置" in t for t in titles))

    def test_total_equals_sum(self):
        data, _ = wordstat.analyze(self.text)
        self.assertEqual(data["total"], sum(c["total"] for c in data["chapters"]))
        self.assertGreater(data["total"], 1000)

    def test_target_too_low(self):
        data, _ = wordstat.analyze(self.text)
        target = int(data["total"] * 2)
        _, issues = wordstat.analyze(self.text, target=target)
        self.assertIn("WS002", codes(issues))

    def test_target_matched_no_issue(self):
        data, _ = wordstat.analyze(self.text)
        _, issues = wordstat.analyze(self.text, target=data["total"])
        self.assertNotIn("WS002", codes(issues))

    def test_thin_chapter_flagged(self):
        text = "# 第 1 章 引言\n\n" + ("内容。" * 400) + "\n\n# 第 2 章 结论\n\n短。\n"
        _, issues = wordstat.analyze(text)
        self.assertIn("WS003", codes(issues))

    def test_figures_and_tables_counted(self):
        data, _ = wordstat.analyze(self.text)
        figures = sum(c["figures"] for c in data["chapters"])
        tables = sum(c["tables"] for c in data["chapters"])
        self.assertGreaterEqual(figures, 1)
        self.assertGreaterEqual(tables, 1)

    def test_main_json(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = wordstat.main([str(FIX / "sample-thesis.md"), "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["tool"], "wordstat")
        self.assertGreater(payload["total"], 1000)

    def test_missing_file(self):
        self.assertEqual(wordstat.main(["无此文件.md"]), 2)


if __name__ == "__main__":
    unittest.main()
