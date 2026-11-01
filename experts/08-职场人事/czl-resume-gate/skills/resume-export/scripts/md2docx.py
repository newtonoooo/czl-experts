#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""md2docx.py - convert a markdown resume into a real .docx, stdlib only.

No python-docx, no pandoc, no Word installation. Writes the OOXML package
directly: document.xml / styles.xml / core.xml + relationships.

Design choices for ATS safety:
  - bullets are paragraphs with a "• " prefix and hanging indent, not Word
    auto-numbering (auto-numbering often vanishes on copy/parse);
  - tables are flattened into single-column lines;
  - no text boxes, no headers/footers, no images.

Usage:
    python md2docx.py resume.md -o resume.docx [--title NAME] [--author NAME]
"""

import argparse
import datetime
import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from md2html import parse_blocks
except Exception:  # pragma: no cover - fallback if imported standalone
    parse_blocks = None

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def esc(text):
    return escape(text, {'"': "&quot;"})


def split_runs(text):
    """Split markdown inline markup into (text, bold, italic, code) runs."""
    tokens = re.split(r"(\*\*[^*]+\*\*|__[^_]+__|`[^`]+`|\*[^*\n]+\*)", text)
    out = []
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**"):
            out.append((tok[2:-2], True, False, False))
        elif tok.startswith("__") and tok.endswith("__"):
            out.append((tok[2:-2], True, False, False))
        elif tok.startswith("`") and tok.endswith("`"):
            out.append((tok[1:-1], False, False, True))
        elif tok.startswith("*") and tok.endswith("*") and len(tok) > 2:
            out.append((tok[1:-1], False, True, False))
        else:
            out.append((tok, False, False, False))
    return out


def run_xml(text, bold=False, italic=False, code=False):
    rpr = []
    if bold:
        rpr.append("<w:b/>")
    if italic:
        rpr.append("<w:i/>")
    if code:
        rpr.append('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>')
        rpr.append('<w:color w:val="333333"/>')
    rpr_xml = "<w:rPr>%s</w:rPr>" % "".join(rpr) if rpr else ""
    return '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rpr_xml, esc(text))


def para_xml(runs, style=None, indent=None, hanging=None, before=0, after=0,
             keep_next=False, border=False):
    ppr = []
    if style:
        ppr.append('<w:pStyle w:val="%s"/>' % style)
    if keep_next:
        ppr.append("<w:keepNext/>")
    if border:
        ppr.append('<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="BFBFBF"/></w:pBdr>')
    if before or after:
        ppr.append('<w:spacing w:before="%d" w:after="%d"/>' % (before, after))
    if indent:
        if hanging:
            ppr.append('<w:ind w:left="%d" w:hanging="%d"/>' % (indent, hanging))
        else:
            ppr.append('<w:ind w:left="%d"/>' % indent)
    ppr_xml = "<w:pPr>%s</w:pPr>" % "".join(ppr) if ppr else ""
    return "<w:p>%s%s</w:p>" % (ppr_xml, "".join(runs))


def paras_from_inline(text, **kw):
    return [run_xml(t, b, i, c) for (t, b, i, c) in split_runs(text)]


def build_document(blocks):
    body = []
    for kind, val in blocks:
        if kind == "h1":
            body.append(para_xml(paras_from_inline(val), style="Heading1", after=40))
        elif kind == "h2":
            body.append(para_xml(paras_from_inline(val), style="Heading2",
                                 before=180, after=60, keep_next=True, border=True))
        elif kind == "h3":
            body.append(para_xml(paras_from_inline(val), style="Heading3",
                                 before=100, after=20, keep_next=True))
        elif kind == "h4":
            body.append(para_xml(paras_from_inline(val), style="Heading4",
                                 before=60, after=10, keep_next=True))
        elif kind == "p":
            body.append(para_xml(paras_from_inline(val), after=20))
        elif kind == "quote":
            body.append(para_xml(paras_from_inline(val), style="Quote", indent=240))
        elif kind == "hr":
            body.append(para_xml([run_xml("")], border=True, after=0))
        elif kind == "ul":
            for item in val:
                runs = [run_xml("•  ")] + paras_from_inline(item)
                body.append(para_xml(runs, indent=340, hanging=200, after=20))
        elif kind == "ol":
            for n, item in enumerate(val, 1):
                runs = [run_xml("%d.  " % n)] + paras_from_inline(item)
                body.append(para_xml(runs, indent=360, hanging=220, after=20))
        elif kind == "table":
            header, rows = val
            body.append(para_xml(paras_from_inline(" ｜ ".join(header)), after=20))
            for r in rows:
                body.append(para_xml(paras_from_inline(" ｜ ".join(r)), after=20))
    body.append(
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1134" w:right="1021" w:bottom="1134" w:left="1021" '
        'w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:document xmlns:w="%s"><w:body>%s</w:body></w:document>' % (W_NS, "".join(body))
    )


STYLES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="%s">
<w:docDefaults>
  <w:rPrDefault><w:rPr>
    <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="微软雅黑" w:cs="Calibri"/>
    <w:sz w:val="21"/><w:szCs w:val="21"/>
    <w:color w:val="1A1A1A"/>
  </w:rPr></w:rPrDefault>
  <w:pPrDefault><w:pPr><w:spacing w:line="320" w:lineRule="auto"/></w:pPr></w:pPrDefault>
</w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:qFormat/>
  <w:rPr><w:b/><w:sz w:val="40"/><w:szCs w:val="40"/><w:color w:val="1F2937"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:qFormat/>
  <w:rPr><w:b/><w:sz w:val="24"/><w:szCs w:val="24"/><w:color w:val="1F2937"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:qFormat/>
  <w:rPr><w:b/><w:sz w:val="22"/><w:szCs w:val="22"/><w:color w:val="111827"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading4"><w:name w:val="heading 4"/><w:basedOn w:val="Normal"/><w:qFormat/>
  <w:rPr><w:b/><w:sz w:val="21"/><w:szCs w:val="21"/><w:color w:val="374151"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/><w:basedOn w:val="Normal"/><w:qFormat/>
  <w:rPr><w:i/><w:color w:val="4B5563"/><w:sz w:val="19"/><w:szCs w:val="19"/></w:rPr></w:style>
</w:styles>""" % W_NS

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

APP_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
<Application>czl-resume-gate / md2docx</Application>
</Properties>"""


def core_xml(title, author):
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:title>%s</dc:title><dc:creator>%s</dc:creator><cp:lastModifiedBy>%s</cp:lastModifiedBy>
<dcterms:created xsi:type="dcterms:W3CDTF">%s</dcterms:created>
<dcterms:modified xsi:type="dcterms:W3CDTF">%s</dcterms:modified>
</cp:coreProperties>""" % (esc(title), esc(author), esc(author), now, now)


def write_docx(md_text, out_path, title=None, author="czl-resume-gate"):
    if parse_blocks is None:
        raise RuntimeError("md2html.parse_blocks unavailable; keep md2html.py beside this script")
    blocks = parse_blocks(md_text)
    document = build_document(blocks)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("word/document.xml", document)
        z.writestr("word/styles.xml", STYLES_XML)
        z.writestr("word/_rels/document.xml.rels", DOC_RELS)
        z.writestr("docProps/core.xml", core_xml(title or out_path.stem, author))
        z.writestr("docProps/app.xml", APP_XML)
    return out_path


def main():
    ap = argparse.ArgumentParser(description="markdown resume -> .docx (no external deps)")
    ap.add_argument("source")
    ap.add_argument("-o", "--out")
    ap.add_argument("--title")
    ap.add_argument("--author", default="czl-resume-gate")
    args = ap.parse_args()

    src = Path(args.source)
    try:
        text = src.read_text(encoding="utf-8-sig")
    except OSError as e:
        print("ERROR: cannot read %s (%s)" % (src, e), file=sys.stderr)
        return 2

    out = Path(args.out) if args.out else src.with_suffix(".docx")
    try:
        write_docx(text, out, args.title or src.stem, args.author)
    except Exception as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1
    print("written: %s (%.1f KB)" % (out, out.stat().st_size / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
