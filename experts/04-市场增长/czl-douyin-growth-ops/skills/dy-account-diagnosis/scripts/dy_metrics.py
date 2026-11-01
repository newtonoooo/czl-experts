#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dy_metrics.py — 抖音短视频/账号指标体检计算器

归属：czl-douyin-growth-ops / skills/dy-account-diagnosis
作者：虫志龙 <47190078@qq.com>

设计要点
--------
1. 只做算术与分级，不做"预测"。所有阈值均为工程参考值（经验区间），
   不是平台官方口径，输出中会显式标注。
2. 采用"漏斗优先"判定法：3 秒留存 → 完播承接 → 互动密度 → 涨粉效率。
   前一级不过线时，后一级的高分不计入结论，因为流量根本没走到那一步。
3. 得分用分段线性插值，避免所有指标都落在同一档、看不出差异。
4. 输入缺字段直接报错并指出字段名，绝不替用户补数字。

用法
----
    python dy_metrics.py --demo
    python dy_metrics.py --input data.json
    python dy_metrics.py --input data.json --format json
    python dy_metrics.py --input data.json --out report.md
"""

import argparse
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

VERSION = "1.0.0"

# ---------------------------------------------------------------- 参考阈值
# 每项为 [(下界, 档位基准分, 判定), ...]，从高到低排列。
# 得分在相邻档位之间做线性插值，最高档以上按斜率延伸到 100 分。
BANDS = {
    "three_sec": [(0.75, 95, "优秀"), (0.60, 80, "良好"), (0.45, 55, "及格"), (0.0, 25, "危险")],
    "finish_short": [(0.50, 95, "优秀"), (0.35, 80, "良好"), (0.20, 55, "及格"), (0.0, 25, "危险")],
    "finish_long": [(0.35, 95, "优秀"), (0.20, 80, "良好"), (0.10, 55, "及格"), (0.0, 25, "危险")],
    "engage": [(0.10, 95, "优秀"), (0.05, 80, "良好"), (0.02, 55, "及格"), (0.0, 25, "危险")],
    "follow": [(0.015, 95, "优秀"), (0.005, 80, "良好"), (0.001, 55, "及格"), (0.0, 25, "危险")],
    "watch_ratio": [(0.60, 95, "优秀"), (0.45, 80, "良好"), (0.30, 55, "及格"), (0.0, 25, "危险")],
}

SHORT_VIDEO_SEC = 30  # <= 30 秒按短视频口径，> 30 秒按长视频口径
PASS_LINE = 55        # 及格线：低于此分视为该环节未过

VIDEO_REQUIRED = ("plays", "duration_sec")


def interp_score(value, key):
    """分段线性插值，返回 0-100 的得分。"""
    anchors = sorted(BANDS[key], key=lambda x: x[0])  # 升序
    if value <= anchors[0][0]:
        return round(anchors[0][1], 1)
    for (lo, lo_score, _), (hi, hi_score, _) in zip(anchors, anchors[1:]):
        if lo <= value <= hi:
            if hi == lo:
                return round(hi_score, 1)
            ratio = (value - lo) / (hi - lo)
            return round(lo_score + ratio * (hi_score - lo_score), 1)
    # 超过最高档：按最高两档的斜率外推，最高 100
    lo, lo_score, _ = anchors[-2]
    hi, hi_score, _ = anchors[-1]
    slope = (hi_score - lo_score) / (hi - lo) if hi != lo else 0
    score = hi_score + slope * (value - hi)
    return round(min(100.0, max(0.0, score)), 1)


def band_label(value, key):
    for lower, _score, label in BANDS[key]:
        if value >= lower:
            return label
    return "无效"


def label_from_score(score):
    """按得分反推判定，用于账号级加权得分（口径已混合，不能再套单条档位）。"""
    if score >= 95:
        return "优秀"
    if score >= 80:
        return "良好"
    if score >= PASS_LINE:
        return "及格"
    return "危险"


def ratio(num, den):
    if den in (None, 0):
        return None
    return num / den


def fmt_pct(value, digits=1):
    if value is None:
        return "—"
    return f"{value * 100:.{digits}f}%"


def make_stage(name, value, key, digits=1):
    return {
        "stage": name,
        "value": value,
        "score": interp_score(value, key),
        "label": band_label(value, key),
        "text": fmt_pct(value, digits),
        "band_key": key,
    }


def analyze_video(video, index):
    missing = [f for f in VIDEO_REQUIRED if video.get(f) is None]
    if missing:
        raise ValueError(f"第 {index} 条视频缺少必填字段：{', '.join(missing)}")

    plays = float(video["plays"])
    duration = float(video["duration_sec"])
    if duration <= 0:
        raise ValueError(f"第 {index} 条视频 duration_sec 必须大于 0")

    likes = float(video.get("likes") or 0)
    comments = float(video.get("comments") or 0)
    shares = float(video.get("shares") or 0)
    saves = float(video.get("saves") or 0)
    new_followers = float(video.get("new_followers") or 0)
    avg_watch = video.get("avg_watch_sec")

    three_sec = video.get("three_sec_rate")
    three_sec = float(three_sec) if three_sec is not None else None

    finish = video.get("finish_rate")
    finish = float(finish) if finish is not None else None

    engagement = (likes + comments + shares + saves) / plays if plays > 0 else None
    follow_rate = ratio(new_followers, plays)
    watch_ratio = ratio(float(avg_watch), duration) if avg_watch is not None else None

    finish_key = "finish_short" if duration <= SHORT_VIDEO_SEC else "finish_long"

    stages = []
    if three_sec is not None:
        stages.append(make_stage("3秒留存", three_sec, "three_sec"))
    if finish is not None:
        stages.append(make_stage("完播承接", finish, finish_key))
    if engagement is not None:
        stages.append(make_stage("互动密度", engagement, "engage"))
    if follow_rate is not None:
        stages.append(make_stage("涨粉效率", follow_rate, "follow", digits=2))

    # 主断点：漏斗上第一个未过及格线的环节
    breakpoint_stage = None
    for st in stages:
        if st["score"] < PASS_LINE:
            breakpoint_stage = st
            break
    if breakpoint_stage is None and stages:
        breakpoint_stage = min(stages, key=lambda s: s["score"])
        weak_kind = "最弱环节"
    else:
        weak_kind = "主断点"

    health = round(sum(s["score"] for s in stages) / len(stages), 1) if stages else None

    notes = []
    if plays < 500:
        notes.append("播放量低于 500，单项比率波动极大，本条结论只作方向参考")
    if watch_ratio is not None:
        notes.append(f"平均播放时长占比 {fmt_pct(watch_ratio)}（{band_label(watch_ratio, 'watch_ratio')}）")

    return {
        "id": video.get("id") or f"v{index}",
        "title": video.get("title") or "",
        "plays": int(plays),
        "duration_sec": duration,
        "three_sec_rate": three_sec,
        "finish_rate": finish,
        "engagement_rate": engagement,
        "follow_rate": follow_rate,
        "watch_ratio": watch_ratio,
        "stages": stages,
        "health_score": health,
        "breakpoint": breakpoint_stage["stage"] if breakpoint_stage else None,
        "breakpoint_kind": weak_kind if stages else None,
        "notes": notes,
    }


def analyze_account(data):
    videos = data.get("videos") or []
    if not videos:
        raise ValueError("输入中没有 videos 数组，至少需要一条视频数据")

    analyzed = [analyze_video(v, i + 1) for i, v in enumerate(videos)]
    total_plays = sum(v["plays"] for v in analyzed)
    weights = [v["plays"] for v in analyzed]

    account = data.get("account") or {}

    # 账号级得分 = 各条视频该环节得分的播放加权平均。
    # 不直接对"完播率"取平均后再套档位，因为长短视频的完播口径不同，
    # 混合平均会失真（30 秒内和 60 秒的完播率不能直接相加）。
    agg_stages = []
    for key, name, digits in (
        ("three_sec_rate", "3秒留存", 1),
        ("finish_rate", "完播承接", 1),
        ("engagement_rate", "互动密度", 2),
        ("follow_rate", "涨粉效率", 2),
    ):
        pairs = []
        for v, w in zip(analyzed, weights):
            st = next((s for s in v["stages"] if s["stage"] == name), None)
            if st is not None:
                pairs.append((st["score"], v[key], w))
        if not pairs:
            continue
        tw = sum(p[2] for p in pairs) or 1
        wscore = round(sum(p[0] * p[2] for p in pairs) / tw, 1)
        wvalue = sum(p[1] * p[2] for p in pairs) / tw
        agg_stages.append({
            "stage": name,
            "value": wvalue,
            "score": wscore,
            "label": label_from_score(wscore),
            "text": fmt_pct(wvalue, digits),
            "band_key": name,
        })

    main_break = None
    main_kind = None
    for st in agg_stages:
        if st["score"] < PASS_LINE:
            main_break = st
            main_kind = "主断点（未过及格线）"
            break
    if main_break is None and agg_stages:
        main_break = min(agg_stages, key=lambda s: s["score"])
        main_kind = "无硬卡点，最弱环节"

    return {
        "version": VERSION,
        "account": {
            "name": account.get("name") or "未命名账号",
            "followers": account.get("followers"),
            "category": account.get("category") or "未标注",
        },
        "video_count": len(analyzed),
        "total_plays": total_plays,
        "avg_plays": int(round(total_plays / len(analyzed))),
        "videos": analyzed,
        "account_stages": agg_stages,
        "main_breakpoint": main_break,
        "main_breakpoint_kind": main_kind,
        "thresholds_note": "阈值为工程参考区间（经验值），非平台官方口径；实际判读请以自己账号的历史基线为第一参照。",
    }


PLAYBOOK = {
    "3秒留存": [
        "把第 1 秒的自我介绍删掉，换成一句冲突或提问",
        "第 2 秒必须出现一个具体数字或具体场景，不要任何铺垫",
        "同一选题拍 3 版不同钩子，其余全不动，只比 3 秒留存",
    ],
    "完播承接": [
        "找出平均播放时长的断点秒数，把最大信息点提到断点前 3 秒",
        "删掉所有过渡句（“接下来”“那么”“下面我们来看”）",
        "长视频先砍到目标时长以下，再谈结构",
    ],
    "互动密度": [
        "结尾给一个两个字就能回答的提问，不要开放式大问题",
        "观点说偏一点，留一处可以被反驳的地方",
        "置顶评论自己补一条信息，给评论区起头",
    ],
    "涨粉效率": [
        "固定一个可复用的身份标签，每条结尾都回到它",
        "做系列编号（第 1/2/3 条），让观众知道还有下一条",
        "主页简介改成一句话：关注你能得到什么",
    ],
}


def render_md(rep):
    acc = rep["account"]
    lines = [f"# 账号体检报告 · {acc['name']}", ""]
    lines.append(f"- 账号类目：{acc['category']}")
    if acc.get("followers") is not None:
        lines.append(f"- 粉丝数：{acc['followers']}")
    lines.append(f"- 样本：{rep['video_count']} 条视频 / 总播放 {rep['total_plays']} / 均播放 {rep['avg_plays']}")
    lines.append("")

    mb = rep["main_breakpoint"]
    lines.append("## 一、结论")
    if mb:
        lines.append(f"**{rep['main_breakpoint_kind']}：{mb['stage']}**（实测 {mb['text']}，判定：{mb['label']}，得分 {mb['score']}）")
        lines.append("")
        lines.append(f"只修这一处，其余环节先不动。{rep['thresholds_note']}")
    else:
        lines.append("样本不足，未能给出卡点判定。")
    lines.append("")

    lines.append("## 二、漏斗判定")
    lines.append("")
    lines.append("| 环节 | 实测（播放加权） | 得分 | 判定 |")
    lines.append("|---|---|---|---|")
    for st in rep["account_stages"]:
        lines.append(f"| {st['stage']} | {st['text']} | {st['score']} | {st['label']} |")
    lines.append("")

    lines.append("## 三、逐条数据")
    lines.append("")
    lines.append("| 视频 | 播放 | 3秒留存 | 完播 | 互动率 | 涨粉率 | 健康分 | 本条判定 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for v in rep["videos"]:
        tag = f"{v['breakpoint'] or '—'}（{v['breakpoint_kind'] or '—'}）" if v["breakpoint"] else "—"
        lines.append(
            f"| {v['id']} {v['title']} | {v['plays']} | {fmt_pct(v['three_sec_rate'])} | "
            f"{fmt_pct(v['finish_rate'])} | {fmt_pct(v['engagement_rate'])} | "
            f"{fmt_pct(v['follow_rate'], 2)} | {v['health_score']} | {tag} |"
        )
    lines.append("")

    low_play = [v for v in rep["videos"] if v["plays"] < 500]
    if low_play:
        lines.append("> 注意：" + "；".join(f"{v['id']} 播放 {v['plays']}" for v in low_play) +
                     "，样本过小，比率波动大，结论请降权使用。")
        lines.append("")

    lines.append("## 四、下一步")
    lines.append("")
    stage = mb["stage"] if mb else None
    for i, item in enumerate(PLAYBOOK.get(stage, ["补足数据后再判定"]), 1):
        lines.append(f"{i}. {item}")
    lines.append("")
    lines.append("> 只改上面这几条，7 天后回看同一个数。同时改多项会导致无法归因。")
    return "\n".join(lines)


DEMO = {
    "account": {"name": "示例账号（家居收纳）", "followers": 3800, "category": "家居/生活"},
    "videos": [
        {"id": "v1", "title": "衣柜分层改造", "plays": 12800, "duration_sec": 38,
         "three_sec_rate": 0.52, "finish_rate": 0.14, "likes": 210, "comments": 18,
         "shares": 26, "saves": 95, "new_followers": 42, "avg_watch_sec": 11},
        {"id": "v2", "title": "9块9收纳盒测评", "plays": 4200, "duration_sec": 25,
         "three_sec_rate": 0.68, "finish_rate": 0.41, "likes": 96, "comments": 7,
         "shares": 4, "saves": 22, "new_followers": 9, "avg_watch_sec": 12},
        {"id": "v3", "title": "厨房抽屉翻车", "plays": 760, "duration_sec": 52,
         "three_sec_rate": 0.38, "finish_rate": 0.08, "likes": 8, "comments": 1,
         "shares": 0, "saves": 3, "new_followers": 0, "avg_watch_sec": 6},
    ],
}


def main():
    ap = argparse.ArgumentParser(description="抖音账号指标体检计算器")
    ap.add_argument("--input", help="输入 JSON 文件路径")
    ap.add_argument("--format", choices=("md", "json"), default="md")
    ap.add_argument("--out", help="输出文件路径（不填则打印到终端）")
    ap.add_argument("--demo", action="store_true", help="使用内置样例数据")
    ap.add_argument("--version", action="version", version=f"dy_metrics {VERSION}")
    args = ap.parse_args()

    if args.demo:
        data = DEMO
    elif args.input:
        path = Path(args.input)
        if not path.exists():
            print(f"错误：找不到输入文件 {path}", file=sys.stderr)
            return 2
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            print(f"输入文件不是合法 JSON：{exc}", file=sys.stderr)
            return 2
    else:
        ap.print_help()
        return 2

    try:
        rep = analyze_account(data)
    except (ValueError, KeyError, TypeError) as exc:
        print(f"输入有误：{exc}", file=sys.stderr)
        return 2

    out_text = render_md(rep) if args.format == "md" else json.dumps(rep, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(out_text, encoding="utf-8")
        print(f"已写入 {args.out}")
    else:
        print(out_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
