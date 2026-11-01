#!/usr/bin/env python3
"""package.py - build the distributable zip.

Layout matters as much as content: the archive root must be a single folder
named exactly like `plugin.json.name`. One extra nesting level and the client
resolves `avatars/expert.png` one directory too deep, the expert still imports,
and the avatar silently falls back to a letter.

    python tools/package.py                # -> dist/czl-math-home-tutor-1.0.0.zip
    python tools/tools/package.py --check   # fail if the checks fail

Exit codes: 0 built, 1 check failed, 2 bad input.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCLUDE_DIRS = {"dist", "__pycache__", ".git", "_build", "node_modules", ".idea"}
EXCLUDE_FILES = {".DS_Store", "Thumbs.db", ".downloaded_at", ".created-by-session"}
# docs/ is shipped: a commercial package should carry its own spec, changelog,
# risk list and test report. dist/ is not, to avoid nesting a zip inside a zip.


def read_version():
    with open(os.path.join(ROOT, ".codebuddy-plugin", "plugin.json"),
              encoding="utf-8") as fh:
        data = json.load(fh)
    return data["name"], data.get("version", "0.0.0")


def build(out_dir, run_check):
    name, version = read_version()
    if run_check:
        proc = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "check_package.py")],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            print(proc.stdout)
            print("ERROR: package check failed, refusing to build", file=sys.stderr)
            return None
        print(proc.stdout.strip().splitlines()[-1])

    os.makedirs(out_dir, exist_ok=True)
    target = os.path.join(out_dir, "%s-%s.zip" % (name, version))
    count = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for base, dirs, files in os.walk(ROOT):
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS)
            for f in sorted(files):
                if f in EXCLUDE_FILES:
                    continue
                full = os.path.join(base, f)
                rel = os.path.relpath(full, ROOT)
                # single top-level folder, named exactly like the package
                arc = os.path.join(name, rel).replace("\\", "/")
                zf.write(full, arc)
                count += 1

    size = os.path.getsize(target)
    digest = hashlib.sha256(open(target, "rb").read()).hexdigest()
    print("\nbuilt  : %s" % target)
    print("files  : %d" % count)
    print("size   : %.1f KB" % (size / 1024))
    print("sha256 : %s" % digest)

    with zipfile.ZipFile(target) as zf:
        names = zf.namelist()
    top = {n.split("/")[0] for n in names}
    print("top-level entries: %s" % ", ".join(sorted(top)))
    assert top == {name}, "archive must contain exactly one top folder named %r" % name
    must = ["%s/.codebuddy-plugin/plugin.json" % name,
            "%s/agents/%s.md" % (name, name),
            "%s/avatars/expert.png" % name]
    for m in must:
        status = "ok" if m in names else "MISSING"
        print("  %-8s %s" % (status, m))
        if m not in names:
            return None
    return target


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build the distributable zip.")
    ap.add_argument("--out", default=os.path.join(ROOT, "dist"))
    ap.add_argument("--no-check", action="store_true", help="skip check_package.py")
    args = ap.parse_args(argv)
    result = build(args.out, not args.no_check)
    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())
