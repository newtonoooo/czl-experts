#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
发布包构建脚本（纯标准库）

流程：
  1. 按平台导出规则收集文件（同样的跳过清单），排除本地开发目录 dev/
  2. 以 <包名>/ 为 zip 根目录写入，条目名统一使用正斜杠
  3. 重新读取 zip，模拟平台的 resolveAvatarFromExpertZip 解析头像
  4. 输出条目清单、大小、SHA256

用法：
  python dev/build_package.py <专家包目录> [输出目录]
"""

import hashlib
import json
import os
import sys
import zipfile

# 与平台 collectExpertPackageEntries 的跳过规则保持一致
SKIP_NAMES = {
    ".DS_Store", ".created-by-session", ".pending-preview-session",
    "node_modules", ".git", ".cache", "cache", "storage", "history",
    "logs", "tmp", "temp", "__pycache__",
}
SKIP_SUFFIX = (".log", ".tmp", ".zip", ".pyc")
# 本项目额外排除：本地开发工具与交付文档，不进发布包（随 zip 一并交付，但不装入专家）
LOCAL_ONLY = {"dev", "docs"}

CONTAINER_DIRS = [".codebuddy-plugin", ".workbuddy-plugin"]


def collect(root, zip_root):
    entries = []
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs
                         if d not in SKIP_NAMES and d not in LOCAL_ONLY and not d.startswith(".git"))
        for name in sorted(files):
            if name in SKIP_NAMES or name.endswith(SKIP_SUFFIX):
                continue
            full = os.path.join(base, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            entries.append(("{}/{}".format(zip_root, rel), full))
    entries.sort(key=lambda x: x[0])
    return entries


def build(pkg_dir, out_dir=None):
    pkg_dir = os.path.abspath(pkg_dir)
    pkg_name = os.path.basename(pkg_dir)

    manifest_path = None
    for c in CONTAINER_DIRS:
        cand = os.path.join(pkg_dir, c, "plugin.json")
        if os.path.isfile(cand):
            manifest_path = cand
            break
    if not manifest_path:
        print("找不到 .codebuddy-plugin/plugin.json，无法打包")
        return 1
    manifest = json.loads(open(manifest_path, encoding="utf-8").read())
    version = manifest.get("version", "0.0.0")

    out_dir = os.path.abspath(out_dir or os.path.join(pkg_dir, "dist"))
    os.makedirs(out_dir, exist_ok=True)
    zip_path = os.path.join(out_dir, "{}-v{}.zip".format(pkg_name, version))

    entries = collect(pkg_dir, pkg_name)

    def write_all(zf, with_shim):
        for name, full in entries:
            zf.write(full, name)
        if with_shim:
            shim = "name: {}\nversion: \"{}\"\ntype: expert\n".format(pkg_name, version)
            # 固定时间戳，保证同一份源码重复打包得到相同的 SHA256
            info = zipfile.ZipInfo("{}/manifest.yaml".format(pkg_name),
                                   date_time=(2026, 10, 28, 0, 0, 0))
            info.external_attr = 0o644 << 16
            zf.writestr(info, shim)

    need_shim = not any(e[0].endswith("/manifest.yaml") for e in entries)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        write_all(zf, need_shim)

    print("=" * 72)
    print("构建发布包")
    print("=" * 72)
    print("输出：{}".format(zip_path))
    print("条目：{} 个文件".format(len(entries)))
    print("大小：{:.1f} KB".format(os.path.getsize(zip_path) / 1024.0))

    ok = verify(zip_path, pkg_name)
    digest = hashlib.sha256(open(zip_path, "rb").read()).hexdigest()
    print("SHA256：{}".format(digest))
    return 0 if ok else 1


def verify(zip_path, pkg_name):
    """模拟平台导入时的解析过程。"""
    print("-" * 72)
    print("包内校验")
    print("-" * 72)
    checks = []

    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]

        checks.append((all(n.startswith(pkg_name + "/") for n in names),
                       "所有条目位于 {}/ 根目录下".format(pkg_name),
                       "{} 个文件".format(len(names))))

        # 平台逻辑：按后缀找 */<container>/plugin.json，取前缀作为根
        prefix = None
        container = None
        for n in names:
            for c in CONTAINER_DIRS:
                if n.endswith("{}/plugin.json".format(c)):
                    prefix = n[: -len("{}/plugin.json".format(c))]
                    container = c
                    break
            if prefix is not None:
                break
        checks.append((prefix is not None, "能定位到 plugin.json", str(prefix)))
        if prefix is None:
            return report(checks)

        manifest = json.loads(
            zf.read("{}{}/plugin.json".format(prefix, container)).decode("utf-8"))

        # 头像解析：先 <prefix>/<avatar>，再 <avatar>
        avatar = str(manifest.get("avatar", ""))
        rel = avatar[2:] if avatar.startswith("./") else avatar.lstrip("/")
        found = None
        for cand in ("{}{}".format(prefix, rel), rel):
            if cand in names:
                found = cand
                break
        checks.append((bool(found), "头像可按平台规则解析", "{} → {}".format(avatar, found)))
        if found:
            data = zf.read(found)
            checks.append((len(data) > 1024, "头像数据非空", "{} bytes".format(len(data))))

        for rel_path in manifest.get("agents", []):
            target = prefix + rel_path.replace("./", "", 1)
            checks.append((target in names, "agent 文件在包内", target))

        for rel_path in manifest.get("skills", []):
            target = prefix + rel_path.replace("./", "", 1) + "/SKILL.md"
            checks.append((target in names, "SKILL.md 在包内", target))

        script = prefix + "skills/czl-taxops-pipeline/scripts/toolkit.py"
        checks.append((script in names, "计算工具在包内", script))

        checks.append((prefix + "manifest.yaml" in names, "含 manifest.yaml", "兼容 YAML 读取方"))

        # 确认没有把本地开发目录打进去
        no_local = not any(("/dev/" in n or "/docs/" in n) for n in names)
        checks.append((no_local, "未包含 dev/ 与 docs/（本地工具与交付文档）", ""))

        total_kb = sum(zf.getinfo(n).file_size for n in names) / 1024.0
        checks.append((total_kb < 5120, "解压后总大小 < 5MB", "{:.1f} KB".format(total_kb)))

    return report(checks)


def report(checks):
    passed = 0
    for ok, label, detail in checks:
        print("[{}] {:<34}{}".format("PASS" if ok else "FAIL", label, detail))
        passed += 1 if ok else 0
    print("-" * 72)
    print("包内校验：{}/{} 通过".format(passed, len(checks)))
    return passed == len(checks)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python dev/build_package.py <package_dir> [out_dir]")
        raise SystemExit(1)
    raise SystemExit(build(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
