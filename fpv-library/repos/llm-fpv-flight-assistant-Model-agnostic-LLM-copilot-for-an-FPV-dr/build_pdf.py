#!/usr/bin/env python3
"""Render the research markdown report to a styled PDF using reportlab + DejaVu fonts."""
import re
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph,
                                Spacer, Preformatted, Table, TableStyle, HRFlowable,
                                KeepTogether)

MD = "/hey/projects/yzup-demo/llm-flight-assistant-research.md"
OUT = "/hey/projects/yzup-demo/llm-flight-assistant-research.pdf"

# ---- fonts ----
FD = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("DJSans", FD + "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DJSans-B", FD + "DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("DJSans-I", FD + "DejaVuSans-Oblique.ttf"))
pdfmetrics.registerFont(TTFont("DJSans-BI", FD + "DejaVuSans-BoldOblique.ttf"))
pdfmetrics.registerFont(TTFont("DJMono", FD + "DejaVuSansMono.ttf"))
pdfmetrics.registerFontFamily("DJSans", normal="DJSans", bold="DJSans-B",
                              italic="DJSans-I", boldItalic="DJSans-BI")

NAVY = colors.HexColor("#16324f")
ACCENT = colors.HexColor("#0b5cad")
GREY = colors.HexColor("#57606a")
LIGHT = colors.HexColor("#eef1f4")
RULE = colors.HexColor("#c9d3dd")

# ---- styles ----
ss = getSampleStyleSheet()
body = ParagraphStyle("body", parent=ss["Normal"], fontName="DJSans", fontSize=9.3,
                      leading=13.5, spaceAfter=5, textColor=colors.HexColor("#1f2328"))
h1 = ParagraphStyle("h1", fontName="DJSans-B", fontSize=19, leading=23, textColor=NAVY,
                    spaceBefore=6, spaceAfter=4)
h2 = ParagraphStyle("h2", fontName="DJSans-B", fontSize=14, leading=18, textColor=NAVY,
                    spaceBefore=15, spaceAfter=3)
h3 = ParagraphStyle("h3", fontName="DJSans-B", fontSize=11, leading=15, textColor=ACCENT,
                    spaceBefore=9, spaceAfter=2)
quote = ParagraphStyle("quote", parent=body, fontName="DJSans-I", leftIndent=10,
                       textColor=GREY, backColor=colors.HexColor("#f6f8fa"),
                       borderColor=RULE, borderWidth=0, spaceBefore=3, spaceAfter=6,
                       leading=13)
listp = ParagraphStyle("listp", parent=body, leftIndent=16, bulletIndent=4, spaceAfter=3)
cell = ParagraphStyle("cell", parent=body, fontSize=8.2, leading=11, spaceAfter=0)
cellh = ParagraphStyle("cellh", parent=cell, fontName="DJSans-B", textColor=colors.white)
code = ParagraphStyle("code", fontName="DJMono", fontSize=8, leading=9.6,
                      textColor=colors.HexColor("#1f2328"))

EMOJI = [
    ("✅", '<font color="#1a7f37"><b>✓</b></font>'),   # ✅ -> ✓
    ("⚠️", '<font color="#9a6700"><b>⚠</b></font>'),  # ⚠️
    ("⚠", '<font color="#9a6700"><b>⚠</b></font>'),   # ⚠
    ("\U0001f527", '<font color="#57606a"><b>⚙</b></font>'),  # 🔧 -> ⚙
    ("⭐", '<font color="#bf8700"><b>★</b></font>'),   # ⭐ -> ★
    ("⭐️", '<font color="#bf8700"><b>★</b></font>'),
]


def inline(s):
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for a, b in EMOJI:
        s = s.replace(a, b)
    s = s.replace("️", "")  # stray variation selectors
    # inline code
    s = re.sub(r"`([^`]+)`",
               r'<font face="DJMono" size="8.2" backColor="#eef1f4">\1</font>', s)
    # bold then italic
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", s)
    # links [text](url)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
               r'<link href="\2"><font color="#0b5cad">\1</font></link>', s)
    return s


with open(MD) as f:
    lines = f.read().split("\n")

flow = []
FRAME_W = A4[0] - 3.4 * cm
i, n = 0, len(lines)
while i < n:
    line = lines[i]
    st = line.strip()

    # code fence
    if st.startswith("```"):
        i += 1
        buf = []
        while i < n and not lines[i].strip().startswith("```"):
            buf.append(lines[i]); i += 1
        i += 1
        txt = "\n".join(buf).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        box = Table([[Preformatted(txt, code)]], colWidths=[FRAME_W])
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f6f8fa")),
            ("BOX", (0, 0), (-1, -1), 0.5, RULE),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        flow.append(box); flow.append(Spacer(1, 6)); continue

    # table
    if st.startswith("|"):
        tbl = []
        while i < n and lines[i].strip().startswith("|"):
            tbl.append(lines[i].strip()); i += 1
        rows = []
        for r in tbl:
            cells = [c.strip() for c in r.strip("|").split("|")]
            rows.append(cells)
        # drop separator row (---|---)
        rows = [r for r in rows if not all(set(c) <= set("-: ") and c for c in r)]
        if rows:
            ncol = max(len(r) for r in rows)
            rows = [r + [""] * (ncol - len(r)) for r in rows]
            data = []
            for ri, r in enumerate(rows):
                stl = cellh if ri == 0 else cell
                data.append([Paragraph(inline(c), stl) for c in r])
            # column widths: first column a bit wider
            w0 = FRAME_W * (0.26 if ncol > 2 else 0.4)
            rest = (FRAME_W - w0) / (ncol - 1) if ncol > 1 else FRAME_W
            widths = [w0] + [rest] * (ncol - 1) if ncol > 1 else [FRAME_W]
            t = Table(data, colWidths=widths, repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8fa")]),
                ("GRID", (0, 0), (-1, -1), 0.4, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
            flow.append(t); flow.append(Spacer(1, 7))
        continue

    # heading
    m = re.match(r"^(#{1,6})\s+(.*)$", line)
    if m:
        lvl = len(m.group(1)); txt = inline(m.group(2))
        if lvl == 1:
            flow.append(Paragraph(txt, h1))
            flow.append(HRFlowable(width="100%", thickness=1.4, color=NAVY,
                                   spaceBefore=2, spaceAfter=8))
        elif lvl == 2:
            flow.append(Paragraph(txt, h2))
            flow.append(HRFlowable(width="100%", thickness=0.5, color=RULE,
                                   spaceBefore=1, spaceAfter=5))
        else:
            flow.append(Paragraph(txt, h3))
        i += 1; continue

    # horizontal rule
    if st in ("---", "***", "___"):
        flow.append(Spacer(1, 2))
        flow.append(HRFlowable(width="100%", thickness=0.5, color=RULE,
                               spaceBefore=3, spaceAfter=6))
        i += 1; continue

    # blockquote
    if st.startswith(">"):
        buf = []
        while i < n and lines[i].strip().startswith(">"):
            buf.append(lines[i].strip()[1:].strip()); i += 1
        para = Paragraph(inline(" ".join(buf)), quote)
        bar = Table([[para]], colWidths=[FRAME_W])
        bar.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f6f8fa")),
            ("LINEBEFORE", (0, 0), (0, -1), 2.5, ACCENT),
            ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        flow.append(bar); flow.append(Spacer(1, 5)); continue

    # bullet list
    mb = re.match(r"^(\s*)[-*]\s+(.*)$", line)
    if mb:
        indent = len(mb.group(1))
        sty = ParagraphStyle("b%d" % indent, parent=listp, leftIndent=16 + indent * 6)
        flow.append(Paragraph(inline(mb.group(2)), sty, bulletText="•"))
        i += 1; continue

    # numbered list
    mn = re.match(r"^(\s*)(\d+)\.\s+(.*)$", line)
    if mn:
        indent = len(mn.group(1))
        sty = ParagraphStyle("n%d" % indent, parent=listp, leftIndent=18 + indent * 6)
        flow.append(Paragraph(inline(mn.group(3)), sty, bulletText=mn.group(2) + "."))
        i += 1; continue

    # blank
    if st == "":
        flow.append(Spacer(1, 3)); i += 1; continue

    # paragraph
    flow.append(Paragraph(inline(line), body)); i += 1


# ---- page furniture ----
def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont("DJSans", 7.5)
    canvas.setFillColor(GREY)
    canvas.drawString(1.7 * cm, 1.1 * cm,
                      "LLM Flight Assistant for UAV Drones — Research Report")
    canvas.drawRightString(A4[0] - 1.7 * cm, 1.1 * cm, "Page %d" % doc.page)
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.4)
    canvas.line(1.7 * cm, 1.4 * cm, A4[0] - 1.7 * cm, 1.4 * cm)
    canvas.restoreState()


doc = BaseDocTemplate(OUT, pagesize=A4, leftMargin=1.7 * cm, rightMargin=1.7 * cm,
                      topMargin=1.6 * cm, bottomMargin=1.7 * cm,
                      title="LLM Flight Assistant for UAV Drones - Research Report",
                      author="Deep research report")
frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
doc.addPageTemplates([PageTemplate(id="t", frames=[frame], onPage=on_page)])
doc.build(flow)
print("WROTE", OUT)
