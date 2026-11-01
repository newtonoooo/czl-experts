#!/usr/bin/env python3
"""install.py - install this expert into the local WorkBuddy expert directory.

Why a script instead of "copy the folder somewhere": a local expert's avatar is
resolved by the client to a `local-file://` URL built from the *registered*
directory. Copy the package to the wrong place, or register it under a different
folder name, and the expert still loads but the picture falls back to a letter.
This script puts the files where the loader looks, registers the entry, and then
reads the result back to prove the avatar path resolves.

    python tools/install.py --dry-run      # show what would happen
    python tools/install.py                # do it
    python tools/install.py --dest D:/wb/plugins/marketplaces/my-experts

Exit codes: 0 installed, 1 failed a post-check, 2 bad input.
"""

import argparse
import json
import os
import shutil
import sys

SKIP_DIRS = {"dist", "__pycache__", "_build", ".git", "node_modules"}
SKIP_FILES = {".DS_Store", "Thumbs.db"}


def config_dir():
    env = os.environ.get("WORKBUDDY_CONFIG_DIR", "").strip()
    return env or os.path.join(os.path.expanduser("~"), ".workbuddy")


def read_plugin(root):
    path = os.path.join(root, ".codebuddy-plugin", "plugin.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def copy_tree(src, dst, dry):
    copied = 0
    for base, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel = os.path.relpath(base, src)
        target_dir = dst if rel == "." else os.path.join(dst, rel)
        if not dry:
            os.makedirs(target_dir, exist_ok=True)
        for name in files:
            if name in SKIP_FILES:
                continue
            s = os.path.join(base, name)
            t = os.path.join(target_dir, name)
            if not dry:
                shutil.copy2(s, t)
            copied += 1
    return copied


def upsert_manifest(marketplace, entry, dry):
    path = os.path.join(marketplace, ".codebuddy-plugin", "marketplace.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    else:
        data = {"name": os.path.basename(marketplace),
                "description": "my-experts marketplace (auto-generated)",
                "plugins": []}
    plugins = data.setdefault("plugins", [])
    for item in plugins:
        if item.get("name") == entry["name"] or item.get("source") == entry["source"]:
            item.update(entry)
            action = "updated"
            break
    else:
        plugins.append(entry)
        action = "added"
    if not dry:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
    return action, path


def manifest_has(path, name):
    """True if the marketplace entry for `name` is on disk right now."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return False
    return any(p.get("name") == name for p in data.get("plugins", []))


def ensure_manifest(marketplace, entry, dry, attempts=3):
    """Upsert the entry and re-read until it sticks.

    WorkBuddy watches this file and rewrites it when plugin directories come and
    go. Deleting the target directory (which the copy step does) can therefore
    race with our write: we add the entry, the watcher rewrites from its own
    model and drops it. Writing again after the copy has settled makes the
    result converge. Verifying beats assuming.
    """
    action, path = upsert_manifest(marketplace, entry, dry)
    if dry:
        return action, path, True
    for _ in range(attempts):
        if manifest_has(path, entry["name"]):
            return action, path, True
        upsert_manifest(marketplace, entry, False)
    return action, path, manifest_has(path, entry["name"])


def main(argv=None):
    ap = argparse.ArgumentParser(description="Install this expert locally.")
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    ap.add_argument("--dest", help="marketplace dir (default: "
                                   "WORKBUDDY_CONFIG_DIR/plugins/marketplaces/my-experts)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)
    try:
        plugin = read_plugin(root)
    except (OSError, json.JSONDecodeError) as exc:
        print("ERROR: cannot read plugin.json: %s" % exc, file=sys.stderr)
        return 2

    name = plugin.get("name") or os.path.basename(root)
    marketplace = args.dest or os.path.join(
        config_dir(), "plugins", "marketplaces", "my-experts")
    target = os.path.join(marketplace, "plugins", name)

    print("source : %s" % root)
    print("target : %s" % target)
    print("mode   : %s\n" % ("dry-run" if args.dry_run else "install"))

    if os.path.exists(target) and os.path.samefile(root, target):
        print("Package is already in place; skipping the copy.")
        copied = 0
    else:
        if os.path.exists(target) and not args.dry_run:
            shutil.rmtree(target)
        copied = copy_tree(root, target, args.dry_run)
        print("copied %d files" % copied)

    entry = {
        "name": name,
        "source": "./plugins/%s" % name,
        "description": plugin.get("description", ""),
        "version": plugin.get("version", ""),
    }
    action, manifest, settled = ensure_manifest(marketplace, entry, args.dry_run)
    print("marketplace.json %s: %s" % (action, manifest))
    print("entry in manifest: %s" % ("verified" if settled else "NOT PERSISTED"))
    if not settled:
        print("  the app may be rewriting this file; re-run install or add the "
              "entry by hand (see README, 方式 C)")

    # read the result back - this is the part that catches the silent failure
    check_root = root if args.dry_run else target
    avatar_rel = plugin.get("avatar", "")
    avatar_abs = os.path.join(check_root, avatar_rel)
    print("\npost-check%s" % (" (against source; nothing was copied)" if args.dry_run else ""))
    ok = True
    if os.path.exists(avatar_abs):
        size = os.path.getsize(avatar_abs)
        print("  avatar      : %s (%.0f KB)" % (avatar_abs, size / 1024))
        print("  resolved as : local-file://local/%s"
              % os.path.join(target, avatar_rel).replace("\\", "/").replace(":", "%3A"))
    else:
        ok = False
        print("  avatar      : MISSING at %s" % avatar_abs)
    for rel in plugin.get("agents", []):
        p = os.path.join(check_root, rel[2:] if rel.startswith("./") else rel)
        print("  agent       : %s %s" % ("ok" if os.path.exists(p) else "MISSING", p))
        ok &= os.path.exists(p)
    for rel in plugin.get("skills", []):
        p = os.path.join(check_root, rel[2:] if rel.startswith("./") else rel, "SKILL.md")
        print("  skill       : %s %s" % ("ok" if os.path.exists(p) else "MISSING", p))
        ok &= os.path.exists(p)

    print("\n%s" % ("Done. Restart WorkBuddy, then pick the expert under "
                    "专家中心 - 我的专家." if ok else "Post-check failed; do not ship."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
