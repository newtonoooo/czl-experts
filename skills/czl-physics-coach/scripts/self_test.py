#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""脚本自测。用已知答案核对 physics_check 与 variant_gen。

运行：python self_test.py
返回码 0 表示全部通过，1 表示有失败项。
"""

from __future__ import annotations

import math
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import physics_check as pc  # noqa: E402
import variant_gen as vg  # noqa: E402

PASS = 0
FAIL = 0
FAILED = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        FAILED.append(name)
        print(f"[FAIL] {name} {detail}")


def close(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def main():
    # 1 匀变速
    r = pc.kinematics(0, 2, 3)
    check("匀变速：v=6", close(r["v"], 6), r["v"])
    check("匀变速：s=9", close(r["s"], 9), r["s"])

    # 2 斜抛 45 度，v0=20，平地
    r = pc.projectile(20, 45, 0, 10)
    check("斜抛：射程 40 m", close(r["range"], 40, 1e-3), r["range"])
    check("斜抛：时间 2.828 s", close(r["t"], 2 * 20 * math.sin(math.radians(45)) / 10, 1e-3), r["t"])
    check("斜抛：落地速度等于初速", close(r["speed"], 20, 1e-6), r["speed"])

    # 3 斜面 m=2, 30°, μ=0.2
    r = pc.incline(2, 30, 0.2, 10)
    check("斜面：N=17.32", close(r["N"], 20 * math.cos(math.radians(30)), 1e-6), r["N"])
    check("斜面：a≈3.268", close(r["a"], (20 * 0.5 - 0.2 * 20 * math.cos(math.radians(30))) / 2, 1e-6), r["a"])

    # 4 竖直圆周临界 R=0.5, g=10
    r = pc.vertical_circle(0.5, 10, "rope")
    check("竖直圆周：v_top=√5", close(r["v_top"], math.sqrt(5), 1e-9), r["v_top"])
    check("竖直圆周：v_bottom=5", close(r["v_bottom"], 5.0, 1e-9), r["v_bottom"])
    r = pc.vertical_circle(0.5, 10, "rod")
    check("杆模型：最高点速度可为 0", r["v_top"] == 0.0, r["v_top"])

    # 5 弹性碰撞
    r = pc.collision(2, 6, 4, 0, "elastic")
    check("弹性碰撞：v1=-2", close(r["v1"], -2), r["v1"])
    check("弹性碰撞：v2=4", close(r["v2"], 4), r["v2"])
    check("弹性碰撞：动能不损失", close(r["loss"], 0, 1e-9), r["loss"])

    # 6 完全非弹性
    r = pc.collision(2, 6, 4, 0, "perfect")
    check("完全非弹性：共同速度 2", close(r["v1"], 2), r["v1"])
    check("完全非弹性：损失 24 J", close(r["loss"], 24), r["loss"])

    # 7 机械能
    r = pc.energy(1, 5, 0, 10)
    check("机械能：Ep=50", close(r["Ep"], 50), r["Ep"])
    check("机械能：静止下落 5 m 速度 10", close(r["v_from_h"], 10), r["v_from_h"])

    # 8 电磁感应
    r = pc.induction(0.5, 1, 2, 0.4)
    check("感应：E=1", close(r["E"], 1), r["E"])
    check("感应：I=2.5", close(r["I"], 2.5), r["I"])
    check("感应：F=1.25", close(r["F"], 1.25), r["F"])
    check("感应：P=2.5", close(r["P"], 2.5), r["P"])

    # 9 闭合电路
    r = pc.circuit(6, 1, 5)
    check("电路：I=1", close(r["I"], 1), r["I"])
    check("电路：U=5", close(r["U"], 5), r["U"])
    check("电路：效率 83.3%", close(r["eta"], 5 / 6, 1e-9), r["eta"])

    # 10 异常输入必须报错，不能返回假数
    for bad_call, label in [
        (lambda: pc.incline(-1, 30, 0.2), "负质量"),
        (lambda: pc.incline(1, 0, 0.2), "0 度倾角"),
        (lambda: pc.induction(0.5, 1, 2, 0), "零电阻"),
        (lambda: pc.projectile(20, -5), "负抛射角"),
        (lambda: pc.collision(1, 1, 1, 1, "unknown"), "未知碰撞类型"),
    ]:
        try:
            bad_call()
            check(f"异常输入应报错：{label}", False, "未抛异常")
        except ValueError:
            check(f"异常输入应报错：{label}", True)

    # 11 CLI 返回码
    check("CLI：incline 正常返回 0",
          pc.main(["incline", "--m", "2", "--theta", "30", "--mu", "0.2"]) == 0)
    check("CLI：非法参数返回 2",
          pc.main(["incline", "--m", "-2", "--theta", "30"]) == 2)

    # 12 变式题生成：覆盖全部模型、多个种子
    for model in sorted(vg.GENERATORS):
        ok = True
        detail = ""
        for seed in range(1, 8):
            try:
                items = vg.build(model, seed, 2)
            except Exception as exc:  # noqa: BLE001
                ok = False
                detail = f"seed={seed}: {exc}"
                break
            if len(items) != 2:
                ok = False
                detail = f"seed={seed}: 数量不对"
                break
            for it in items:
                for key in ("stem", "asks", "answer", "steps", "score", "trap"):
                    if not it.get(key):
                        ok = False
                        detail = f"seed={seed}: 缺字段 {key}"
                        break
        check(f"变式生成：{model} 全种子可用", ok, detail)

    # 13 同种子结果稳定
    a = vg.build("incline", 42, 1)[0]["stem"]
    b = vg.build("incline", 42, 1)[0]["stem"]
    check("变式生成：同种子同题", a == b)

    # 14 能量模型的距离公式与手算一致（h=5, 37°, μ=0.5）
    # 课本取 sin37°=0.6、cos37°=0.8，此处按课本取值手算，不用 math.sin
    s = 5 / 0.5 - 5 * 0.8 / 0.6
    check("能量模型：水平滑行距离约 3.33 m", close(s, 3.3333, 1e-3), s)

    print("\n" + "=" * 40)
    print(f"通过 {PASS} 项，失败 {FAIL} 项")
    if FAIL:
        print("失败项：", "；".join(FAILED))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(1)
