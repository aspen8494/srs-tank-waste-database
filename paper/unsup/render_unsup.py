#!/usr/bin/env python3
"""Render the unsupervised-taxonomy white paper to .docx and .pdf from typed blocks.

Adapted from paper/render_paper.py (validated pipeline). Fixes inherited bug:
proper XML escaping for reportlab (&, <, >) before math-italic wrapping.
Block types: h1, h2, p, eq (display, centered italic), fig, tbl, ref, pagebreak.
Run with the project venv (.venv/bin/python).
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from content_u1 import META, EXEC_SUMMARY, INTRO, RESULTS
from content_u2 import METHOD, GUIDE, CAVEATS, CONCLUSIONS, REFERENCES, TABLES_U

FIGS = os.path.join(HERE, "figs")
TABLES = TABLES_U

BLOCKS = EXEC_SUMMARY + INTRO + RESULTS + METHOD + GUIDE + CAVEATS + CONCLUSIONS + REFERENCES

# ---- assign figure numbers by first appearance in final order ----
fig_no = 0
for b in BLOCKS:
    if b["t"] == "fig":
        fig_no += 1
        b["caption"] = re.sub(r"^Figure \d+\.", f"Figure {fig_no}.", b["caption"])
N_FIGS = fig_no
print(f"figures renumbered 1..{N_FIGS}")


def esc(s):
    return s.replace("&", "&").replace("<", "<").replace(">", ">")


def fmt_pdf(s):
    """reportlab XML-escape, then $math$ -> italic. Escape FIRST (inherited-pipeline bug fixed)."""
    s = esc(s)
    return re.sub(r"\$([^$]+)\$", r"<i>\1</i>", s)


# ================= DOCX =================
def build_docx(path):
    import docx
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT

    doc = docx.Document()
    for s in doc.sections:
        s.page_width, s.page_height = Inches(8.5), Inches(11)
        for a in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
            setattr(s, a, Inches(1.0))
    st = doc.styles["Normal"]
    st.font.name = "Times New Roman"
    st.font.size = Pt(12)
    st.paragraph_format.space_after = Pt(10)
    st.paragraph_format.line_spacing = 1.25

    def head(text, size, level):
        p = doc.add_paragraph()
        r = p.add_run(text)
        r.font.name = "Times New Roman"
        r.font.size = Pt(size)
        r.font.bold = True
        r.font.color.rgb = RGBColor(0, 0, 0)
        p.paragraph_format.space_before = Pt(16 if level == 1 else 10)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        return p

    def body(text, justify=True, italic=False, indent=None, center=False):
        p = doc.add_paragraph()
        parts = re.split(r"(\$[^$]+\$)", text)
        for part in parts:
            if part.startswith("$") and part.endswith("$"):
                r = p.add_run(part[1:-1]); r.italic = True
            else:
                r = p.add_run(part)
                r.italic = italic
            r.font.name = "Times New Roman"; r.font.size = Pt(12)
        if center:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif justify:
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        if indent:
            p.paragraph_format.left_indent = Inches(indent)
            p.paragraph_format.first_line_indent = Inches(-indent)
        return p

    for _ in range(6):
        doc.add_paragraph()
    tp = doc.add_paragraph(); tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = tp.add_run(META["title"]); r.font.name = "Times New Roman"; r.font.size = Pt(18); r.bold = True
    sp = doc.add_paragraph(); sp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = sp.add_run(META["subtitle"]); r.font.name = "Times New Roman"; r.font.size = Pt(13); r.italic = True
    for line in (META["author"], META["org"], META["date"]):
        ap = doc.add_paragraph(); ap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = ap.add_run(line); r.font.name = "Times New Roman"; r.font.size = Pt(12)
    doc.add_page_break()

    for b in BLOCKS:
        t = b["t"]
        if t == "h1":
            head(b["text"], 16, 1)
        elif t == "h2":
            head(b["text"], 13, 2)
        elif t == "p":
            body(b["text"])
        elif t == "eq":
            body(b["text"], justify=False, italic=True, center=True)
        elif t == "ref":
            body(b["text"], justify=False, indent=0.5)
        elif t == "fig":
            from PIL import Image
            f = os.path.join(FIGS, b["file"])
            im = Image.open(f)
            w_in = min(6.0, doc.sections[0].page_width.inches - 2.0)
            h_in = w_in * im.size[1] / im.size[0]
            if h_in > 3.4:
                h_in = 3.4; w_in = h_in * im.size[0] / im.size[1]
            doc.add_picture(f, width=Inches(w_in))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            cap = doc.add_paragraph(); cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = cap.add_run(b["caption"]); r.font.name = "Times New Roman"; r.font.size = Pt(10); r.italic = True
            cap.paragraph_format.space_after = Pt(12)
        elif t == "tbl":
            spec = TABLES[b["id"]]
            tbl = doc.add_table(rows=1 + len(spec["rows"]), cols=len(spec["header"]))
            tbl.style = "Table Grid"
            tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
            for j, h in enumerate(spec["header"]):
                c = tbl.rows[0].cells[j]
                c.text = h
                for pp in c.paragraphs:
                    for rr in pp.runs:
                        rr.font.bold = True; rr.font.size = Pt(9.5); rr.font.name = "Times New Roman"
            for i, row in enumerate(spec["rows"]):
                for j, v in enumerate(row):
                    c = tbl.rows[i + 1].cells[j]
                    c.text = str(v)
                    for pp in c.paragraphs:
                        for rr in pp.runs:
                            rr.font.size = Pt(9.5); rr.font.name = "Times New Roman"
            cap = doc.add_paragraph(); cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = cap.add_run(spec["caption"]); r.font.name = "Times New Roman"; r.font.size = Pt(10); r.italic = True
            cap.paragraph_format.space_after = Pt(4)
            if spec.get("note"):
                note = doc.add_paragraph(); note.alignment = WD_ALIGN_PARAGRAPH.CENTER
                rn = note.add_run("Note: " + spec["note"])
                rn.font.name = "Times New Roman"; rn.font.size = Pt(9); rn.italic = True
                note.paragraph_format.space_after = Pt(12)
        elif t == "pagebreak":
            doc.add_page_break()
    doc.save(path)
    print(f"docx: {path}")


# ================= PDF =================
def build_pdf(path):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer,
                                    Image, Table, TableStyle, KeepTogether, PageBreak)
    from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER
    from PIL import Image as PILImage

    styles = {
        "body": ParagraphStyle("body", fontName="Times-Roman", fontSize=12, leading=16.2,
                               alignment=TA_JUSTIFY, spaceAfter=10),
        "h1": ParagraphStyle("h1", fontName="Times-Bold", fontSize=16, leading=19,
                             spaceBefore=16, spaceAfter=6),
        "h2": ParagraphStyle("h2", fontName="Times-Bold", fontSize=13, leading=16,
                             spaceBefore=10, spaceAfter=6),
        "caption": ParagraphStyle("caption", fontName="Times-Italic", fontSize=10, leading=12,
                                  alignment=TA_CENTER, spaceAfter=12),
        "note": ParagraphStyle("note", fontName="Times-Italic", fontSize=9, leading=11,
                               alignment=TA_CENTER, spaceAfter=12),
        "eq": ParagraphStyle("eq", fontName="Times-Italic", fontSize=12, leading=16,
                             alignment=TA_CENTER, spaceBefore=6, spaceAfter=10),
        "ref": ParagraphStyle("ref", fontName="Times-Roman", fontSize=12, leading=16.2,
                              alignment=TA_LEFT, leftIndent=36, firstLineIndent=-36, spaceAfter=6),
    }

    doc = BaseDocTemplate(path, pagesize=letter,
                          leftMargin=inch, rightMargin=inch, topMargin=inch, bottomMargin=inch,
                          title=META["title"], author=META["author"])
    frame = Frame(inch, inch, letter[0] - 2 * inch, letter[1] - 2 * inch, id="main")

    def footer(canvas, doc_):
        if doc_.page == 1:
            return
        canvas.setFont("Times-Roman", 9)
        canvas.drawCentredString(letter[0] / 2, 0.5 * inch, str(doc_.page))

    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=footer)])
    story = []

    for _ in range(6):
        story.append(Spacer(1, 24))
    story.append(Paragraph(f"<b>{fmt_pdf(META['title'])}</b>",
                  ParagraphStyle("t", fontName="Times-Bold", fontSize=18, leading=22, alignment=TA_CENTER)))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"<i>{fmt_pdf(META['subtitle'])}</i>",
                  ParagraphStyle("st", fontName="Times-Italic", fontSize=13, leading=17, alignment=TA_CENTER)))
    story.append(Spacer(1, 24))
    for line in (META["author"], META["org"], META["date"]):
        story.append(Paragraph(fmt_pdf(line),
                      ParagraphStyle("a", fontName="Times-Roman", fontSize=12, leading=16, alignment=TA_CENTER)))
    story.append(PageBreak())

    for b in BLOCKS:
        t = b["t"]
        if t == "h1":
            story.append(Paragraph(fmt_pdf(b["text"]), styles["h1"]))
        elif t == "h2":
            story.append(Paragraph(fmt_pdf(b["text"]), styles["h2"]))
        elif t == "p":
            story.append(Paragraph(fmt_pdf(b["text"]), styles["body"]))
        elif t == "eq":
            story.append(Paragraph(fmt_pdf(b["text"]), styles["eq"]))
        elif t == "ref":
            story.append(Paragraph(fmt_pdf(b["text"]), styles["ref"]))
        elif t == "fig":
            f = os.path.join(FIGS, b["file"])
            im = PILImage.open(f)
            w = min(6.2 * inch, doc.width)
            h = w * im.size[1] / im.size[0]
            if h > 3.4 * inch:
                h = 3.4 * inch; w = h * im.size[0] / im.size[1]
            img = Image(f, width=w, height=h)
            story.append(KeepTogether([img, Paragraph(fmt_pdf(b["caption"]), styles["caption"])]))
        elif t == "tbl":
            spec = TABLES[b["id"]]
            data = [[fmt_pdf(x) for x in spec["header"]]] + [[fmt_pdf(str(x)) for x in row] for row in spec["rows"]]
            maxlens = [max(len(str(spec["header"][j])), *(len(str(r[j])) for r in spec["rows"]))
                       for j in range(len(spec["header"]))]
            tot = sum(maxlens)
            widths = [doc.width * ml / tot for ml in maxlens]
            tbl = Table(data, colWidths=widths, repeatRows=1)
            tbl.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9aa7b4")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf3")),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(KeepTogether([tbl, Paragraph(fmt_pdf(spec["caption"]), styles["caption"])]))
            if spec.get("note"):
                story.append(Paragraph(fmt_pdf("Note: " + spec["note"]), styles["note"]))
        elif t == "pagebreak":
            story.append(PageBreak())
    doc.build(story)
    print(f"pdf: {path}")


if __name__ == "__main__":
    build_docx(os.path.join(HERE, "Unsupervised_Taxonomy_White_Paper.docx"))
    build_pdf(os.path.join(HERE, "Unsupervised_Taxonomy_White_Paper.pdf"))
