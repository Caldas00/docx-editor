"""Unit tests for structural operations: move, duplicate, paragraph format, split, merge,
page breaks, table columns, paragraphs -> table, hyperlinks, headers/footers."""

import pytest
from helpers import BOLD, ITALIC, P, R, block_xml, pkg_of, run_plan, texts
from test_ops import icon, table

from docx_agent.document import DocxPackage, EditError
from docx_agent.document.model import build_index, paragraph_view
from docx_agent.document.ns import W, qn

THREE = P(R("one")) + P(R("two", BOLD)) + P(R("three"))


# ------------------------------------------------------------------- move
def test_move_paragraph_keeps_its_xml():
    pkg = pkg_of(THREE)
    original = block_xml(pkg, "p1")
    out, _ = run_plan(pkg, {"op": "move_blocks", "block_ids": ["p1"], "target_id": "p2",
                            "position": "after"})
    assert list(texts(out).values()) == ["one", "three", "two"]
    assert block_xml(out, "p2") == original


def test_move_several_keeps_their_order():
    pkg = pkg_of(THREE + P(R("four")))
    out, _ = run_plan(pkg, {"op": "move_blocks", "block_ids": ["p2", "p0"], "target_id": "p3",
                            "position": "after"})
    assert list(texts(out).values()) == ["two", "four", "one", "three"]


def test_move_table_to_the_end_adds_closing_paragraph():
    pkg = pkg_of(P(R("a")) + table([["x", "y"]]) + P(R("b")))
    out, _ = run_plan(pkg, {"op": "move_blocks", "block_ids": ["t0"], "target_id": "p1",
                            "position": "after"})
    assert list(texts(out).values()) == ["a", "b", "x", "y", ""]


def test_move_that_would_join_two_tables_is_refused():
    pkg = pkg_of(table([["a"]]) + P(R("gap")) + table([["b"]]) + P(R("end")))
    with pytest.raises(EditError, match="two tables touching"):
        run_plan(pkg, {"op": "move_blocks", "block_ids": ["p0"], "target_id": "p1",
                       "position": "after"})


def test_move_into_itself_is_refused():
    pkg = pkg_of(table([["a"]]) + P(R("x")))
    with pytest.raises(EditError, match="target is one of the blocks"):
        run_plan(pkg, {"op": "move_blocks", "block_ids": ["t0"], "target_id": "t0.r0.c0.p0",
                       "position": "after"})


# -------------------------------------------------------------- duplicate
def test_duplicate_paragraph_with_picture_gets_new_drawing_id():
    pkg = pkg_of(P(R("see ") + icon(7)) + P(R("end")))
    out, _ = run_plan(pkg, {"op": "duplicate_blocks", "block_ids": ["p0"]})
    assert list(texts(out).values()) == ["see ⟦IMAGE#7⟧", "see ⟦IMAGE#8⟧", "end"]


def test_duplicate_drops_bookmarks_and_comment_anchors():
    body = P('<w:bookmarkStart w:id="1" w:name="b"/>' + R("x") + '<w:bookmarkEnd w:id="1"/>'
             '<w:commentRangeStart w:id="0"/>' + R("y") + '<w:commentRangeEnd w:id="0"/>'
             '<w:r><w:commentReference w:id="0"/></w:r>') + P(R("z"))
    out, _ = run_plan(pkg_of(body), {"op": "duplicate_blocks", "block_ids": ["p0"],
                                     "target_id": "p1", "position": "after"})
    copy_xml = block_xml(out, "p2")
    assert "bookmark" not in copy_xml and "comment" not in copy_xml
    assert texts(out)["p2"] == "xy"


def test_duplicate_after_edit_is_refused():
    pkg = pkg_of(THREE)
    with pytest.raises(EditError, match="changed earlier in this plan"):
        run_plan(pkg, {"op": "replace_text", "block_id": "p0", "find": "one", "replace_with": "1"},
                 {"op": "duplicate_blocks", "block_ids": ["p0"]})


# ------------------------------------------------------- paragraph format
def test_set_style_alignment_and_remove_numbering():
    list_ppr = ('<w:pPr><w:pStyle w:val="ListBullet"/><w:numPr><w:ilvl w:val="0"/>'
                '<w:numId w:val="1"/></w:numPr></w:pPr>')
    pkg = pkg_of(P(R("item"), list_ppr) + P(R("title")))
    out, _ = run_plan(pkg,
                      {"op": "set_paragraph_format", "block_ids": ["p0"], "style": "normal",
                       "remove_numbering": True},
                      {"op": "set_paragraph_format", "block_ids": ["p1"], "style": "heading 1",
                       "align": "center"})
    assert "numPr" not in block_xml(out, "p0") and 'w:val="Normal"' in block_xml(out, "p0")
    assert '<w:pPr><w:pStyle w:val="Heading1"/><w:jc w:val="center"/></w:pPr>' in block_xml(out, "p1")


def test_unknown_style_lists_available_ones():
    with pytest.raises(EditError, match="Available: .*Heading 1"):
        run_plan(pkg_of(THREE), {"op": "set_paragraph_format", "block_ids": ["p0"],
                                 "style": "Fancy Style"})


# ----------------------------------------------------------- split / merge
def test_split_keeps_formatting_and_trims_the_space():
    pkg = pkg_of(P(R("First part ", ITALIC) + R("second part", BOLD), "<w:pPr><w:jc w:val=\"center\"/></w:pPr>"))
    out, _ = run_plan(pkg, {"op": "split_paragraph", "block_id": "p0", "at": "second"})
    assert list(texts(out).values()) == ["First part", "second part"]
    assert 'w:jc w:val="center"' in block_xml(out, "p0") and "<w:i/>" in block_xml(out, "p0")
    assert "<w:b/>" in block_xml(out, "p1")


def test_split_inside_a_word_of_one_run():
    out, _ = run_plan(pkg_of(P(R("abcdef"))), {"op": "split_paragraph", "block_id": "p0", "at": "def"})
    assert list(texts(out).values()) == ["abc", "def"]


def test_split_inside_a_link_is_refused():
    link = ('<w:hyperlink r:id="rId99"><w:r><w:t>click here</w:t></w:r></w:hyperlink>')
    with pytest.raises(EditError, match="Cannot split inside a link"):
        run_plan(pkg_of(P(R("go ") + link)), {"op": "split_paragraph", "block_id": "p0",
                                              "at": "here"})


def test_merge_paragraphs_keeps_inline_formatting():
    out, _ = run_plan(pkg_of(THREE), {"op": "merge_paragraphs", "block_ids": ["p0", "p1", "p2"]})
    assert list(texts(out).values()) == ["one two three"]
    assert "<w:b/>" in block_xml(out, "p0")


def test_merge_requires_consecutive_paragraphs():
    with pytest.raises(EditError, match="consecutive"):
        run_plan(pkg_of(THREE), {"op": "merge_paragraphs", "block_ids": ["p0", "p2"]})


# ------------------------------------------------------------ page breaks
def test_insert_and_delete_page_break():
    out, _ = run_plan(pkg_of(THREE), {"op": "insert_page_break", "target_id": "p0",
                                      "position": "after"})
    assert texts(out)["p1"] == "⟦PAGE BREAK⟧"
    out2, _ = run_plan(out, {"op": "delete_paragraph", "block_id": "p1"})
    assert list(texts(out2).values()) == ["one", "two", "three"]


# ---------------------------------------------------------- table columns
GRID = P(R("x")) + table([["H1", "H2"], ["a", "b"]]) + P(R("y"))


def test_insert_and_delete_columns():
    out, _ = run_plan(pkg_of(GRID), {"op": "insert_table_column", "table_id": "t0", "column": 0,
                                     "position": "after", "cells": ["Mid", "m"]})
    t = texts(out)
    assert [t["t0.r0.c0.p0"], t["t0.r0.c1.p0"], t["t0.r0.c2.p0"]] == ["H1", "Mid", "H2"]
    assert len(list(build_index(out).get("t0").element.iter(qn("w:gridCol")))) == 3
    out2, _ = run_plan(pkg_of(GRID), {"op": "delete_table_columns", "table_id": "t0",
                                      "columns": [0]})
    assert texts(out2)["t0.r1.c0.p0"] == "b"


def test_columns_refused_on_merged_cells():
    merged = ("<w:tbl><w:tblGrid><w:gridCol/><w:gridCol/></w:tblGrid><w:tr><w:tc><w:tcPr>"
              "<w:gridSpan w:val=\"2\"/></w:tcPr>" + P(R("wide")) + "</w:tc></w:tr></w:tbl>"
              + P(R("z")))
    with pytest.raises(EditError, match="merged cells"):
        run_plan(pkg_of(merged), {"op": "delete_table_columns", "table_id": "t0", "columns": [0]})


def test_paragraphs_into_a_table_keep_their_xml():
    pkg = pkg_of(THREE + P(R("end")))
    before = block_xml(pkg, "p1")
    out, _ = run_plan(pkg, {"op": "blocks_to_table", "block_ids": ["p0", "p1", "p2"],
                            "columns": 2})
    t = texts(out)
    assert [t["t0.r0.c0.p0"], t["t0.r0.c1.p0"], t["t0.r1.c0.p0"], t["t0.r1.c1.p0"]] == \
        ["one", "two", "three", ""]
    assert block_xml(out, "t0.r0.c1.p0") == before


# -------------------------------------------------------------- hyperlinks
def test_insert_set_and_remove_hyperlink():
    pkg = pkg_of(P(R("Read the guide today")))
    out, _ = run_plan(pkg, {"op": "insert_hyperlink", "block_id": "p0", "find": "the guide",
                            "url": "https://example.org/guide"})
    xml = block_xml(out, "p0")
    rid = build_index(out).get("p0").element.find(W.hyperlink).get(qn("r:id"))
    assert out.relationships[rid].target == "https://example.org/guide"
    assert '<w:rStyle w:val="Hyperlink"/>' in xml or 'w:val="0563C1"' in xml
    assert texts(out)["p0"] == "Read the guide today"
    out2, _ = run_plan(out, {"op": "set_hyperlink_url", "block_id": "p0", "find": "guide",
                             "url": "https://example.org/v2"})
    rid2 = build_index(out2).get("p0").element.find(W.hyperlink).get(qn("r:id"))
    assert out2.relationships[rid2].target == "https://example.org/v2"
    out3, _ = run_plan(out2, {"op": "remove_hyperlink", "block_id": "p0", "find": "guide"})
    assert "hyperlink" not in block_xml(out3, "p0") and texts(out3)["p0"] == "Read the guide today"


def test_unsafe_urls_are_rejected():
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        run_plan(pkg_of(P(R("x"))), {"op": "insert_hyperlink", "block_id": "p0", "find": "x",
                                     "url": "javascript:alert(1)"})


# --------------------------------------------------------- headers/footers
def test_edit_existing_header_and_footer(session_note):
    out, report = run_plan(session_note,
                           {"op": "replace_text", "block_id": "ftr1.p0", "find": "Page ",
                            "replace_with": "Página "},
                           {"op": "replace_text", "block_id": "hdr1.p0", "find": "Confidential",
                            "replace_with": "Private"})
    assert texts(out)["ftr1.p0"].startswith("Página ")
    assert "Private" in texts(out)["hdr1.p0"]
    assert report.passed


def test_create_footer_with_page_number(referral):
    out, report = run_plan(referral, {"op": "create_header_footer", "kind": "footer",
                                      "text": "Lumen", "page_numbers": True})
    footers = [h for h in out.hf_parts if h.kind == "footer"]
    assert len(footers) == 1
    assert paragraph_view(footers[0].root.find(W.p)).text == "Lumen 1"
    assert "Lumen 1" in texts(out)[f"{footers[0].label}.p0"]
    assert report.passed


def test_create_footer_when_one_exists_is_refused(session_note):
    with pytest.raises(EditError, match="already has a footer"):
        run_plan(session_note, {"op": "create_header_footer", "kind": "footer", "text": "x"})


def test_outline_lists_header_and_footer(session_note):
    from docx_agent.document.model import render_outline

    outline, _ = render_outline(session_note)
    assert "[ftr1] FOOTER (default, section 1)" in outline
    assert '[hdr1.p0] (Header) "Lumen Counselling Practice' in outline


def test_untouched_headers_keep_their_bytes(session_note):
    out, _ = run_plan(session_note, {"op": "replace_text", "block_id": "p0", "find": "Session",
                                     "replace_with": "Visit"})
    assert out.parts["word/header1.xml"] == session_note.parts["word/header1.xml"]
    assert isinstance(out, DocxPackage)


def test_paragraphs_and_tables_into_one_table():
    pkg = pkg_of(P(R("intro")) + table([["a", "b"]]) + P(R("outro")) + P(R("end")))
    out, _ = run_plan(pkg, {"op": "blocks_to_table", "block_ids": ["p0", "t0", "p1"]})
    t = texts(out)
    assert t["t0.r0.c0.p0"] == "intro" and t["t0.r1.c0.t0.r0.c1.p0"] == "b"
    assert t["t0.r1.c0.p0"] == "" and t["t0.r2.c0.p0"] == "outro"


def test_blocks_to_table_can_copy_the_look_of_a_table_it_contains(intake_bytes):
    pkg = DocxPackage(intake_bytes)
    ids = [b.id for b in build_index(pkg).blocks if b.depth == 0 and b.kind != "part"]
    out, report = run_plan(pkg, {"op": "blocks_to_table", "block_ids": ids, "table_like": "t0"})
    assert report.passed and texts(out)["t0.r0.c0.p0"] == "Client Intake Form"
