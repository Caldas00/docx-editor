from helpers import BOLD, ITALIC, P, R, pkg_of, texts

from docx_agent.document.model import build_index, paragraph_view, render_outline


def test_words_split_across_runs_are_joined():
    pkg = pkg_of(P(R("anx") + R("iety") + R(" rises", BOLD)))
    assert texts(pkg)["p0"] == "anxiety rises"


def test_block_ids_cover_tables_and_nested_tables():
    cell = lambda inner: f"<w:tc>{inner}</w:tc>"  # noqa: E731
    nested = f"<w:tbl><w:tr>{cell(P(R('deep')))}</w:tr></w:tbl>{P('')}"
    body = (P(R("intro")) + f"<w:tbl><w:tr>{cell(P(R('a')))}{cell(P(R('b')) + nested)}</w:tr></w:tbl>"
            + P(R("outro")))
    ids = [b.id for b in build_index(pkg_of(body)).blocks]
    assert ids == ["p0", "t0", "t0.r0.c0.p0", "t0.r0.c1.p0", "t0.r0.c1.t0",
                   "t0.r0.c1.t0.r0.c0.p0", "t0.r0.c1.p1", "p1"]


def test_protected_and_hidden_content():
    body = P(
        R("A")
        + "<w:r><w:tab/></w:r>"
        + "<w:r><w:br/></w:r>"
        + '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
        + '<w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
        + '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
        + R("3")
        + '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
        + '<w:ins w:id="1" w:author="x">' + R("new") + "</w:ins>"
        + '<w:del w:id="2" w:author="x"><w:r><w:delText>old</w:delText></w:r></w:del>'
        + '<w:bookmarkStart w:id="0" w:name="b"/>' + R("Z") + '<w:bookmarkEnd w:id="0"/>'
    )
    view = paragraph_view(build_index(pkg_of(body)).get("p0").element)
    assert view.text == "A\t\n3newZ"
    labels = [(p.text, p.kind, p.label) for p in view.pieces]
    assert labels == [
        ("A", "text", None), ("\t", "protected", "TAB"), ("\n", "protected", "BR"),
        ("3", "protected", "FIELD"), ("new", "protected", "TRACKED_CHANGE"), ("Z", "text", None),
    ]


def test_content_control_blocks_are_read_only():
    body = ("<w:sdt><w:sdtPr/><w:sdtContent>" + P(R("locked")) + "</w:sdtContent></w:sdt>"
            + P(R("free")))
    idx = build_index(pkg_of(body))
    assert not idx.get("p0").editable
    assert idx.get("p1").editable


def test_outline_mentions_formatting_and_links(session_note):
    outline, truncated = render_outline(session_note)
    assert not truncated
    assert 'bold="improved sleep"' in outline
    assert 'italic="two weeks"' in outline
    assert 'link="Sleep hygiene leaflet"' in outline
    assert "⟦IMAGE⟧" in outline
    assert "(Heading 1)" in outline


def test_outline_truncation(session_note):
    outline, truncated = render_outline(session_note, max_chars=300)
    assert truncated
    assert "search_document" in outline


def test_italic_only_paragraph_note():
    outline, _ = render_outline(pkg_of(P(R("all italic", ITALIC))))
    assert "all italic" in outline
