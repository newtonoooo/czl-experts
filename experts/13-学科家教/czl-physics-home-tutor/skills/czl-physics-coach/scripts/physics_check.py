#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""高中物理数值复核器。

用途：给家庭辅导场景做"算一遍 + 提醒常见错法"。只覆盖高中范围内的基础模型，
不追求通用符号运算；参数不合理时直接报错，不返回似是而非的数。

用法示例：
    python physics_check.py incline --m 2 --theta 30 --mu 0.2
    python physics_check.py projectile --v0 20 --angle 45
    python physics_check.py collision --m1 2 --u1 6 --m2 4 --u2 0 --kind elastic
    python physics_check.py induction --B 0.5 --L 1 --v 2 --R 0.4

本文件为独立实现，仅使用 Python 标准库。
"""

from __future__ import annotations

import argparse
import math
import sys

G_DEFAULT = 10.0


# ---------------------------------------------------------------- 计算函数

def kinematics(u0: float, a: float, t: float):
    """匀变速直线运动。返回末速度与位移。"""
    if t < 0:
        raise ValueError("时间不能为负")
    v = u0 + a * t
    s = u0 * t + 0.5 * a * t * t
    return {"v": v, "s": s}


def projectile(v0: float, angle_deg: float, h0: float = 0.0, g: float = G_DEFAULT):
    """平抛/斜抛（从高度 h0 抛出）。返回飞行时间、水平射程、落地速度分量。"""
    if v0 <= 0:
        raise ValueError("初速度必须大于 0")
    if not 0 <= angle_deg <= 90:
        raise ValueError("抛射角需在 0 到 90 度之间")
    th = math.radians(angle_deg)
    vx = v0 * math.cos(th)
    vy0 = v0 * math.sin(th)
    disc = vy0 * vy0 + 2 * g * h0
    if disc < 0:
        raise ValueError("参数不合理：落地判别式为负")
    t = (vy0 + math.sqrt(disc)) / g
    rng = vx * t
    vy = vy0 - g * t
    return {
        "t": t,
        "range": rng,
        "vx": vx,
        "vy": vy,
        "speed": math.hypot(vx, vy),
        "hmax": h0 + (vy0 * vy0) / (2 * g) if vy0 > 0 else h0,
    }


def incline(m: float, theta_deg: float, mu: float, g: float = G_DEFAULT,
            extra_force: float = 0.0):
    """斜面下滑（有摩擦，可加沿面向下的外力）。返回支持力、摩擦力、加速度。"""
    if m <= 0:
        raise ValueError("质量必须大于 0")
    if not 0 < theta_deg < 90:
        raise ValueError("倾角需在 0 到 90 度之间（不含端点）")
    if mu < 0:
        raise ValueError("动摩擦因数不能为负")
    th = math.radians(theta_deg)
    n = m * g * math.cos(th)
    f = mu * n
    drive = m * g * math.sin(th) + extra_force
    a = (drive - f) / m
    return {"N": n, "f": f, "a": a, "drive": m * g * math.sin(th)}


def circular(r: float, v: float | None = None, period: float | None = None,
             m: float | None = None):
    """圆周运动。给 v 或周期 T。返回向心加速度，若给质量再返回向心力。"""
    if r <= 0:
        raise ValueError("半径必须大于 0")
    if v is not None:
        a = v * v / r
    elif period is not None:
        if period <= 0:
            raise ValueError("周期必须大于 0")
        a = 4 * math.pi ** 2 * r / (period ** 2)
        v = 2 * math.pi * r / period
    else:
        raise ValueError("需要给出线速度 v 或周期 T")
    out = {"a": a, "v": v}
    if m is not None:
        if m <= 0:
            raise ValueError("质量必须大于 0")
        out["F"] = m * a
    return out


def vertical_circle(r: float, g: float = G_DEFAULT, model: str = "rope"):
    """竖直圆周临界。rope=绳/内轨，rod=杆/双轨。返回最高点与最低点临界速度。"""
    if r <= 0:
        raise ValueError("半径必须大于 0")
    if model == "rope":
        v_top = math.sqrt(g * r)
    elif model == "rod":
        v_top = 0.0
    else:
        raise ValueError("model 只能是 rope 或 rod")
    v_bottom = math.sqrt(v_top * v_top + 4 * g * r)
    return {"v_top": v_top, "v_bottom": v_bottom}


def collision(m1: float, u1: float, m2: float, u2: float, kind: str = "elastic"):
    """一维碰撞。kind: elastic / perfect / general(e)。返回碰后速度与动能损失。"""
    if m1 <= 0 or m2 <= 0:
        raise ValueError("质量必须大于 0")
    e_before = 0.5 * m1 * u1 ** 2 + 0.5 * m2 * u2 ** 2
    p_before = m1 * u1 + m2 * u2

    if kind == "elastic":
        v1 = ((m1 - m2) * u1 + 2 * m2 * u2) / (m1 + m2)
        v2 = ((m2 - m1) * u2 + 2 * m1 * u1) / (m1 + m2)
    elif kind == "perfect":
        v = p_before / (m1 + m2)
        v1 = v2 = v
    else:
        raise ValueError("kind 只能是 elastic 或 perfect")

    e_after = 0.5 * m1 * v1 ** 2 + 0.5 * m2 * v2 ** 2
    # 合理性检查：碰后动量必须守恒，动能不得增加
    p_after = m1 * v1 + m2 * v2
    if abs(p_after - p_before) > 1e-9:
        raise ArithmeticError("内部校验失败：动量不守恒")
    if e_after - e_before > 1e-9:
        raise ArithmeticError("内部校验失败：动能增加，参数或模型有误")
    return {"v1": v1, "v2": v2, "loss": e_before - e_after,
            "p_before": p_before, "e_before": e_before, "e_after": e_after}


def energy(m: float, h: float, v: float = 0.0, g: float = G_DEFAULT):
    """机械能。返回重力势能、动能、总机械能、若从静止下落的高度对应速度。"""
    if m <= 0:
        raise ValueError("质量必须大于 0")
    ep = m * g * h
    ek = 0.5 * m * v * v
    return {"Ep": ep, "Ek": ek, "E": ep + ek, "v_from_h": math.sqrt(2 * g * h)}


def induction(B: float, L: float, v: float, R: float):
    """单杆切割磁感线（匀速）。返回电动势、电流、安培力、电功率。"""
    if R <= 0:
        raise ValueError("总电阻必须大于 0")
    if B < 0 or L <= 0:
        raise ValueError("B 不能为负，L 必须大于 0")
    emf = B * L * v
    i = emf / R
    f = B * i * L
    p = emf * i
    return {"E": emf, "I": i, "F": f, "P": p}


def circuit(emf: float, r: float, R: float):
    """闭合电路。返回电流、路端电压、外电阻功率、总功率、效率。"""
    if R <= 0 or r < 0:
        raise ValueError("外电阻需大于 0，内阻不能为负")
    i = emf / (R + r)
    u = emf - i * r
    p_out = i * i * R
    p_all = emf * i
    return {"I": i, "U": u, "P_out": p_out, "P_all": p_all,
            "eta": p_out / p_all if p_all else 0.0}


# ---------------------------------------------------------------- 输出

def _line(label: str, text: str) -> None:
    print(f"【{label}】{text}")


def _num(x: float, nd: int = 3) -> str:
    return f"{x:.{nd}g}"


def report(title: str, formula: str, subst: str, results: list[tuple[str, str]],
           reminds: list[str]) -> None:
    print(f"\n== {title} ==")
    _line("公式", formula)
    _line("代入", subst)
    for name, val in results:
        print(f"【结果】{name} = {val}")
    for r in reminds:
        _line("提醒", r)
    print()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="高中物理数值复核器（只覆盖高中基础模型）")
    parser.add_argument("--g", type=float, default=G_DEFAULT, help="重力加速度，默认 10")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("kinematics", help="匀变速直线运动")
    p.add_argument("--u0", type=float, required=True, help="初速度 m/s")
    p.add_argument("--a", type=float, required=True, help="加速度 m/s^2")
    p.add_argument("--t", type=float, required=True, help="时间 s")

    p = sub.add_parser("projectile", help="平抛/斜抛")
    p.add_argument("--v0", type=float, required=True)
    p.add_argument("--angle", type=float, default=0.0, help="抛射角（度），平抛填 0")
    p.add_argument("--h0", type=float, default=0.0, help="抛出点高度 m")

    p = sub.add_parser("incline", help="斜面下滑")
    p.add_argument("--m", type=float, required=True)
    p.add_argument("--theta", type=float, required=True, help="倾角（度）")
    p.add_argument("--mu", type=float, default=0.0, help="动摩擦因数")
    p.add_argument("--extra-force", type=float, default=0.0, help="沿面向下的外力 N")

    p = sub.add_parser("circular", help="圆周运动")
    p.add_argument("--r", type=float, required=True)
    p.add_argument("--v", type=float, default=None)
    p.add_argument("--period", type=float, default=None)
    p.add_argument("--m", type=float, default=None)

    p = sub.add_parser("vertical-circle", help="竖直圆周临界速度")
    p.add_argument("--r", type=float, required=True)
    p.add_argument("--model", choices=["rope", "rod"], default="rope")

    p = sub.add_parser("collision", help="一维碰撞")
    p.add_argument("--m1", type=float, required=True)
    p.add_argument("--u1", type=float, required=True)
    p.add_argument("--m2", type=float, required=True)
    p.add_argument("--u2", type=float, default=0.0)
    p.add_argument("--kind", choices=["elastic", "perfect"], default="elastic")

    p = sub.add_parser("energy", help="机械能")
    p.add_argument("--m", type=float, required=True)
    p.add_argument("--h", type=float, required=True)
    p.add_argument("--v", type=float, default=0.0)

    p = sub.add_parser("induction", help="单杆切割磁感线")
    p.add_argument("--B", type=float, required=True)
    p.add_argument("--L", type=float, required=True)
    p.add_argument("--v", type=float, required=True)
    p.add_argument("--R", type=float, required=True)

    p = sub.add_parser("circuit", help="闭合电路")
    p.add_argument("--emf", type=float, required=True)
    p.add_argument("--r", type=float, required=True)
    p.add_argument("--R", type=float, required=True)

    args = parser.parse_args(argv)
    g = args.g

    try:
        if args.cmd == "kinematics":
            r = kinematics(args.u0, args.a, args.t)
            report(
                "匀变速直线运动",
                "v = v0 + at,  x = v0 t + 1/2 a t^2",
                f"v = {_num(args.u0)} + {_num(args.a)}x{_num(args.t)}; "
                f"x = {_num(args.u0)}x{_num(args.t)} + 1/2x{_num(args.a)}x{_num(args.t)}^2",
                [("末速度 v", f"{_num(r['v'])} m/s"), ("位移 x", f"{_num(r['s'])} m")],
                ["若加速度与初速度反向，位移可能为正而速度已反向；"
                 "先检查 t 是否超过速度减为零的时刻。"])

        elif args.cmd == "projectile":
            r = projectile(args.v0, args.angle, args.h0, g)
            report(
                "平抛/斜抛",
                "x = v0 cosθ t,  y = h0 + v0 sinθ t - 1/2 g t^2",
                f"v0={_num(args.v0)} m/s, θ={_num(args.angle)}°, h0={_num(args.h0)} m, g={_num(g)}",
                [("飞行时间 t", f"{_num(r['t'])} s"),
                 ("水平射程", f"{_num(r['range'])} m"),
                 ("落地速度", f"{_num(r['speed'])} m/s"),
                 ("最大高度", f"{_num(r['hmax'])} m")],
                ["时间由竖直方向决定，与水平速度无关；"
                 "平抛时不要把 45° 当成速度方向。"])

        elif args.cmd == "incline":
            r = incline(args.m, args.theta, args.mu, g, args.extra_force)
            a = r["a"]
            reminds = ["正压力 N = mg cosθ，仅当垂直斜面方向无其他力时成立。"]
            if a < 0:
                reminds.append("加速度为负：摩擦力大于下滑分力，物块不会自行下滑（可能静止）。")
            report(
                "斜面下滑",
                "N = mg cosθ,  f = μN,  ma = mg sinθ - f (+F)",
                f"m={_num(args.m)} kg, θ={_num(args.theta)}°, μ={_num(args.mu)}",
                [("支持力 N", f"{_num(r['N'])} N"),
                 ("摩擦力 f", f"{_num(r['f'])} N"),
                 ("下滑分力", f"{_num(r['drive'])} N"),
                 ("加速度 a", f"{_num(a)} m/s^2")],
                reminds)

        elif args.cmd == "circular":
            r = circular(args.r, args.v, args.period, args.m)
            res = [("线速度 v", f"{_num(r['v'])} m/s"),
                   ("向心加速度 a", f"{_num(r['a'])} m/s^2")]
            if "F" in r:
                res.append(("向心力 F", f"{_num(r['F'])} N"))
            report("圆周运动", "a = v^2/r = 4π^2 r/T^2,  F = ma",
                   f"r={_num(args.r)} m",
                   res,
                   ["向心力是效果力，由实际的力提供，受力图上不要再画一个'向心力'。"])

        elif args.cmd == "vertical-circle":
            r = vertical_circle(args.r, g, args.model)
            report("竖直圆周临界",
                   "绳模型：mg = mv^2/r；杆模型：v_top ≥ 0",
                   f"r={_num(args.r)} m, 模型={args.model}",
                   [("最高点临界速度", f"{_num(r['v_top'])} m/s"),
                    ("最低点临界速度", f"{_num(r['v_bottom'])} m/s")],
                   ["杆模型最高点速度可以为零，不要套 sqrt(gR)；"
                    "最低点到最高点若无摩擦，用机械能守恒求速度。"])

        elif args.cmd == "collision":
            r = collision(args.m1, args.u1, args.m2, args.u2, args.kind)
            report("一维碰撞",
                   "m1u1 + m2u2 = m1v1 + m2v2（弹性碰撞另加动能守恒）",
                   f"m1={_num(args.m1)}, u1={_num(args.u1)}, "
                   f"m2={_num(args.m2)}, u2={_num(args.u2)}, 类型={args.kind}",
                   [("碰后 v1", f"{_num(r['v1'])} m/s"),
                    ("碰后 v2", f"{_num(r['v2'])} m/s"),
                    ("动能损失", f"{_num(r['loss'])} J")],
                   ["负号表示方向与正方向相反；"
                    "碰后要检查是否出现'后面追上前面'的不合理情形。"])

        elif args.cmd == "energy":
            r = energy(args.m, args.h, args.v, g)
            report("机械能",
                   "Ep = mgh,  Ek = 1/2 mv^2",
                   f"m={_num(args.m)} kg, h={_num(args.h)} m, v={_num(args.v)} m/s",
                   [("重力势能 Ep", f"{_num(r['Ep'])} J"),
                    ("动能 Ek", f"{_num(r['Ek'])} J"),
                    ("总机械能 E", f"{_num(r['E'])} J"),
                    ("静止下落该高度的速度", f"{_num(r['v_from_h'])} m/s")],
                   ["有摩擦时机械能不守恒，先算热 Q = f·s相对。"])

        elif args.cmd == "induction":
            r = induction(args.B, args.L, args.v, args.R)
            report("单杆切割磁感线",
                   "E = BLv,  I = E/R,  F = BIL,  P = EI",
                   f"B={_num(args.B)} T, L={_num(args.L)} m, v={_num(args.v)} m/s, R={_num(args.R)} Ω",
                   [("电动势 E", f"{_num(r['E'])} V"),
                    ("电流 I", f"{_num(r['I'])} A"),
                    ("安培力 F", f"{_num(r['F'])} N"),
                    ("电功率 P", f"{_num(r['P'])} W")],
                   ["R 要用回路总电阻，不能只算外电阻；"
                    "稳定时加速度为零，不是速度为零。"])

        elif args.cmd == "circuit":
            r = circuit(args.emf, args.r, args.R)
            report("闭合电路",
                   "I = E/(R+r),  U = E - Ir",
                   f"E={_num(args.emf)} V, r={_num(args.r)} Ω, R={_num(args.R)} Ω",
                   [("电流 I", f"{_num(r['I'])} A"),
                    ("路端电压 U", f"{_num(r['U'])} V"),
                    ("外电阻功率", f"{_num(r['P_out'])} W"),
                    ("总功率", f"{_num(r['P_all'])} W"),
                    ("效率", f"{r['eta'] * 100:.1f}%")],
                   ["外电阻增大时路端电压升高；短路时 U=0，I 最大。"])

    except (ValueError, ArithmeticError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
