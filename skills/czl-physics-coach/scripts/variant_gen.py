#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""变式题生成器（自编题）。

为什么要有它：家长和老师手编数字，经常出现"答案不整、物理不合理、条件互相矛盾"。
这里所有答案都由 physics_check 里的函数算出来，题干与答案不会打架。

用法：
    python variant_gen.py --list
    python variant_gen.py --model incline --seed 7 --n 2
    python variant_gen.py --model collision --seed 3 --n 3 --format json

生成的题目一律标注"自编题"，不是真题，也不冒充真题。
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import physics_check as pc  # noqa: E402

G = 10.0


def _f(x: float, nd: int = 2) -> str:
    return f"{x:.{nd}f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------- 各模型出题

def gen_incline(rng: random.Random):
    theta = rng.choice([30, 37, 45, 53])
    mu = rng.choice([0.1, 0.2, 0.25, 0.3, 0.4])
    m = rng.choice([1, 2, 3, 4])
    length = rng.choice([2, 3, 4, 5, 6, 8])
    # 题干里公布的正弦余弦就是计算所用的值，避免"学生按 0.6 算、答案按 0.6018 算"
    sin_t = round(math.sin(math.radians(theta)), 3)
    cos_t = round(math.cos(math.radians(theta)), 3)
    n_force = m * G * cos_t
    f = mu * n_force
    a = G * sin_t - f / m
    if a <= 0.2:
        return None
    v = math.sqrt(2 * a * length)
    return {
        "model": "incline",
        "title": "斜面下滑（动力学 + 运动学）",
        "stem": (f"质量 {m} kg 的物块从倾角 {theta}° 的斜面顶端由静止释放，"
                 f"斜面长 {length} m，物块与斜面间的动摩擦因数为 {mu}。"
                 f"取 g=10 m/s²，sin{theta}°={_f(sin_t, 3)}，cos{theta}°={_f(cos_t, 3)}。"),
        "asks": ["物块下滑的加速度大小", "物块滑到斜面底端时的速度大小"],
        "answer": (f"① 沿斜面方向：ma = mg sinθ − μmg cosθ，"
                   f"得 a = {_f(a)} m/s²；\n"
                   f"② 由 v² = 2aL，得 v = {_f(v)} m/s。"),
        "steps": [f"N = mg cosθ = {_f(n_force)} N",
                  f"f = μN = {_f(f)} N",
                  f"a = (mg sinθ − f)/m = {_f(a)} m/s²",
                  f"v = sqrt(2aL) = {_f(v)} m/s"],
        "score": ["写出牛顿第二定律原式（2 分）",
                  "算出加速度（2 分）",
                  "写出 v²=2aL 并代入（2 分）",
                  "结果带单位（1 分）"],
        "trap": "把正压力写成 mg；忘记摩擦力方向沿斜面向上。",
    }


def gen_projectile(rng: random.Random):
    v0 = rng.choice([10, 15, 20, 25])
    angle = rng.choice([30, 45, 60])
    res = pc.projectile(v0, angle, 0.0, G)
    return {
        "model": "projectile",
        "title": "斜抛运动（分解）",
        "stem": (f"从地面以 {v0} m/s 的初速度、与水平方向成 {angle}° 抛出一个小球，"
                 f"不计空气阻力，取 g=10 m/s²。"),
        "asks": ["小球在空中运动的时间", "水平射程", "落地时速度的大小"],
        "answer": (f"① 竖直方向：t = 2v₀sinθ/g = {_f(res['t'])} s；\n"
                   f"② 水平方向：x = v₀cosθ·t = {_f(res['range'])} m；\n"
                   f"③ 落地速度 v = {_f(res['speed'])} m/s（与抛出速度等大）。"),
        "steps": [f"v₀y = v₀sinθ = {_f(v0 * math.sin(math.radians(angle)))} m/s",
                  f"t = 2v₀y/g = {_f(res['t'])} s",
                  f"x = v₀cosθ·t = {_f(res['range'])} m"],
        "score": ["分解为水平匀速、竖直匀变速（2 分）",
                  "由竖直方向求时间（2 分）",
                  "水平方向求射程（2 分）",
                  "结果与单位（1 分）"],
        "trap": "用水平速度去算时间；把抛射角当成落地速度与水平方向的夹角。",
    }


def gen_collision(rng: random.Random):
    m1 = rng.choice([1, 2, 3])
    m2 = rng.choice([1, 3, 4])
    if m1 == m2:
        m2 += 1
    u1 = rng.choice([4, 6, 8])
    res = pc.collision(m1, u1, m2, 0.0, "elastic")
    return {
        "model": "collision",
        "title": "弹性碰撞（动量与动能同时守恒）",
        "stem": (f"质量 {m1} kg 的小球以 {u1} m/s 的速度与静止的质量 {m2} kg 的小球"
                 f"发生一维弹性碰撞，碰撞后两球速度均沿原方向或反方向。"),
        "asks": ["碰后两球的速度", "碰撞过程中损失的动能"],
        "answer": (f"① 动量守恒与动能守恒联立，得 v₁′ = {_f(res['v1'])} m/s，"
                   f"v₂′ = {_f(res['v2'])} m/s；\n"
                   f"② 弹性碰撞动能不损失，损失量为 {_f(res['loss'])} J。"),
        "steps": [f"m₁u₁ = m₁v₁′ + m₂v₂′",
                  f"½m₁u₁² = ½m₁v₁′² + ½m₂v₂′²",
                  f"v₁′ = (m₁−m₂)u₁/(m₁+m₂) = {_f(res['v1'])} m/s",
                  f"v₂′ = 2m₁u₁/(m₁+m₂) = {_f(res['v2'])} m/s"],
        "score": ["声明动量守恒及条件（2 分）",
                  "写出两个守恒方程（2 分）",
                  "解出两个速度（2 分）",
                  "说明弹性碰撞动能不损失（1 分）"],
        "trap": "弹性碰撞却算出一个'动能损失'；负号漏写导致方向判断错。",
    }


def gen_induction(rng: random.Random):
    B = rng.choice([0.2, 0.4, 0.5, 1.0])
    L = rng.choice([0.5, 1.0, 2.0])
    v = rng.choice([1, 2, 4])
    R = rng.choice([0.2, 0.4, 0.5, 1.0])
    res = pc.induction(B, L, v, R)
    return {
        "model": "induction",
        "title": "单杆切割磁感线（电磁感应 + 电路）",
        "stem": (f"水平导轨间距 {_f(L)} m，处于竖直向下、磁感应强度 {_f(B)} T 的匀强磁场中。"
                 f"一根导体棒以 {_f(v)} m/s 匀速向右运动，回路总电阻 {_f(R)} Ω，"
                 f"导轨与棒的其他电阻不计。"),
        "asks": ["回路中的感应电动势", "感应电流", "棒受到的安培力", "回路的电功率"],
        "answer": (f"① E = BLv = {_f(res['E'])} V；\n"
                   f"② I = E/R = {_f(res['I'])} A；\n"
                   f"③ F = BIL = {_f(res['F'])} N，方向与运动方向相反；\n"
                   f"④ P = EI = {_f(res['P'])} W。"),
        "steps": [f"E = BLv = {_f(res['E'])} V",
                  f"I = E/R = {_f(res['I'])} A",
                  f"F = BIL = {_f(res['F'])} N",
                  f"P = EI = {_f(res['P'])} W"],
        "score": ["写出 E=BLv（2 分）",
                  "用总电阻求电流（2 分）",
                  "安培力大小与方向（2 分）",
                  "功率与单位（1 分）"],
        "trap": "只算外电阻；把'达到稳定'理解成'速度为零'。",
    }


def gen_vertical_circle(rng: random.Random):
    R = rng.choice([0.4, 0.5, 0.8, 1.0])
    res = pc.vertical_circle(R, G, "rope")
    return {
        "model": "circular",
        "title": "竖直圆周（绳模型临界）",
        "stem": (f"长 {_f(R)} m 的轻绳一端固定，另一端系一个小球，在竖直平面内做圆周运动，"
                 f"不计空气阻力，取 g=10 m/s²。"),
        "asks": ["小球通过最高点的最小速度", "对应最低点的最小速度"],
        "answer": (f"① 最高点：mg = mv²/R，得 v_top = {_f(res['v_top'])} m/s；\n"
                   f"② 最低点到最高点机械能守恒：v_bottom = {_f(res['v_bottom'])} m/s。"),
        "steps": [f"v_top = sqrt(gR) = {_f(res['v_top'])} m/s",
                  f"½mv_b² = ½mv_t² + mg·2R",
                  f"v_bottom = sqrt(5gR) = {_f(res['v_bottom'])} m/s"],
        "score": ["最高点临界条件（2 分）",
                  "最低点到最高点用机械能守恒（3 分）",
                  "结果与单位（2 分）"],
        "trap": "杆模型也套 sqrt(gR)；用运动学公式处理竖直圆周（加速度不恒定）。",
    }


def gen_energy(rng: random.Random):
    h = rng.choice([2, 3, 5])
    theta = rng.choice([37, 53])
    mu = rng.choice([0.2, 0.3, 0.5])
    sin_t = round(math.sin(math.radians(theta)), 3)
    cos_t = round(math.cos(math.radians(theta)), 3)
    s = h / mu - h * cos_t / sin_t
    if s <= 0.3:
        return None
    return {
        "model": "energy",
        "title": "斜面 + 水平面（动能定理全程）",
        "stem": (f"物块从倾角 {theta}°、高 {h} m 的斜面顶端由静止下滑，随后进入水平面。"
                 f"斜面与水平面的动摩擦因数均为 {mu}，交接处平滑，取 g=10 m/s²，"
                 f"sin{theta}°={_f(sin_t, 3)}，cos{theta}°={_f(cos_t, 3)}。"),
        "asks": ["物块在水平面上滑行的距离"],
        "answer": (f"对全程用动能定理：mgh − μmg cosθ·(h/sinθ) − μmgs = 0，"
                   f"解得 s = {_f(s)} m。"),
        "steps": [f"斜面段摩擦生热：μmg cosθ·(h/sinθ)",
                  f"水平段摩擦生热：μmgs",
                  f"mgh = μmg cosθ·(h/sinθ) + μmgs",
                  f"s = {_f(s)} m"],
        "score": ["声明全程用动能定理（2 分）",
                  "斜面段与水平段摩擦做功都写到（3 分）",
                  "解出 s 并带单位（2 分）"],
        "trap": "只算水平段摩擦，漏掉斜面段；用分段法但忘了求交接处速度。",
    }


GENERATORS = {
    "incline": gen_incline,
    "projectile": gen_projectile,
    "collision": gen_collision,
    "induction": gen_induction,
    "circular": gen_vertical_circle,
    "energy": gen_energy,
}


def build(model: str, seed: int, n: int):
    rng = random.Random(seed)
    out = []
    guard = 0
    while len(out) < n and guard < n * 20:
        guard += 1
        item = GENERATORS[model](rng)
        if item is None:
            continue
        item["index"] = len(out) + 1
        item["source"] = "自编题（数字随机生成，答案由程序计算）"
        out.append(item)
    if not out:
        raise RuntimeError("参数范围太窄，未能生成合理解，请换一个 --seed")
    return out


def render_text(items):
    lines = []
    for it in items:
        lines.append(f"\n===== 题 {it['index']} · {it['title']} =====")
        lines.append(f"【题干】{it['stem']}")
        lines.append("【求】" + "；".join(it["asks"]))
        lines.append("【参考答案】" + it["answer"])
        lines.append("【关键步骤】")
        for s in it["steps"]:
            lines.append(f"  - {s}")
        lines.append("【评分点】")
        for s in it["score"]:
            lines.append(f"  - {s}")
        lines.append(f"【易错】{it['trap']}")
        lines.append(f"【来源】{it['source']}")
    lines.append("\n提示：先用题干让学生独立做，再看答案；答案里的步骤对应评分点。")
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="高中物理变式题生成器（自编题）")
    p.add_argument("--model", choices=sorted(GENERATORS), help="模型")
    p.add_argument("--seed", type=int, default=1, help="随机种子，同种子同题")
    p.add_argument("--n", type=int, default=1, help="生成几道")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--list", action="store_true", help="列出可用模型")
    args = p.parse_args(argv)

    if args.list:
        print("可用模型：")
        for k in sorted(GENERATORS):
            print(f"  {k}")
        return 0

    if not args.model:
        print("请用 --model 指定模型，或 --list 查看可选值", file=sys.stderr)
        return 2
    if args.n < 1 or args.n > 10:
        print("--n 需在 1 到 10 之间", file=sys.stderr)
        return 2

    try:
        items = build(args.model, args.seed, args.n)
    except RuntimeError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        print(render_text(items))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
