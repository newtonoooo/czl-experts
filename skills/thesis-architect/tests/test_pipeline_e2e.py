"""端到端：六个写作工具在示例论文上跑通，且各自能命中设计好的问题。"""

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import abstract_check
import cite_format
import dup_scan
import figtable
import style_lint
import wordstat

FIX = Path(__file__).resolve().parent / "fixtures"
THESIS = str(FIX / "sample-thesis.md")


def run(func, args):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = func(args)
    return code, buf.getvalue()


class TestPipeline(unittest.TestCase):
    def test_all_six_tools(self):
        code, out = run(wordstat.main, [THESIS, "--target", "3000"])
        self.assertEqual(code, 0, out)
        self.assertIn("合计", out)

        code, out = run(abstract_check.main, [THESIS])
        self.assertEqual(code, 0, out)
        self.assertIn("关键词：5 个", out)

        code, out = run(style_lint.main, [THESIS])
        self.assertIn("SL003", out)

        code, out = run(cite_format.main, [THESIS])
        self.assertIn("CF009", out)

        code, out = run(figtable.main, [THESIS])
        self.assertEqual(code, 1, out)
        self.assertIn("FT006", out)

        code, out = run(dup_scan.main, [THESIS, "--sources", str(FIX / "source-text.md")])
        self.assertIn("source-text.md", out)

    def test_json_contract(self):
        for func, args in (
            (wordstat.main, [THESIS, "--json"]),
            (abstract_check.main, [THESIS, "--json"]),
            (style_lint.main, [THESIS, "--json"]),
            (cite_format.main, [THESIS, "--json"]),
            (figtable.main, [THESIS, "--json"]),
            (dup_scan.main, [THESIS, "--sources", str(FIX / "source-text.md"), "--json"]),
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                try:
                    func(args)
                except SystemExit as exc:  # 工具内部不会 sys.exit，防御性处理
                    self.fail(f"工具意外退出：{exc}")
            payload = json.loads(buf.getvalue())
            self.assertIn("tool", payload)
            self.assertIn("issues", payload)
            self.assertIn("summary", payload)


if __name__ == "__main__":
    unittest.main()
