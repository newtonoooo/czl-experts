#!/usr/bin/env python3
"""Tests for the campaign calendar builder (bin/uae_campaign_calendar.py)."""

import datetime as dt
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

import uae_campaign_calendar as cal  # noqa: E402


class TestAnchors(unittest.TestCase):
    def test_known_year_matches_table(self):
        anchors = cal.estimate_for(2027)
        self.assertEqual(anchors["ramadan_start"], dt.date(2027, 2, 8))
        self.assertEqual(anchors["eid_fitr"], dt.date(2027, 3, 10))

    def test_unknown_year_drifts_backwards(self):
        """Beyond the table, dates shift earlier by roughly 11 days per year."""
        anchors = cal.estimate_for(2033)
        self.assertLess(anchors["ramadan_start"], dt.date(2030, 1, 6))
        self.assertGreater(anchors["ramadan_start"], dt.date(2024, 1, 1))

    def test_ramadan_window_is_about_thirty_days(self):
        data = cal.build(2027, None)
        start = dt.date.fromisoformat(data["ramadan_start"])
        end = dt.date.fromisoformat(data["ramadan_end"])
        self.assertGreaterEqual((end - start).days, 28)
        self.assertLessEqual((end - start).days, 30)


class TestOverride(unittest.TestCase):
    def test_override_shifts_every_hijri_node(self):
        base = cal.build(2027, None)
        shifted = cal.build(2027, dt.date(2027, 2, 12))
        delta = dt.date.fromisoformat(shifted["ramadan_start"]) - dt.date.fromisoformat(base["ramadan_start"])
        self.assertEqual(delta.days, 4)

        base_eid = next(w for w in base["windows"] if w["name"].startswith("开斋节"))
        new_eid = next(w for w in shifted["windows"] if w["name"].startswith("开斋节"))
        self.assertEqual(
            (dt.date.fromisoformat(new_eid["start"]) - dt.date.fromisoformat(base_eid["start"])).days, 4)

    def test_gregorian_nodes_do_not_shift(self):
        base = cal.build(2027, None)
        shifted = cal.build(2027, dt.date(2027, 2, 12))
        for name in ("阿联酋国庆日", "新年"):
            b = next(w for w in base["windows"] if w["name"] == name)
            s = next(w for w in shifted["windows"] if w["name"] == name)
            self.assertEqual(b["start"], s["start"])


class TestWindows(unittest.TestCase):
    def test_windows_sorted_by_start(self):
        data = cal.build(2028, None)
        starts = [w["start"] for w in data["windows"]]
        self.assertEqual(starts, sorted(starts))

    def test_ramadan_prep_precedes_ramadan(self):
        data = cal.build(2026, None)
        prep = next(w for w in data["windows"] if w["name"] == "斋月前备货窗口")
        ramadan = next(w for w in data["windows"] if w["name"].startswith("斋月期"))
        self.assertLess(prep["start"], ramadan["start"])

    def test_caveats_always_present(self):
        data = cal.build(2029, None)
        self.assertGreaterEqual(len(data["caveats"]), 3)
        self.assertTrue(any("官方观月" in c for c in data["caveats"]))

    def test_milestones_anchor_on_a_high_priority_window(self):
        data = cal.build(2027, None)
        anchor = data["milestones"][0]["anchor"]
        target = next(w for w in data["windows"] if w["name"] == anchor)
        self.assertTrue(target["budget_tilt"].startswith("高"))


class TestWorkdayShift(unittest.TestCase):
    def test_saturday_moves_back_to_thursday(self):
        self.assertEqual(cal.shift_to_workday(dt.date(2027, 1, 2)).weekday(), 3)

    def test_sunday_moves_back_to_thursday(self):
        self.assertEqual(cal.shift_to_workday(dt.date(2027, 1, 3)).weekday(), 3)

    def test_friday_is_not_a_safe_deadline(self):
        """Friday is a half day for government, so deadlines move to Thursday."""
        self.assertEqual(cal.shift_to_workday(dt.date(2027, 1, 1)).weekday(), 3)

    def test_weekday_unchanged(self):
        self.assertEqual(cal.shift_to_workday(dt.date(2027, 1, 5)), dt.date(2027, 1, 5))

    def test_shift_never_moves_later(self):
        for offset in range(14):
            day = dt.date(2027, 1, 1) + dt.timedelta(days=offset)
            self.assertLessEqual(cal.shift_to_workday(day), day)


class TestOutputs(unittest.TestCase):
    def test_ics_structure(self):
        payload = cal.to_ics(cal.build(2027, None))
        self.assertTrue(payload.startswith("BEGIN:VCALENDAR"))
        self.assertTrue(payload.rstrip().endswith("END:VCALENDAR"))
        self.assertEqual(payload.count("BEGIN:VEVENT"), payload.count("END:VEVENT"))
        self.assertGreater(payload.count("BEGIN:VEVENT"), 5)

    def test_markdown_contains_caveat(self):
        md = cal.to_markdown(cal.build(2027, None))
        self.assertIn("以官方观月为准", md)

    def test_cli_rejects_out_of_range_year(self):
        self.assertEqual(cal.main(["--year", "1999"]), 2)

    def test_cli_accepts_valid_year(self):
        self.assertEqual(cal.main(["--year", "2027", "--format", "json"]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
