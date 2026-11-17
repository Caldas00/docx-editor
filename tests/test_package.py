import io
import zipfile

import pytest
from helpers import P, R, make_docx

from docx_agent.document import DocxError, DocxPackage
from docx_agent.document.verify import c14n


def test_roundtrip_without_edits_is_lossless(session_note_bytes):
    pkg = DocxPackage(session_note_bytes)
    out = pkg.to_bytes()
    src = zipfile.ZipFile(io.BytesIO(session_note_bytes))
    dst = zipfile.ZipFile(io.BytesIO(out))
    assert [i.filename for i in src.infolist()] == [i.filename for i in dst.infolist()]
    for info in src.infolist():
        if info.filename == pkg.main_part_name:
            continue
        assert src.read(info) == dst.read(info.filename), info.filename
    # main part: canonically identical
    again = DocxPackage(out)
    assert c14n(again.document) == c14n(DocxPackage(session_note_bytes).document)


def test_rejects_non_zip():
    with pytest.raises(DocxError, match="not a zip"):
        DocxPackage(b"hello")


def test_rejects_zip_without_word_document():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("foo.txt", "x")
    with pytest.raises(DocxError):
        DocxPackage(buf.getvalue())


def test_rejects_malformed_xml():
    data = make_docx(P(R("ok")))
    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for info in src.infolist():
            payload = b"<w:document><broken" if info.filename == "word/document.xml" \
                else src.read(info)
            z.writestr(info, payload)
    with pytest.raises(DocxError, match="malformed"):
        DocxPackage(out.getvalue())


def test_external_entities_are_not_expanded(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP-SECRET")
    data = make_docx(P(R("x")))
    src = zipfile.ZipFile(io.BytesIO(data))
    xml = src.read("word/document.xml").decode()
    xml = xml.replace(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f'<?xml version="1.0"?><!DOCTYPE d [<!ENTITY x SYSTEM "file://{secret}">]>',
    ).replace(">x<", ">&x;<")
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for info in src.infolist():
            z.writestr(info, xml.encode() if info.filename == "word/document.xml" else src.read(info))
    try:
        pkg = DocxPackage(out.getvalue())
    except DocxError:
        return  # refusing is also fine
    assert b"TOP-SECRET" not in pkg.to_bytes()
