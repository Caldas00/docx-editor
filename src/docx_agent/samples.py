"""Synthetic sample documents (no real patient data).

They deliberately contain the things that break naive editors: words split
across runs, mixed bold/italic inside a sentence, hyperlinks, a field, a
comment, tabs, line and page breaks, bullet and numbered lists, tables with
merged and shaded cells, inline images, and an image in the header.
"""

from __future__ import annotations

import io
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT  # noqa: F401  (kept for readers exploring options)
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


def _png(width: int = 480, height: int = 180, seed: int = 0) -> bytes:
    """A small synthetic bar chart rendered with Pillow."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (width, height), (255, 255, 255))
    d = ImageDraw.Draw(img)
    values = [(seed * 7 + i * 13) % 9 + 3 for i in range(8)]
    bar_w = width // (len(values) * 2)
    for i, v in enumerate(values):
        x0 = bar_w // 2 + i * bar_w * 2
        y0 = height - 20 - v * 14
        d.rectangle([x0, y0, x0 + bar_w, height - 20], fill=(31, 122, 112))
    d.line([0, height - 20, width, height - 20], fill=(80, 80, 80), width=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _add_hyperlink(paragraph, text: str, url: str) -> None:
    part = paragraph.part
    r_id = part.relate_to(url, RT.HYPERLINK, is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), r_id)
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    style = OxmlElement("w:rStyle")
    style.set(qn("w:val"), "Hyperlink")
    rpr.append(style)
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0563C1")
    rpr.append(color)
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    rpr.append(u)
    run.append(rpr)
    t = OxmlElement("w:t")
    t.text = text
    run.append(t)
    link.append(run)
    paragraph._p.append(link)


def _add_simple_field(paragraph, instr: str, shown: str) -> None:
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), instr)
    run = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = shown
    run.append(t)
    fld.append(run)
    paragraph._p.append(fld)


def _add_page_field(paragraph) -> None:
    """Complex field: { PAGE } with begin/separate/end runs."""
    def fld_char(kind: str):
        r = OxmlElement("w:r")
        fc = OxmlElement("w:fldChar")
        fc.set(qn("w:fldCharType"), kind)
        r.append(fc)
        return r

    paragraph._p.append(fld_char("begin"))
    r = OxmlElement("w:r")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    r.append(instr)
    paragraph._p.append(r)
    paragraph._p.append(fld_char("separate"))
    r = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = "1"
    r.append(t)
    paragraph._p.append(r)
    paragraph._p.append(fld_char("end"))


def _shade(cell, hex_fill: str) -> None:
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcpr.append(shd)


def _split_runs(paragraph, pieces: list[tuple[str, dict]]) -> None:
    for text, fmt in pieces:
        run = paragraph.add_run(text)
        run.bold = fmt.get("bold")
        run.italic = fmt.get("italic")
        run.underline = fmt.get("underline")
        if "color" in fmt:
            run.font.color.rgb = RGBColor.from_string(fmt["color"])
        if fmt.get("highlight"):
            from docx.enum.text import WD_COLOR_INDEX

            run.font.highlight_color = WD_COLOR_INDEX.YELLOW


def build_session_note() -> bytes:
    doc = Document()
    styles = doc.styles
    styles["Normal"].font.name = "Calibri"
    styles["Normal"].font.size = Pt(11)

    section = doc.sections[0]
    section.left_margin = section.right_margin = Cm(2.2)
    header_p = section.header.paragraphs[0]
    header_p.text = "Lumen Counselling Practice  ·  Confidential clinical record"
    header_p.runs[0].font.size = Pt(8)
    header_p.add_run().add_picture(io.BytesIO(_png(120, 40, seed=3)), width=Cm(1.6))
    footer_p = section.footer.paragraphs[0]
    footer_p.text = "Page "
    _add_page_field(footer_p)
    footer_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    doc.add_heading("Session Progress Note", level=0)
    meta = doc.add_paragraph()
    _split_runs(meta, [("Prepared by ", {}), ("Dr. Maya Ferreira", {"bold": True}),
                       (", Clinical Psychologist · Generated on ", {})])
    _add_simple_field(meta, 'DATE \\@ "d MMMM yyyy"', "17 November 2026")

    doc.add_heading("1. Session details", level=1)
    table = doc.add_table(rows=5, cols=2)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    rows = [("Client ID", "CL-2026-0147 (synthetic)"), ("Session date", "12 November 2026"),
            ("Session number", "6 of 12"), ("Modality", "Cognitive Behavioural Therapy (CBT)"),
            ("Attendance", "Attended on time, in person")]
    for (k, v), row in zip(rows, table.rows):
        row.cells[0].text = ""
        r = row.cells[0].paragraphs[0].add_run(k)
        r.bold = True
        _shade(row.cells[0], "E8F3F1")
        row.cells[1].text = v
    doc.add_paragraph()

    doc.add_heading("2. Presenting concerns", level=1)
    p = doc.add_paragraph()
    _split_runs(p, [
        ("The client reported ", {}),
        ("improved sleep", {"bold": True}),
        (" over the past ", {}),
        ("two weeks", {"italic": True}),
        (", with fewer night-time awakenings. Work-related ", {}),
        ("anx", {}), ("iety", {}),  # same formatting, split runs (typical of real Word files)
        (" remains the main concern, particularly before team meetings.", {}),
    ])
    p = doc.add_paragraph()
    _split_runs(p, [("Risk assessment: ", {"bold": True}),
                    ("No current risk indicators. ", {}),
                    ("Review again next session.", {"highlight": True})])

    doc.add_heading("3. Interventions used", level=1)
    for item in ["Thought record review focusing on catastrophic predictions",
                 "Paced breathing practice (4-6 pattern) in session",
                 "Behavioural experiment planned for the next team meeting"]:
        doc.add_paragraph(item, style="List Bullet")

    doc.add_heading("4. Progress overview", level=1)
    doc.add_paragraph("Weekly self-reported anxiety (0-10 scale, synthetic data):")
    pic_p = doc.add_paragraph()
    pic_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pic_p.add_run().add_picture(io.BytesIO(_png(seed=1)), width=Cm(11))
    cap = doc.add_paragraph("Figure 1. Anxiety ratings across sessions 1-6.")
    cap.runs[0].italic = True
    cap.runs[0].font.size = Pt(9)
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_heading("5. Plan", level=1)
    for item in ["Continue weekly sessions for six more weeks.",
                 "Client to complete two thought records before the next session.",
                 "Share the psychoeducation leaflet on sleep hygiene."]:
        doc.add_paragraph(item, style="List Number")
    p = doc.add_paragraph("Resource shared: ")
    _add_hyperlink(p, "Sleep hygiene leaflet", "https://example.org/sleep-hygiene")
    p.add_run(" (opens in browser).")

    p = doc.add_paragraph()
    _split_runs(p, [("Next appointment: ", {"bold": True}), ("19 November 2026 at 10:00", {})])
    commented = p.runs[1]
    doc.add_comment([commented], text="Confirm room booking.", author="Practice Admin",
                    initials="PA")

    p = doc.add_paragraph()
    p.add_run("Clinician signature:")
    p.add_run().add_tab()
    p.add_run("Dr. Maya Ferreira")
    p.runs[-1].add_break(WD_BREAK.LINE)
    p.add_run("Registration no. PSY-00000 (synthetic)")

    p = doc.add_paragraph()
    p.add_run().add_break(WD_BREAK.PAGE)
    doc.add_heading("Appendix A. Homework agreed", level=2)
    doc.add_paragraph(
        "Record situations that trigger anxiety, the automatic thought, and an alternative "
        "balanced thought. Bring the record to the next session."
    )

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def build_referral_letter() -> bytes:
    doc = Document()
    styles = doc.styles
    styles["Normal"].font.name = "Georgia"
    styles["Normal"].font.size = Pt(11)
    section = doc.sections[0]
    hp = section.header.paragraphs[0]
    hp.add_run().add_picture(io.BytesIO(_png(160, 48, seed=5)), width=Cm(2.4))
    hp.add_run("\tLumen Counselling Practice").bold = True
    hp.alignment = WD_ALIGN_PARAGRAPH.LEFT

    for line in ["Lumen Counselling Practice", "12 Example Street", "1000-000 Lisbon"]:
        doc.add_paragraph(line).paragraph_format.space_after = Pt(0)
    doc.add_paragraph()
    doc.add_paragraph("18 November 2026")
    doc.add_paragraph()
    p = doc.add_paragraph()
    _split_runs(p, [("Re: ", {"bold": True}), ("Referral for psychiatric assessment - ", {}),
                    ("Client CL-2026-0147", {"bold": True})])
    doc.add_paragraph("Dear Dr. Almeida,")
    doc.add_paragraph(
        "I am writing to refer the above client, whom I have seen for six sessions of "
        "cognitive behavioural therapy for work-related anxiety and sleep difficulties."
    )
    p = doc.add_paragraph()
    _split_runs(p, [
        ("Although the client has made ", {}), ("good progress", {"italic": True}),
        (" with sleep, persistent physical symptoms of anxiety are affecting daily functioning. "
         "I would be grateful for your opinion on whether ", {}),
        ("a medication review", {"bold": True}),
        (" would be appropriate.", {}),
    ])
    doc.add_paragraph("Current summary:")
    t = doc.add_table(rows=1, cols=3)
    t.style = "Light Grid Accent 1"
    hdr = t.rows[0].cells
    for c, txt in zip(hdr, ["Area", "Status", "Notes"]):
        c.text = txt
    for row in [("Sleep", "Improving", "Fewer awakenings"),
                ("Anxiety", "Moderate", "Triggered by meetings"),
                ("Mood", "Stable", "No concerns reported")]:
        cells = t.add_row().cells
        for c, txt in zip(cells, row):
            c.text = txt
    doc.add_paragraph()
    doc.add_paragraph("Please do not hesitate to contact me if you need further information.")
    doc.add_paragraph("Kind regards,")
    p = doc.add_paragraph()
    _split_runs(p, [("Dr. Maya Ferreira", {"bold": True})])
    p.runs[0].add_break(WD_BREAK.LINE)
    p.add_run("Clinical Psychologist")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


SAMPLES = {
    "session_note.docx": build_session_note,
    "referral_letter.docx": build_referral_letter,
}


def write_samples(directory: Path) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    out = []
    for name, builder in SAMPLES.items():
        path = directory / name
        path.write_bytes(builder())
        out.append(path)
    return out


if __name__ == "__main__":  # pragma: no cover
    for p in write_samples(Path("samples/input")):
        print(p)
