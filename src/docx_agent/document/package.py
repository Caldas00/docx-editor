"""Reading and writing the .docx (OPC/zip) container.

Design rule: the agent only ever rewrites the *main document part*
(usually ``word/document.xml``). Every other part of the package - styles,
numbering, headers/footers, media, comments, custom XML, ... - is copied
byte-for-byte from the input zip into the output zip. That makes "we did not
touch anything else" a property that can be checked mechanically (see
``verify.check_package_parts``).
"""

from __future__ import annotations

import io
import posixpath
import zipfile
from dataclasses import dataclass
from functools import cached_property

from lxml import etree

from .ns import NSMAP, W, qn

MAIN_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
    "application/vnd.ms-word.document.macroEnabled.main+xml",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml",
    "application/vnd.ms-word.template.macroEnabledTemplate.main+xml",
}
OFFICE_DOCUMENT_REL = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
)
STRICT_OFFICE_DOCUMENT_REL = "http://purl.oclc.org/ooxml/officeDocument/relationships/officeDocument"

MAX_UNCOMPRESSED_BYTES = 250 * 1024 * 1024  # zip-bomb guard


class DocxError(ValueError):
    """The input is not a .docx we can safely process."""


def _parser() -> etree.XMLParser:
    # resolve_entities/no_network: never expand external entities (XXE).
    # remove_blank_text=False: keep the XML exactly as authored.
    return etree.XMLParser(
        resolve_entities=False, no_network=True, huge_tree=True, remove_blank_text=False
    )


def parse_xml(data: bytes) -> etree._Element:
    return etree.fromstring(data, _parser())


def serialize_xml(element: etree._Element) -> bytes:
    return etree.tostring(
        element, xml_declaration=True, encoding="UTF-8", standalone=True
    )


@dataclass(frozen=True)
class Relationship:
    rel_id: str
    rel_type: str
    target: str
    external: bool


class DocxPackage:
    """An opened .docx: raw parts plus a parsed, mutable main document tree."""

    def __init__(self, data: bytes) -> None:
        self.source_bytes = data
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise DocxError("File is not a valid .docx (not a zip archive).") from exc
        with zf:
            self._infos = zf.infolist()
            total = sum(i.file_size for i in self._infos)
            if total > MAX_UNCOMPRESSED_BYTES:
                raise DocxError("Document is too large to process safely.")
            names = [i.filename for i in self._infos]
            if len(set(names)) != len(names):
                raise DocxError("Corrupt package: duplicate zip entries.")
            self.parts: dict[str, bytes] = {i.filename: zf.read(i.filename) for i in self._infos}

        self.main_part_name = self._find_main_part()
        try:
            self.document = parse_xml(self.parts[self.main_part_name])
        except etree.XMLSyntaxError as exc:
            raise DocxError(f"Main document XML is malformed: {exc}") from exc
        body = self.document.find(W.body)
        if body is None:
            raise DocxError("Main document has no <w:body>.")
        self.body: etree._Element = body

    # ------------------------------------------------------------------ parts
    def _find_main_part(self) -> str:
        rels = self.parts.get("_rels/.rels")
        if rels is not None:
            root = parse_xml(rels)
            for rel in root.findall(qn("rel:Relationship")):
                if rel.get("Type") in (OFFICE_DOCUMENT_REL, STRICT_OFFICE_DOCUMENT_REL):
                    target = rel.get("Target", "").lstrip("/")
                    if target in self.parts:
                        self._check_content_type(target)
                        return target
        if "word/document.xml" in self.parts:
            self._check_content_type("word/document.xml")
            return "word/document.xml"
        raise DocxError("Not a Word document: no main document part found.")

    def _check_content_type(self, part: str) -> None:
        ct_xml = self.parts.get("[Content_Types].xml")
        if ct_xml is None:
            raise DocxError("Corrupt package: missing [Content_Types].xml.")
        root = parse_xml(ct_xml)
        for ov in root.findall(qn("ct:Override")):
            if ov.get("PartName", "").lstrip("/") == part:
                if ov.get("ContentType") not in MAIN_CONTENT_TYPES:
                    raise DocxError("Not a Word document (unexpected main content type).")
                return

    @property
    def main_part_dir(self) -> str:
        return posixpath.dirname(self.main_part_name)

    @cached_property
    def relationships(self) -> dict[str, Relationship]:
        rels_name = posixpath.join(
            self.main_part_dir, "_rels", posixpath.basename(self.main_part_name) + ".rels"
        )
        data = self.parts.get(rels_name)
        if data is None:
            return {}
        out: dict[str, Relationship] = {}
        for rel in parse_xml(data).findall(qn("rel:Relationship")):
            rid = rel.get("Id", "")
            out[rid] = Relationship(
                rel_id=rid,
                rel_type=rel.get("Type", ""),
                target=rel.get("Target", ""),
                external=rel.get("TargetMode") == "External",
            )
        return out

    def resolve_part(self, rel_id: str) -> str | None:
        rel = self.relationships.get(rel_id)
        if rel is None or rel.external:
            return None
        if rel.target.startswith("/"):
            return rel.target.lstrip("/")
        return posixpath.normpath(posixpath.join(self.main_part_dir, rel.target))

    @cached_property
    def style_names(self) -> dict[str, str]:
        """styleId -> human readable style name (paragraph + character styles)."""
        styles_part = posixpath.join(self.main_part_dir, "styles.xml")
        data = self.parts.get(styles_part)
        if data is None:
            return {}
        out: dict[str, str] = {}
        for style in parse_xml(data).findall(W.style):
            sid = style.get(W.styleId)
            name_el = style.find(W.name)
            if sid:
                out[sid] = name_el.get(W.val, sid) if name_el is not None else sid
        return out

    @cached_property
    def default_paragraph_style(self) -> str | None:
        styles_part = posixpath.join(self.main_part_dir, "styles.xml")
        data = self.parts.get(styles_part)
        if data is None:
            return None
        for style in parse_xml(data).findall(W.style):
            if style.get(W.styleType) == "paragraph" and style.get(W.default) in ("1", "true", "on"):
                return style.get(W.styleId)
        return None

    # ----------------------------------------------------------------- output
    def main_xml_bytes(self) -> bytes:
        return serialize_xml(self.document)

    def to_bytes(self) -> bytes:
        """Write the package. Only the main document part is re-serialised."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as out:
            for info in self._infos:
                data = (
                    self.main_xml_bytes()
                    if info.filename == self.main_part_name
                    else self.parts[info.filename]
                )
                new_info = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                new_info.compress_type = info.compress_type
                new_info.external_attr = info.external_attr
                new_info.create_system = info.create_system
                out.writestr(new_info, data)
        return buf.getvalue()

    def copy(self) -> DocxPackage:
        """Independent working copy (re-parsed from the current state)."""
        return DocxPackage(self.to_bytes())


__all__ = ["DocxError", "DocxPackage", "NSMAP", "parse_xml", "serialize_xml"]
