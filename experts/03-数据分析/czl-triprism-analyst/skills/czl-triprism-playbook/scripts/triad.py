# -*- coding: utf-8 -*-
"""三棱镜 · 工具链启动器

技能包里只放这一个入口，真正的实现在包根的 tools/ 下。
这样无论从哪个工作目录调用，都能找到工具。

用法：
  python scripts/triad.py run --path data.xlsx --outdir out
  python scripts/triad.py profile --path data.csv --brief
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# scripts/ -> czl-triprism-playbook/ -> skills/ -> 包根
PACKAGE_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
TOOLS = os.path.join(PACKAGE_ROOT, "tools")


def main():
    if not os.path.isdir(TOOLS):
        print(f"找不到工具目录：{TOOLS}", file=sys.stderr)
        print("请确认本技能包位于专家包内（与 tools/ 同级），或用绝对路径直接调用 tools/triad_cli.py",
              file=sys.stderr)
        return 2
    sys.path.insert(0, TOOLS)
    import triad_cli
    return triad_cli.main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
