#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
W5 履约跟踪：把合同里“谁在什么时候该干什么”变成可核对的台账

数据存在本地 JSON 文件（默认 .contract-workspace/ledger.json），不上传任何服务器。
节点状态按截止日与当天日期实时计算：逾期 / 临近（7 天内）/ 正常 / 已完成。
"""

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from cc_common import ensure_dir, write_text  # noqa: E402

DEFAULT_PATH = Path(".contract-workspace") / "ledger.json"
SOON_DAYS = 7


def _today():
    return date.today()


def load(path=None):
    p = Path(path) if path else DEFAULT_PATH
    if not p.exists():
        return {"meta": {"version": "1.0.0", "created": _today().isoformat()}, "entries": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise ValueError("台账文件损坏（JSON 解析失败）：%s，请先备份后删除重建。" % p)
    data.setdefault("entries", [])
    return data


def save(data, path=None):
    p = Path(path) if path else DEFAULT_PATH
    ensure_dir(p.parent)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(p.resolve())


def _next_id(data):
    nums = [int(e["id"][1:]) for e in data["entries"] if e.get("id", "").startswith("L") and e["id"][1:].isdigit()]
    return "L%04d" % (max(nums) + 1 if nums else 1)


def add(contract, items, obligor="", due=None, note="", path=None):
    data = load(path)
    created = []
    for item in items:
        entry = {
            "id": _next_id(data),
            "contract": contract,
            "item": item,
            "obligor": obligor,
            "due": due or "",
            "note": note,
            "status": "open",
            "created": _today().isoformat(),
        }
        data["entries"].append(entry)
        created.append(entry)
    save(data, path)
    return created


def import_from_draft(meta_path, start_date=None, path=None):
    """读取 cc_draft 产出的 meta.json，按 ledger_hints 批量生成节点。"""
    meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))
    base = date.fromisoformat(start_date) if start_date else date.fromisoformat(
        (meta.get("placeholders") or {}).get("start_date") or _today().isoformat())
    hints = meta.get("ledger_hints") or []
    data = load(path)
    created = []
    for hint in hints:
        due = (base + timedelta(days=int(hint.get("offset_days", 0)))).isoformat()
        entry = {
            "id": _next_id(data),
            "contract": meta.get("title") or meta.get("type_label", "未命名合同"),
            "item": hint.get("item", "履约节点"),
            "obligor": hint.get("obligor", ""),
            "due": due,
            "note": "由起草台自动生成（基准日 %s + %s 天）" % (base.isoformat(), hint.get("offset_days", 0)),
            "status": "open",
            "created": _today().isoformat(),
        }
        data["entries"].append(entry)
        created.append(entry)
    save(data, path)
    return created


def _decorate(entry):
    today = _today()
    due = entry.get("due") or ""
    out = dict(entry)
    if entry.get("status") == "done":
        out["days_left"] = None
        out["state"] = "已完成"
        return out
    if not due:
        out["days_left"] = None
        out["state"] = "无截止日"
        return out
    try:
        d = date.fromisoformat(due)
    except ValueError:
        out["days_left"] = None
        out["state"] = "日期格式有误"
        return out
    left = (d - today).days
    out["days_left"] = left
    if left < 0:
        out["state"] = "逾期 %d 天" % abs(left)
    elif left <= SOON_DAYS:
        out["state"] = "临近（%d 天）" % left
    else:
        out["state"] = "正常"
    return out


def list_entries(path=None, state=None, contract=None):
    data = load(path)
    rows = [_decorate(e) for e in data["entries"]]
    if state == "open":
        rows = [r for r in rows if r["status"] != "done"]
    elif state == "done":
        rows = [r for r in rows if r["status"] == "done"]
    if contract:
        rows = [r for r in rows if contract in r.get("contract", "")]
    rows.sort(key=lambda r: (r.get("due") or "9999-12-31", r["id"]))
    return rows


def due_soon(days=SOON_DAYS, path=None):
    rows = [r for r in list_entries(path) if r["status"] != "done" and r["days_left"] is not None and r["days_left"] <= days]
    return rows


def mark_done(entry_id, path=None):
    data = load(path)
    for e in data["entries"]:
        if e["id"] == entry_id:
            e["status"] = "done"
            e["done_at"] = _today().isoformat()
            save(data, path)
            return e
    raise KeyError("台账中没有编号为 %s 的节点" % entry_id)


def remove(entry_id, path=None):
    data = load(path)
    before = len(data["entries"])
    data["entries"] = [e for e in data["entries"] if e["id"] != entry_id]
    if len(data["entries"]) == before:
        raise KeyError("台账中没有编号为 %s 的节点" % entry_id)
    save(data, path)
    return True


def render_report(rows, title="履约台账"):
    lines = ["# %s" % title, ""]
    lines.append("- 生成时间：%s" % datetime.now().strftime("%Y-%m-%d %H:%M"))
    open_rows = [r for r in rows if r["status"] != "done"]
    overdue = [r for r in open_rows if (r.get("days_left") or 0) < 0]
    soon = [r for r in open_rows if r.get("days_left") is not None and 0 <= r["days_left"] <= SOON_DAYS]
    lines.append("- 未完成 %d 项，其中逾期 %d 项、7 日内到期 %d 项" % (len(open_rows), len(overdue), len(soon)))
    lines.append("")
    if not rows:
        lines.append("台账为空。可以先用起草台的 meta.json 导入节点，或手工添加。")
        lines.append("")
        return "\n".join(lines)
    lines.append("| 编号 | 合同 | 节点 | 义务方 | 截止日 | 剩余 | 状态 |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in rows:
        left = "—" if r["days_left"] is None else ("%+d 天" % r["days_left"] if r["days_left"] >= 0 else "逾期 %d 天" % abs(r["days_left"]))
        lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            r["id"], (r.get("contract") or "")[:14], r["item"], r.get("obligor", ""),
            r.get("due") or "—", left if r["status"] != "done" else "—", r["state"]))
    lines.append("")
    if overdue:
        lines.append("## 已逾期（需要立刻处理）")
        lines.append("")
        for r in overdue:
            lines.append("- **%s**（%s）%s 应完成，已逾期 %d 天%s" % (
                r["item"], r["contract"], r["due"], abs(r["days_left"]),
                "；备注：" + r["note"] if r.get("note") else ""))
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("台账只记录合同约定的时间节点，不代替对履约实质的判断；"
                 "节点到期前请留存交付凭证、验收记录、付款回单。")
    lines.append("")
    return "\n".join(lines)


def report(path=None, out_dir=".contract-workspace"):
    rows = list_entries(path)
    md = render_report(rows)
    p = Path(out_dir) / "ledger_report.md"
    write_text(p, md)
    return {"ok": True, "entries": len(rows), "report": str(p.resolve()), "markdown": md}
