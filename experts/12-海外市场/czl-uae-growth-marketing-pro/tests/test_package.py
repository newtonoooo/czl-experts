#!/usr/bin/env python3
"""Tests for package integrity (bin/package_check.py) and the shipped assets."""

import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

import package_check  # noqa: E402
import uae_plan  # noqa: E402


class TestPluginJson(unittest.TestCase):
    def setUp(self):
        self.pj = json.loads((ROOT / ".codebuddy-plugin" / "plugin.json").read_text(encoding="utf-8"))

    def test_name_is_prefixed_and_kebab(self):
        self.assertTrue(self.pj["name"].startswith("czl-"))
        self.assertRegex(self.pj["name"], r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")

    def test_plugin_field_matches_name(self):
        self.assertEqual(self.pj["plugin"], self.pj["name"])

    def test_author_is_the_developer(self):
        self.assertEqual(self.pj["author"]["name"], "虫志龙")
        self.assertEqual(self.pj["author"]["email"], "47190078@qq.com")

    def test_exactly_three_tags_and_prompts(self):
        self.assertEqual(len(self.pj["tags"]), 3)
        self.assertEqual(len(self.pj["quickPrompts"]), 3)

    def test_default_prompt_matches_first_quick_prompt(self):
        self.assertEqual(self.pj["defaultInitPrompt"]["zh"], self.pj["quickPrompts"][0]["zh"])

    def test_agent_file_matches_agent_name(self):
        agent_md = ROOT / "agents" / f"{self.pj['agentName']}.md"
        self.assertTrue(agent_md.exists())

    def test_declared_skills_exist(self):
        for rel in self.pj["skills"]:
            self.assertTrue((ROOT / rel.lstrip("./") / "SKILL.md").exists(), rel)


class TestAvatar(unittest.TestCase):
    def test_avatar_is_square_png_within_budget(self):
        pj = json.loads((ROOT / ".codebuddy-plugin" / "plugin.json").read_text(encoding="utf-8"))
        path = ROOT / pj["avatar"]
        self.assertTrue(path.exists())
        with path.open("rb") as fh:
            head = fh.read(33)
        self.assertEqual(head[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", head[16:24])
        self.assertEqual(width, height)
        self.assertGreaterEqual(width, 512)
        self.assertLess(path.stat().st_size / 1024, 500)


class TestPackageCheck(unittest.TestCase):
    def test_package_check_passes(self):
        """The shipped package must pass its own gate with zero FAIL results."""
        package_check.RESULTS.clear()
        exit_code = package_check.main(["--path", str(ROOT)])
        failures = [r for r in package_check.RESULTS if r[0] == "FAIL"]
        self.assertEqual(failures, [])
        self.assertEqual(exit_code, 0)


class TestDataFiles(unittest.TestCase):
    def test_channel_catalog_is_consistent(self):
        channels = uae_plan.load_channels()
        self.assertGreaterEqual(len(channels), 10)
        ids = [c["id"] for c in channels]
        self.assertEqual(len(ids), len(set(ids)), "duplicate channel ids")
        for channel in channels:
            self.assertIn(channel["role"], ("trust", "discovery", "conversion"))
            has_rate = bool(channel.get("cpm_band") or channel.get("cpc_band"))
            self.assertTrue(has_rate or channel.get("pricing_model") == "retainer",
                            f"{channel['id']} has neither a rate band nor a retainer model")

    def test_every_sector_bias_points_to_a_real_channel(self):
        sectors = json.loads((ROOT / "skills/uae-market-intel/data/sector_notes.json")
                             .read_text(encoding="utf-8"))["sectors"]
        known = {c["id"] for c in uae_plan.load_channels()}
        for sector in sectors:
            for cid in sector["channel_bias"] + sector["avoid"]:
                self.assertIn(cid, known, f"{sector['id']} -> {cid}")

    def test_audience_segments_have_basis(self):
        segments = json.loads((ROOT / "skills/uae-market-intel/data/audience_segments.json")
                              .read_text(encoding="utf-8"))["segments"]
        self.assertEqual(len(segments), 5)
        for segment in segments:
            self.assertIn(segment["basis"],
                          ("official-stat", "industry-report", "platform-stated", "planning-range"))

    def test_risk_rules_are_well_formed(self):
        rules = json.loads((ROOT / "skills/uae-brand-safety/data/risk_rules.json")
                           .read_text(encoding="utf-8"))["rules"]
        ids = [r["id"] for r in rules]
        self.assertEqual(len(ids), len(set(ids)))
        for rule in rules:
            self.assertIn(rule["severity"], ("high", "medium", "low"))
            self.assertTrue(rule["patterns"])
            self.assertTrue(rule["alternative"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
