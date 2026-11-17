"""Reading and writing the .docx (OPC/zip) container.

Design rule: the agent rewrites only what an edit needs - the main document part
(``word/document.xml``), the header/footer parts it edits, and *additions* to the
document's relationships and content types (for new hyperlinks and new
headers/footers). Every other part - styles, numbering, media, comments, footnotes,
settings, custom XML, metadata... - is copied byte-for-byte from the input zip, and
unchanged headers/footers keep their original bytes. The verifier checks all of this
mechanically.
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
_REL_BASE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
HEADER_REL = _REL_BASE + "header"
FOOTER_REL = _REL_BASE + "footer"
HYPERLINK_REL = _REL_BASE + "hyperlink"
HEADER_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"
FOOTER_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"
RELS_CT = "application/vnd.openxmlformats-package.relationships+xml"

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


@dataclass
class HeaderFooterPart:
    """A header or footer part, parsed and editable like the body."""

    label: str  # block-id prefix: "hdr1", "ftr2", ...
    kind: str  # "header" | "footer"
    part_name: str  # e.g. "word/footer1.xml"
    root: etree._Element  # <w:hdr> / <w:ftr>
    uses: list[str]  # e.g. ["default, section 1"]
    original: bytes = b""  # canonical XML at load time (to keep untouched parts byte-identical)
    created: bool = False


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
        self._rels_root: etree._Element | None = None  # parsed on first addition
        self._ct_root: etree._Element | None = None
        self._new_parts: dict[str, etree._Element] = {}
        self.hf_parts: list[HeaderFooterPart] = self._load_headers_footers()

    def _load_headers_footers(self) -> list[HeaderFooterPart]:
        parts: dict[str, HeaderFooterPart] = {}
        counters = {"header": 0, "footer": 0}
        for n, sect in enumerate(self.body.iter(W.sectPr), 1):
            for ref in sect:
                kind = {qn("w:headerReference"): "header",
                        qn("w:footerReference"): "footer"}.get(ref.tag)
                if kind is None:
                    continue
                name = self.resolve_part(ref.get(qn("r:id")) or "")
                if name is None or name not in self.parts:
                    continue
                if name not in parts:
                    try:
                        root = parse_xml(self.parts[name])
                    except etree.XMLSyntaxError:
                        continue
                    counters[kind] += 1
                    label = f"{'hdr' if kind == 'header' else 'ftr'}{counters[kind]}"
                    parts[name] = HeaderFooterPart(label, kind, name, root, [],
                                                   _canonical(root))
                parts[name].uses.append(f"{ref.get(W.type) or 'default'}, section {n}")
        return list(parts.values())

    def part_root(self, element: etree._Element) -> etree._Element:
        node = element
        while node.getparent() is not None:
            node = node.getparent()
        return node

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

    @property
    def rels_part_name(self) -> str:
        return posixpath.join(self.main_part_dir, "_rels",
                              posixpath.basename(self.main_part_name) + ".rels")

    # --------------------------------------------------------------- additions
    def _rels(self) -> etree._Element:
        if self._rels_root is None:
            data = self.parts.get(self.rels_part_name)
            self._rels_root = parse_xml(data) if data is not None else etree.Element(
                qn("rel:Relationships"), nsmap={None: NSMAP["rel"]})
        return self._rels_root

    def add_relationship(self, rel_type: str, target: str, external: bool = False) -> str:
        """Add a relationship from the main document; existing ones are never changed."""
        root = self._rels()
        taken = {r.get("Id") for r in root}
        n = 1
        while f"rIdDA{n}" in taken:
            n += 1
        rel = etree.SubElement(root, qn("rel:Relationship"))
        rel.set("Id", f"rIdDA{n}")
        rel.set("Type", rel_type)
        rel.set("Target", target)
        if external:
            rel.set("TargetMode", "External")
        self.__dict__.pop("relationships", None)  # refresh the cached view
        return f"rIdDA{n}"

    def add_part(self, name: str, root: etree._Element, content_type: str) -> None:
        """Add a new XML part (e.g. a footer) with a content-type override."""
        if self._ct_root is None:
            self._ct_root = parse_xml(self.parts["[Content_Types].xml"])
        override = etree.SubElement(self._ct_root, qn("ct:Override"))
        override.set("PartName", "/" + name)
        override.set("ContentType", content_type)
        self._new_parts[name] = root

    def new_part_name(self, stem: str) -> str:
        n = 1
        while (f"{self.main_part_dir}/{stem}{n}.xml" in self.parts
               or f"{self.main_part_dir}/{stem}{n}.xml" in self._new_parts):
            n += 1
        return f"{self.main_part_dir}/{stem}{n}.xml"

    @cached_property
    def relationships(self) -> dict[str, Relationship]:
        if self._rels_root is not None:
            root = self._rels_root
        else:
            data = self.parts.get(self.rels_part_name)
            if data is None:
                return {}
            root = parse_xml(data)
        out: dict[str, Relationship] = {}
        for rel in root.findall(qn("rel:Relationship")):
            rid = rel.get("Id", "")
            out[rid] = Relationship(
                rel_id=rid,
                rel_type=rel.get("Type", ""),
                target=rel.get("Target", ""),
                external=rel.get("TargetMode") == "External",
            )
        return out

    def resolve_part_from(self, part_name: str, rel_id: str) -> str | None:
        """Resolve a relationship of any part (e.g. a picture inside a header)."""
        if part_name == self.main_part_name:
            return self.resolve_part(rel_id)
        base_dir = posixpath.dirname(part_name)
        data = self.parts.get(posixpath.join(base_dir, "_rels",
                                             posixpath.basename(part_name) + ".rels"))
        if data is None:
            return None
        for rel in parse_xml(data).findall(qn("rel:Relationship")):
            if rel.get("Id") == rel_id and rel.get("TargetMode") != "External":
                target = rel.get("Target", "")
                if target.startswith("/"):
                    return target.lstrip("/")
                return posixpath.normpath(posixpath.join(base_dir, target))
        return None

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
    def paragraph_styles(self) -> dict[str, str]:
        """styleId -> name for paragraph styles defined in styles.xml."""
        data = self.parts.get(posixpath.join(self.main_part_dir, "styles.xml"))
        if data is None:
            return {}
        out: dict[str, str] = {}
        for style in parse_xml(data).findall(W.style):
            sid = style.get(W.styleId)
            if sid and style.get(W.styleType) == "paragraph":
                name_el = style.find(W.name)
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

    def _part_bytes(self, name: str) -> bytes:
        if name == self.main_part_name:
            return self.main_xml_bytes()
        if name == self.rels_part_name and self._rels_root is not None:
            return serialize_xml(self._rels_root)
        if name == "[Content_Types].xml" and self._ct_root is not None:
            return serialize_xml(self._ct_root)
        for hf in self.hf_parts:
            if hf.part_name == name and not hf.created and _canonical(hf.root) != hf.original:
                return serialize_xml(hf.root)  # an edited header/footer
        return self.parts[name]

    def to_bytes(self) -> bytes:
        """Write the package: edited parts re-serialised, everything else byte-for-byte."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as out:
            last = self._infos[-1] if self._infos else None
            for info in self._infos:
                new_info = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                new_info.compress_type = info.compress_type
                new_info.external_attr = info.external_attr
                new_info.create_system = info.create_system
                out.writestr(new_info, self._part_bytes(info.filename))
            extra = dict(self._new_parts)
            if self._rels_root is not None and self.rels_part_name not in self.parts:
                extra[self.rels_part_name] = self._rels_root
            for name, root in extra.items():
                new_info = zipfile.ZipInfo(name, date_time=last.date_time if last else
                                           (1980, 1, 1, 0, 0, 0))
                new_info.compress_type = zipfile.ZIP_DEFLATED
                out.writestr(new_info, serialize_xml(root))
        return buf.getvalue()

    def copy(self) -> DocxPackage:
        """Independent working copy (re-parsed from the current state)."""
        return DocxPackage(self.to_bytes())


def _canonical(root: etree._Element) -> bytes:
    return etree.tostring(root, method="c14n", exclusive=True, with_comments=False)


__all__ = ["DocxError", "DocxPackage", "HeaderFooterPart", "NSMAP", "parse_xml", "serialize_xml"]
