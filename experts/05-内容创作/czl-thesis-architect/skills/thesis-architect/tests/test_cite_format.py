"""cite_format 行为测试。"""

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import cite_format

FIX = Path(__file__).resolve().parent / "fixtures"


def codes(issues):
    return {i.code for i in issues}


class TestCiteFormat(unittest.TestCase):
    def setUp(self):
        self.text = (FIX / "sample-thesis.md").read_text(encoding="utf-8")
        start = self.text.index("[1] 陈某")
        self.refs = self.text[start:]
        self.entries = cite_format.parse_entries(self.refs)

    def test_parse_entries(self):
        self.assertEqual(len(self.entries), 7)
        self.assertEqual(self.entries[0]["number"], 1)

    def test_gap_detected(self):
        issues = cite_format.check(self.entries)
        self.assertIn("CF002", codes(issues))

    def test_book_missing_place(self):
        issues = cite_format.check(self.entries)
        msgs = [i.message for i in issues if i.code == "CF005"]
        self.assertTrue(any("出版地" in m for m in msgs))

    def test_web_missing_cite_date(self):
        issues = cite_format.check(self.entries)
        msgs = [i.message for i in issues if i.code == "CF007"]
        self.assertTrue(any("引用日期" in m for m in msgs))

    def test_journal_missing_pages(self):
        issues = cite_format.check(self.entries)
        msgs = [i.message for i in issues if i.code == "CF004"]
        self.assertTrue(any("页码" in m for m in msgs))

    def test_duplicate_detected(self):
        issues = cite_format.check(self.entries)
        self.assertIn("CF009", codes(issues))

    def test_same_number_is_blocker(self):
        text = "[1] 陈某. 研究一[J]. 教育研究, 2022, 43(5): 45-52.\n[1] 王某. 研究二[J]. 教育研究, 2021, 42(3): 11-20.\n"
        issues = cite_format.check(cite_format.parse_entries(text))
        blockers = [i for i in issues if i.severity == "BLOCKER"]
        self.assertTrue(blockers)
        self.assertEqual(blockers[0].code, "CF001")

    def test_convert_apa(self):
        rendered, notes = cite_format.render(self.entries[0], "apa")
        self.assertIn("(2022)", rendered)
        self.assertIn("*教育研究*", rendered)
        self.assertTrue(any("拼音" in n for n in notes))

    def test_convert_ieee(self):
        rendered, _ = cite_format.render(self.entries[0], "ieee")
        self.assertIn('"县域课后服务参与率调查,"', rendered)
        self.assertIn("vol. 43", rendered)

    def test_convert_gb7714_keeps_marker(self):
        rendered, _ = cite_format.render(self.entries[0], "gb7714")
        self.assertIn("[J]", rendered)

    def test_main_convert_output(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cite_format.main([str(FIX / "sample-thesis.md"), "--to", "apa"])
        out = buf.getvalue()
        self.assertIn(code, (0, 1))
        self.assertIn("目标格式：apa", out)
        self.assertIn("需人工调整", out)

    def test_missing_file(self):
        self.assertEqual(cite_format.main(["无此文件.md"]), 2)


if __name__ == "__main__":
    unittest.main()
