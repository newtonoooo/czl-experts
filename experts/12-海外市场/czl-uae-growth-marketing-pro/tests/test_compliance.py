#!/usr/bin/env python3
"""Tests for the compliance scanner (bin/uae_compliance.py)."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

import uae_compliance  # noqa: E402


class TestScan(unittest.TestCase):
    def test_absolute_claim_is_high_risk(self):
        result = uae_compliance.scan("我们是全网第一品牌，100% 保证有效", "beauty")
        self.assertEqual(result["verdict"], "block")
        self.assertGreaterEqual(result["counts"]["high"], 2)
        ids = {f["rule_id"] for f in result["findings"]}
        self.assertIn("CLM-01", ids)
        self.assertIn("CLM-02", ids)

    def test_clean_copy_passes(self):
        text = "本周新品上市，欢迎到店体验。营业时间 10:00-22:00。"
        result = uae_compliance.scan(text, "beauty")
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["counts"]["high"], 0)

    def test_gambling_blocked(self):
        result = uae_compliance.scan("注册即送彩金，casino 玩法上线", "ecommerce")
        self.assertEqual(result["verdict"], "block")
        self.assertIn("SUB-01", {f["rule_id"] for f in result["findings"]})

    def test_sector_scoping_excludes_other_sectors(self):
        """An education-only rule must not fire for a beauty brief."""
        text = "包就业，保录取"
        beauty = uae_compliance.scan(text, "beauty")
        education = uae_compliance.scan(text, "education")
        self.assertNotIn("EDU-01", {f["rule_id"] for f in beauty["findings"]})
        self.assertIn("EDU-01", {f["rule_id"] for f in education["findings"]})

    def test_ascii_pattern_uses_word_boundary(self):
        """'roi' must not match inside an unrelated word such as 'android'."""
        result = uae_compliance.scan("our android app is live", "fintech")
        self.assertNotIn("FIN-02", {f["rule_id"] for f in result["findings"]})

    def test_findings_sorted_by_severity(self):
        result = uae_compliance.scan("第一品牌，限时秒杀", "ecommerce")
        severities = [f["severity"] for f in result["findings"]]
        self.assertEqual(severities, sorted(severities, key=lambda s: {"high": 0, "medium": 1, "low": 2}[s]))

    def test_context_snippet_present(self):
        result = uae_compliance.scan("这是一段很长的文案，中间写着保证收益，后面还有内容", "fintech")
        self.assertTrue(result["findings"])
        self.assertTrue(all(h["context"] for f in result["findings"] for h in f["hits"]))


class TestCli(unittest.TestCase):
    def test_high_risk_returns_exit_1(self):
        self.assertEqual(uae_compliance.main(["--text", "保证收益，零风险"]), 1)

    def test_clean_text_returns_exit_0(self):
        self.assertEqual(uae_compliance.main(["--text", "欢迎光临，营业时间见门店公告"]), 0)

    def test_empty_text_rejected(self):
        self.assertEqual(uae_compliance.main(["--text", "   "]), 2)

    def test_missing_file_rejected(self):
        self.assertEqual(uae_compliance.main(["--file", "no-such-file.md"]), 2)

    def test_json_format_is_parseable(self):
        import json
        import io
        from contextlib import redirect_stdout
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            uae_compliance.main(["--text", "第一品牌", "--format", "json"])
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["verdict"], "block")


if __name__ == "__main__":
    unittest.main(verbosity=2)
