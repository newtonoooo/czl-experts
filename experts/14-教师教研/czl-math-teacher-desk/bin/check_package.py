#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_package.py —— 专家包自检（纯标准库，零依赖）。

检查三件事：
    1. 元数据：plugin.json 该有的字段齐不齐、数量对不对、占位符清没清。
    2. 引用：agents / skills / avatar 指向的文件真的存在吗，路径写法在别的机器上还成立吗。
    3. 头像：这是"导入新环境后头像变成文字"的最高频原因，按运行时规则逐条验。

头像为什么会变成文字（运行时行为）：
    avatar 字段若不是 http(s)/data 开头，就按"专家根目录 + 相对路径"解析；
    路径必须仍在专家目录内、文件必须真实存在、体积必须 ≤5MB；
    任一条不满足，头像字段被置空，界面回退成"姓名首字"的字母块。
    另外：反斜杠路径、绝对路径、大小写不一致、外链 CDN 失效，都会导致同样的结果。

用法：
    python bin/check_package.py .
    python bin/check_package.py . --json

退出码：0 通过；1 有错误。
"""

import json
import os
import struct
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

MANIFEST_DIRS = (".codebuddy-plugin", ".workbuddy-plugin")
MAX_AVATAR_RUNTIME = 5 * 1024 * 1024      # 运行时上限（超出会被置空）
AVATAR_ADVISED = 500 * 1024               # 建议上限（开放平台上传更保守）
MAGIC = {
    b"\x89PNG\r\n\x1a\n": "png",
    b"\xff\xd8\xff": "jpg",
    b"GIF8": "gif",
    b"RIFF": "webp",
}


def sniff(head):
    for sig, name in MAGIC.items():
        if head.startswith(sig):
            return name
    return "unknown"


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(33)
    if not head.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    w, h = struct.unpack(">II", head[16:24])
    return w, h


class Report:
    def __init__(self):
        self.rows = []
        self.errors = 0
        self.warns = 0

    def ok(self, name, detail=""):
        self.rows.append(("OK", name, detail))

    def fail(self, name, detail=""):
        self.rows.append(("FAIL", name, detail))
        self.errors += 1

    def warn(self, name, detail=""):
        self.rows.append(("WARN", name, detail))
        self.warns += 1

    def dump(self, as_json=False):
        if as_json:
            print(json.dumps([{"level": l, "check": n, "detail": d} for l, n, d in self.rows],
                             ensure_ascii=False, indent=2))
            return
        for level, name, detail in self.rows:
            tag = {"OK": "[OK]  ", "WARN": "[警告]", "FAIL": "[FAIL]"}[level]
            print("%s %s%s" % (tag, name, ("：" + str(detail)) if detail else ""))


def main():
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
    as_json = "--json" in sys.argv
    rep = Report()

    manifest = None
    for d in MANIFEST_DIRS:
        p = os.path.join(root, d, "plugin.json")
        if os.path.isfile(p):
            manifest = p
            break
    if not manifest:
        print("❌ 找不到 .codebuddy-plugin/plugin.json")
        sys.exit(1)
    rep.ok("清单文件", os.path.relpath(manifest, root))

    with open(manifest, encoding="utf-8") as f:
        data = json.load(f)
    rep.ok("JSON 可解析", "version %s" % data.get("version", "?"))

    raw = json.dumps(data, ensure_ascii=False)
    if "[TODO" in raw:
        rep.fail("占位符", "plugin.json 中仍有 [TODO]")

    for field in ("name", "version", "description", "author", "agents", "expertType",
                  "agentName", "displayName", "profession", "displayDescription",
                  "avatar", "categoryId", "defaultInitPrompt", "plugin", "tags", "quickPrompts"):
        if field not in data:
            rep.fail("字段 %s" % field, "缺失")
    rep.ok("必填字段", "已检查 16 项")

    if data.get("plugin") != data.get("name"):
        rep.fail("plugin 与 name 一致", "%s ≠ %s" % (data.get("plugin"), data.get("name")))

    for key in ("displayName", "profession", "displayDescription", "defaultInitPrompt"):
        v = data.get(key)
        if not isinstance(v, dict) or not v.get("zh") or not v.get("en"):
            rep.fail("双语字段 %s" % key, "缺 zh 或 en")

    dd = (data.get("displayDescription") or {}).get("zh", "")
    n = len(dd)
    if 40 <= n <= 50:
        rep.ok("displayDescription 字数", "%d 字（要求 40–50）" % n)
    else:
        rep.warn("displayDescription 字数", "%d 字，规范要求 40–50 字" % n)

    tags = data.get("tags") or []
    qp = data.get("quickPrompts") or []
    rep.ok("tags 数量", "%d" % len(tags)) if len(tags) == 3 else rep.fail("tags 数量", "应为 3，实际 %d" % len(tags))
    rep.ok("quickPrompts 数量", "%d" % len(qp)) if len(qp) == 3 else rep.fail("quickPrompts 数量", "应为 3，实际 %d" % len(qp))
    if qp and isinstance(qp[0], dict):
        if qp[0].get("zh") != (data.get("defaultInitPrompt") or {}).get("zh"):
            rep.fail("defaultInitPrompt 一致", "应等于 quickPrompts[0]")
        else:
            rep.ok("defaultInitPrompt 一致", "等于 quickPrompts[0]")

    # agents
    agents = data.get("agents") or []
    for a in agents:
        rel = a[2:] if a.startswith("./") else a
        p = os.path.join(root, rel)
        if os.path.isfile(p):
            rep.ok("agent 文件", rel)
        else:
            rep.fail("agent 文件", "%s 不存在" % rel)
    if agents:
        stem = os.path.splitext(os.path.basename(agents[0]))[0]
        if stem != data.get("agentName"):
            rep.fail("agentName 与文件名一致", "%s ≠ %s" % (data.get("agentName"), stem))
        else:
            rep.ok("agentName 与文件名一致", stem)

    # skills
    skills = data.get("skills") or []
    for s in skills:
        rel = s[2:] if s.startswith("./") else s
        p = os.path.join(root, rel, "SKILL.md")
        if os.path.isfile(p):
            rep.ok("skill", rel)
        else:
            rep.fail("skill", "%s 缺 SKILL.md" % rel)
    if skills:
        rep.ok("skills 数量", "%d 个" % len(skills))

    # avatar —— 重点
    avatar = (data.get("avatar") or "").strip()
    if not avatar:
        rep.fail("avatar 字段", "为空")
    elif avatar.startswith(("http://", "https://", "data:")):
        rep.warn("avatar 类型", "外链头像，离线或 CDN 失效时会回落成文字")
    else:
        if "\\" in avatar:
            rep.fail("avatar 路径分隔符", "含反斜杠，跨平台解析会失败")
        if os.path.isabs(avatar):
            rep.fail("avatar 路径", "绝对路径在新机器上必然失效")
        rel = avatar[2:] if avatar.startswith("./") else avatar
        target = os.path.abspath(os.path.join(root, rel))
        if not (target == root or target.startswith(root + os.sep)):
            rep.fail("avatar 越界", target)
        else:
            parent = os.path.dirname(target)
            want = os.path.basename(target)
            if os.path.isdir(parent):
                actual = os.listdir(parent)
                if want in actual:
                    rep.ok("avatar 文件名大小写", want)
                else:
                    rep.fail("avatar 文件名大小写",
                             "声明 %s，目录中实际：%s" % (want, "、".join(sorted(actual)[:5]) or "空"))
            if os.path.isfile(target):
                size = os.path.getsize(target)
                if size <= MAX_AVATAR_RUNTIME:
                    rep.ok("avatar 存在且不超 5MB", "%.1f KB" % (size / 1024))
                else:
                    rep.fail("avatar 体积", "%.1f MB，超过 5MB 会被置空" % (size / 1048576))
                if size > AVATAR_ADVISED:
                    rep.warn("avatar 体积偏大", "%.1f KB，建议压到 500KB 以内（开放平台上传更保守）"
                             % (size / 1024))
                with open(target, "rb") as f:
                    fmt = sniff(f.read(16))
                if fmt == "unknown":
                    rep.fail("avatar 格式", "无法识别编码，可能是改了扩展名")
                else:
                    rep.ok("avatar 格式", fmt)
                if fmt == "png":
                    wh = png_size(target)
                    if wh:
                        rep.ok("avatar 尺寸", "%d×%d" % wh)
                        if wh[0] != wh[1]:
                            rep.warn("avatar 非正方形", "%d×%d" % wh)
                        if wh[0] > 1024:
                            rep.warn("avatar 尺寸偏大", "%d×%d，市场展示 512×512 足够" % wh)
            else:
                rep.fail("avatar 文件存在", "%s 缺失——这是头像变成文字的第一原因" % rel)

    # 目录清单
    count = 0
    for _dirpath, _dirnames, filenames in os.walk(root):
        count += len(filenames)
    rep.ok("文件总数", "%d 个" % count)

    rep.dump(as_json)
    if not as_json:
        print("-" * 56)
        print("错误 %d 项，警告 %d 项。" % (rep.errors, rep.warns))
    sys.exit(1 if rep.errors else 0)


if __name__ == "__main__":
    main()
