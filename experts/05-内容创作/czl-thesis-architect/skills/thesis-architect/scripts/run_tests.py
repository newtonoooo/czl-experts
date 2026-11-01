#!/usr/bin/env python3
"""测试入口：跑 tests/ 下全部用例。

用法：
    python scripts/run_tests.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TESTS_DIR = HERE.parent / "tests"

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(TESTS_DIR))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print(f"技能目录：{HERE.parent}")
    suite = unittest.TestLoader().discover(str(TESTS_DIR), pattern="test_*.py", top_level_dir=str(TESTS_DIR))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("")
    print(f"用例：{result.testsRun} 个｜失败 {len(result.failures)}｜错误 {len(result.errors)}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
