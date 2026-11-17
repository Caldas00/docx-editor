"""Unit tests for the edit engine. Every successful edit is also run through the
integrity verifier (``run_plan`` asserts the report passes)."""

import pytest
from helpers import BOLD, ITALIC, P, R, block_xml, pkg_of, run_plan, texts

from docx_agent.document import EditError
from docx_agent.document.model import build_index, paragraph_view

LINK = ('<w:hyperlink r:id="rId99"><w:r><w:rPr><w:rStyle w:val="Hyperlink"/></w:rPr>'
        '<w:t>the leaflet</w:t></w:r></w:hyperlink>')
IMG = ('<w:r><w:drawing><wp:inline><wp:extent cx="114300" cy="114300"/>'
       '<wp:docPr id="1" name="icon"/><a:graphic><a:graphicData><pic:pic><pic:blipFill>'
       '<a:blip r:embed="rId99"/></pic:blipFill></pic:pic></a:graphicData></a:graphic>'
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
    (P(IMG) + P(R("x")), "⟦IMAGE#1⟧", "image"),
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


# ------------------------------------------------- formatting (colour, size...)
GREEN = '<w:color w:val="70AD47"/>'


def test_format_text_colour_highlight_and_size():
    pkg = pkg_of(P(R("plain then coloured words", ITALIC)))
    out, _ = run_plan(pkg, {"op": "format_text", "block_id": "p0", "find": "coloured",
                            "color": "7030a0", "highlight": "yellow", "font_size": 14})
    xml = block_xml(out, "p0")
    assert ('<w:rPr><w:i/><w:color w:val="7030A0"/><w:sz w:val="28"/><w:szCs w:val="28"/>'
            '<w:highlight w:val="yellow"/></w:rPr><w:t>coloured</w:t>') in xml


def test_format_text_replaces_theme_colour():
    pkg = pkg_of(P(R("x", '<w:color w:val="70AD47" w:themeColor="accent6"/>')))
    out, _ = run_plan(pkg, {"op": "format_text", "block_id": "p0", "find": "x", "color": "auto"})
    assert '<w:color w:val="auto"/>' in block_xml(out, "p0")


def test_restyle_changes_every_matching_run_only():
    body = (P(R("Green title", GREEN + BOLD)) + P(R("black ") + R("green word", GREEN))
            + "<w:tbl><w:tr><w:tc>" + P(R("green cell", GREEN)) + "</w:tc></w:tr></w:tbl>"
            + P(R("red", '<w:color w:val="FF0000"/>')))
    out, report = run_plan(pkg_of(body), {"op": "restyle_text", "match": {"color": "70ad47"},
                                          "set": {"color": "7030A0"}})
    xml = "".join(block_xml(out, b) for b in ("p0", "p1", "t0.r0.c0.p0", "p2"))
    assert xml.count('w:val="7030A0"') == 3 and "70AD47" not in xml
    assert '<w:color w:val="FF0000"/>' in xml and "<w:b/>" in xml
    assert report.passed


def test_restyle_reports_what_exists_when_nothing_matches():
    pkg = pkg_of(P(R("red", '<w:color w:val="FF0000"/>')))
    with pytest.raises(EditError, match=r"color=FF0000 \(1 runs\)"):
        run_plan(pkg, {"op": "restyle_text", "match": {"color": "00B050"},
                       "set": {"color": "7030A0"}})


def test_restyle_by_bold_scoped_to_one_paragraph():
    pkg = pkg_of(P(R("a", BOLD) + R(" b")) + P(R("c", BOLD)))
    out, _ = run_plan(pkg, {"op": "restyle_text", "block_id": "p0", "match": {"bold": True},
                            "set": {"bold": False, "underline": True}})
    assert '<w:b w:val="0"/><w:u w:val="single"/>' in block_xml(out, "p0")
    assert "<w:b/>" in block_xml(out, "p1")


# ------------------------------------------------------------------ images
def icon(n: int, px: int = 12) -> str:
    emu = px * 9525
    return (f'<w:r><w:drawing><wp:inline><wp:extent cx="{emu}" cy="{emu}"/>'
            f'<wp:docPr id="{n}" name="icon{n}"/><a:graphic><a:graphicData><pic:pic>'
            f'<pic:blipFill><a:blip r:embed="rId9{n}"/></pic:blipFill></pic:pic>'
            f'</a:graphicData></a:graphic></wp:inline></w:drawing></w:r>')


def test_images_get_stable_refs_in_the_text():
    pkg = pkg_of(P(R("code ") + icon(7)))
    assert texts(pkg)["p0"] == "code ⟦IMAGE#7⟧"


def test_delete_images_by_ref_and_by_size():
    big = icon(9, px=300)
    pkg = pkg_of(P(R("a ") + icon(7) + R(" b") + icon(8)) + P(big))
    out, report = run_plan(pkg, {"op": "delete_images", "images": ["#7"]})
    assert texts(out)["p0"] == "a  b⟦IMAGE#8⟧"
    out, report = run_plan(pkg, {"op": "delete_images", "max_size_px": 16})
    assert texts(out) == {"p0": "a  b", "p1": "⟦IMAGE#9⟧"}
    assert "1 images" in report.checks[-2].detail


def test_delete_images_errors_list_available_pictures():
    pkg = pkg_of(P(icon(7)))
    with pytest.raises(EditError, match=r"#99.*IMAGE#7⟧ 12x12px"):
        run_plan(pkg, {"op": "delete_images", "images": ["#99"]})
    with pytest.raises(EditError, match="needs `images`"):
        run_plan(pkg, {"op": "delete_images"})


def test_shapes_are_not_deleted_as_images():
    shape = ('<w:r><w:drawing><wp:anchor><wp:extent cx="95250" cy="95250"/>'
             '<wp:docPr id="5" name="Text Box 5"/></wp:anchor></w:drawing></w:r>')
    pkg = pkg_of(P(R("x") + shape))
    assert texts(pkg)["p0"] == "x⟦SHAPE#5⟧"
    with pytest.raises(EditError, match="Could not find"):
        run_plan(pkg, {"op": "delete_images", "max_size_px": 50})


def test_delete_paragraph_with_picture_needs_explicit_flag():
    pkg = pkg_of(P(icon(3)) + P(R("x")))
    with pytest.raises(EditError, match="delete_images=true"):
        run_plan(pkg, {"op": "delete_paragraph", "block_id": "p0"})
    out, _ = run_plan(pkg, {"op": "delete_paragraph", "block_id": "p0", "delete_images": True})
    assert list(texts(out).values()) == ["x"]


# ------------------------------------------------------------------ tables
def table(rows: list[list[str]], header_props: str = "") -> str:
    out = "<w:tbl><w:tblPr/><w:tblGrid><w:gridCol/><w:gridCol/></w:tblGrid>"
    for i, row in enumerate(rows):
        trpr = f"<w:trPr>{header_props}</w:trPr>" if i == 0 and header_props else ""
        cells = "".join(f'<w:tc><w:tcPr><w:shd w:val="clear" w:fill="EEEEEE"/></w:tcPr>'
                        f"{P(R(c, BOLD if i == 0 else ''))}</w:tc>" for c in row)
        out += f"<w:tr>{trpr}{cells}</w:tr>"
    return out + "</w:tbl>"


TBL = P(R("intro")) + table([["Name", "Value"], ["a", "1"], ["b", "2"], ["c", "3"]],
                            "<w:tblHeader/>") + P(R("outro"))


def row_texts(pkg) -> list[str]:
    t = texts(pkg)
    rows: dict[str, list[str]] = {}
    for bid, txt in t.items():
        if bid.startswith("t0.r"):
            rows.setdefault(bid.split(".c")[0], []).append(txt)
    return [" | ".join(v) for v in rows.values()]


def test_delete_table_rows():
    out, _ = run_plan(pkg_of(TBL), {"op": "delete_table_rows", "rows": ["t0.r1", "t0.r3"]})
    assert row_texts(out) == ["Name | Value", "b | 2"]


def test_insert_table_row_copies_body_row_formatting():
    out, report = run_plan(pkg_of(TBL), {"op": "insert_table_row", "row": "t0.r2",
                                         "position": "after", "cells": ["new", "9\n10"]})
    assert row_texts(out) == ["Name | Value", "a | 1", "b | 2", "new | 9 | 10", "c | 3"]
    xml = block_xml(out, "t0.r3.c0.p0")
    assert "<w:b/>" not in xml
    assert report.passed


def test_inserted_row_from_header_template_is_not_a_header():
    out, _ = run_plan(pkg_of(TBL), {"op": "insert_table_row", "row": "t0.r0", "position": "after",
                                    "cells": ["x", "y"], "format_like_row": "t0.r0"})
    tbl = build_index(out).get("t0").element
    from docx_agent.document.ns import qn
    assert len(list(tbl.iter(qn("w:tblHeader")))) == 1


def test_row_ids_keep_original_numbering_within_a_plan():
    out, _ = run_plan(pkg_of(TBL),
                      {"op": "delete_table_rows", "rows": ["t0.r1"]},
                      {"op": "insert_table_row", "row": "t0.r3", "position": "after",
                       "cells": ["d", "4"]},
                      {"op": "replace_text", "block_id": "t0.r2.c1.p0", "find": "2",
                       "replace_with": "22"})
    assert row_texts(out) == ["Name | Value", "b | 22", "c | 3", "d | 4"]


@pytest.mark.parametrize("op,match", [
    ({"op": "delete_table_rows", "rows": ["t0.r0", "t0.r1", "t0.r2", "t0.r3"]}, "delete_table"),
    ({"op": "delete_table_rows", "rows": ["t0.r9"]}, "only 4 rows"),
    ({"op": "delete_table_rows", "rows": ["t0"]}, "not a row id"),
    ({"op": "insert_table_row", "row": "t0.r1", "position": "after", "cells": ["one"]},
     "has 2 cells"),
])
def test_table_row_refusals(op, match):
    with pytest.raises(EditError, match=match):
        run_plan(pkg_of(TBL), op)


def test_row_starting_a_vertical_merge_is_refused():
    merged = ("<w:tbl><w:tr><w:tc><w:tcPr><w:vMerge w:val=\"restart\"/></w:tcPr>" + P(R("m"))
              + "</w:tc></w:tr><w:tr><w:tc><w:tcPr><w:vMerge/></w:tcPr>" + P("")
              + "</w:tc></w:tr><w:tr><w:tc>" + P(R("z")) + "</w:tc></w:tr></w:tbl>" + P(R("x")))
    with pytest.raises(EditError, match="vertically merged"):
        run_plan(pkg_of(merged), {"op": "delete_table_rows", "rows": ["t0.r0"]})
    out, _ = run_plan(pkg_of(merged), {"op": "delete_table_rows", "rows": ["t0.r0", "t0.r1"]})
    assert texts(out)["t0.r0.c0.p0"] == "z"


def test_delete_table_and_reference_after_it():
    out, _ = run_plan(pkg_of(TBL), {"op": "delete_table", "table_id": "t0"})
    assert list(texts(out).values()) == ["intro", "outro"]
    with pytest.raises(EditError, match="removed by an earlier operation"):
        run_plan(pkg_of(TBL), {"op": "delete_table", "table_id": "t0"},
                 {"op": "replace_text", "block_id": "t0.r1.c0.p0", "find": "a",
                  "replace_with": "z"})


def test_row_id_used_as_paragraph_gets_a_hint():
    with pytest.raises(EditError, match="is a table row"):
        run_plan(pkg_of(TBL), {"op": "delete_paragraph", "block_id": "t0.r1"})


# --------------------------------------------------------------- new tables
def new_table(target="p0", position="after", rows=(("1",), ("2",)), **kw):
    return {"op": "insert_table", "target_id": target, "position": position,
            "rows": [list(r) for r in rows], "format_like": kw.pop("format_like", "p0"), **kw}


def test_insert_table_with_header_and_grid():
    pkg = pkg_of(P(R("intro")) + P(R("outro")))
    out, report = run_plan(pkg, new_table(rows=(("N", "Square"), ("1", "1"), ("2", "4")),
                                          header=True))
    t = texts(out)
    assert t["t0.r0.c0.p0"] == "N" and t["t0.r2.c1.p0"] == "4"
    assert list(t)[-1] == "p1" and t["p1"] == "outro"
    xml = block_xml(out, "t0.r0.c0.p0")
    assert "<w:b/>" in xml
    tbl = build_index(out).get("t0").element
    from docx_agent.document.ns import qn
    assert len(list(tbl.iter(qn("w:tblHeader")))) == 1
    assert len(list(tbl.iter(qn("w:gridCol")))) == 2
    assert report.passed


def test_insert_table_at_end_of_body_gets_a_closing_paragraph():
    pkg = pkg_of(P(R("only")))
    out, _ = run_plan(pkg, new_table())
    assert list(texts(out)) == ["p0", "t0.r0.c0.p0", "t0.r1.c0.p0", "p1"]
    assert texts(out)["p1"] == ""


def test_insert_table_next_to_a_table_keeps_them_apart():
    pkg = pkg_of(P(R("a")) + table([["x", "y"], ["1", "2"]]) + P(R("b")))
    out, _ = run_plan(pkg, new_table(target="t0", rows=(("new", "row"),), table_like="t0"))
    ids = list(texts(out))
    assert ids.index("p1") < ids.index("t1.r0.c0.p0")  # spacer paragraph between the tables
    assert texts(out)["p1"] == ""


def test_insert_table_rows_must_be_rectangular():
    import pydantic

    with pytest.raises(pydantic.ValidationError, match="same number of cells"):
        run_plan(pkg_of(P(R("a"))), new_table(rows=(("1", "2"), ("3",))))


def test_table_inside_a_cell():
    pkg = pkg_of("<w:tbl><w:tr><w:tc>" + P(R("cell")) + "</w:tc></w:tr></w:tbl>" + P(R("x")))
    out, _ = run_plan(pkg, new_table(target="t0.r0.c0.p0", format_like="t0.r0.c0.p0"))
    t = texts(out)
    assert t["t0.r0.c0.t0.r1.c0.p0"] == "2" and t["t0.r0.c0.p1"] == ""


def test_not_found_points_to_the_right_block():
    pkg = pkg_of(P(R("first line")) + P(R("second line")))
    with pytest.raises(EditError, match="It does appear in p0"):
        run_plan(pkg, replace("first", "1st", block_id="p1"))
