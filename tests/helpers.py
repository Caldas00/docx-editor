"""Test helpers: build .docx files from raw body XML and run plans."""

from __future__ import annotations

import io
import zipfile
from functools import lru_cache

from docx import Document

from docx_agent.document import DocxPackage, EditPlan, apply_plan, verify_edit
from docx_agent.document.model import build_index, paragraph_view

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_DECL = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" '
    'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
    'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
    'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
    'xmlns:v="urn:schemas-microsoft-com:vml"'
)


def TEXT_BOX(text: str, fill: str = "00B050", docpr: int = 7) -> str:
    """A run with a filled text box shape, as Word writes it: DrawingML in mc:Choice and a
    VML copy (same text) in mc:Fallback."""
    body = f'<w:p><w:r><w:t>{text}</w:t></w:r></w:p>'
    return (
        '<w:r><mc:AlternateContent><mc:Choice Requires="wps"><w:drawing><wp:inline>'
        '<wp:extent cx="1905000" cy="381000"/>'
        f'<wp:docPr id="{docpr}" name="Banner {docpr}"/><a:graphic><a:graphicData '
        'uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"><wps:wsp>'
        '<wps:cNvPr id="1" name="box"/><wps:spPr><a:xfrm><a:off x="0" y="0"/>'
        '<a:ext cx="1905000" cy="381000"/></a:xfrm><a:prstGeom prst="rect"/>'
        f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill></wps:spPr>'
        f'<wps:txbx><w:txbxContent>{body}</w:txbxContent></wps:txbx><wps:bodyPr/></wps:wsp>'
        '</a:graphicData></a:graphic></wp:inline></w:drawing></mc:Choice><mc:Fallback>'
        f'<w:pict><v:rect fillcolor="#{fill}"><v:textbox><w:txbxContent>{body}'
        '</w:txbxContent></v:textbox></v:rect></w:pict></mc:Fallback></mc:AlternateContent></w:r>'
    )
SECT = '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>'


@lru_cache(maxsize=1)
def _template() -> bytes:
    buf = io.BytesIO()
    Document().save(buf)
    return buf.getvalue()


def make_docx(body_xml: str, with_sect: bool = True) -> bytes:
    """A real .docx (python-docx default template) whose body is ``body_xml``."""
    doc_xml = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<w:document {NS_DECL}><w:body>{body_xml}{SECT if with_sect else ""}</w:body></w:document>'
    )
    src = zipfile.ZipFile(io.BytesIO(_template()))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for info in src.infolist():
            data = doc_xml.encode() if info.filename == "word/document.xml" else src.read(info)
            z.writestr(info, data)
    return out.getvalue()


def P(inner: str, ppr: str = "") -> str:
    return f"<w:p>{ppr}{inner}</w:p>"


def R(text: str, rpr: str = "") -> str:
    space = ' xml:space="preserve"' if text != text.strip() else ""
    rpr_xml = f"<w:rPr>{rpr}</w:rPr>" if rpr else ""
    return f"<w:r>{rpr_xml}<w:t{space}>{text}</w:t></w:r>"


BOLD = "<w:b/>"
ITALIC = "<w:i/>"


def pkg_of(body_xml: str) -> DocxPackage:
    return DocxPackage(make_docx(body_xml))


def plan(*ops: dict) -> EditPlan:
    return EditPlan.model_validate({"summary": "test", "operations": list(ops)})


def run_plan(pkg: DocxPackage, *ops: dict, check: bool = True):
    """Apply ops to a copy, verify, and return (edited_pkg, report)."""
    p = plan(*ops)
    work = pkg.copy()
    apply_plan(work, p)
    data = work.to_bytes()
    report = verify_edit(pkg, data, p)
    if check:
        assert report.passed, report.summary()
    return DocxPackage(data), report


def texts(pkg: DocxPackage) -> dict[str, str]:
    return {b.id: paragraph_view(b.element).text for b in build_index(pkg).paragraphs()}


def block_xml(pkg: DocxPackage, block_id: str) -> str:
    from lxml import etree

    return etree.tostring(build_index(pkg).get(block_id).element, encoding="unicode")
