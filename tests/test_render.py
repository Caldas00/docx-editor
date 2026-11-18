"""The HTML preview shows the document's structure and the redline marks exactly what changed."""

import re

from helpers import BOLD, P, R, pkg_of, plan

from docx_agent.document import DocxPackage, apply_plan
from docx_agent.document.render import render_preview, render_redline


def test_preview_renders_structure(session_note):
    html = render_preview(session_note)
    title = re.search(r'<div class="para"[^>]*data-bid="p0">Session Progress Note</div>', html)
    assert title and "font-size:26.0pt" in title.group(0)  # the Title style's own size
    assert 'data-bid="t0.r2.c1.p0"' in html and 'data-row="t0.r2"' in html
    assert "<table" in html and "data:image/png;base64," in html
    assert re.search(r'font-weight:700[^"]*">Dr\. Maya Ferreira</span>', html)
    assert 'class="link"' in html


def test_redline_marks_insertions_deletions_and_formatting():
    before = pkg_of(P(R("Risk is ") + R("high", BOLD) + R(" today")) + P(R("drop me")) + P(R("end")))
    p = plan(
        {"op": "replace_text", "block_id": "p0", "find": "high", "replace_with": "low"},
        {"op": "format_text", "block_id": "p0", "find": "today", "italic": True},
        {"op": "delete_paragraph", "block_id": "p1"},
        {"op": "insert_paragraph", "target_id": "p2", "position": "after", "text": "added",
         "format_like": "p2"},
    )
    after = before.copy()
    apply_plan(after, p)
    html = render_redline(before, after, p)
    assert re.search(r'<del><span style="font-weight:700">high</span></del>'
                     r'<ins><span style="font-weight:700">low</span></ins>', html)
    assert 'class="fmt-changed"' in html
    assert "block-del" in html and "<del>drop me</del>" in html
    assert "block-ins" in html and "<ins>added</ins>" in html


def test_redline_trims_unchanged_words():
    before = pkg_of(P(R("Session 6 of 12")))
    p = plan({"op": "replace_text", "block_id": "p0", "find": "6 of 12", "replace_with": "7 of 12"})
    after = before.copy()
    apply_plan(after, p)
    html = render_redline(before, after, p)
    assert "Session <del>6</del><ins>7</ins> of 12" in html


def test_redline_shows_row_and_picture_changes(api_reference_bytes):
    before = DocxPackage(api_reference_bytes)
    p = plan({"op": "delete_table_rows", "rows": ["t0.r4"]},
             {"op": "insert_table_row", "row": "t0.r1", "position": "after",
              "cells": ["void", "reset()", "Clears the note."]},
             {"op": "delete_images", "images": ["#5"]})
    after = before.copy()
    apply_plan(after, p)
    html = render_redline(before, after, p)
    assert html.count('class="row-ins"') == 1 and html.count('class="row-del"') == 1
    assert re.search(r"<del>(<span[^>]*>)?set_date\(Date d\)", html)
    assert "<del><img" in html


def test_redline_shows_deleted_table(api_reference_bytes):
    before = DocxPackage(api_reference_bytes)
    p = plan({"op": "delete_table", "table_id": "t0"})
    after = before.copy()
    apply_plan(after, p)
    html = render_redline(before, after, p)
    assert "tbl-del" in html and re.search(r"<del>(<span[^>]*>)?get_client_id\(\)", html)


def test_header_picture_is_rendered(session_note):
    html = render_preview(session_note)
    header = html.split('data-part="hdr1"', 1)[1].split("</div>", 1)[0]
    assert "data:image/png;base64," in header


def _hf(label: str, kind: str, body: str, *uses: str):
    from lxml import etree

    from docx_agent.document.package import HeaderFooterPart
    tag = "hdr" if kind == "header" else "ftr"
    root = etree.fromstring(
        f'<w:{tag} xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        f'xmlns:v="urn:schemas-microsoft-com:vml">{body}</w:{tag}>')
    return HeaderFooterPart(label, kind, f"word/{label}.xml", root, list(uses))


SHAPE_ONLY = '<w:p><w:r><w:pict><v:shape id="WordArt1" style="width:10pt;height:10pt"/></w:pict></w:r></w:p>'


def test_preview_hides_shape_only_headers_and_merges_identical_variants():
    pkg = pkg_of(P(R("Body text")))
    pkg.hf_parts = [
        _hf("hdr1", "header", SHAPE_ONLY, "even, section 1"),
        _hf("hdr2", "header", SHAPE_ONLY, "default, section 1"),
        _hf("hdr3", "header", "<w:p/>", "first, section 1"),
        _hf("ftr1", "footer", P(R("ELFIO tutorial")), "even, section 1"),
        _hf("ftr2", "footer", P(R("ELFIO tutorial")), "default, section 1"),
        _hf("ftr3", "footer", P(R("Cover")), "first, section 1"),
    ]
    html = render_preview(pkg)
    assert ">shape<" not in html and 'data-part="hdr' not in html
    assert html.count("ELFIO tutorial") == 1
    assert '<span class="hf-label">Footer</span>' in html
    assert '<span class="hf-label">Footer · first page</span>' in html
    # the default footer comes first, the first-page variant after it
    assert html.index('data-part="ftr2"') < html.index('data-part="ftr3"')


def _page_field(cached: str) -> str:
    return ('<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r>'
            '<w:r><w:instrText xml:space="preserve"> PAGE \\* MERGEFORMAT </w:instrText></w:r>'
            '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
            f'<w:r><w:t>{cached}</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>')


def test_page_number_footers_show_once_without_stale_numbers():
    pkg = pkg_of(P(R("Body text")))
    pkg.hf_parts = [
        _hf("ftr1", "footer", SHAPE_ONLY + _page_field("vi"), "even, section 1"),
        _hf("ftr2", "footer", SHAPE_ONLY + _page_field("2"), "default, section 1"),
        _hf("ftr3", "footer", SHAPE_ONLY + _page_field("0"), "first, section 1"),
    ]
    html = render_preview(pkg)
    assert html.count('class="hf"') == 1 and '<span class="hf-label">Footer</span>' in html
    assert 'title="Page number (Word fills it in)">#</span>' in html
    assert ">vi<" not in html and ">2<" not in html and ">shape<" not in html


def test_redline_marks_a_converted_table_with_one_bar_not_green_cells():
    # "Why is the table green?" - every row of a table made from existing paragraphs was
    # painted as inserted. The table now gets a single blue "moved" bar; a table with new
    # content gets a green one; rows added to an existing table are still filled green.
    before = pkg_of(P(R("name")) + P(R("desc")) + P(R("end")))
    p = plan({"op": "blocks_to_table", "block_ids": ["p0", "p1"], "columns": 2})
    after = before.copy()
    apply_plan(after, p)
    html = render_redline(before, after, p)
    assert 'class="doc-table tbl-moved"' in html and "row-ins" not in html

    # removed blank lines are not drawn as empty struck-through paragraphs
    before = pkg_of(P(R("name")) + P("") + P(R("desc")) + P(R("end")))
    p = plan({"op": "blocks_to_table", "block_ids": ["p0", "p1", "p2"], "columns": 2})
    after = before.copy()
    apply_plan(after, p)
    assert "block-del" not in render_redline(before, after, p)

    p = plan({"op": "insert_table", "target_id": "p2", "position": "after",
              "rows": [["1"], ["2"]], "format_like": "p2", "table_like": None})
    after = before.copy()
    apply_plan(after, p)
    html = render_redline(before, after, p)
    assert 'class="doc-table tbl-ins"' in html and "row-ins" not in html


def test_redline_marks_reordered_rows_as_moved(api_reference_bytes):
    before = DocxPackage(api_reference_bytes)
    p = plan({"op": "reorder_table_rows", "order": ["t0.r3", "t0.r2", "t0.r1"]})
    after = before.copy()
    apply_plan(after, p)
    html = render_redline(before, after, p)
    assert html.count('class="row-moved"') == 2  # r2 keeps its place in a reversal of three


# ------------------------------------------------- formatting read from the document
def test_preview_numbers_lists_like_word(session_note):
    html = render_preview(session_note)
    labels = re.findall(r'<span class="num-label"[^>]*>([^<]*)</span>', html)
    assert labels[-3:] == ["1.", "2.", "3."]  # the "5. Plan" numbered list


def test_theme_colour_wins_over_its_cached_value_and_explicit_fonts_win_over_theme_fonts():
    from docx_agent.document.styles import StyleSheet
    pkg = pkg_of(P(R("x", '<w:color w:val="FF0000" w:themeColor="accent1"/>'
                          '<w:rFonts w:ascii="Courier New" w:hAnsi="Courier New"/>')))
    sheet = StyleSheet(pkg)
    accent = sheet.colors["accent1"]
    html = render_preview(pkg)
    assert f"color:#{accent}" in html and "FF0000" not in html.upper().replace(accent, "")
    assert "Courier New" in html


def test_hidden_text_is_hidden_but_web_hidden_text_is_shown():
    html = render_preview(pkg_of(P(R("shown ") + R("secret", "<w:vanish/>")
                                   + R("page 7", "<w:webHidden/>"))))
    assert "secret" not in html and "page 7" in html


def test_content_controls_and_tables_without_borders_are_shown_as_in_word():
    sdt = ("<w:sdt><w:sdtPr/><w:sdtContent>" + P(R("Table of Contents"))
           + "</w:sdtContent></w:sdt>")
    table = ("<w:tbl><w:tblPr/><w:tblGrid><w:gridCol w:w=\"2000\"/></w:tblGrid>"
             "<w:tr><w:tc>" + P(R("cell")) + "</w:tc></w:tr></w:tbl>")
    html = render_preview(pkg_of(sdt + table + P(R("end"))))
    assert "Table of Contents" in html
    cell = re.search(r"<td style=\"([^\"]*)\"", html).group(1)
    assert "border-top:none" in cell  # no table style borders -> none drawn
