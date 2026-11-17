"""Mutation tests for the verifier: take a correct edit, tamper with the output in
ways a buggy editor could, and check the verifier catches each one."""

import io
import zipfile

import pytest
from helpers import plan

from docx_agent.document import DocxPackage, apply_plan, verify_edit
from docx_agent.document.model import build_index
from docx_agent.document.ns import W

PLAN = plan(
    {"op": "replace_text", "block_id": "p5", "find": "anxiety", "replace_with": "stress"},
    {"op": "insert_paragraph", "target_id": "p10", "position": "after",
     "text": "Grounding exercise", "format_like": "p10"},
)


@pytest.fixture()
def edited(session_note):
    work = session_note.copy()
    apply_plan(work, PLAN)
    return session_note, work


def failing(report) -> set[str]:
    return {c.name for c in report.failures()}


def test_correct_edit_passes(edited):
    before, after = edited
    assert verify_edit(before, after.to_bytes(), PLAN).passed


def test_detects_change_to_untouched_paragraph(edited):
    before, after = edited
    run = build_index(after).get("p12").element.find(W.r)
    run.find(W.t).text = "Weekly self-reported anxiety (tampered)"
    assert "Untouched blocks are XML-identical" in failing(verify_edit(before, after.to_bytes(), PLAN))


def test_detects_formatting_change_on_untouched_paragraph(edited):
    before, after = edited
    from lxml import etree

    run = build_index(after).get("p0").element.find(W.r)
    rpr = run.find(W.rPr) if run.find(W.rPr) is not None else etree.SubElement(run, W.rPr)
    etree.SubElement(rpr, W.i)
    assert "Untouched blocks are XML-identical" in failing(verify_edit(before, after.to_bytes(), PLAN))


def test_detects_lost_formatting_inside_edited_paragraph(edited):
    before, after = edited
    p5 = build_index(after).get("p5").element
    for rpr in p5.iter(W.rPr):
        for b in rpr.findall(W.b):
            rpr.remove(b)  # "improved sleep" loses bold
    assert "Formatting preserved in edited paragraphs" in failing(
        verify_edit(before, after.to_bytes(), PLAN))


def test_detects_unexpected_text_in_edited_paragraph(edited):
    before, after = edited
    t = build_index(after).get("p5").element.find(".//" + W.t)
    t.text = t.text + " extra"
    assert "Edited text matches the plan exactly" in failing(verify_edit(before, after.to_bytes(), PLAN))


def test_detects_wrong_style_on_new_paragraph(edited):
    before, after = edited
    new_p = build_index(after).get("p10").element.getnext()
    new_p.find(W.pPr).find(W.pStyle).set(W.val, "Heading1")
    assert "New paragraphs copy their template's formatting" in failing(
        verify_edit(before, after.to_bytes(), PLAN))


def test_detects_removed_image(edited):
    before, after = edited
    drawing = next(after.body.iter(W.drawing))
    drawing.getparent().remove(drawing)
    names = failing(verify_edit(before, after.to_bytes(), PLAN))
    assert "Images, tables, links, fields, bookmarks, sections preserved" in names


def test_detects_missing_paragraph(edited):
    before, after = edited
    p = build_index(after).get("p23").element
    p.getparent().remove(p)
    assert "Block structure matches the plan" in failing(verify_edit(before, after.to_bytes(), PLAN))


def test_detects_modified_other_part(edited):
    before, after = edited
    data = after.to_bytes()
    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for info in src.infolist():
            payload = src.read(info)
            if info.filename == "word/styles.xml":
                payload = payload.replace(b"Calibri", b"Comic Sans MS")
            z.writestr(info, payload)
    names = failing(verify_edit(before, out.getvalue(), PLAN))
    assert "Styles, headers/footers, media and all other parts untouched" in names


def test_detects_unreadable_output(edited):
    before, _ = edited
    report = verify_edit(before, b"not a zip", PLAN)
    assert not report.passed
    assert report.checks[0].name == "Output is a valid .docx"


def test_report_serialises(edited):
    before, after = edited
    d = verify_edit(before, after.to_bytes(), PLAN).to_dict()
    assert d["passed"] is True
    assert all({"name", "passed", "detail"} <= set(c) for c in d["checks"])
    assert DocxPackage(after.to_bytes())  # sanity
