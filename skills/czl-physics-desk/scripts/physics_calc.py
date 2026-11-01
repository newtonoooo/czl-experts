#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""常用物理公式计算器（零依赖）。

用途：出题、批改、写教案时快速复核数值，避免手算错。

用法：
  python physics_calc.py --list
  python physics_calc.py --formula kinematics.v2 --args v0=0,a=2,t=3
  python physics_calc.py --formula pendulum.T --args l=1.0 --sigfig 3
  python physics_calc.py --self-check

约定：角度参数一律用"度"；不写单位时按国际单位制。
"""

import argparse
import json
import math
import sys

G = 6.674e-11
K_E = 9.0e9
H_PLANCK = 6.63e-34
C_LIGHT = 3.0e8

D2R = math.pi / 180.0


def _cos(deg):
    return math.cos(deg * D2R)


def _sin(deg):
    return math.sin(deg * D2R)


def _deg(rad):
    return rad / D2R


# name: (params, func, unit, note)
REGISTRY = {
    # 运动学
    "kinematics.v": (["v0", "a", "t"], lambda p: p["v0"] + p["a"] * p["t"], "m/s", "v=v0+at，匀变速"),
    "kinematics.x": (["v0", "a", "t"], lambda p: p["v0"] * p["t"] + 0.5 * p["a"] * p["t"] ** 2, "m", "x=v0t+at²/2，匀变速"),
    "kinematics.v2": (["v0", "a", "x"], lambda p: math.sqrt(max(p["v0"] ** 2 + 2 * p["a"] * p["x"], 0.0)), "m/s", "v²=v0²+2ax"),
    "kinematics.avg": (["v0", "v"], lambda p: (p["v0"] + p["v"]) / 2, "m/s", "匀变速平均速度"),
    "freefall.h": (["t"], lambda p: 0.5 * 9.8 * p["t"] ** 2, "m", "自由落体下落高度（g=9.8）"),
    "freefall.v": (["t"], lambda p: 9.8 * p["t"], "m/s", "自由落体速度（g=9.8）"),
    # 力与运动
    "newton.a": (["F", "m"], lambda p: p["F"] / p["m"], "m/s²", "a=F合/m"),
    "newton.F": (["m", "a"], lambda p: p["m"] * p["a"], "N", "F=ma"),
    "friction.f": (["mu", "N"], lambda p: p["mu"] * p["N"], "N", "滑动摩擦 f=μN（N 为正压力）"),
    "circular.a": (["v", "r"], lambda p: p["v"] ** 2 / p["r"], "m/s²", "a=v²/r"),
    "circular.F": (["m", "v", "r"], lambda p: p["m"] * p["v"] ** 2 / p["r"], "N", "F向=mv²/r"),
    "circular.T": (["r", "v"], lambda p: 2 * math.pi * p["r"] / p["v"], "s", "T=2πr/v"),
    "circular.critical": (["g", "r"], lambda p: math.sqrt(p["g"] * p["r"]), "m/s", "绳模型最高点最小速度 √(gr)"),
    # 万有引力
    "grav.F": (["m1", "m2", "r"], lambda p: G * p["m1"] * p["m2"] / p["r"] ** 2, "N", "F=GMm/r²"),
    "grav.v": (["M", "r"], lambda p: math.sqrt(G * p["M"] / p["r"]), "m/s", "圆轨道 v=√(GM/r)"),
    "grav.T": (["M", "r"], lambda p: 2 * math.pi * math.sqrt(p["r"] ** 3 / (G * p["M"])), "s", "T=2π√(r³/GM)"),
    "grav.g": (["M", "R"], lambda p: G * p["M"] / p["R"] ** 2, "m/s²", "表面重力加速度 g=GM/R²"),
    # 功与能
    "work.W": (["F", "l", "theta"], lambda p: p["F"] * p["l"] * _cos(p.get("theta", 0)), "J", "W=Flcosθ，theta 为力与位移夹角（度）"),
    "power.P": (["F", "v", "theta"], lambda p: p["F"] * p["v"] * _cos(p.get("theta", 0)), "W", "P=Fvcosθ"),
    "energy.ke": (["m", "v"], lambda p: 0.5 * p["m"] * p["v"] ** 2, "J", "Ek=½mv²"),
    "energy.pe": (["m", "h", "g"], lambda p: p["m"] * p.get("g", 9.8) * p["h"], "J", "Ep=mgh（g 默认 9.8）"),
    "momentum.p": (["m", "v"], lambda p: p["m"] * p["v"], "kg·m/s", "p=mv"),
    "impulse.F": (["m", "dv", "dt"], lambda p: p["m"] * p["dv"] / p["dt"], "N", "F=Δp/Δt=ma"),
    "collision.v": (["m1", "v1", "m2", "v2"], lambda p: (p["m1"] * p["v1"] + p["m2"] * p["v2"]) / (p["m1"] + p["m2"]), "m/s", "完全非弹性碰撞共同速度"),
    # 振动与波
    "pendulum.T": (["l", "g"], lambda p: 2 * math.pi * math.sqrt(p["l"] / p.get("g", 9.8)), "s", "单摆 T=2π√(l/g)，摆角<5°"),
    "spring.T": (["m", "k"], lambda p: 2 * math.pi * math.sqrt(p["m"] / p["k"]), "s", "弹簧振子 T=2π√(m/k)"),
    "wave.v": (["lam", "f"], lambda p: p["lam"] * p["f"], "m/s", "v=λf"),
    # 电场
    "coulomb.F": (["q1", "q2", "r"], lambda p: K_E * p["q1"] * p["q2"] / p["r"] ** 2, "N", "F=kq1q2/r²，真空点电荷"),
    "field.E": (["F", "q"], lambda p: p["F"] / p["q"], "N/C", "E=F/q"),
    "field.point": (["Q", "r"], lambda p: K_E * p["Q"] / p["r"] ** 2, "N/C", "点电荷场强 E=kQ/r²"),
    "field.uniform": (["U", "d"], lambda p: p["U"] / p["d"], "V/m", "匀强电场 E=U/d（d 沿场线）"),
    "capacitor.C": (["Q", "U"], lambda p: p["Q"] / p["U"], "F", "C=Q/U"),
    "capacitor.parallel": (["S", "d", "eps_r"], lambda p: p.get("eps_r", 1.0) * 8.85e-12 * p["S"] / p["d"], "F", "平行板 C=εS/d"),
    # 电路
    "ohm.I": (["U", "R"], lambda p: p["U"] / p["R"], "A", "I=U/R"),
    "closed.I": (["E", "R", "r"], lambda p: p["E"] / (p["R"] + p["r"]), "A", "闭合电路 I=E/(R+r)"),
    "closed.U": (["E", "I", "r"], lambda p: p["E"] - p["I"] * p["r"], "V", "路端电压 U=E-Ir"),
    "power.electric": (["U", "I"], lambda p: p["U"] * p["I"], "W", "P=UI"),
    "joule.Q": (["I", "R", "t"], lambda p: p["I"] ** 2 * p["R"] * p["t"], "J", "Q=I²Rt"),
    # 磁场与电磁感应
    "ampere.F": (["B", "I", "L", "theta"], lambda p: p["B"] * p["I"] * p["L"] * _sin(p.get("theta", 90)), "N", "F=BILsinθ（L 为有效长度）"),
    "lorentz.f": (["q", "v", "B", "theta"], lambda p: p["q"] * p["v"] * p["B"] * _sin(p.get("theta", 90)), "N", "f=qvBsinθ"),
    "cyclotron.r": (["m", "v", "q", "B"], lambda p: p["m"] * p["v"] / (abs(p["q"]) * p["B"]), "m", "r=mv/(qB)"),
    "cyclotron.T": (["m", "q", "B"], lambda p: 2 * math.pi * p["m"] / (abs(p["q"]) * p["B"]), "s", "T=2πm/(qB)"),
    "flux.phi": (["B", "S", "theta"], lambda p: p["B"] * p["S"] * _cos(p.get("theta", 0)), "Wb", "Φ=BScosθ"),
    "faraday.emf": (["n", "dphi", "dt"], lambda p: p["n"] * p["dphi"] / p["dt"], "V", "E=nΔΦ/Δt"),
    "motional.emf": (["B", "L", "v"], lambda p: p["B"] * p["L"] * p["v"], "V", "E=BLv"),
    "transformer.U": (["U1", "n1", "n2"], lambda p: p["U1"] * p["n2"] / p["n1"], "V", "U2=U1n2/n1"),
    # 热学
    "gas.p2": (["p1", "V1", "T1", "V2", "T2"], lambda p: p["p1"] * p["V1"] * p["T2"] / (p["T1"] * p["V2"]), "Pa", "p1V1/T1=p2V2/T2，求 p2"),
    "thermo.dU": (["Q", "W"], lambda p: p["Q"] + p["W"], "J", "ΔU=Q+W（W 为外界对气体做功）"),
    # 光学
    "optics.n": (["i", "r"], lambda p: _sin(p["i"]) / _sin(p["r"]), "", "n=sin i/sin r（度）"),
    "optics.tir": (["n"], lambda p: _deg(math.asin(1.0 / p["n"])), "°", "全反射临界角 C=arcsin(1/n)"),
    "optics.fringe": (["L", "lam", "d"], lambda p: p["L"] * p["lam"] / p["d"], "m", "双缝干涉 Δx=Lλ/d"),
    # 原子
    "photon.E": (["nu"], lambda p: H_PLANCK * p["nu"], "J", "E=hν"),
    "photon.Elambda": (["lam"], lambda p: H_PLANCK * C_LIGHT / p["lam"], "J", "E=hc/λ"),
    "photoelectric.Ek": (["nu", "W0"], lambda p: H_PLANCK * p["nu"] - p["W0"], "J", "Ek=hν-W0"),
    "nuclear.E": (["dm"], lambda p: p["dm"] * C_LIGHT ** 2, "J", "E=Δmc²"),
}


def fmt(value, sigfig=4):
    if value == 0:
        return "0"
    if abs(value) >= 1e6 or abs(value) < 1e-3:
        return f"{value:.{max(sigfig - 1, 1)}e}"
    digits = sigfig - int(math.floor(math.log10(abs(value)))) - 1
    digits = max(digits, 0)
    return f"{value:.{digits}f}".rstrip("0").rstrip(".") if digits > 0 else f"{value:.0f}"


def parse_args(pairs, names):
    p = {}
    for name in names:
        if name in ("theta", "g", "eps_r"):
            p[name] = 0.0 if name == "theta" else (9.8 if name == "g" else 1.0)
    flat = []
    for item in pairs:
        flat.extend(x for x in str(item).replace("，", ",").split(",") if x.strip())
    if flat and all("=" not in x for x in flat):
        if len(flat) != len(names):
            raise ValueError(f"需要 {len(names)} 个参数：{', '.join(names)}")
        return {n: float(v) for n, v in zip(names, flat)}
    for item in flat:
        if "=" not in item:
            raise ValueError(f"参数格式应为 key=value，收到：{item}")
        k, v = item.split("=", 1)
        p[k.strip()] = float(v.strip())
    missing = [n for n in names if n not in p]
    if missing:
        raise ValueError("缺少参数：" + ", ".join(missing))
    return p


def cmd_list():
    print("可用公式（共 {} 条）：\n".format(len(REGISTRY)))
    print(f"{'名称':<22}{'参数':<34}{'单位':<10}说明")
    for name, (params, _, unit, note) in REGISTRY.items():
        print(f"{name:<22}{','.join(params):<34}{unit:<10}{note}")


def cmd_calc(name, arg_list, sigfig, as_json):
    if name not in REGISTRY:
        print(f"没有公式：{name}（用 --list 查看）")
        return 2
    params, func, unit, note = REGISTRY[name]
    try:
        p = parse_args(arg_list, params)
        value = func(p)
    except Exception as e:
        print(f"计算失败：{e}")
        return 2
    if as_json:
        print(json.dumps({"formula": name, "value": value, "unit": unit, "note": note}, ensure_ascii=False))
    else:
        print(f"{name} = {fmt(value, sigfig)} {unit}".rstrip())
        print(f"（{note}）")
    return 0


def cmd_self_check():
    cases = [
        ("kinematics.v", {"v0": 0, "a": 2, "t": 3}, 6.0, 1e-9),
        ("kinematics.x", {"v0": 0, "a": 2, "t": 3}, 9.0, 1e-9),
        ("kinematics.v2", {"v0": 0, "a": 2, "x": 9}, 6.0, 1e-9),
        ("newton.a", {"F": 10, "m": 2}, 5.0, 1e-9),
        ("friction.f", {"mu": 0.2, "N": 50}, 10.0, 1e-9),
        ("circular.F", {"m": 1, "v": 2, "r": 1}, 4.0, 1e-9),
        ("pendulum.T", {"l": 0.994, "g": 9.8}, 2.0, 5e-3),
        ("closed.I", {"E": 6, "R": 2, "r": 1}, 2.0, 1e-9),
        ("closed.U", {"E": 6, "I": 2, "r": 1}, 4.0, 1e-9),
        ("ampere.F", {"B": 0.5, "I": 2, "L": 0.4}, 0.4, 1e-9),
        ("motional.emf", {"B": 0.5, "L": 0.4, "v": 2}, 0.4, 1e-9),
        ("optics.tir", {"n": 2.0}, 30.0, 1e-6),
        ("gas.p2", {"p1": 1e5, "V1": 2, "T1": 300, "V2": 1, "T2": 300}, 2e5, 1.0),
    ]
    bad = 0
    for name, args, expect, tol in cases:
        params, func, unit, _ = REGISTRY[name]
        got = func({**args, **({"theta": 90, "g": 9.8} if name in ("ampere.F",) else {})})
        ok = abs(got - expect) <= tol
        print(("✓" if ok else "✗"), name, "→", fmt(got), unit, "期望", expect)
        bad += 0 if ok else 1
    print(f"\n{len(cases) - bad}/{len(cases)} 通过")
    return 0 if bad == 0 else 1


def main():
    ap = argparse.ArgumentParser(description="常用物理公式计算器")
    ap.add_argument("--formula")
    ap.add_argument("--args", nargs="*", default=[])
    ap.add_argument("--sigfig", type=int, default=4)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if a.list:
        cmd_list()
        return 0
    if a.self_check:
        return cmd_self_check()
    if a.formula:
        return cmd_calc(a.formula, a.args, a.sigfig, a.json)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
