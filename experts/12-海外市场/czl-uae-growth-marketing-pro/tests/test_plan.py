#!/usr/bin/env python3
"""Tests for the deterministic channel budget model (bin/uae_plan.py)."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

import uae_plan  # noqa: E402


class TestAllocation(unittest.TestCase):
    def test_allocation_sums_exactly_to_working_budget(self):
        """Integer allocation must never drift, at any budget level."""
        for budget in (12000, 50000, 87321, 150000, 300000, 999999, 1250000):
            for objective in uae_plan.OBJECTIVES:
                plan = uae_plan.build_plan(budget, objective, "mixed", "ecommerce", "uae_wide", 0.10)
                with self.subTest(budget=budget, objective=objective):
                    self.assertNotIn("error", plan)
                    self.assertEqual(plan["totals"]["spend"], plan["working_budget"])
                    self.assertEqual(plan["working_budget"] + plan["test_reserve"], budget)

    def test_shares_sum_to_about_hundred(self):
        plan = uae_plan.build_plan(300000, "conversion", "expand", "beauty", "dubai", 0.10)
        total_share = sum(row["share"] for row in plan["channels"])
        self.assertAlmostEqual(total_share, 100.0, delta=1.0)

    def test_reserve_zero_allocates_whole_budget(self):
        plan = uae_plan.build_plan(200000, "awareness", "core", "fmcg", "uae_wide", 0.0)
        self.assertEqual(plan["test_reserve"], 0)
        self.assertEqual(plan["totals"]["spend"], 200000)


class TestSelectionRules(unittest.TestCase):
    def test_channel_count_respects_budget_tier(self):
        cases = [(20000, 2), (50000, 4), (300000, 4), (800000, 6)]
        for budget, cap in cases:
            plan = uae_plan.build_plan(budget, "awareness", "mixed", "ecommerce", "uae_wide", 0.10)
            with self.subTest(budget=budget):
                self.assertLessEqual(len(plan["channels"]), cap)

    def test_large_budget_keeps_a_trust_channel(self):
        plan = uae_plan.build_plan(300000, "awareness", "core", "beauty", "uae_wide", 0.10)
        roles = {row["role"] for row in plan["channels"]}
        self.assertIn("trust", roles)

    def test_conversion_objective_keeps_conversion_channel(self):
        for budget in (30000, 150000, 600000):
            plan = uae_plan.build_plan(budget, "conversion", "mixed", "ecommerce", "uae_wide", 0.10)
            roles = {row["role"] for row in plan["channels"]}
            with self.subTest(budget=budget):
                self.assertIn("conversion", roles)

    def test_awareness_objective_keeps_discovery_channel(self):
        plan = uae_plan.build_plan(300000, "awareness", "mixed", "travel", "uae_wide", 0.10)
        roles = {row["role"] for row in plan["channels"]}
        self.assertIn("discovery", roles)

    def test_no_channel_below_its_minimum_budget(self):
        plan = uae_plan.build_plan(250000, "consideration", "mixed", "fintech", "abu_dhabi", 0.10)
        for row in plan["channels"]:
            channel = next(c for c in uae_plan.load_channels() if c["id"] == row["id"])
            with self.subTest(channel=row["id"]):
                self.assertGreaterEqual(row["spend"], channel["min_budget"])

    def test_avoided_channels_are_never_selected(self):
        """Beauty avoids OOH in the sector notes; it must not appear."""
        plan = uae_plan.build_plan(2000000, "awareness", "core", "beauty", "dubai", 0.10)
        ids = {row["id"] for row in plan["channels"]}
        self.assertNotIn("ooh", ids)


class TestEstimation(unittest.TestCase):
    def test_impression_band_is_ordered(self):
        channels = uae_plan.load_channels()
        for channel in channels:
            est = uae_plan.estimate(channel, 100000)
            if est["impressions"]:
                with self.subTest(channel=channel["id"]):
                    self.assertLessEqual(est["impressions"][0], est["impressions"][1])
                    self.assertLessEqual(est["reach"][0], est["impressions"][0])

    def test_assumptions_are_always_attached(self):
        plan = uae_plan.build_plan(120000, "retention", "core", "fnb", "sharjah", 0.10)
        self.assertGreaterEqual(len(plan["assumptions"]), 4)

    def test_markdown_output_carries_the_disclaimer(self):
        plan = uae_plan.build_plan(120000, "retention", "core", "fnb", "sharjah", 0.10)
        md = uae_plan.to_markdown(plan)
        self.assertIn("建模假设", md)
        self.assertIn("平台实时报价", md)


class TestCli(unittest.TestCase):
    def test_bad_budget_rejected(self):
        self.assertEqual(uae_plan.main(["--budget", "0", "--objective", "awareness",
                                        "--audience", "core", "--sector", "beauty"]), 2)

    def test_bad_reserve_rejected(self):
        self.assertEqual(uae_plan.main(["--budget", "100000", "--objective", "awareness",
                                        "--audience", "core", "--sector", "beauty",
                                        "--reserve", "1.5"]), 2)

    def test_valid_run_returns_zero(self):
        self.assertEqual(uae_plan.main(["--budget", "150000", "--objective", "consideration",
                                        "--audience", "mixed", "--sector", "education",
                                        "--format", "json"]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
