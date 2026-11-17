"""Unit tests for the edit engine. Every successful edit is also run through the
integrity verifier (``run_plan`` asserts the report passes)."""

import pytest
from helpers import BOLD, ITALIC, P, R, block_xml, pkg_of, run_plan, texts

from docx_agent.document import EditError
from docx_agent.document.model import build_index, paragraph_view

LINK = ('<w:hyperlink r:id="rId99"><w:r><w:rPr><w:rStyle w:val="Hyperlink"/></w:rPr>'
        '<w:t>the leaflet</w:t></w:r></w:hyperlink>')
IMG = ('<w:r><w:drawing><wp:inline><wp:extent cx="1" cy="1"/><wp:docPr id="1" name="i"/>'
       '</wp:inline></w:drawing></w:r>')


def replace(find, new, block_id="p0", **kw):
    return {"op": "replace_text", "block_id": block_id, "find": find, "replace_with": new, **kw}


# ------------------------------------------------------------------ replace
def test_replace_inside_one_run_keeps_its_formatting():
    pkg = pkg_of(P(R("Plain ") + R("bold words", BOLD) + R(" tail")))
    out, _ = run_plan(pkg, replace("words", "text"))
    assert texts(out)["p0"] == "Plain bold text tail"
    assert "<w:b/></w:rPr><w:t>bold text</w:t>" in block_xml(out, "p0")


def test_replace_across_split_runs():
    pkg = pkg_of(P(R("anx") + R("iety is high")))
    out, _ = run_plan(pkg, replace("anxiety", "stress"))
    assert texts(out)["p0"] == "stress is high"


def test_replace_across_formats_takes_first_run_format():
    pkg = pkg_of(P(R("Risk: ", BOLD) + R("low")))
    out, report = run_plan(pkg, replace("Risk: low", "Risk: none"))
    assert texts(out)["p0"] == "Risk: none"
    assert report.passed


def test_untouched_runs_are_byte_identical():
    pkg = pkg_of(P(R("keep ", ITALIC) + R("change") + R(" keep", BOLD)))
    out, _ = run_plan(pkg, replace("change", "changed"))
    xml = block_xml(out, "p0")
    assert "<w:i/></w:rPr><w:t xml:space=\"preserve\">keep </w:t>" in xml
    assert "<w:b/></w:rPr><w:t xml:space=\"preserve\"> keep</w:t>" in xml


def test_replace_sets_space_preserve():
    pkg = pkg_of(P(R("ab")))
    out, _ = run_plan(pkg, replace("ab", " a b "))
    assert 'xml:space="preserve"> a b </w:t>' in block_xml(out, "p0")


def test_replace_inside_hyperlink_keeps_link():
    pkg = pkg_of(P(R("See ") + LINK))
    out, _ = run_plan(pkg, replace("leaflet", "guide"))
    xml = block_xml(out, "p0")
    assert "<w:hyperlink" in xml and ">the guide</w:t>" in xml


def test_replace_crossing_hyperlink_boundary_is_refused():
    pkg = pkg_of(P(R("See ") + LINK))
    with pytest.raises(EditError, match="hyperlink boundary"):
        run_plan(pkg, replace("See the", "Read the"))


@pytest.mark.parametrize("protected", [
    IMG,
    '<w:fldSimple w:instr="DATE"><w:r><w:t>1 May</w:t></w:r></w:fldSimple>',
    '<w:ins w:id="1" w:author="a"><w:r><w:t>1 May</w:t></w:r></w:ins>',
])
def test_overlapping_protected_content_is_refused(protected):
    pkg = pkg_of(P(R("Date ") + protected + R(" end")))
    text = texts(pkg)["p0"]
    with pytest.raises(EditError, match="protected"):
        run_plan(pkg, replace(text[3:9], "X"))


def test_tab_can_be_removed_by_a_covering_replacement():
    pkg = pkg_of(P(R("Name:") + "<w:r><w:tab/></w:r>" + R("Ana")))
    out, _ = run_plan(pkg, replace("Name:\tAna", "Name: Ana"))
    assert texts(out)["p0"] == "Name: Ana"
    assert "<w:tab/>" not in block_xml(out, "p0")


def test_ambiguous_match_lists_locations():
    pkg = pkg_of(P(R("the client")) + P(R("the client again")))
    with pytest.raises(EditError, match=r"occurs 2 times.*p0, p1"):
        run_plan(pkg, replace("client", "person", block_id=None))


def test_occurrence_index_and_all():
    pkg = pkg_of(P(R("a-a-a")))
    out, _ = run_plan(pkg, replace("a", "b", occurrence=2))
    assert texts(out)["p0"] == "a-b-a"
    out, _ = run_plan(pkg, replace("a", "c", occurrence="all"))
    assert texts(out)["p0"] == "c-c-c"


def test_occurrence_out_of_range():
    pkg = pkg_of(P(R("a-a")))
    with pytest.raises(EditError, match="out of range"):
        run_plan(pkg, replace("a", "b", occurrence=3))


def test_global_replace_reaches_table_cells():
    tbl = "<w:tbl><w:tr><w:tc>" + P(R("Dr. Lee")) + "</w:tc></w:tr></w:tbl>"
    pkg = pkg_of(P(R("By Dr. Lee")) + tbl)
    out, _ = run_plan(pkg, replace("Dr. Lee", "Dr. Kim", block_id=None, occurrence="all"))
    assert set(texts(out).values()) == {"By Dr. Kim", "Dr. Kim"}


def test_not_found_suggests_case_fix():
    pkg = pkg_of(P(R("Session Notes")))
    with pytest.raises(EditError, match="case differs"):
        run_plan(pkg, replace("session notes", "x"))


def test_not_found_suggests_near_miss():
    pkg = pkg_of(P(R("Dr. Maya Ferreira")))
    with pytest.raises(EditError, match="Closest text"):
        run_plan(pkg, replace("Dr Maya Ferreira", "x"))


def test_unknown_and_readonly_blocks():
    body = "<w:sdt><w:sdtContent>" + P(R("locked")) + "</w:sdtContent></w:sdt>" + P(R("x"))
    pkg = pkg_of(body)
    with pytest.raises(EditError, match="no block"):
        run_plan(pkg, replace("x", "y", block_id="p9"))
    with pytest.raises(EditError, match="read-only"):
        run_plan(pkg, replace("locked", "open"))


def test_line_breaks_in_replacement_are_refused():
    with pytest.raises(EditError, match="line breaks"):
        run_plan(pkg_of(P(R("a"))), replace("a", "b\nc"))


# ------------------------------------------------------------------- delete
def test_delete_text_with_space():
    pkg = pkg_of(P(R("very ") + R("good", BOLD) + R(" result")))
    out, _ = run_plan(pkg, {"op": "delete_text", "block_id": "p0", "find": "very "})
    assert texts(out)["p0"] == "good result"
    assert "very" not in block_xml(out, "p0")


def test_delete_text_refuses_double_space():
    pkg = pkg_of(P(R("a very good result")))
    with pytest.raises(EditError, match="double space"):
        run_plan(pkg, {"op": "delete_text", "block_id": "p0", "find": "very"})


def test_delete_text_refuses_emptying_paragraph():
    with pytest.raises(EditError, match="delete_paragraph"):
        run_plan(pkg_of(P(R("all"))), {"op": "delete_text", "block_id": "p0", "find": "all"})


def test_delete_spanning_runs_removes_emptied_runs():
    pkg = pkg_of(P(R("keep ") + R("drop", BOLD) + R("me ") + R("end")))
    out, _ = run_plan(pkg, {"op": "delete_text", "block_id": "p0", "find": "dropme "})
    xml = block_xml(out, "p0")
    assert texts(out)["p0"] == "keep end"
    assert "<w:b/>" not in xml  # the bold run became empty and was removed


# ------------------------------------------------------------------- insert
@pytest.mark.parametrize("position,anchor,expected", [
    ("before", "world", "hello big world"),
    ("after", "hello", "hello big world"),
])
def test_insert_text_next_to_anchor(position, anchor, expected):
    pkg = pkg_of(P(R("hello ") + R("world", BOLD)))
    text = "big " if position == "before" else " big"
    out, _ = run_plan(pkg, {"op": "insert_text", "block_id": "p0", "position": position,
                            "anchor": anchor, "text": text})
    assert texts(out)["p0"] == expected


def test_insert_text_start_end():
    pkg = pkg_of(P(R("middle")))
    out, _ = run_plan(
        pkg,
        {"op": "insert_text", "block_id": "p0", "position": "start", "text": "Start "},
        {"op": "insert_text", "block_id": "p0", "position": "end", "text": " end."},
    )
    assert texts(out)["p0"] == "Start middle end."


def test_insert_after_hyperlink_stays_outside_link():
    pkg = pkg_of(P(R("See ") + LINK))
    out, _ = run_plan(pkg, {"op": "insert_text", "block_id": "p0", "position": "end",
                            "text": " (PDF)"})
    xml = block_xml(out, "p0")
    assert texts(out)["p0"] == "See the leaflet (PDF)"
    assert xml.index(" (PDF)") > xml.index("</w:hyperlink>")


def test_insert_into_empty_paragraph_uses_mark_formatting():
    pkg = pkg_of(P("", "<w:pPr><w:rPr><w:b/></w:rPr></w:pPr>"))
    out, _ = run_plan(pkg, {"op": "insert_text", "block_id": "p0", "position": "end",
                            "text": "Now filled"})
    assert texts(out)["p0"] == "Now filled"
    assert "<w:r><w:rPr><w:b/></w:rPr><w:t>Now filled" in block_xml(out, "p0")


def test_insert_text_requires_anchor():
    with pytest.raises(EditError, match="anchor is required"):
        run_plan(pkg_of(P(R("x"))), {"op": "insert_text", "block_id": "p0",
                                     "position": "after", "text": "y"})


# -------------------------------------------------------- insert paragraph
LIST_PPR = ('<w:pPr><w:pStyle w:val="ListBullet"/><w:numPr><w:ilvl w:val="0"/>'
            '<w:numId w:val="1"/></w:numPr></w:pPr>')


def test_insert_paragraph_copies_list_formatting_and_dominant_run():
    pkg = pkg_of(P(R("Note: ", BOLD) + R("a fairly long plain item"), LIST_PPR) + P(R("after")))
    out, _ = run_plan(pkg, {"op": "insert_paragraph", "target_id": "p0", "position": "after",
                            "text": "Second item", "format_like": "p0"})
    assert list(texts(out).values()) == ["Note: a fairly long plain item", "Second item", "after"]
    xml = block_xml(out, "p1")
    assert '<w:numId w:val="1"/>' in xml
    assert "<w:b/>" not in xml  # dominant (plain) formatting, not the bold label


def test_insert_multiple_paragraphs_keeps_order():
    pkg = pkg_of(P(R("a")) + P(R("d")))
    out, _ = run_plan(pkg, {"op": "insert_paragraph", "target_id": "p0", "position": "after",
                            "text": "b\nc", "format_like": "p0"})
    assert list(texts(out).values()) == ["a", "b", "c", "d"]


def test_insert_paragraph_before_and_after_table():
    tbl = "<w:tbl><w:tr><w:tc>" + P(R("cell")) + "</w:tc></w:tr></w:tbl>"
    pkg = pkg_of(P(R("intro")) + tbl + P(R("outro")))
    out, _ = run_plan(
        pkg,
        {"op": "insert_paragraph", "target_id": "t0", "position": "after", "text": "below",
         "format_like": "p0"},
        {"op": "insert_paragraph", "target_id": "t0", "position": "before", "text": "above",
         "format_like": "p0"},
    )
    assert list(texts(out).values()) == ["intro", "above", "cell", "below", "outro"]


def test_insert_paragraph_does_not_copy_section_break():
    ppr = "<w:pPr><w:sectPr><w:pgSz w:w='100' w:h='100'/></w:sectPr></w:pPr>"
    pkg = pkg_of(P(R("end of section"), ppr) + P(R("next")))
    out, _ = run_plan(pkg, {"op": "insert_paragraph", "target_id": "p1", "position": "after",
                            "text": "new", "format_like": "p0"})
    assert "sectPr" not in block_xml(out, "p2")


def test_insert_paragraph_in_table_cell():
    tbl = "<w:tbl><w:tr><w:tc>" + P(R("first")) + "</w:tc></w:tr></w:tbl>"
    out, _ = run_plan(pkg_of(tbl), {"op": "insert_paragraph", "target_id": "t0.r0.c0.p0",
                                    "position": "after", "text": "second",
                                    "format_like": "t0.r0.c0.p0"})
    assert texts(out) == {"t0.r0.c0.p0": "first", "t0.r0.c0.p1": "second"}


# -------------------------------------------------------- delete paragraph
def test_delete_paragraph():
    pkg = pkg_of(P(R("a")) + P(R("b")) + P(R("c")))
    out, _ = run_plan(pkg, {"op": "delete_paragraph", "block_id": "p1"})
    assert list(texts(out).values()) == ["a", "c"]


def test_delete_paragraph_with_balanced_bookmark_is_allowed():
    body = P('<w:bookmarkStart w:id="1" w:name="x"/>' + R("a") + '<w:bookmarkEnd w:id="1"/>')
    out, _ = run_plan(pkg_of(body + P(R("b"))), {"op": "delete_paragraph", "block_id": "p0"})
    assert list(texts(out).values()) == ["b"]


@pytest.mark.parametrize("body,target_text,match", [
    (P(IMG) + P(R("x")), "⟦IMAGE⟧", "image"),
    ("<w:tbl><w:tr><w:tc>" + P(R("only")) + "</w:tc></w:tr></w:tbl>", "only", "only paragraph"),
    ("<w:tbl><w:tr><w:tc>" + P(R("a")) + "</w:tc></w:tr></w:tbl>" + P(R("gap"))
     + "<w:tbl><w:tr><w:tc>" + P(R("b")) + "</w:tc></w:tr></w:tbl>", "gap", "merge"),
    (P(R("s"), "<w:pPr><w:sectPr/></w:pPr>") + P(R("x")), "s", "section break"),
    (P('<w:commentRangeStart w:id="0"/>' + R("c") + '<w:commentRangeEnd w:id="0"/>') + P(R("x")),
     "c", "comment"),
    (P('<w:bookmarkStart w:id="1" w:name="x"/>' + R("a")) + P(R("b") + '<w:bookmarkEnd w:id="1"/>'),
     "a", "bookmark"),
])
def test_delete_paragraph_refusals(body, target_text, match):
    pkg = pkg_of(body)
    target = next(b.id for b in build_index(pkg).paragraphs()
                  if paragraph_view(b.element).text == target_text)
    with pytest.raises(EditError, match=match):
        run_plan(pkg, {"op": "delete_paragraph", "block_id": target})


def test_reference_after_delete_is_refused():
    pkg = pkg_of(P(R("a")) + P(R("b")))
    with pytest.raises(EditError, match="was deleted by operation #1"):
        run_plan(pkg, {"op": "delete_paragraph", "block_id": "p0"}, replace("a", "z"))


# ----------------------------------------------------------------- format
def test_format_text_bold_splits_runs_and_keeps_other_properties():
    pkg = pkg_of(P(R("make this bold please", ITALIC)))
    out, _ = run_plan(pkg, {"op": "format_text", "block_id": "p0", "find": "this bold",
                            "bold": True})
    xml = block_xml(out, "p0")
    assert texts(out)["p0"] == "make this bold please"
    assert "<w:rPr><w:b/><w:i/></w:rPr><w:t>this bold</w:t>" in xml  # schema order b before i
    assert xml.count("<w:i/>") == 3


def test_format_text_can_switch_bold_off():
    pkg = pkg_of(P(R("Loud", BOLD) + R(" quiet")))
    out, _ = run_plan(pkg, {"op": "format_text", "block_id": "p0", "find": "Loud", "bold": False})
    assert '<w:b w:val="0"/>' in block_xml(out, "p0")


def test_format_text_needs_a_property():
    with pytest.raises(EditError, match="at least one"):
        run_plan(pkg_of(P(R("x"))), {"op": "format_text", "block_id": "p0", "find": "x"})


# --------------------------------------------------------- whole sample docs
def test_realistic_multi_operation_plan(session_note):
    out, report = run_plan(
        session_note,
        replace("6 of 12", "7 of 12", block_id="t0.r2.c1.p0"),
        replace("anxiety remains", "stress remains", block_id="p5"),
        {"op": "delete_text", "block_id": "p6", "find": " Review again next session."},
        {"op": "insert_paragraph", "target_id": "p10", "position": "after",
         "text": "Grounding exercise (5-4-3-2-1)", "format_like": "p10"},
        replace("Dr. Maya Ferreira", "Dr. Ana Costa", block_id=None, occurrence="all"),
        {"op": "format_text", "block_id": "p17", "find": "two thought records", "bold": True},
    )
    t = texts(out)
    assert t["t0.r2.c1.p0"] == "7 of 12"
    assert "Dr. Maya Ferreira" not in " ".join(t.values())
    assert report.passed
