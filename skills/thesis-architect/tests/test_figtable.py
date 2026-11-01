"""figtable 行为测试。"""

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import figtable

FIX = Path(__file__).resolve().parent / "fixtures"


def codes(issues):
    return {i.code for i in issues}


class TestFigtable(unittest.TestCase):
    def test_fixture_dangling_reference(self):
        text = (FIX / "sample-thesis.md").read_text(encoding="utf-8")
        captions, refs = figtable.scan(text)
        issues = figtable.analyze(captions, refs)
        self.assertIn("FT006", codes(issues))

    def test_fixture_unreferenced_table(self):
        text = (FIX / "sample-thesis.md").read_text(encoding="utf-8")
        captions, refs = figtable.scan(text)
        issues = figtable.analyze(captions, refs)
        self.assertIn("FT005", codes(issues))

    def test_duplicate_number(self):
        text = "图 1-1 甲\n\n如图 1-1 所示。\n\n图 1-1 乙\n"
        captions, refs = figtable.scan(text)
        issues = figtable.analyze(captions, refs)
        self.assertIn("FT001", codes(issues))

    def test_gap(self):
        text = "图 1-1 甲\n\n图 1-3 乙\n\n如图 1-1 所示，如图 1-3 所示。\n"
        captions, refs = figtable.scan(text)
        issues = figtable.analyze(captions, refs)
        self.assertIn("FT004", codes(issues))

    def test_style_mix(self):
        text = "图 1 甲\n\n如图 1 所示。\n\n图 2-1 乙\n\n如图 2-1 所示。\n"
        captions, refs = figtable.scan(text)
        issues = figtable.analyze(captions, refs)
        self.assertIn("FT003", codes(issues))

    def test_prose_not_caption(self):
        captions, refs = figtable.scan("表3显示了差异。\n")
        self.assertEqual(captions, [])
        self.assertTrue(refs)

    def test_clean_doc(self):
        text = "表 3-1 样本分布\n\n如表 3-1 所示，样本分布均衡。\n"
        captions, refs = figtable.scan(text)
        issues = figtable.analyze(captions, refs)
        self.assertNotIn("FT005", codes(issues))
        self.assertNotIn("FT006", codes(issues))

    def test_main_exit_code(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = figtable.main([str(FIX / "sample-thesis.md")])
        self.assertEqual(code, 1)
        self.assertIn("FT006", buf.getvalue())

    def test_missing_file(self):
        self.assertEqual(figtable.main(["无此.md"]), 2)


if __name__ == "__main__":
    unittest.main()
