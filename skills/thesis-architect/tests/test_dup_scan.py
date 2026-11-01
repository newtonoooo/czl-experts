"""dup_scan 行为测试。"""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import dup_scan

FIX = Path(__file__).resolve().parent / "fixtures"


def codes(issues):
    return {i.code for i in issues}


class TestDupScan(unittest.TestCase):
    def test_finds_overlap(self):
        target = (FIX / "sample-thesis.md").read_text(encoding="utf-8")
        sources = [(p.name, p.read_text(encoding="utf-8")) for p in [FIX / "source-text.md"]]
        _, _, segments, coverage = dup_scan.find_segments(target, sources, 13)
        self.assertTrue(segments)
        self.assertGreater(coverage, 0)
        longest = max(segments, key=lambda s: s["length"])
        self.assertGreaterEqual(longest["length"], 40)
        self.assertEqual(longest["source"], "source-text.md")

    def test_line_numbers_reasonable(self):
        target = (FIX / "sample-thesis.md").read_text(encoding="utf-8")
        sources = [("source-text.md", (FIX / "source-text.md").read_text(encoding="utf-8"))]
        _, _, segments, _ = dup_scan.find_segments(target, sources, 13)
        seg = max(segments, key=lambda s: s["length"])
        self.assertGreater(seg["start_line"], 20)
        self.assertLessEqual(seg["end_line"], len(target.splitlines()))

    def test_no_overlap(self):
        target = "本研究讨论县域学校的通勤约束与参与决策之间的关系，并提出三项可检验的推论。"
        sources = [("other.md", "完全无关的另一段文字，用于确认工具不会误报普通短句和常见搭配。")]
        _, _, segments, coverage = dup_scan.find_segments(target, sources, 13)
        self.assertEqual(segments, [])
        self.assertEqual(coverage, 0.0)

    def test_main_json(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = dup_scan.main([str(FIX / "sample-thesis.md"), "--sources", str(FIX / "source-text.md"), "--json"])
        self.assertIn(code, (0, 1))
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["tool"], "dup_scan")
        self.assertTrue(payload["segments"])

    def test_missing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty_dir = Path(tmp) / "empty"
            empty_dir.mkdir()
            code = dup_scan.main([str(FIX / "sample-thesis.md"), "--sources", str(empty_dir)])
            self.assertEqual(code, 2)

    def test_missing_target(self):
        self.assertEqual(dup_scan.main(["无此.md", "--sources", str(FIX)]), 2)


if __name__ == "__main__":
    unittest.main()
