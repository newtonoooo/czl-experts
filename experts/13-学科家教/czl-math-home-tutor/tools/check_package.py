#!/usr/bin/env python3
"""check_package.py - pre-flight check for a WorkBuddy expert package.

Run this before every upload. It checks the things that silently break an
import: a mismatched agentName, a tag list of four, an avatar that is 501 KB,
a skill directory the manifest points at but which is not there.

    python tools/check_package.py
    python tools/check_package.py --root path/to/czl-math-home-tutor
    python tools/check_package.py --verbose

Exit codes: 0 all pass (warnings allowed), 1 one or more failures, 2 could not run.

Why the avatar check is fussy
-----------------------------
A package can import cleanly, show the right name and prompt, and still render
a letter instead of a picture. The client resolves a local expert's avatar to a
`local-file://` URL built from the *registered directory*, so the three ways it
goes wrong are: path in plugin.json does not match the file, file is not really
a PNG (an image saved as .png but encoded as JPEG), or the file is over the size
or dimension the renderer accepts. All three are mechanical and all three are
checked here.
"""

import argparse
import json
import os
import re
import struct
import sys

REQUIRED_FIELDS = ["name", "version", "description", "agents", "expertType",
                   "agentName", "displayName", "profession", "displayDescription",
                   "avatar", "categoryId", "defaultInitPrompt", "plugin", "tags",
                   "quickPrompts"]
AVATAR_MAX_BYTES = 500 * 1024
AVATAR_SIZE = (512, 512)
VALID_CATEGORIES = {
    "01-ProductDesign", "02-Engineering", "03-GameSpatial", "04-DataAI",
    "05-MarketingGrowth", "06-ContentCreative", "07-SalesCommerce",
    "08-FinanceInvestment", "09-OperationsHR", "10-ProjectQuality",
    "11-SecurityCompliance", "12-IndustryConsultant", "15-Education",
}


class Report:
    def __init__(self, verbose=False):
        self.rows = []
        self.verbose = verbose

    def add(self, level, code, message):
        self.rows.append((level, code, message))

    def ok(self, code, message):
        if self.verbose:
            self.add("PASS", code, message)

    def fail(self, code, message):
        self.add("FAIL", code, message)

    def warn(self, code, message):
        self.add("WARN", code, message)

    def counts(self):
        c = {"PASS": 0, "FAIL": 0, "WARN": 0}
        for level, _c, _m in self.rows:
            c[level] = c.get(level, 0) + 1
        return c

    def dump(self):
        marks = {"PASS": "  ok  ", "FAIL": " FAIL ", "WARN": " WARN "}
        for level, code, message in self.rows:
            print("[%s] %-18s %s" % (marks[level], code, message))
        c = self.counts()
        print("\n%d failed, %d warnings, %d passed checks"
              % (c["FAIL"], c["WARN"], c["PASS"]))


def png_info(path):
    """Return dict(width, height, bit_depth, colour_type) or raise ValueError."""
    with open(path, "rb") as fh:
        head = fh.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG (signature mismatch) - likely a JPEG or WebP "
                         "saved with a .png extension")
    if head[12:16] != b"IHDR":
        raise ValueError("missing IHDR")
    w, h, depth, colour = struct.unpack(">IIBB", head[16:26])
    return {"width": w, "height": h, "bit_depth": depth, "colour_type": colour}


def check_avatar(root, data, rep):
    rel = data.get("avatar", "")
    if not rel:
        rep.fail("avatar.field", "plugin.json has no avatar field")
        return
    if rel.startswith("/") or re.match(r"^[A-Za-z]:", rel):
        rep.fail("avatar.absolute", "avatar must be a package-relative path, got %r" % rel)
        return
    if rel.startswith("./"):
        rep.warn("avatar.dot", "leading './' is tolerated but the documented form "
                               "is 'avatars/expert.png'; normalise it if the client "
                               "fails to resolve the file")
    path = os.path.join(root, rel)
    if not os.path.exists(path):
        rep.fail("avatar.missing", "declared avatar %r does not exist in the package" % rel)
        return
    rep.ok("avatar.exists", rel)
    size = os.path.getsize(path)
    if size > AVATAR_MAX_BYTES:
        rep.fail("avatar.size", "%s is %.0f KB, over the 500 KB cap"
                 % (rel, size / 1024))
    else:
        rep.ok("avatar.size", "%.0f KB" % (size / 1024))
    try:
        info = png_info(path)
    except ValueError as exc:
        rep.fail("avatar.format", "%s: %s" % (rel, exc))
        return
    if (info["width"], info["height"]) != AVATAR_SIZE:
        rep.fail("avatar.dimensions", "%s is %dx%d, expected 512x512"
                 % (rel, info["width"], info["height"]))
    else:
        rep.ok("avatar.dimensions", "512x512")
    if info["colour_type"] not in (2, 6, 3):
        rep.warn("avatar.colour", "colour type %d is unusual for an avatar; "
                                  "RGB (2) is the safest" % info["colour_type"])


def check_plugin_json(root, rep):
    path = os.path.join(root, ".codebuddy-plugin", "plugin.json")
    if not os.path.exists(path):
        rep.fail("json.missing", ".codebuddy-plugin/plugin.json not found")
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        rep.fail("json.invalid", "cannot parse plugin.json: %s" % exc)
        return None

    raw = open(path, encoding="utf-8").read()
    if "[TODO" in raw:
        rep.fail("json.todo", "plugin.json still contains [TODO] placeholders")

    for field in REQUIRED_FIELDS:
        if field not in data or data[field] in ("", None, [], {}):
            rep.fail("json.field", "missing required field %r" % field)
        else:
            rep.ok("json.field", field)

    name = data.get("name", "")
    if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name):
        rep.fail("json.name", "name %r is not kebab-case" % name)
    if data.get("plugin") != name:
        rep.fail("json.plugin", "plugin (%r) must equal name (%r)"
                 % (data.get("plugin"), name))
    if name != os.path.basename(root.rstrip("\\/")):
        rep.warn("json.dirname", "directory %r differs from name %r; the loader "
                                 "keys the entry by directory, keep them equal"
                 % (os.path.basename(root.rstrip("\\/")), name))

    version = data.get("version", "")
    if not re.match(r"^\d+\.\d+\.\d+", str(version)):
        rep.fail("json.version", "version %r is not semver" % version)

    cat = data.get("categoryId", "")
    if cat not in VALID_CATEGORIES:
        rep.warn("json.category", "categoryId %r is not in the known list" % cat)

    for key in ("displayName", "profession", "displayDescription", "defaultInitPrompt"):
        val = data.get(key)
        if not isinstance(val, dict) or not val.get("zh") or not val.get("en"):
            rep.fail("json.i18n", "%s needs both zh and en" % key)

    desc = (data.get("displayDescription") or {}).get("zh", "")
    n = len(desc)
    if n < 40 or n > 50:
        rep.warn("json.desc", "displayDescription.zh is %d chars; the spec asks for "
                              "40-50" % n)

    tags = data.get("tags") or []
    if len(tags) != 3:
        rep.fail("json.tags", "tags must have exactly 3 items, found %d" % len(tags))
    qp = data.get("quickPrompts") or []
    if len(qp) != 3:
        rep.fail("json.prompts", "quickPrompts must have exactly 3 items, found %d"
                 % len(qp))
    dip = (data.get("defaultInitPrompt") or {}).get("zh")
    if qp and dip and qp[0].get("zh") != dip:
        rep.fail("json.initprompt",
                 "defaultInitPrompt.zh must equal quickPrompts[0].zh")

    for i, item in enumerate(tags + qp):
        if not isinstance(item, dict) or not item.get("zh") or not item.get("en"):
            rep.fail("json.i18nitem", "tags/quickPrompts item %d needs zh and en" % i)
    return data


def check_agents(root, data, rep):
    declared = data.get("agents") or []
    if not declared:
        rep.fail("agent.empty", "agents[] is empty")
        return
    for rel in declared:
        clean = rel[2:] if rel.startswith("./") else rel
        path = os.path.join(root, clean)
        if not os.path.exists(path):
            rep.fail("agent.missing", "declared agent %r not found" % rel)
            continue
        rep.ok("agent.exists", clean)
        text = open(path, encoding="utf-8").read()
        if "[TODO" in text:
            rep.fail("agent.todo", "%s still contains [TODO]" % clean)
        if not text.startswith("---"):
            rep.fail("agent.frontmatter", "%s does not start with YAML frontmatter"
                     % clean)
            continue
        fm = text.split("---", 2)[1] if text.count("---") >= 2 else ""
        if re.search(r"^\s*tools\s*:", fm, re.M):
            rep.fail("agent.tools", "%s declares a tools field; tool access is "
                                    "assigned by the platform" % clean)
        m = re.search(r"^name:\s*(\S+)", fm, re.M)
        stem = os.path.splitext(os.path.basename(clean))[0]
        if not m:
            rep.fail("agent.name", "%s has no name in frontmatter" % clean)
        elif m.group(1).strip() != stem:
            rep.fail("agent.name", "frontmatter name %r != filename %r"
                     % (m.group(1).strip(), stem))
        if data.get("agentName") and data["agentName"] != stem:
            rep.fail("agent.agentName", "agentName %r != agent filename %r"
                     % (data["agentName"], stem))
        if len(text) < 1500:
            rep.warn("agent.thin", "%s is only %d chars; a usable prompt is usually "
                                   "much longer" % (clean, len(text)))


def check_skills(root, data, rep):
    declared = data.get("skills") or []
    if not declared:
        rep.warn("skill.none", "no skills declared - fine for a prompt-only expert")
        return
    on_disk = set()
    skills_dir = os.path.join(root, "skills")
    if os.path.isdir(skills_dir):
        on_disk = {d for d in os.listdir(skills_dir)
                   if os.path.isdir(os.path.join(skills_dir, d))}
    for rel in declared:
        clean = rel[2:] if rel.startswith("./") else rel
        path = os.path.join(root, clean)
        skill_md = os.path.join(path, "SKILL.md")
        if not os.path.exists(skill_md):
            rep.fail("skill.missing", "declared skill %r has no SKILL.md" % rel)
            continue
        rep.ok("skill.exists", clean)
        head = open(skill_md, encoding="utf-8").read(600)
        m = re.search(r"^name:\s*(\S+)", head, re.M)
        if not m:
            rep.fail("skill.name", "%s/SKILL.md has no name in frontmatter" % clean)
        elif m.group(1).strip() != os.path.basename(clean):
            rep.fail("skill.name", "%s/SKILL.md name %r != directory name"
                     % (clean, m.group(1).strip()))
        if "description:" not in head:
            rep.fail("skill.description", "%s/SKILL.md has no description" % clean)
    extra = on_disk - {os.path.basename((r[2:] if r.startswith("./") else r))
                       for r in declared}
    for name in sorted(extra):
        rep.warn("skill.undeclared", "skills/%s exists but is not declared in "
                                     "plugin.json" % name)


def check_scripts(root, rep):
    scripts = []
    for base, _dirs, files in os.walk(root):
        for f in files:
            if f.endswith(".py"):
                scripts.append(os.path.join(base, f))
    if not scripts:
        rep.warn("scripts.none", "no Python scripts in the package")
        return
    for path in scripts:
        rel = os.path.relpath(path, root)
        try:
            compile(open(path, encoding="utf-8").read(), path, "exec")
        except SyntaxError as exc:
            rep.fail("script.syntax", "%s: line %s: %s" % (rel, exc.lineno, exc.msg))
        else:
            rep.ok("script.syntax", rel)


def check_docs(root, rep):
    for name in ("README.md", "CHANGELOG.md", "LICENSE"):
        if os.path.exists(os.path.join(root, name)):
            rep.ok("docs.file", name)
        else:
            rep.warn("docs.missing", "%s not found" % name)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pre-flight check for an expert package.")
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), help="package root (default: parent of tools/)")
    ap.add_argument("--verbose", action="store_true", help="also list passing checks")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print("ERROR: %s is not a directory" % root, file=sys.stderr)
        return 2

    rep = Report(verbose=args.verbose)
    data = check_plugin_json(root, rep)
    if data:
        check_avatar(root, data, rep)
        check_agents(root, data, rep)
        check_skills(root, data, rep)
    check_scripts(root, rep)
    check_docs(root, rep)

    print("package: %s\n" % root)
    rep.dump()
    return 1 if rep.counts()["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
