#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""calibrate.py — 用标注样本校准人味体检的阈值（纯标准库，离线）

这是本产品唯一"别人没有"的东西：阈值可改，改完能自证改对了。

原理很土但有效：把已知"像人写的"和"像机器写的"两组样本各跑一遍，
看当前阈值下两组的分数有没有分开。负样本最高分 < 正样本最低分 =
完全分开。分不开，就逐项调阈值，让这个间隔最大化。

用法：
    python calibrate.py --pos samples/pos --neg samples/neg
    python calibrate.py --pos samples/pos --neg samples/neg --out thresholds.json
    python calibrate.py --pos ... --neg ... --check thresholds.json   # 只评估不改

输出：
    当前阈值的分离间隔与准确率
    逐项扫描后的推荐阈值
    一份可直接给 voice_scan.py --thresholds 用的 JSON

注意：样本少于每类 3 份时只做提示，不给"推荐值"——两组各 1 份样本
      调出来的阈值，等于用 2 个点拟合一条曲线，没有意义。

作者：虫志龙 <47190078@qq.com>
许可：MIT
"""

import argparse
import glob
import importlib.util
import json
import os
import sys

# 可调参数与扫描范围
SWEEP = {
    "sentence_cv_fail": (0.30, 0.40, 0.50, 0.60),
    "short_run_warn": (2, 3, 4, 5),
    "short_run_fail": (3, 4, 5, 6),
    "dash_per_1k_fail": (2.0, 3.0, 4.0, 6.0),
    "dash_per_1k_warn": (1.0, 2.0, 3.0),
    "not_but_fail": (2, 3, 4),
    "not_but_warn": (1, 2, 3),
    "simile_per_1k_fail": (5.0, 8.0, 12.0),
    "emotion_direct_fail": (2, 3, 5),
    "blacklist_fail": (3, 5, 8),
    "summary_open_warn": (1, 2, 3),
    "adverb_per_1k_warn": (3.0, 5.0, 8.0),
    "exclaim_per_1k_warn": (5.0, 8.0, 12.0),
}


def load_scanner(root):
    """按路径加载 voice_scan，避免包依赖。"""
    p = os.path.join(root, "skills", "czl-voice-tune", "scripts", "voice_scan.py")
    if not os.path.exists(p):
        raise SystemExit("找不到 voice_scan.py：%s" % p)
    spec = importlib.util.spec_from_file_location("voice_scan", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_dir(d):
    files = []
    for pat in ("*.md", "*.txt"):
        files.extend(glob.glob(os.path.join(d, pat)))
    return sorted(files)


def scores(mod, files, cfg):
    out = []
    for f in files:
        with open(f, "r", encoding="utf-8", errors="replace") as fh:
            r = mod.scan(fh.read(), cfg)
        if r.get("ok"):
            out.append((os.path.basename(f), r["score"], r["verdict"], r["fail_count"]))
    return out


def evaluate(mod, pos, neg, cfg):
    ps = scores(mod, pos, cfg)
    ns = scores(mod, neg, cfg)
    if not ps or not ns:
        return None
    p_min = min(s for _, s, _, _ in ps)
    n_max = max(s for _, s, _, _ in ns)
    gap = p_min - n_max
    # 准确率：正样本判 PASS，负样本判 FAIL
    hit = sum(1 for _, _, v, _ in ps if v == "PASS") + sum(1 for _, _, v, _ in ns if v == "FAIL")
    acc = hit / float(len(ps) + len(ns))
    return {"gap": gap, "acc": acc, "pos": ps, "neg": ns,
            "p_min": p_min, "n_max": n_max}


def sweep(mod, pos, neg, base):
    """逐项单参数扫描，取使间隔最大的取值；两轮坐标下降。"""
    cfg = dict(base)
    cur = evaluate(mod, pos, neg, cfg)
    trace = []
    for _ in range(2):
        for key, cands in SWEEP.items():
            best_v, best_e = cfg.get(key), cur
            for v in cands:
                trial = dict(cfg)
                trial[key] = v
                e = evaluate(mod, pos, neg, trial)
                if not e:
                    continue
                # 先比间隔，间隔相同再比准确率
                if (e["gap"], e["acc"]) > (best_e["gap"], best_e["acc"]):
                    best_v, best_e = v, e
            if best_v != cfg.get(key):
                trace.append((key, cfg.get(key), best_v, round(best_e["gap"], 1)))
                cfg[key] = best_v
                cur = best_e
    return cfg, cur, trace


def render(ev, mod_cfg, trace, pos_n, neg_n):
    L = []
    L.append("=" * 66)
    L.append("阈值校准 ｜ 正样本 %d 份 ｜ 负样本 %d 份" % (pos_n, neg_n))
    L.append("=" * 66)
    L.append("当前阈值：正样本最低 %d ｜ 负样本最高 %d ｜ 间隔 %+d ｜ 准确率 %.0f%%"
             % (ev["p_min"], ev["n_max"], ev["gap"], ev["acc"] * 100))
    L.append("")
    L.append("%-28s %-8s %-8s %s" % ("样本", "分数", "判定", "阻断项"))
    for n, s, v, f in ev["pos"]:
        L.append("  正 %-25s %-8d %-8s %d" % (n[:25], s, v, f))
    for n, s, v, f in ev["neg"]:
        L.append("  负 %-25s %-8d %-8s %d" % (n[:25], s, v, f))
    L.append("")
    if trace:
        L.append("逐项调整（项 / 原值 → 新值 / 调整后间隔）：")
        for k, a, b, g in trace:
            L.append("  %-24s %-8s → %-8s %+d" % (k, a, b, g))
    else:
        L.append("逐项扫描后没有找到更优取值——当前阈值对这组样本已是最佳。")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="人味体检阈值校准")
    ap.add_argument("--pos", required=True, help="正样本目录（像人写的）")
    ap.add_argument("--neg", required=True, help="负样本目录（像机器写的）")
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default=None, help="把推荐阈值写成 JSON")
    ap.add_argument("--check", default=None, help="只评估给定的阈值 JSON，不扫描")
    ap.add_argument("--json", dest="json_out", default=None)
    a = ap.parse_args()

    mod = load_scanner(os.path.abspath(a.root))
    pos, neg = read_dir(a.pos), read_dir(a.neg)
    if not pos or not neg:
        print("样本不足：正 %d 份，负 %d 份。两个目录都要有 .md 或 .txt。" % (len(pos), len(neg)))
        return 2

    base = {}
    if a.check:
        if not os.path.exists(a.check):
            print("找不到阈值文件：%s" % a.check)
            return 2
        with open(a.check, "r", encoding="utf-8") as f:
            base = json.load(f)
        ev = evaluate(mod, pos, neg, dict(mod.norm_thresholds(base)))
        print(render(ev, base, [], len(pos), len(neg)))
        return 0 if ev["gap"] > 0 else 1

    ev = evaluate(mod, pos, neg, dict(mod.norm_thresholds(base)))
    print(render(ev, base, [], len(pos), len(neg)))
    print()

    if len(pos) < 3 or len(neg) < 3:
        print("样本少于每类 3 份，不做推荐。"
              "两组各 1 份样本调出来的阈值没有统计意义，先补样本。")
        return 0 if ev["gap"] > 0 else 1

    cfg, best, trace = sweep(mod, pos, neg, dict(mod.norm_thresholds(base)))
    print(render(best, cfg, trace, len(pos), len(neg)))
    print()
    if best["gap"] <= 0:
        print("注意：即使调到最优，两组仍有重叠（间隔 %+d）。" % best["gap"])
        print("      说明样本本身特征相近，或需要新增检查项，而不是继续拧阈值。")

    out = {k: v for k, v in cfg.items()}
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print("已写出推荐阈值：%s" % a.out)
        print("用法：voice_scan.py 稿件.md --thresholds %s" % a.out)
    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as f:
            json.dump({"thresholds": out, "gap": best["gap"], "acc": best["acc"],
                       "trace": trace}, f, ensure_ascii=False, indent=2)
        print("已写入：%s" % a.json_out)
    return 0 if best["gap"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
