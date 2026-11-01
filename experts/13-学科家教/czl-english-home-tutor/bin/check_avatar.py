#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_avatar.py —— 诊断"专家头像显示成文字"的问题。

WorkBuddy 的头像解析规则（依据运行时行为）：
  1. plugin.json 的 avatar 若是 http(s)/data 开头，直接使用；
  2. 否则按"专家根目录 + avatar 相对路径"解析；
  3. 解析后的路径必须仍在专家目录内；
  4. 文件必须真实存在，且不超过 5 MB；
  5. 任一条不满足，头像字段会被置空，界面回退为"姓名首字"的字母块。

本脚本按同一套规则检查，并给出具体修法。

用法：
    python bin/check_avatar.py <专家目录>
    python bin/check_avatar.py <专家目录> --json
"""

import json
import os
import struct
import sys

MAX_AVATAR_BYTES = 5 * 1024 * 1024
MANIFEST_DIRS = (".codebuddy-plugin", ".workbuddy-plugin")
MAGIC = {
    b"\x89PNG\r\n\x1a\n": "png",
    b"\xff\xd8\xff": "jpg",
    b"GIF8": "gif",
    b"RIFF": "webp",
}


def sniff_format(head):
    for sig, name in MAGIC.items():
        if head.startswith(sig):
            return name
    return "unknown"


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(33)
    if not head.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    width, height = struct.unpack(">II", head[16:24])
    return width, height


def load_manifest(root):
    for d in MANIFEST_DIRS:
        p = os.path.join(root, d, "plugin.json")
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                return p, json.load(f)
    return None, None


def check(root):
    root = os.path.abspath(root)
    report = {"expert_dir": root, "ok": True, "checks": [], "fixes": []}

    def add(name, ok, detail):
        report["checks"].append({"check": name, "ok": ok, "detail": detail})
        if not ok:
            report["ok"] = False

    manifest_path, data = load_manifest(root)
    add("plugin.json 存在", manifest_path is not None, manifest_path or "未找到 .codebuddy-plugin/plugin.json")
    if not data:
        report["fixes"].append("确认目录结构：<专家目录>/.codebuddy-plugin/plugin.json")
        return report

    avatar = data.get("avatar") or ""
    add("avatar 字段非空", bool(avatar.strip()), repr(avatar))

    if avatar.strip():
        if avatar.startswith(("http://", "https://", "data:")):
            add("头像类型", True, "远程/内联头像，不走本地解析（离线或 CDN 失效时会回落为文字）")
            if avatar.startswith("http"):
                report["fixes"].append("远程头像在无网或 CDN 鉴权失败时会显示成文字；建议改为本地 avatars/ 相对路径。")
        else:
            rel = avatar[2:] if avatar.startswith("./") else avatar
            add("路径使用正斜杠", "\\" not in avatar, repr(avatar))
            if "\\" in avatar:
                report["fixes"].append("Windows 导出的反斜杠路径在部分环境解析失败，改成 avatars/expert.png。")

            add("不是绝对路径", not os.path.isabs(rel), repr(rel))
            if os.path.isabs(rel):
                report["fixes"].append("绝对路径在新机器上必然失效，改成相对路径。")

            target = os.path.abspath(os.path.join(root, rel))
            inside = target == root or target.startswith(root + os.sep)
            add("头像路径未越出专家目录", inside, target)

            # 大小写一致性：Windows 不区分，平台侧可能区分
            parent = os.path.dirname(target)
            if os.path.isdir(parent):
                actual = os.listdir(parent)
                want = os.path.basename(target)
                add("文件名大小写一致", want in actual,
                    want if want in actual else "%s（目录中实际为：%s）" % (want, ", ".join(sorted(actual)[:6]) or "空"))
                if want not in actual:
                    report["fixes"].append("文件名大小写与声明不一致，在区分大小写的环境会找不到文件。")

            exists = inside and os.path.isfile(target)
            add("头像文件存在", exists, target if exists else target + "（缺失）")
            if not exists:
                report["fixes"].append(
                    "头像文件缺失是最常见原因：确认打包 zip 内包含 avatars/ 目录，"
                    "且 plugin.json 里的文件名与磁盘完全一致（Windows 不区分大小写，平台可能区分）。"
                )
            else:
                size = os.path.getsize(target)
                add("头像体积 ≤ 5MB", size <= MAX_AVATAR_BYTES, "%.1f KB" % (size / 1024))
                if size > MAX_AVATAR_BYTES:
                    report["fixes"].append("头像超过 5MB 会被拒绝，用 bin/prepare_avatar.py 压到 512×512 / ≤400KB。")

                with open(target, "rb") as f:
                    fmt = sniff_format(f.read(16))
                add("头像格式可识别", fmt != "unknown", fmt)
                if fmt == "unknown":
                    report["fixes"].append("扩展名与实际编码不符时解码会失败，重新导出为 PNG。")

                if fmt == "png":
                    wh = png_size(target)
                    add("PNG 可读出尺寸", wh is not None, "×".join(map(str, wh)) if wh else "无法解析 IHDR")
                    if wh:
                        add("头像为正方形", wh[0] == wh[1], "%d×%d" % wh)
                        if wh[0] != wh[1]:
                            report["fixes"].append("非正方形会被裁切或留白，建议 512×512。")

    agents = data.get("agents") or []
    for a in agents:
        rel = a[2:] if a.startswith("./") else a
        add("agent 文件存在", os.path.isfile(os.path.join(root, rel)), rel)

    for s in data.get("skills") or []:
        rel = s[2:] if s.startswith("./") else s
        add("skill 含 SKILL.md", os.path.isfile(os.path.join(root, rel, "SKILL.md")), rel)

    if data.get("categoryId", "").startswith("15-"):
        report["checks"].append({
            "check": "categoryId",
            "ok": True,
            "detail": data["categoryId"] + "（平台侧教育分类；本地校验脚本的分类表可能未收录，属已知差异）",
        })

    return report


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    root = sys.argv[1]
    as_json = "--json" in sys.argv
    report = check(root)

    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1

    print("专家目录：%s" % report["expert_dir"])
    print("-" * 56)
    for c in report["checks"]:
        print(("  [OK]   " if c["ok"] else "  [FAIL] ") + c["check"] + "：" + str(c["detail"]))
    print("-" * 56)
    if report["ok"]:
        print("结论：头像与资源引用均通过检查，界面应显示图片而非文字。")
        return 0
    print("结论：存在会导致头像回落为文字的问题。")
    for i, fix in enumerate(report["fixes"], 1):
        print("  修法 %d：%s" % (i, fix))
    return 1


if __name__ == "__main__":
    sys.exit(main())
