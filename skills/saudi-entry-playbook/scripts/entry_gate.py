#!/usr/bin/env python3
"""G1 准入闸门规则引擎。

只做结构性规则匹配与参数校验，不做政策判断，不内置任何未经核实的门槛数字。
行业敏感清单可替换：--rules my_rules.json

用法：
    python entry_gate.py --input case.json
    python entry_gate.py --input case.json --format md
    python entry_gate.py --rules rules.json --input case.json

退出码：0 = GO/CONDITIONAL，2 = BLOCKED，1 = 输入错误
"""

import argparse
import json
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

LEVEL_ORDER = {"BLOCK": 0, "CONDITION": 1, "WARN": 2, "INFO": 3}

# 基线敏感活动清单：仅用于提示「需特别核对」，不代表官方负面清单。
# 任何结论都必须回到 MISA 最新公告复核。
DEFAULT_RESTRICTED = {
    "upstream-oil-gas": "上游油气勘探与开发",
    "makkah-madinah-realestate": "麦加与麦地那特定房地产活动",
    "recruitment-services": "人力招聘与劳务供应服务",
    "security-services": "安保与调查服务",
    "fishing": "渔业捕捞",
    "printing-publishing": "印刷与出版（部分细分）",
}

TRADE_LIKE = {
    "trading-general",
    "trading-retail",
    "trading-wholesale",
    "distribution",
    "import-export",
}


def load_rules(path):
    if not path:
        return dict(DEFAULT_RESTRICTED)
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and "restricted_activities" in data:
        data = data["restricted_activities"]
    if not isinstance(data, dict):
        raise ValueError("rules 文件应为 {活动代码: 说明} 的字典")
    return data


def evaluate(case, restricted=None):
    """返回 {verdict, findings, required_actions, gate_open, can_proceed}"""
    restricted = DEFAULT_RESTRICTED if restricted is None else restricted
    findings = []

    def add(level, code, message, action=""):
        findings.append(
            {"level": level, "code": code, "message": message, "action": action}
        )

    ownership = case.get("foreign_ownership_pct")
    code = (case.get("activity_code") or "").strip()
    zone = (case.get("zone") or "none").strip()
    has_partner = bool(case.get("has_local_partner"))
    required = list(case.get("required_licenses") or [])
    held = list(case.get("held_licenses") or [])

    # 1. 参数合法性
    if not isinstance(ownership, (int, float)) or ownership < 0 or ownership > 100:
        add("BLOCK", "OWNERSHIP_INVALID", "外资持股比例缺失或不在 0-100 区间", "补全股权意向")
    if not code:
        add("BLOCK", "ACTIVITY_MISSING", "缺少活动代码，无法判定准入路径", "补充产品或服务对应的活动代码")

    # 2. 股权结构是否成立
    if isinstance(ownership, (int, float)) and 0 < ownership < 100 and not has_partner:
        add(
            "BLOCK",
            "EQUITY_STRUCTURE",
            f"外资持股 {ownership}% 但无本地股东，股权结构不成立",
            "确定本地股东或改为 100% 外资（若该活动允许）",
        )
    if isinstance(ownership, (int, float)) and ownership == 0:
        add("BLOCK", "NO_FOREIGN_EQUITY", "外资持股为 0，不属于外资进入场景", "确认委托方角色")

    # 3. 敏感活动
    if code in restricted:
        if zone in ("sez", "rhq"):
            add(
                "CONDITION",
                "RESTRICTED_ACTIVITY_ZONE",
                f"活动「{restricted[code]}」属高敏感领域，当前拟走 {zone.upper()} 通道",
                "确认该通道是否覆盖此活动，并取得主管机构书面意见",
            )
        else:
            add(
                "CONDITION",
                "RESTRICTED_ACTIVITY",
                f"活动「{restricted[code]}」属高敏感领域，默认不可直接设立",
                "核对 MISA 最新负面清单；评估特区、RHQ 或本地持股等例外通道",
            )

    # 4. 许可缺口
    missing = [lic for lic in required if lic not in held]
    if missing:
        add(
            "CONDITION",
            "LICENSE_GAP",
            "尚缺许可/资质：" + "、".join(missing),
            "逐项确认发证机构、材料清单与办理周期，并写入前置条件",
        )

    # 5. 政府采购
    if case.get("sells_to_government"):
        if "CR" not in held:
            add("CONDITION", "GOV_CR", "拟向政府/国企销售但未取得商业注册（CR）", "完成 CR 与活动代码匹配")
        if "ZATCA" not in held:
            add("CONDITION", "GOV_TAX", "拟投标但税务登记/完税状态未就绪", "完成税务登记并取得完税证明")
        if "GOSI" not in held:
            add("CONDITION", "GOV_GOSI", "拟投标但社保登记未就绪", "完成 GOSI 登记并保留缴纳记录")
        add(
            "INFO",
            "GOV_TENDER_FIT",
            "政府项目还需分类分级、业绩与保函能力，转入 G4 闸门核对",
            "使用 references/04-etimad-tender.md 的资格核对表",
        )

    # 6. 进口与产品合规
    if case.get("imports_goods"):
        certs = list(case.get("certificates_held") or [])
        if case.get("product_regulated") and not certs:
            add(
                "CONDITION",
                "SABER_MISSING",
                "进口受管制产品但无 SABER/SASO 证书记录",
                "确认 HS 编码是否受管制，启动 PC 申领，首批货前取得 SC",
            )
        add("INFO", "CUSTOMS", "关税与 HS 编码需按品类核对", "按 references/05、06 卡片核对")

    # 7. 用工
    if case.get("employs_staff") and "GOSI" not in held:
        add("CONDITION", "HR_GOSI", "拟本地雇工但社保登记未就绪", "完成 GOSI 与 Qiwa 登记，核算沙特化比例")

    # 8. 贸易类活动 + 100% 外资
    if code in TRADE_LIKE and ownership == 100:
        add(
            "WARN",
            "TRADING_100",
            "纯贸易类活动申请 100% 外资，历史上存在额外门槛",
            "核对最新规则；如不成立，考虑本地代理、本地持股或特区通道",
        )

    # 9. 售后责任
    if case.get("product_regulated") and not case.get("local_after_sales"):
        add(
            "WARN",
            "AFTER_SALES",
            "受管制产品未见本地售后与备件安排",
            "指定本地服务责任方，写入代理或自设实体方案",
        )

    add(
        "INFO",
        "OFFICIAL_CHECK",
        "所有结论需以 MISA 与行业监管机构最新公告复核",
        "记录检索日期并写入待核实项",
    )

    levels = {f["level"] for f in findings}
    if "BLOCK" in levels:
        verdict = "BLOCKED"
    elif "CONDITION" in levels:
        verdict = "CONDITIONAL"
    else:
        verdict = "GO"

    actions = [f["action"] for f in findings if f["level"] in ("BLOCK", "CONDITION") and f["action"]]
    return {
        "case_id": case.get("case_id", ""),
        "verdict": verdict,
        "can_proceed_to_g2": verdict != "BLOCKED",
        "counts": {
            "block": sum(1 for f in findings if f["level"] == "BLOCK"),
            "condition": sum(1 for f in findings if f["level"] == "CONDITION"),
            "warn": sum(1 for f in findings if f["level"] == "WARN"),
            "info": sum(1 for f in findings if f["level"] == "INFO"),
        },
        "findings": sorted(findings, key=lambda f: LEVEL_ORDER[f["level"]]),
        "required_actions": actions,
        "disclaimer": "结构性规则匹配结果，不构成法律或投资意见；政策条款须以官方最新公告为准。",
    }


def to_markdown(result):
    lines = [
        f"## 准入判定：{result['verdict']}",
        "",
        f"- 案例：{result['case_id'] or '（未命名）'}",
        f"- 可进入 G2：{'是' if result['can_proceed_to_g2'] else '否'}",
        f"- 计数：BLOCK {result['counts']['block']} / CONDITION {result['counts']['condition']}"
        f" / WARN {result['counts']['warn']} / INFO {result['counts']['info']}",
        "",
        "| 级别 | 代码 | 说明 | 动作 |",
        "|---|---|---|---|",
    ]
    for f in result["findings"]:
        lines.append(f"| {f['level']} | {f['code']} | {f['message']} | {f['action']} |")
    lines += ["", f"> {result['disclaimer']}"]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="G1 准入闸门规则引擎")
    ap.add_argument("--input", required=True, help="案例 JSON 文件")
    ap.add_argument("--rules", help="自定义敏感活动清单 JSON")
    ap.add_argument("--format", choices=["json", "md"], default="json")
    args = ap.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as fh:
            case = json.load(fh)
        restricted = load_rules(args.rules)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1

    result = evaluate(case, restricted)
    if args.format == "md":
        print(to_markdown(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["verdict"] != "BLOCKED" else 2


if __name__ == "__main__":
    sys.exit(main())
