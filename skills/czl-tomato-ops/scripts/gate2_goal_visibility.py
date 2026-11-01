#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2026 虫志龙. All rights reserved.
"""第一章目标可见性检查：三问缺一即不可见。

用法：
    python gate2_goal_visibility.py --want "拿回父亲留下的铺子" --obstacle "二叔" --cost "母亲的病治不了"
"""
import argparse
import sys

ABSTRACT = ["变强", "成长", "活下去", "活下去", "称霸", "逆袭", "复仇", "变厉害", "变富"]


def check(text, label, hint):
    t = (text or "").strip()
    if not t:
        return False, "%s：未填写" % label
    if len(t) <= 3 and any(w in t for w in ABSTRACT):
        return False, "%s：「%s」过于抽象，要具体到可验证（%s）" % (label, t, hint)
    if any(t == w for w in ABSTRACT):
        return False, "%s：「%s」过于抽象，要具体到可验证（%s）" % (label, t, hint)
    return True, "%s：%s" % (label, t)


def main():
    p = argparse.ArgumentParser(description="第一章目标可见性检查")
    p.add_argument("--want", required=True, help="主角想要什么（具体、可验证）")
    p.add_argument("--obstacle", required=True, help="谁挡着他")
    p.add_argument("--cost", required=True, help="失败会失去什么")
    a = p.parse_args()

    ok1, m1 = check(a.want, "想要", "如「拿回被夺走的铺子」")
    ok2, m2 = check(a.obstacle, "阻碍", "写具体的对手，不写「命运」")
    ok3, m3 = check(a.cost, "代价", "写不可逆的损失，不写「很惨」")

    passed = sum([ok1, ok2, ok3])
    print("第一章目标可见性检查")
    print("-" * 34)
    for ok, msg in ((ok1, m1), (ok2, m2), (ok3, m3)):
        print(("[通过] " if ok else "[不过] ") + msg)
    print("-" * 34)
    print("得分        %d/3" % passed)
    if passed == 3:
        print("判定        清晰")
        print("建议        目标要在第一章内以台词或动作落地，不能只在设定里")
    elif passed == 2:
        print("判定        模糊")
        print("建议        补齐缺的那一项，三问缺一读者就抓不住主线")
    else:
        print("判定        不可见")
        print("建议        回 G1 检查选题核心冲突是否成立")
    return 0 if passed == 3 else 1


if __name__ == "__main__":
    sys.exit(main())
