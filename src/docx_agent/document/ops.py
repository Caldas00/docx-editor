"""Edit operations and the engine that applies them to the XML.

The LLM produces an :class:`EditPlan` - a list of typed operations that address
text by *block id + exact anchor text*, never by character offsets or XPath.
:class:`DocumentEditor` resolves those anchors and performs minimal run-level
surgery:

* text replacement rewrites only the ``<w:t>`` nodes inside the matched range;
  the new text inherits the formatting of the run where the match starts,
* untouched runs, run properties, paragraph properties and every non-text node
  are left exactly as they were,
* anything ambiguous or unsafe raises :class:`EditError` with a message written
  for the LLM, so the planner can correct itself.
"""

from __future__ import annotations

import copy
import difflib
import re
from dataclasses import dataclass, field
from typing import Annotated, Literal

from lxml import etree
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .model import (
    TXBX,
    Block,
    DocumentIndex,
    ParagraphView,
    Piece,
    _walk_container,
    build_index,
    image_info,
    paragraph_view,
    run_props,
    text_box_fallback,
    text_box_key,
    text_boxes,
)
from .ns import R_ID, XML_SPACE, W, qn
from .package import (
    FOOTER_CT,
    FOOTER_REL,
    HEADER_CT,
    HEADER_REL,
    HYPERLINK_REL,
    DocxPackage,
    HeaderFooterPart,
)

Occurrence = int | Literal["all"] | None

_OCC_DESC = (
    "Which match to edit when `find` occurs more than once in the scope: a 1-based "
    "index, or \"all\". Leave null when the text is unique (preferred)."
)


# ===================================================================== schemas
class _Op(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReplaceText(_Op):
    """Replace an exact piece of text. The new text takes the formatting of the
    text it replaces."""

    op: Literal["replace_text"]
    block_id: str | None = Field(
        description="Paragraph id (e.g. 'p4', 't0.r1.c0.p0'). Null = search the whole document."
    )
    find: str = Field(min_length=1, description="Exact text currently in the document.")
    replace_with: str = Field(min_length=1, description="New text (no line breaks).")
    occurrence: Occurrence = Field(default=None, description=_OCC_DESC)


class DeleteText(_Op):
    """Delete an exact piece of text inside a paragraph (the paragraph stays)."""

    op: Literal["delete_text"]
    block_id: str | None = Field(
        description="Paragraph id. Null = search the whole document."
    )
    find: str = Field(
        min_length=1,
        description="Exact text to delete, including the adjacent space(s) so no double, "
                    "leading or trailing space is left.",
    )
    occurrence: Occurrence = Field(default=None, description=_OCC_DESC)


class InsertText(_Op):
    """Insert text inside an existing paragraph, next to an anchor or at its
    start/end. The new text takes the formatting of the neighbouring text."""

    op: Literal["insert_text"]
    block_id: str = Field(description="Paragraph id.")
    position: Literal["before", "after", "start", "end"] = Field(
        description="before/after `anchor`, or start/end of the paragraph."
    )
    anchor: str | None = Field(
        default=None, description="Exact text to insert next to (required for before/after)."
    )
    text: str = Field(min_length=1, description="Text to insert, including any needed spaces.")
    occurrence: Occurrence = Field(default=None, description=_OCC_DESC)


class InsertParagraph(_Op):
    """Insert one or more new paragraphs next to an existing paragraph or table."""

    op: Literal["insert_paragraph"]
    target_id: str = Field(description="Id of the paragraph or table to insert next to.")
    position: Literal["before", "after"]
    text: str = Field(
        min_length=1,
        description="Paragraph text. Each line ('\\n') becomes its own paragraph with the same formatting.",
    )
    format_like: str = Field(
        description=(
            "Id of an existing paragraph whose look (style, list/bullet, alignment, font) the "
            "new paragraph must copy - e.g. a sibling body paragraph, or a list item when adding "
            "to a list. Do NOT pick a heading unless the new paragraph is a heading."
        )
    )


class DeleteParagraph(_Op):
    """Remove a whole paragraph."""

    op: Literal["delete_paragraph"]
    block_id: str = Field(description="Paragraph id.")
    delete_images: bool = Field(
        default=False,
        description="Must be true to delete a paragraph that contains pictures (only when the "
                    "user wants those pictures gone too).",
    )


HexColor = Annotated[str, Field(pattern=r"^(?:[0-9A-Fa-f]{6}|auto)$")]
Highlight = Literal[
    "yellow", "green", "cyan", "magenta", "blue", "red", "darkBlue", "darkCyan", "darkGreen",
    "darkMagenta", "darkRed", "darkYellow", "darkGray", "lightGray", "black", "none",
]


class Formatting(BaseModel):
    """Run formatting. Null fields are ignored."""

    model_config = ConfigDict(extra="forbid")

    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    strike: bool | None = None
    color: HexColor | None = Field(
        default=None, description="Text colour as RRGGBB hex, e.g. 7030A0 (purple), or 'auto'."
    )
    highlight: Highlight | None = Field(default=None, description="Highlighter colour or 'none'.")
    font_size: float | None = Field(default=None, ge=1, le=400, description="Size in points.")

    def props(self) -> dict:
        return {k: v for k, v in self.model_dump().items() if v is not None}


class FormatText(_Op):
    """Change the formatting of an exact piece of text (bold, italic, underline, strike,
    colour, highlight, font size)."""

    op: Literal["format_text"]
    block_id: str | None = Field(description="Paragraph id. Null = whole document.")
    find: str = Field(min_length=1)
    bold: bool | None = Field(default=None, description="true/false to set, null to leave as is.")
    italic: bool | None = None
    underline: bool | None = None
    strike: bool | None = None
    color: HexColor | None = Field(
        default=None, description="Text colour as RRGGBB hex, e.g. 7030A0 (purple), or 'auto'."
    )
    highlight: Highlight | None = None
    font_size: float | None = Field(default=None, ge=1, le=400, description="Size in points.")
    occurrence: Occurrence = Field(default=None, description=_OCC_DESC)

    def props(self) -> dict:
        return Formatting.model_validate(
            self.model_dump(include=set(Formatting.model_fields))).props()


class RestyleText(_Op):
    """Change the formatting of ALL existing text that currently has some formatting, e.g.
    make every green run purple, or un-bold all red text. Text is not changed; paragraphs
    added earlier in the same plan are not affected."""

    op: Literal["restyle_text"]
    block_id: str | None = Field(default=None, description="Limit to one paragraph; null = whole document.")
    match: Formatting = Field(description="Formatting the text has now (e.g. {color: '70AD47'}).")
    set: Formatting = Field(description="Formatting to apply to that text.")


class DeleteImages(_Op):
    """Delete pictures (icons, emojis, photos, charts). Shapes and text boxes are kept."""

    op: Literal["delete_images"]
    images: list[str] | None = Field(
        default=None, description="Picture refs from the outline, e.g. ['#18', '#19']."
    )
    block_id: str | None = Field(default=None, description="Only pictures in this paragraph.")
    max_size_px: int | None = Field(
        default=None, ge=1,
        description="Only pictures whose width AND height are at most this (e.g. 32 for icons).",
    )


class DeleteTableRows(_Op):
    """Delete whole table rows (use this instead of emptying their cells)."""

    op: Literal["delete_table_rows"]
    rows: list[str] = Field(min_length=1, description="Row ids: table id + '.r' + row index, e.g. 't1.r23'.")


class ReorderTableRows(_Op):
    """Put rows of ONE table in a new order (reverse, sort, swap, move up/down): the rows in
    `order` fill, in that order, the positions those same rows occupy now. Rows move whole,
    with their formatting and pictures."""

    op: Literal["reorder_table_rows"]
    order: list[str] = Field(
        min_length=2, max_length=500,
        description="Row ids in their NEW order, e.g. ['t0.r4', 't0.r3', 't0.r2', 't0.r1'] "
                    "reverses rows 1-4. Leave header rows out to keep them on top.")


class InsertTableRow(_Op):
    """Insert a new table row next to an existing one, copying a row's formatting."""

    op: Literal["insert_table_row"]
    row: str = Field(description="Existing row id to insert next to, e.g. 't1.r3'.")
    position: Literal["before", "after"]
    cells: list[str] = Field(
        min_length=1,
        description="Text of each cell, left to right; one entry per cell of the template row "
                    "('' for an empty cell, '\\n' for several paragraphs).",
    )
    format_like_row: str | None = Field(
        default=None, description="Row to copy the look from (default: `row`). Avoid header rows."
    )


class DeleteTable(_Op):
    """Delete a whole table."""

    op: Literal["delete_table"]
    table_id: str = Field(description="Table id, e.g. 't1'.")


class InsertTable(_Op):
    """Create a new table next to an existing paragraph or table."""

    op: Literal["insert_table"]
    target_id: str = Field(description="Id of the paragraph or table to put the new table next to.")
    position: Literal["before", "after"]
    rows: list[list[str]] = Field(
        min_length=1, max_length=200,
        description="Cell texts, row by row; every row has the same number of cells "
                    "('\\n' inside a cell = several paragraphs).",
    )
    header: bool = Field(default=False, description="First row is a header (bold, repeated).")
    format_like: str = Field(description="A body paragraph whose text look the cells copy.")
    table_like: str | None = Field(
        default=None, description="Existing table whose borders/style/widths to copy; null = "
                                  "a simple table with single borders.",
    )

    @model_validator(mode="after")
    def _rectangular(self) -> InsertTable:
        widths = {len(r) for r in self.rows}
        if len(widths) != 1 or 0 in widths or max(widths) > 30:
            raise ValueError("every row must have the same number of cells (1-30)")
        return self


class MoveBlocks(_Op):
    """Move paragraphs and/or tables (reorder, or move to another section). Everything inside
    them - formatting, pictures, links, fields - moves unchanged."""

    op: Literal["move_blocks"]
    block_ids: list[str] = Field(min_length=1, max_length=80,
                                 description="Paragraph/table ids, kept in document order.")
    target_id: str = Field(description="Paragraph or table to put them next to.")
    position: Literal["before", "after"]


class DuplicateBlocks(_Op):
    """Copy paragraphs and/or tables, with all their formatting."""

    op: Literal["duplicate_blocks"]
    block_ids: list[str] = Field(min_length=1, max_length=80)
    target_id: str | None = Field(
        default=None, description="Where to put the copy; null = right after the originals.")
    position: Literal["before", "after"] = "after"


class SetParagraphFormat(_Op):
    """Change paragraph style (e.g. Heading 1 -> Heading 2, Normal -> Title), alignment, the
    background colour of the paragraph (its shading, the "box" behind it), or take paragraphs
    out of a numbered/bulleted list."""

    op: Literal["set_paragraph_format"]
    block_ids: list[str] = Field(min_length=1, max_length=100)
    style: str | None = Field(default=None, description="A paragraph style that exists in the "
                                                        "document, e.g. 'Heading 2'.")
    align: Literal["left", "center", "right", "justify"] | None = None
    remove_numbering: bool = Field(default=False, description="Remove list bullets/numbers.")
    shading: Annotated[str, Field(pattern=r"^(?:[0-9A-Fa-f]{6}|none)$")] | None = Field(
        default=None, description="Background colour of the whole paragraph (RRGGBB), or "
                                  "'none' to remove it.")


def shading_element(fill: str) -> etree._Element:
    """The w:shd a paragraph gets for a background colour (shared with the verifier)."""
    shd = etree.Element(qn("w:shd"))
    shd.set(W.val, "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill.upper())
    return shd


class SetShapeFill(_Op):
    """Change the fill (background) colour of a shape drawn in the document - a coloured
    banner, band or box, including the area behind a text box. Every filled area of that
    drawing gets the colour; its text and outline stay as they are."""

    op: Literal["set_shape_fill"]
    target: str = Field(description="The text box part it holds, e.g. 'tb3', or a shape ref "
                                    "from the outline, e.g. '#5'.")
    color: Annotated[str, Field(pattern=r"^[0-9A-Fa-f]{6}$")]


_FILLS = (qn("a:solidFill"), qn("a:gradFill"), qn("a:pattFill"))
_VML_FILL = "{urn:schemas-microsoft-com:vml}fill"


def recolor_drawing(node: etree._Element, color: str) -> int:
    """Give every filled area of a drawing one solid colour, in its DrawingML and its VML
    copy alike; returns how many fills changed. Shared with the verifier, which applies it
    to the original drawing to know exactly what the edited one must be."""
    color = color.upper()
    changed = 0
    for sppr in list(node.iter()):
        if not isinstance(sppr.tag, str) or not sppr.tag.endswith(("}spPr", "}grpSpPr")):
            continue
        for child in list(sppr):
            if child.tag in _FILLS:
                fill = etree.Element(qn("a:solidFill"))
                etree.SubElement(fill, qn("a:srgbClr")).set("val", color)
                child.addprevious(fill)
                sppr.remove(child)
                changed += 1
    for el in node.iter():
        if not isinstance(el.tag, str):
            continue
        if el.get("fillcolor") is not None and el.get("filled") not in ("f", "false"):
            el.set("fillcolor", f"#{color}")
            changed += 1
        if el.tag == _VML_FILL and el.get("color") is not None:
            el.set("color", f"#{color}")
    return changed


def find_drawing(pkg: DocxPackage, index: DocumentIndex, target: str
                 ) -> tuple[etree._Element, etree._Element, str]:
    """(the run child holding the drawing, its paragraph in the body, a label) for a text box
    part id ('tb3') or a shape ref ('#5'). Shared by the engine and the oracle."""
    target = target.strip()
    block = index.get(target)
    if block is not None and block.element.tag == TXBX:
        node = block.element
        while node.getparent() is not None and node.getparent().tag != W.r:
            node = node.getparent()
        host = next((a for a in node.iterancestors() if a.tag == W.p), None)
        if host is None or node.getparent() is None:
            raise EditError(f"{target} is not inside a paragraph's drawing.")
        return node, host, f"the shape holding {target}"
    ref = target.lstrip("#")
    for b in index.paragraphs():
        if not b.editable or b.id.startswith("tb"):
            continue
        for pc in paragraph_view(b.element).pieces:
            if pc.label in ("SHAPE", "IMAGE") and image_info(pc.node).ref == ref:
                return pc.node, b.element, f"shape #{ref}"
    raise EditError(f"There is no shape {target!r}; use a text box id (tb3) or a shape ref "
                    "from the outline (#5).")


class SplitParagraph(_Op):
    """Split a paragraph in two; the second paragraph starts at `at`."""

    op: Literal["split_paragraph"]
    block_id: str
    at: str = Field(min_length=1, description="Exact text the new (second) paragraph starts with.")
    occurrence: Occurrence = Field(default=None, description=_OCC_DESC)


class MergeParagraphs(_Op):
    """Join consecutive paragraphs into the first one (keeps all inline formatting)."""

    op: Literal["merge_paragraphs"]
    block_ids: list[str] = Field(min_length=2, max_length=50,
                                 description="Consecutive paragraph ids, in order.")
    separator: str = Field(default=" ", max_length=5,
                           description="Text put between the joined paragraphs.")


class InsertPageBreak(_Op):
    """Start a new page before/after a paragraph or table."""

    op: Literal["insert_page_break"]
    target_id: str
    position: Literal["before", "after"]


class InsertTableColumn(_Op):
    """Insert a column next to an existing one (simple tables without merged cells)."""

    op: Literal["insert_table_column"]
    table_id: str
    column: int = Field(ge=0, description="0-based index of the column to copy and insert next to.")
    position: Literal["before", "after"]
    cells: list[str] = Field(min_length=1, description="Text for each row, top to bottom.")


class DeleteTableColumns(_Op):
    """Delete columns (simple tables without merged cells)."""

    op: Literal["delete_table_columns"]
    table_id: str
    columns: list[int] = Field(min_length=1, description="0-based column indexes.")


class BlocksToTable(_Op):
    """Put existing consecutive paragraphs and/or tables into a new table (one block per
    cell, row by row), keeping their formatting; tables become nested tables. Blank spacer
    paragraphs among them are removed instead of getting a cell of their own."""

    op: Literal["blocks_to_table"]
    block_ids: list[str] = Field(min_length=1, max_length=200)
    columns: int = Field(default=1, ge=1, le=10)
    table_like: str | None = Field(default=None, description="Existing table to copy the look from.")


Url = Annotated[str, Field(pattern=r"^(https?://|mailto:)[^\s<>\"]+$", max_length=2000)]


class InsertHyperlink(_Op):
    """Turn existing text into a hyperlink."""

    op: Literal["insert_hyperlink"]
    block_id: str
    find: str = Field(min_length=1)
    url: Url
    occurrence: Occurrence = Field(default=None, description=_OCC_DESC)


class RemoveHyperlink(_Op):
    """Remove a hyperlink but keep its text."""

    op: Literal["remove_hyperlink"]
    block_id: str
    find: str = Field(min_length=1, description="Text inside the link.")
    occurrence: Occurrence = Field(default=None, description=_OCC_DESC)


class SetHyperlinkUrl(_Op):
    """Change where an existing hyperlink points to (its text is unchanged)."""

    op: Literal["set_hyperlink_url"]
    block_id: str
    find: str = Field(min_length=1, description="Text inside the link.")
    url: Url
    occurrence: Occurrence = Field(default=None, description=_OCC_DESC)


class CreateHeaderFooter(_Op):
    """Add a header or footer to a document (sections) that has none."""

    op: Literal["create_header_footer"]
    kind: Literal["header", "footer"]
    text: str = Field(default="", max_length=300)
    page_numbers: bool = Field(default=False, description="Add the page number.")
    align: Literal["left", "center", "right"] = "center"


EditOp = Annotated[
    ReplaceText | DeleteText | InsertText | InsertParagraph | DeleteParagraph | FormatText
    | RestyleText | DeleteImages | DeleteTableRows | ReorderTableRows | InsertTableRow
    | DeleteTable | InsertTable
    | MoveBlocks | DuplicateBlocks | SetParagraphFormat | SplitParagraph | MergeParagraphs
    | InsertPageBreak | InsertTableColumn | DeleteTableColumns | BlocksToTable
    | InsertHyperlink | RemoveHyperlink | SetHyperlinkUrl | CreateHeaderFooter | SetShapeFill,
    Field(discriminator="op"),
]


class EditPlan(BaseModel):
    """The complete set of edits that fulfils the user's instruction."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(description="One sentence describing the change for the user.")
    operations: list[EditOp] = Field(min_length=1, max_length=60)


# ====================================================================== errors
class EditError(Exception):
    """An operation cannot be applied. The message is shown to the planner LLM."""

    def __init__(self, message: str, op_index: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.op_index = op_index

    def __str__(self) -> str:
        if self.op_index is None:
            return self.message
        return f"operation #{self.op_index + 1}: {self.message}"


# ============================================================== text helpers
_INVALID_XML_CHARS = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")


def find_all(text: str, needle: str) -> list[int]:
    """Start offsets of non-overlapping occurrences of ``needle``."""
    out, i = [], 0
    while needle:
        j = text.find(needle, i)
        if j < 0:
            break
        out.append(j)
        i = j + len(needle)
    return out


def deletion_whitespace_problem(text: str, start: int, end: int) -> str | None:
    """Would deleting text[start:end] leave a double/leading/trailing space?"""
    before = text[:start]
    after = text[end:]
    if before.endswith(" ") and after.startswith(" "):
        return "it would leave a double space"
    if not before and after.startswith(" ") and after.strip():
        return "it would leave a leading space"
    if not after and before.endswith(" ") and before.strip():
        return "it would leave a trailing space"
    return None


def deletion_with_spaces(text: str, start: int, end: int) -> str | None:
    """The `find` that deletes text[start:end] plus the spaces that would otherwise be
    left over (a whole run of them: code lines are often padded up to a callout icon), or
    None when no such widening fixes it."""
    if text[:start].endswith(" ") and (not text[end:].startswith(" ") or not text[:start].strip()):
        while start > 0 and text[start - 1] == " ":
            start -= 1
    else:
        while end < len(text) and text[end] == " ":
            end += 1
    if deletion_whitespace_problem(text, start, end) or text[start:end] == text:
        return None
    return text[start:end]


def _check_inline_text(value: str, what: str) -> str:
    if "\n" in value or "\r" in value:
        raise EditError(
            f"{what} must not contain line breaks; use insert_paragraph to add new paragraphs."
        )
    if "\t" in value:
        raise EditError(f"{what} must not contain tab characters.")
    if "⟦" in value or "⟧" in value:
        raise EditError(f"{what} must not contain ⟦…⟧ placeholders; those are images/fields.")
    return _INVALID_XML_CHARS.sub("", value)


def _suggest(texts: list[tuple[str, str]], needle: str) -> str:
    """Hint for a `find` string that does not exist (case/whitespace/near miss)."""
    low = needle.lower()
    norm = " ".join(needle.split())
    for bid, text in texts:
        idx = text.lower().find(low)
        if idx >= 0:
            return f" Did you mean {text[idx:idx + len(needle)]!r} in {bid} (case differs)?"
        squashed = " ".join(text.split())
        if norm and norm in squashed and norm != needle:
            return f" The text exists in {bid} but with different whitespace: copy it exactly."
    best: tuple[float, str, str] | None = None
    n = len(needle)
    budget = 200_000  # characters scanned at most: this runs on every failed anchor
    matcher = difflib.SequenceMatcher(autojunk=False)
    matcher.set_seq2(needle)
    for bid, text in texts:
        if budget <= 0:
            break
        budget -= len(text)
        # candidate windows start at word boundaries only
        for start in (m.start() for m in re.finditer(r"(?<!\w)\w|^", text)):
            cand = text[start:start + n]
            matcher.set_seq1(cand)
            if matcher.real_quick_ratio() <= 0.8 or matcher.quick_ratio() <= 0.8:
                continue
            r = matcher.ratio()
            if r > 0.8 and (best is None or r > best[0]):
                best = (r, bid, cand)
    if best:
        return f" Closest text: {best[2]!r} in {best[1]}."
    return ""


# ============================================================= XML primitives
def _set_t(t: etree._Element, text: str) -> None:
    t.text = text
    if text != text.strip() or "  " in text:
        t.set(XML_SPACE, "preserve")


def _new_t(text: str) -> etree._Element:
    t = etree.Element(W.t)
    _set_t(t, text)
    return t


def _has_content(run: etree._Element) -> bool:
    return any(child.tag != W.rPr for child in run)


def _remove(el: etree._Element) -> None:
    parent = el.getparent()
    if parent is not None:
        parent.remove(el)


def _clean_runs(runs: list[etree._Element]) -> None:
    """Drop runs that we emptied (only an rPr left)."""
    seen: set[int] = set()
    for run in runs:
        if id(run) in seen:
            continue
        seen.add(id(run))
        if run.getparent() is not None and not _has_content(run):
            _remove(run)


def _strip_revision_markup(el: etree._Element) -> etree._Element:
    """Remove tracked-change bookkeeping from copied pPr/rPr."""
    for tag in ("w:ins", "w:del", "w:moveFrom", "w:moveTo", "w:rPrChange", "w:pPrChange",
                "w:sectPr", "w:numberingChange"):
        for found in el.iter(qn(tag)):
            _remove(found)
    return el


_RPR_ORDER = [
    "rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike", "dstrike",
    "outline", "shadow", "emboss", "imprint", "noProof", "snapToGrid", "vanish", "webHidden",
    "color", "spacing", "w", "kern", "position", "sz", "szCs", "highlight", "u", "effect",
    "bdr", "shd", "fitText", "vertAlign", "rtl", "cs", "em", "lang", "eastAsianLayout",
    "specVanish", "oMath",
]
_RPR_RANK = {qn(f"w:{name}"): i for i, name in enumerate(_RPR_ORDER)}


def _set_rpr_prop(run: etree._Element, tag: str, value: str | None) -> None:
    """Set (value) or explicitly switch off (value=None -> val="0"/"none") a run property,
    keeping the schema order of rPr children."""
    rpr = run.find(W.rPr)
    if rpr is None:
        rpr = etree.Element(W.rPr)
        run.insert(0, rpr)
    existing = rpr.find(tag)
    if existing is None:
        existing = etree.Element(tag)
        rank = _RPR_RANK.get(tag, len(_RPR_ORDER))
        for idx, child in enumerate(rpr):
            if _RPR_RANK.get(child.tag, len(_RPR_ORDER)) > rank:
                rpr.insert(idx, existing)
                break
        else:
            rpr.append(existing)
    for attr in list(existing.attrib):
        del existing.attrib[attr]
    if value is not None:
        existing.set(W.val, value)


def _split_run_at(piece: Piece, offset: int) -> None:
    """Split ``piece.run`` so that a run boundary falls at ``offset`` (absolute,
    within the paragraph view). No-op if a boundary already exists there."""
    run = piece.run
    assert run is not None
    k = offset - piece.start
    assert piece.kind == "text" or k in (0, len(piece.text)), "can only split inside text"
    t = piece.node
    content = [c for c in run if c.tag != W.rPr]
    idx = content.index(t)
    if k == 0 and idx == 0:
        return
    if k == len(piece.text) and idx == len(content) - 1:
        return
    new_run = copy.deepcopy(run)
    for child in list(new_run):
        if child.tag != W.rPr:
            new_run.remove(child)
    # move content after the split point into new_run
    if 0 < k < len(piece.text):
        tail = piece.text[k:]
        _set_t(t, piece.text[:k])
        new_run.append(_new_t(tail))
        movers = content[idx + 1:]
    elif k == 0:
        movers = content[idx:]
    else:  # k == len
        movers = content[idx + 1:]
    for m in movers:
        new_run.append(m)  # lxml append moves the node
    run.addnext(new_run)


_ON_OFF_TAGS = {"bold": W.b, "italic": W.i, "strike": W.strike}
_SZ_CS = qn("w:szCs")


def apply_props(run: etree._Element, props: dict) -> None:
    """Write formatting ``props`` (see :class:`Formatting`) into a run's rPr."""
    for key, value in props.items():
        if key in _ON_OFF_TAGS:
            _set_rpr_prop(run, _ON_OFF_TAGS[key], None if value else "0")
        elif key == "underline":
            _set_rpr_prop(run, W.u, "single" if value else "none")
        elif key == "color":
            _set_rpr_prop(run, W.color, "auto" if value == "auto" else value.upper())
        elif key == "highlight":
            _set_rpr_prop(run, W.highlight, value)
        elif key == "font_size":
            half_points = str(round(value * 2))
            _set_rpr_prop(run, W.sz, half_points)
            _set_rpr_prop(run, _SZ_CS, half_points)


def normalise_prop(key: str, value):
    """Map a requested value to what :func:`run_props` reports after it is applied."""
    if key == "color":
        return None if value == "auto" else value.upper()
    if key == "highlight":
        return None if value == "none" else value
    if key == "font_size":
        return round(value * 2) / 2
    return value


def props_match(actual: dict, wanted: dict) -> bool:
    return all(actual.get(k) == normalise_prop(k, v) for k, v in wanted.items())


def describe_props(props: dict) -> str:
    return ", ".join(f"{k}={'#' + v if k == 'color' and v != 'auto' else v}"
                     for k, v in props.items())


def normalise_image_refs(refs: list[str]) -> set[str]:
    return {re.sub(r"[⟦⟧#\s]|IMAGE", "", r) for r in refs if r.strip()}


def image_selected(piece: Piece, refs: set[str] | None, max_px: int | None) -> bool:
    """Does a delete_images selection cover this piece? Only pictures qualify."""
    if piece.kind != "protected" or piece.label != "IMAGE":
        return False
    info = image_info(piece.node)
    if refs is not None and info.ref not in refs:
        return False
    if max_px is not None:
        return bool(info.width_px and info.height_px
                    and info.width_px <= max_px and info.height_px <= max_px)
    return True


_W_NSMAP = {"w": W.p[1:].split("}")[0]}
_ROW_ID = re.compile(r"^(?P<table>.+)\.r(?P<row>\d+)$")


def new_row_skeleton(template: etree._Element) -> etree._Element:
    """An empty <w:tr> carrying the template row's properties (minus header-repeat and
    revision markup). Shared with the verifier, which predicts the new row from it."""
    tr = etree.Element(W.tr, nsmap=_W_NSMAP)  # 'w' prefix, as in the document
    for child in template:
        if child.tag in (qn("w:tblPrEx"), qn("w:trPr")):
            prop = _strip_revision_markup(copy.deepcopy(child))
            for tag in ("w:tblHeader", "w:trPrChange", "w:tblPrExChange"):
                for found in prop.findall(qn(tag)):
                    prop.remove(found)
            tr.append(prop)
    return tr


def new_cell_skeleton(template: etree._Element) -> etree._Element:
    """An empty <w:tc> with the template cell's properties, never vertically merged."""
    tc = etree.Element(W.tc, nsmap=_W_NSMAP)
    tcpr = template.find(W.tcPr)
    if tcpr is not None:
        tcpr = _strip_revision_markup(copy.deepcopy(tcpr))
        for tag in ("w:vMerge", "w:cellIns", "w:cellDel", "w:cellMerge", "w:tcPrChange"):
            for found in tcpr.findall(qn(tag)):
                tcpr.remove(found)
        tc.append(tcpr)
    return tc


def cell_template_paragraph(tc: etree._Element) -> etree._Element:
    p = tc.find(W.p)
    return p if p is not None else tc.find(".//" + W.p)


_DEFAULT_TEXT_WIDTH = 9026  # twips: A4 with 2.54 cm margins


def text_width_twips(pkg: DocxPackage) -> int:
    """Usable page width of the document's last section, in twips."""
    sect = pkg.body.find(W.sectPr)
    if sect is None:
        return _DEFAULT_TEXT_WIDTH
    size, margins = sect.find(qn("w:pgSz")), sect.find(qn("w:pgMar"))

    def num(el, attr, default):
        v = el.get(qn(attr)) if el is not None else None
        return int(v) if v and v.lstrip("-").isdigit() else default

    width = num(size, "w:w", 11906) - num(margins, "w:left", 1440) - num(margins, "w:right", 1440)
    return width if width > 1000 else _DEFAULT_TEXT_WIDTH


def new_table_skeleton(pkg: DocxPackage, template: etree._Element | None,
                       ncols: int) -> etree._Element:
    """<w:tbl> with properties and column grid only. Copies ``template``'s look when given,
    otherwise a plain table with single borders across the text width. Shared with the
    verifier, which predicts new tables with it."""
    tbl = etree.Element(W.tbl, nsmap=_W_NSMAP)
    total = text_width_twips(pkg)
    widths: list[int] | None = None
    if template is not None:
        tpl_pr = template.find(qn("w:tblPr"))
        if tpl_pr is not None:
            pr = _strip_revision_markup(copy.deepcopy(tpl_pr))
            for found in pr.findall(qn("w:tblPrChange")):
                pr.remove(found)
            tbl.append(pr)
        tpl_grid = template.find(qn("w:tblGrid"))  # direct child: ignore nested tables
        grid = [int(g.get(qn("w:w"))) for g in (tpl_grid if tpl_grid is not None else [])
                if g.tag == qn("w:gridCol") and (g.get(qn("w:w")) or "").isdigit()]
        if len(grid) == ncols:
            widths = grid
        elif grid:
            total = sum(grid)
    if tbl.find(qn("w:tblPr")) is None:
        pr = etree.SubElement(tbl, qn("w:tblPr"))
        if "TableGrid" in pkg.style_names:
            etree.SubElement(pr, qn("w:tblStyle")).set(W.val, "TableGrid")
        etree.SubElement(pr, qn("w:tblW"), {W.w_attr: "0", W.type: "auto"})
        if "TableGrid" not in pkg.style_names:
            borders = etree.SubElement(pr, qn("w:tblBorders"))
            for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
                etree.SubElement(borders, qn(f"w:{side}"),
                                 {W.val: "single", qn("w:sz"): "4", qn("w:space"): "0",
                                  qn("w:color"): "auto"})
        etree.SubElement(pr, qn("w:tblLook"), {W.val: "04A0"})
    widths = widths or [total // ncols] * ncols
    grid_el = etree.SubElement(tbl, qn("w:tblGrid"))
    for w in widths:
        etree.SubElement(grid_el, qn("w:gridCol")).set(qn("w:w"), str(w))
    return tbl


def new_table_row(header: bool) -> etree._Element:
    tr = etree.Element(W.tr, nsmap=_W_NSMAP)
    if header:
        etree.SubElement(etree.SubElement(tr, qn("w:trPr")), qn("w:tblHeader"))
    return tr


def new_table_cell(width: int) -> etree._Element:
    tc = etree.Element(W.tc, nsmap=_W_NSMAP)
    etree.SubElement(etree.SubElement(tc, W.tcPr), qn("w:tcW"),
                     {qn("w:w"): str(width), W.type: "dxa"})
    return tc


def table_grid_widths(tbl: etree._Element) -> list[int]:
    return [int(g.get(qn("w:w"))) for g in tbl.find(qn("w:tblGrid"))]


PAGE_BREAK_TEXT = "⟦PAGE BREAK⟧"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
JC = {"left": "left", "center": "center", "right": "right", "justify": "both"}
_PPR_ORDER = [
    "pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr", "widowControl", "numPr",
    "suppressLineNumbers", "pBdr", "shd", "tabs", "suppressAutoHyphens", "kinsoku", "wordWrap",
    "overflowPunct", "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd",
    "snapToGrid", "spacing", "ind", "contextualSpacing", "mirrorIndents", "suppressOverlap", "jc",
    "textDirection", "textAlignment", "textboxTightWrap", "outlineLvl", "divId", "cnfStyle",
    "rPr", "sectPr", "pPrChange",
]
_PPR_RANK = {qn(f"w:{name}"): i for i, name in enumerate(_PPR_ORDER)}


def page_break_text() -> str:
    return PAGE_BREAK_TEXT


def page_break_paragraph() -> etree._Element:
    p = etree.Element(W.p, nsmap=_W_NSMAP)
    etree.SubElement(etree.SubElement(p, W.r), W.br).set(W.type, "page")
    return p


def merge_separator_needed(first: str, second: str, separator: str) -> bool:
    return bool(separator and first and second and not first[-1].isspace()
                and not second[0].isspace())


def _style_key(name: str) -> str:
    return re.sub(r"[\s_-]+", "", name).lower()


def resolve_paragraph_style(pkg: DocxPackage, name: str) -> str | None:
    """Paragraph style id for a style name or id ("Heading 2", "heading2"), if it exists."""
    want = _style_key(name)
    for sid, sname in pkg.paragraph_styles.items():
        if _style_key(sid) == want or _style_key(sname) == want:
            return sid
    return None


def ppr_set(ppr: etree._Element, tag: str, value: str | None) -> None:
    """Set (or remove, value=None) a pPr child, keeping schema order."""
    for found in ppr.findall(tag):
        ppr.remove(found)
    if value is None:
        return
    el = etree.Element(tag)
    el.set(W.val, value)
    rank = _PPR_RANK.get(tag, len(_PPR_ORDER))
    for idx, child in enumerate(ppr):
        if _PPR_RANK.get(child.tag, len(_PPR_ORDER)) > rank:
            ppr.insert(idx, el)
            return
    ppr.append(el)


def without_sectpr(ppr: etree._Element | None) -> etree._Element | None:
    if ppr is None:
        return None
    out = copy.deepcopy(ppr)
    for s in out.findall(W.sectPr):
        out.remove(s)
    return out


def sanitize_copy(el: etree._Element) -> etree._Element:
    """Make a deep copy safe to insert next to its original: drop bookmarks and comment
    anchors (they must be unique), section breaks, and per-paragraph ids. Used by the
    editor for duplicates and by the verifier to predict them."""
    for tag in (W.bookmarkStart, W.bookmarkEnd, W.commentRangeStart, W.commentRangeEnd):
        for found in list(el.iter(tag)):
            _remove(found)
    for ref in list(el.iter(W.commentReference)):
        run = ref.getparent()
        _remove(ref)
        if run is not None and run.tag == W.r and not _has_content(run):
            _remove(run)
    for ppr in el.iter(W.pPr):
        for s in ppr.findall(W.sectPr):
            ppr.remove(s)
    for node in el.iter():
        for attr in [a for a in node.attrib if a.startswith(f"{{{W14}}}")]:
            del node.attrib[attr]
    for sdt_id in list(el.iter(qn("w:sdtPr"))):
        for found in sdt_id.findall(W.id):
            sdt_id.remove(found)
    return el


def _c14n(el: etree._Element) -> bytes:
    return etree.tostring(el, method="c14n", exclusive=True, with_comments=False)


def first_free_docpr_id(pkg: DocxPackage) -> int:
    """Drawing ids for copies start after the largest id in the original document."""
    nums = [int(d.get("id")) for root in [pkg.document] + [hf.root for hf in pkg.hf_parts]
            for d in root.iter(qn("wp:docPr")) if (d.get("id") or "").isdigit()]
    return max(nums, default=0) + 1


def build_header_footer(kind: str, text: str, page_numbers: bool, align: str,
                        style_id: str | None) -> etree._Element:
    """A new header/footer part. Shared with the verifier, which predicts it."""
    tag = qn("w:hdr") if kind == "header" else qn("w:ftr")
    root = etree.Element(tag, nsmap={"w": _W_NSMAP["w"], "r": qn("r:x")[1:].split("}")[0]})
    p = etree.SubElement(root, W.p)
    ppr = etree.SubElement(p, W.pPr)
    if style_id:
        ppr_set(ppr, W.pStyle, style_id)
    ppr_set(ppr, qn("w:jc"), JC[align])
    if text:
        etree.SubElement(p, W.r).append(_new_t(text + (" " if page_numbers else "")))
    if page_numbers:
        for kind_, extra in (("begin", None), (None, " PAGE "), ("separate", None),
                             (None, "1"), ("end", None)):
            run = etree.SubElement(p, W.r)
            if kind_:
                etree.SubElement(run, W.fldChar).set(W.fldCharType, kind_)
            elif extra == " PAGE ":
                instr = etree.SubElement(run, W.instrText)
                instr.set(XML_SPACE, "preserve")
                instr.text = extra
            else:
                run.append(_new_t(extra))
    return root


def removal_problem(el: etree._Element) -> str | None:
    """Would removing this subtree corrupt something outside it?"""
    if any(True for t in (W.commentRangeStart, W.commentRangeEnd, W.commentReference)
           for _ in el.iter(t)):
        return "it is anchored to a comment"
    starts = {b.get(W.id) for b in el.iter(W.bookmarkStart)}
    ends = {b.get(W.id) for b in el.iter(W.bookmarkEnd)}
    if starts != ends:
        return "it holds one end of a bookmark that continues elsewhere"
    if any(True for _ in el.iter(W.sectPr)):
        return "it carries a section break"
    return None


def is_blank_paragraph(el: etree._Element) -> bool:
    """An empty spacer paragraph: no text, pictures or other content, nothing anchored to it.
    Shared with the oracle (blocks_to_table removes these instead of giving them a cell)."""
    return el.tag == W.p and not paragraph_view(el).pieces and removal_problem(el) is None


# ================================================================ change log
@dataclass
class Change:
    op_index: int
    kind: str
    block_id: str
    before: str | None
    after: str | None


@dataclass
class ApplyResult:
    changes: list[Change] = field(default_factory=list)
    deleted_ids: list[str] = field(default_factory=list)
    inserted: int = 0


# ==================================================================== editor
class DocumentEditor:
    """Applies an :class:`EditPlan` to a :class:`DocxPackage` in place."""

    def __init__(self, pkg: DocxPackage) -> None:
        self.pkg = pkg
        self.index: DocumentIndex = build_index(pkg)
        self._ids: dict[etree._Element, str] = {b.element: b.id for b in self.index.blocks}
        self._deleted: dict[str, int] = {}
        # original row lists, so row ids keep their meaning after earlier row edits
        self._table_rows: dict[etree._Element, list[etree._Element]] = {
            b.element: b.element.findall(W.tr) for b in self.index.blocks if b.kind == "table"}
        self._new_counter = 0
        self._touched: set[etree._Element] = set()  # elements changed earlier in this plan
        self._created_links: set[etree._Element] = set()
        self._rows_inserted: set[etree._Element] = set()  # tables that got new rows
        self._cols_changed: set[etree._Element] = set()  # tables whose columns changed
        self._next_docpr = first_free_docpr_id(pkg)
        # block -> (its id, "before"/"after") for page breaks this plan put next to it
        self._page_breaks_at: dict[etree._Element, tuple[str, str]] = {}
        # moved block -> the page-break paragraph that stood right before it and stayed behind
        self._left_breaks: dict[etree._Element, etree._Element] = {}
        self._source_bytes = pkg.to_bytes()  # for templates as they were (see _original)
        self._cell_first: dict[etree._Element, etree._Element] = {}
        for b in self.index.blocks:
            parent = b.element.getparent()
            if b.kind == "paragraph" and parent is not None and parent.tag == W.tc:
                self._cell_first.setdefault(parent, b.element)
        self._pristine: DocumentIndex | None = None
        # table looks as they were before the plan (table_like copies these)
        self._table_looks: dict[etree._Element, etree._Element] = {}
        for b in self.index.blocks:
            if b.kind == "table":
                look = etree.Element(W.tbl, nsmap=_W_NSMAP)
                for tag in (qn("w:tblPr"), qn("w:tblGrid")):
                    found = b.element.find(tag)
                    if found is not None:
                        look.append(copy.deepcopy(found))
                self._table_looks[b.element] = look
        self.result = ApplyResult()

    # ------------------------------------------------------------ resolving
    def _label(self, el: etree._Element) -> str:
        return self._ids.get(el, "(new paragraph)")

    def _block(self, block_id: str, kinds: tuple[str, ...] = ("paragraph",)) -> Block:
        if block_id in self._deleted:
            raise EditError(
                f"{block_id} was deleted by operation #{self._deleted[block_id] + 1}."
            )
        block = self.index.get(block_id)
        if block is None:
            hint = (f" {block_id!r} is a table row: use it with delete_table_rows / "
                    f"insert_table_row; paragraphs in it look like {block_id}.c0.p0."
                    if _ROW_ID.match(block_id) else "")
            if not hint:
                # Usually a guessed id for a paragraph this plan inserts. New content has no
                # id: it gets its look from `format_like` when it is inserted.
                hint = (" Paragraphs and tables added by this plan have no ids and cannot be "
                        "referenced; give a new paragraph its style with `format_like` (e.g. a "
                        "heading of the same level) and position it next to an existing block.")
            raise EditError(f"There is no block with id {block_id!r}.{hint}")
        if block.kind not in kinds:
            raise EditError(f"{block_id} is a {block.kind}, expected a {' or '.join(kinds)}.")
        if not block.editable:
            raise EditError(f"{block_id} is read-only ({block.readonly_reason}).")
        if not self._attached(block.element):
            raise EditError(f"{block_id} was removed by an earlier operation in this plan.")
        return block

    def _attached(self, el: etree._Element) -> bool:
        node = el
        while node.getparent() is not None:
            node = node.getparent()
        return node is self.pkg.document or any(node is hf.root for hf in self.pkg.hf_parts)

    def _root_of(self, el: etree._Element) -> etree._Element:
        """The part an element belongs to: the body, a header/footer, or a text box."""
        node = el
        while node.getparent() is not None and node.tag not in (W.body, TXBX):
            node = node.getparent()
        return node

    def _touch(self, el: etree._Element) -> None:
        self._touched.add(el)

    def _row(self, row_id: str) -> tuple[etree._Element, etree._Element]:
        """Resolve 't1.r3' to (table element, row element) in the original numbering."""
        m = _ROW_ID.match(row_id.strip())
        if m is None:
            raise EditError(f"{row_id!r} is not a row id; use table id + '.r' + row index, "
                            "e.g. 't1.r3'.")
        table = self._block(m.group("table"), ("table",)).element
        rows = self._table_rows.setdefault(table, table.findall(W.tr))
        idx = int(m.group("row"))
        if idx >= len(rows):
            raise EditError(f"{m.group('table')} has only {len(rows)} rows (r0-r{len(rows) - 1}).")
        tr = rows[idx]
        if not self._attached(tr):
            raise EditError(f"{row_id} was removed by an earlier operation in this plan.")
        return table, tr

    def _current_paragraphs(self) -> list[tuple[str, etree._Element]]:
        blocks: list[Block] = []
        _walk_container(self.pkg.body, "", blocks, 0, None, {"p": 0, "t": 0})
        for hf in self.pkg.hf_parts:
            if not hf.created:
                _walk_container(hf.root, f"{hf.label}.", blocks, 1, None, {"p": 0, "t": 0})
        for label, box in text_boxes(self.pkg.body):  # same order as the oracle's parts
            _walk_container(box, f"{label}.", blocks, 1, None, {"p": 0, "t": 0})
        return [(self._label(b.element), b.element) for b in blocks
                if b.kind == "paragraph" and b.editable]

    def _matches(self, block_id: str | None, needle: str,
                 occurrence: Occurrence) -> list[tuple[str, etree._Element, int]]:
        if block_id is not None:
            scope = [(block_id, self._block(block_id).element)]
        else:
            scope = self._current_paragraphs()
        found: list[tuple[str, etree._Element, int]] = []
        texts: list[tuple[str, str]] = []
        for bid, el in scope:
            text = paragraph_view(el).text
            texts.append((bid, text))
            found.extend((bid, el, pos) for pos in find_all(text, needle))
        where = block_id or "the document"
        if not found:
            elsewhere = ""
            if block_id is not None:  # the planner often picks the neighbouring block
                others = [b for b, e in self._current_paragraphs()
                          if needle in paragraph_view(e).text][:5]
                if others:
                    elsewhere = f" It does appear in {', '.join(others)} - check the block id."
            raise EditError(f"Text {needle!r} was not found in {where}.{elsewhere}"
                            f"{_suggest(texts, needle) if not elsewhere else ''}")
        if occurrence is None:
            if len(found) > 1:
                locs = ", ".join(sorted({b for b, _, _ in found}, key=lambda s: s))
                raise EditError(
                    f"Text {needle!r} occurs {len(found)} times in {where} (in {locs}). "
                    "Give a block_id, a longer unique `find`, or set occurrence (1-based or \"all\")."
                )
            return found
        if occurrence == "all":
            return found
        if not isinstance(occurrence, int) or occurrence < 1 or occurrence > len(found):
            raise EditError(
                f"occurrence={occurrence!r} is out of range: {needle!r} occurs {len(found)} "
                f"time(s) in {where}."
            )
        return [found[occurrence - 1]]

    @staticmethod
    def _ordered_for_mutation(matches):
        # Later matches first inside a paragraph, so earlier offsets stay valid.
        return sorted(matches, key=lambda m: -m[2])

    # ------------------------------------------------------------ primitives
    def _check_range(self, view: ParagraphView, start: int, end: int, bid: str,
                     allow_removable: bool) -> list[Piece]:
        covered = view.pieces_in(start, end)
        for pc in covered:
            if pc.kind == "text":
                continue
            fully = start <= pc.start and pc.end <= end
            if allow_removable and pc.removable and fully:
                continue
            what = (pc.label or "protected").lower().replace("_", " ")
            raise EditError(
                f"The text range in {bid} overlaps a protected element ({what}: {pc.text!r}). "
                "Edit only the plain text around it."
            )
        if len({id(pc.container) for pc in covered}) > 1:
            raise EditError(
                f"The text range in {bid} crosses a hyperlink boundary. Split it into separate "
                "edits for the text inside and outside the link."
            )
        return covered

    def _replace_range(self, el: etree._Element, start: int, end: int, new_text: str,
                       bid: str) -> None:
        view = paragraph_view(el)
        covered = self._check_range(view, start, end, bid, allow_removable=True)
        touched_runs: list[etree._Element] = []
        text_pieces = [pc for pc in covered if pc.kind == "text"]
        receiver = text_pieces[0] if (new_text and text_pieces) else None
        if new_text and receiver is None:
            # Range is only removable protected nodes (e.g. a tab): put the text in
            # a new <w:t> at the position of the first one, in the same run.
            first = covered[0]
            first.node.addprevious(_new_t(new_text))
        for pc in covered:
            if pc.kind != "text":
                touched_runs.append(pc.run)
                _remove(pc.node)
                continue
            s = max(start, pc.start) - pc.start
            e = min(end, pc.end) - pc.start
            kept = pc.text[:s] + (new_text if pc is receiver else "") + pc.text[e:]
            touched_runs.append(pc.run)
            if kept:
                _set_t(pc.node, kept)
            else:
                _remove(pc.node)
        _clean_runs([r for r in touched_runs if r is not None])

    def _insert_at(self, el: etree._Element, offset: int, text: str, prefer: str,
                   bid: str) -> None:
        """Insert ``text`` at ``offset``. ``prefer`` = 'left'|'right' neighbour formatting."""
        view = paragraph_view(el)
        inside = view.piece_at(offset)
        if inside is not None and inside.start < offset:
            if inside.kind != "text":
                raise EditError(f"Cannot insert inside a protected element in {bid}.")
            k = offset - inside.start
            _set_t(inside.node, inside.text[:k] + text + inside.text[k:])
            return
        left = view.piece_at(offset - 1) if offset > 0 else None
        right = inside
        order = [left, right] if prefer == "left" else [right, left]
        candidates = [p for p in order if p is not None]
        # At a boundary, only extend a run that lives directly in the paragraph - or, when
        # both neighbours sit inside the *same* hyperlink, a run of that hyperlink. Never
        # silently extend a link with text that was written next to it.
        same_container = (left is not None and right is not None
                          and left.container is right.container)
        target = [p for p in candidates
                  if p.kind == "text" and (p.container is el or same_container)]
        if target:
            pc = target[0]
            if pc is left:
                _set_t(pc.node, pc.text + text)
            else:
                _set_t(pc.node, text + pc.text)
            return
        # No text neighbour usable: create a new run next to a neighbour run.
        for pc in candidates:
            if pc.label in ("FIELD", "TRACKED_CHANGE", "CONTENT_CONTROL", "EQUATION"):
                raise EditError(
                    f"Cannot insert directly next to a {pc.label.lower().replace('_', ' ')} "
                    f"in {bid}; anchor on nearby plain text instead."
                )
        new_run = etree.Element(W.r)
        rpr = self._nearest_plain_rpr(view, el, offset)
        if rpr is not None:
            new_run.append(copy.deepcopy(rpr))
        new_run.append(_new_t(text))
        anchor_pc = candidates[0] if candidates else None
        if anchor_pc is None:
            # Empty paragraph: append after pPr.
            el.append(new_run)
            return
        # climb to the child of the paragraph that holds the neighbour (e.g. the hyperlink)
        node = anchor_pc.run if anchor_pc.run is not None else anchor_pc.node
        while node.getparent() is not None and node.getparent() is not el:
            node = node.getparent()
        if anchor_pc is left:
            node.addnext(new_run)
        else:
            node.addprevious(new_run)

    @staticmethod
    def _nearest_plain_rpr(view: ParagraphView, el: etree._Element,
                           offset: int = 0) -> etree._Element | None:
        plain = [pc for pc in view.pieces
                 if pc.kind == "text" and pc.container is el and pc.run is not None]
        if plain:
            nearest = min(plain, key=lambda pc: min(abs(pc.start - offset), abs(pc.end - offset)))
            return nearest.run.find(W.rPr)
        ppr = el.find(W.pPr)
        if ppr is not None and ppr.find(W.rPr) is not None:
            return _strip_revision_markup(copy.deepcopy(ppr.find(W.rPr)))
        return None

    # ----------------------------------------------------------- operations
    def apply(self, plan: EditPlan) -> ApplyResult:
        boxes = {text_box_key(box): _c14n(box) for _, box in text_boxes(self.pkg.body)}
        for idx, op in enumerate(plan.operations):
            try:
                self._apply_one(idx, op)
            except EditError as exc:
                exc.op_index = idx
                raise
        self._sync_text_box_copies(boxes)
        return self.result

    def _sync_text_box_copies(self, before: dict[tuple, bytes]) -> None:
        """Word stores a text box twice: DrawingML (read by today's Word and LibreOffice) and
        a VML copy for old readers. After an edit the VML copy gets the same content, so
        every reader shows the same text (the verifier checks that they match)."""
        for _, box in text_boxes(self.pkg.body):
            if before.get(text_box_key(box)) == _c14n(box):
                continue
            copy_ = text_box_fallback(box)
            if copy_ is None:
                continue
            for child in list(copy_):
                copy_.remove(child)
            for child in box:
                copy_.append(copy.deepcopy(child))

    def _record(self, idx: int, kind: str, bid: str, before: str | None, after: str | None):
        self.result.changes.append(Change(idx, kind, bid, before, after))

    def _for_each_match(self, idx: int, kind: str, matches, fn) -> None:
        """Run ``fn(bid, el, pos)`` for every match (last first) and log one change
        per touched paragraph."""
        befores: dict[etree._Element, tuple[str, str]] = {}
        for bid, el, pos in self._ordered_for_mutation(matches):
            befores.setdefault(el, (bid, paragraph_view(el).text))
            fn(bid, el, pos)
        for el, (bid, before) in befores.items():
            self._touch(el)
            self._record(idx, kind, bid, before, paragraph_view(el).text)

    def _apply_one(self, idx: int, op) -> None:
        if isinstance(op, ReplaceText):
            new = _check_inline_text(op.replace_with, "replace_with")
            n = len(op.find)
            self._for_each_match(
                idx, "replace_text", self._matches(op.block_id, op.find, op.occurrence),
                lambda bid, el, pos: self._replace_range(el, pos, pos + n, new, bid),
            )
        elif isinstance(op, DeleteText):
            n = len(op.find)

            def delete(bid: str, el: etree._Element, pos: int) -> None:
                text = paragraph_view(el).text
                if text[pos:pos + n] == text:
                    raise EditError(
                        f"delete_text would empty {bid} completely; use delete_paragraph instead."
                    )
                problem = deletion_whitespace_problem(text, pos, pos + n)
                if problem:
                    better = deletion_with_spaces(text, pos, pos + n)
                    hint = (f"Use find={better!r} instead (it includes the spaces next to it)."
                            if better else "Include the adjacent space(s) in `find`.")
                    raise EditError(f"Deleting {op.find!r} in {bid}: {problem}. {hint}")
                self._replace_range(el, pos, pos + n, "", bid)

            self._for_each_match(
                idx, "delete_text", self._matches(op.block_id, op.find, op.occurrence), delete
            )
        elif isinstance(op, InsertText):
            text = _check_inline_text(op.text, "text")
            el = self._block(op.block_id).element
            before = paragraph_view(el).text
            if op.position in ("start", "end"):
                if op.anchor:
                    raise EditError("anchor must be null when position is start/end.")
                if op.position == "start":
                    self._insert_at(el, 0, text, "right", op.block_id)
                else:
                    self._insert_at(el, len(before), text, "left", op.block_id)
            else:
                if not op.anchor:
                    raise EditError("anchor is required when position is before/after.")
                if op.occurrence == "all":
                    raise EditError('occurrence="all" is not supported for insert_text.')
                _, _, pos = self._matches(op.block_id, op.anchor, op.occurrence)[0]
                if op.position == "before":
                    self._insert_at(el, pos, text, "right", op.block_id)
                else:
                    self._insert_at(el, pos + len(op.anchor), text, "left", op.block_id)
            self._touch(el)
            self._record(idx, "insert_text", op.block_id, before, paragraph_view(el).text)
        elif isinstance(op, InsertParagraph):
            self._insert_paragraph(idx, op)
        elif isinstance(op, DeleteParagraph):
            self._delete_paragraph(idx, op)
        elif isinstance(op, FormatText):
            self._format_text(idx, op)
        elif isinstance(op, RestyleText):
            self._restyle_text(idx, op)
        elif isinstance(op, DeleteImages):
            self._delete_images(idx, op)
        elif isinstance(op, DeleteTableRows):
            self._delete_table_rows(idx, op)
        elif isinstance(op, ReorderTableRows):
            self._reorder_table_rows(idx, op)
        elif isinstance(op, SetShapeFill):
            self._set_shape_fill(idx, op)
        elif isinstance(op, InsertTableRow):
            self._insert_table_row(idx, op)
        elif isinstance(op, DeleteTable):
            self._delete_table(idx, op)
        elif isinstance(op, InsertTable):
            self._insert_table(idx, op)
        elif isinstance(op, MoveBlocks):
            self._move_blocks(idx, op)
        elif isinstance(op, DuplicateBlocks):
            self._duplicate_blocks(idx, op)
        elif isinstance(op, SetParagraphFormat):
            self._set_paragraph_format(idx, op)
        elif isinstance(op, SplitParagraph):
            self._split_paragraph(idx, op)
        elif isinstance(op, MergeParagraphs):
            self._merge_paragraphs(idx, op)
        elif isinstance(op, InsertPageBreak):
            self._insert_page_break(idx, op)
        elif isinstance(op, InsertTableColumn):
            self._insert_table_column(idx, op)
        elif isinstance(op, DeleteTableColumns):
            self._delete_table_columns(idx, op)
        elif isinstance(op, BlocksToTable):
            self._blocks_to_table(idx, op)
        elif isinstance(op, InsertHyperlink):
            self._insert_hyperlink(idx, op)
        elif isinstance(op, RemoveHyperlink):
            self._remove_hyperlink(idx, op)
        elif isinstance(op, SetHyperlinkUrl):
            self._set_hyperlink_url(idx, op)
        elif isinstance(op, CreateHeaderFooter):
            self._create_header_footer(idx, op)
        else:  # pragma: no cover - pydantic guarantees the union
            raise EditError(f"Unknown operation {op!r}")

    # ------------------------------------------------------ insert paragraph
    def _insert_paragraph(self, idx: int, op: InsertParagraph) -> None:
        target = self._block(op.target_id, ("paragraph", "table"))
        template = self._block(op.format_like).element
        lines = [ln for ln in op.text.replace("\r\n", "\n").split("\n")]
        if any(not ln.strip() for ln in lines):
            raise EditError("insert_paragraph text must not contain empty lines.")
        new_paras = [self._make_paragraph(template, _check_inline_text(ln, "text"))
                     for ln in lines]
        anchor = target.element
        if op.position == "after":
            for p in new_paras:
                anchor.addnext(p)
                anchor = p
        else:
            for p in new_paras:
                anchor.addprevious(p)
        for p in new_paras:
            self._record(idx, "insert_paragraph", self._new_id(p), None, paragraph_view(p).text)
        self.result.inserted += len(new_paras)

    @staticmethod
    def _dominant_rpr(template: etree._Element) -> etree._Element | None:
        view = paragraph_view(template)
        weights: dict[int, tuple[int, etree._Element | None]] = {}
        for pc in view.pieces:
            if pc.kind != "text" or pc.run is None:
                continue
            rpr = pc.run.find(W.rPr)
            key = id(rpr) if rpr is not None else 0
            n, _ = weights.get(key, (0, rpr))
            weights[key] = (n + len(pc.text), rpr)
        if weights:
            _, rpr = max(weights.values(), key=lambda v: v[0])
            return copy.deepcopy(rpr) if rpr is not None else None
        ppr = template.find(W.pPr)
        if ppr is not None and ppr.find(W.rPr) is not None:
            return _strip_revision_markup(copy.deepcopy(ppr.find(W.rPr)))
        return None

    def _require_pristine(self, el: etree._Element, what: str) -> None:
        """Deleting is only allowed for blocks still exactly as in the original document, so
        content moved, split or created earlier in the plan is never deleted by accident."""
        if el.tag == W.tr:
            table = el.getparent()
            original = self._original(table)
            rows = self._table_rows.get(table, [])
            idx = next((i for i, r in enumerate(rows) if r is el), None)
            ok = original is not table and idx is not None and \
                len(original.findall(W.tr)) > idx and \
                _c14n(original.findall(W.tr)[idx]) == _c14n(el)
        else:
            original = self._original(el)
            ok = original is not el and _c14n(original) == _c14n(el)
        if not ok:
            raise EditError(f"{what} was changed earlier in this plan (content moved into it, "
                            "split, merged or edited); delete it in a separate request.")

    def _cell_template(self, tc: etree._Element) -> etree._Element:
        """First paragraph of the cell as it was in the original document."""
        first = self._cell_first.get(tc)
        return first if first is not None else cell_template_paragraph(tc)

    def _original(self, el: etree._Element) -> etree._Element:
        """The paragraph as it was before this plan (templates are copied from originals,
        so an earlier operation on the template does not leak into new paragraphs)."""
        bid = self._ids.get(el)
        if not bid or bid.startswith("new"):
            return el
        if self._pristine is None:
            self._pristine = build_index(DocxPackage(self._source_bytes))
        block = self._pristine.get(bid)
        return block.element if block is not None else el

    def _make_paragraph(self, template: etree._Element, text: str) -> etree._Element:
        template = self._original(template)
        p = etree.Element(W.p)
        ppr = template.find(W.pPr)
        if ppr is not None:
            p.append(_strip_revision_markup(copy.deepcopy(ppr)))
        if not text:
            return p  # an empty paragraph has no run
        run = etree.SubElement(p, W.r)
        rpr = self._dominant_rpr(template)
        if rpr is not None:
            run.append(rpr)
        run.append(_new_t(text))
        return p

    def _new_id(self, el: etree._Element) -> str:
        self._new_counter += 1
        self._ids[el] = f"new{self._new_counter}"
        return self._ids[el]

    # ------------------------------------------------------ delete paragraph
    def _delete_paragraph(self, idx: int, op: DeleteParagraph) -> None:
        block = self._block(op.block_id)
        el = block.element
        self._require_pristine(el, op.block_id)
        view = paragraph_view(el)
        allowed = {"TAB", "BR", "NBHYPHEN", "PAGE_BREAK", "COLUMN_BREAK"} | (
            {"IMAGE"} if op.delete_images else set())
        blockers = sorted({pc.label or "protected" for pc in view.pieces
                           if pc.kind == "protected" and pc.label not in allowed})
        if blockers == ["IMAGE"]:
            raise EditError(
                f"{op.block_id} contains pictures. Set delete_images=true only if the user wants "
                "them removed as well; otherwise delete its text with delete_text."
            )
        if blockers:
            raise EditError(
                f"{op.block_id} contains {', '.join(b.lower() for b in blockers)}; deleting it "
                "would remove that content, which this agent does not do."
            )
        if el.find(".//" + W.commentRangeStart) is not None or \
                el.find(".//" + W.commentRangeEnd) is not None or \
                el.find(".//" + W.commentReference) is not None:
            raise EditError(f"{op.block_id} is anchored to a comment and cannot be deleted.")
        starts = {b.get(W.id) for b in el.iter(W.bookmarkStart)}
        ends = {b.get(W.id) for b in el.iter(W.bookmarkEnd)}
        if starts != ends:
            raise EditError(
                f"{op.block_id} holds one end of a bookmark that spans other paragraphs; "
                "deleting it would corrupt the bookmark. Delete its text instead."
            )
        ppr = el.find(W.pPr)
        if ppr is not None and ppr.find(W.sectPr) is not None:
            raise EditError(f"{op.block_id} carries a section break and cannot be deleted.")
        parent = el.getparent()
        if parent is not None and parent.tag in (qn("w:hdr"), qn("w:ftr"), TXBX) \
                and len(parent.findall(W.p)) == 1:
            raise EditError(f"{op.block_id} is the only paragraph of its header/footer or text "
                            "box; clear its text with delete_text instead.")
        if parent is not None and parent.tag == W.tc:
            paras = parent.findall(W.p)
            if len(paras) == 1:
                raise EditError(
                    f"{op.block_id} is the only paragraph in its table cell (a cell must keep "
                    "one); use delete_text to clear its text instead."
                )
            if paras[-1] is el and el.getprevious() is not None and \
                    el.getprevious().tag == W.tbl:
                raise EditError(f"{op.block_id} must stay: a cell must end with a paragraph.")
        prev, nxt = el.getprevious(), el.getnext()
        if prev is not None and nxt is not None and prev.tag == W.tbl and nxt.tag == W.tbl:
            raise EditError(
                f"{op.block_id} separates two tables; deleting it would merge them."
            )
        if prev is not None and prev.tag == W.tbl and (nxt is None or nxt.tag == W.sectPr):
            raise EditError(
                f"{op.block_id} is the paragraph that must follow the final table; it cannot "
                "be deleted (use delete_text to clear it)."
            )
        before = view.text
        _remove(el)
        self._deleted[op.block_id] = idx
        self.result.deleted_ids.append(op.block_id)
        self._record(idx, "delete_paragraph", op.block_id, before, None)

    # ----------------------------------------------------------- format text
    def _format_text(self, idx: int, op: FormatText) -> None:
        props = op.props()
        if not props:
            raise EditError("format_text needs at least one formatting property to set.")
        label = f"{op.find} ({describe_props(props)})"
        for bid, el, pos in self._ordered_for_mutation(
            self._matches(op.block_id, op.find, op.occurrence)
        ):
            start, end = pos, pos + len(op.find)
            text_before = paragraph_view(el).text
            view = paragraph_view(el)
            covered = view.pieces_in(start, end)
            for pc in covered:
                if pc.kind != "text" and not pc.removable:
                    raise EditError(
                        f"The text range in {bid} overlaps a protected element "
                        f"({(pc.label or 'protected').lower()}); format only plain text."
                    )
            # split at both boundaries (end first so start offsets stay valid)
            last = view.piece_at(end - 1)
            if last is not None and last.run is not None:
                _split_run_at(last, end)
            view = paragraph_view(el)
            first = view.piece_at(start)
            if first is not None and first.run is not None:
                _split_run_at(first, start)
            view = paragraph_view(el)
            runs: list[etree._Element] = []
            for pc in view.pieces_in(start, end):
                if pc.run is not None and pc.run not in runs:
                    runs.append(pc.run)
            for run in runs:
                apply_props(run, props)
            if paragraph_view(el).text != text_before:  # pragma: no cover - defensive
                raise EditError("internal error: formatting changed the text")
            self._touch(el)
            self._record(idx, "format_text", bid, op.find, label)

    def _scope(self, block_id: str | None) -> list[tuple[str, etree._Element]]:
        if block_id is not None:
            return [(block_id, self._block(block_id).element)]
        return self._current_paragraphs()

    # ---------------------------------------------------------- restyle text
    def _restyle_text(self, idx: int, op: RestyleText) -> None:
        match, new = op.match.props(), op.set.props()
        if not match or not new:
            raise EditError("restyle_text needs at least one property in `match` and in `set`.")
        present: dict[str, int] = {}
        hits = 0
        for bid, el in self._scope(op.block_id):
            if bid.startswith("new"):
                continue  # restyling applies to the document's existing text
            runs: list[etree._Element] = []
            for pc in paragraph_view(el).pieces:
                if pc.kind != "text" or pc.run is None or not pc.text.strip():
                    continue
                props = run_props(pc.run)
                if props_match(props, match):
                    if pc.run not in runs:
                        runs.append(pc.run)
                else:
                    for k in match:
                        if props.get(k) not in (None, False):
                            label = f"{k}={props[k]}"
                            present[label] = present.get(label, 0) + 1
            if not runs:
                continue
            if el in self._touched:
                raise EditError(f"restyle_text must come before other edits to {bid} in the plan "
                                "(it matches formatting as it is in the original); reorder the "
                                "operations.")
            hits += len(runs)
            self._touch(el)
            for run in runs:
                apply_props(run, new)
            text = paragraph_view(el).text
            self._record(idx, "restyle_text", bid, text, f"{text} ({describe_props(new)})")
        if not hits:
            where = op.block_id or "the document"
            seen = ", ".join(f"{k} ({n} runs)" for k, n in sorted(
                present.items(), key=lambda kv: -kv[1])[:10]) or "none"
            raise EditError(f"No text in {where} has {describe_props(match)}. "
                            f"Values present for those properties: {seen}.")

    # --------------------------------------------------------- delete images
    def _delete_images(self, idx: int, op: DeleteImages) -> None:
        if op.images is None and op.block_id is None and op.max_size_px is None:
            raise EditError("delete_images needs `images`, `block_id` or `max_size_px` to say "
                            "which pictures to delete.")
        refs = normalise_image_refs(op.images) if op.images is not None else None
        found: set[str | None] = set()
        available: list[str] = []
        for bid, el in self._scope(op.block_id):
            if bid.startswith("new"):
                continue  # applies to the document's existing content, like restyle_text
            view = paragraph_view(el)
            hits = [pc for pc in view.pieces if image_selected(pc, refs, op.max_size_px)]
            available += [f"{image_info(pc.node).describe()} in {bid}" for pc in view.pieces
                          if pc.kind == "protected" and pc.label == "IMAGE"]
            if not hits:
                continue
            before = view.text
            for pc in hits:
                found.add(image_info(pc.node).ref)
                _remove(pc.node)
            _clean_runs([pc.run for pc in hits if pc.run is not None])
            self._touch(el)
            self._record(idx, "delete_images", bid, before, paragraph_view(el).text)
        missing = sorted(refs - found) if refs is not None else []
        if not found or missing:
            what = f"pictures {', '.join('#' + m for m in missing)}" if missing else \
                "any matching picture"
            listing = "; ".join(available[:15]) or "none"
            raise EditError(f"Could not find {what} in {op.block_id or 'the document'}. "
                            f"Pictures available: {listing}.")

    # ------------------------------------------------------------ table rows
    def _delete_table_rows(self, idx: int, op: DeleteTableRows) -> None:
        targets: dict[etree._Element, list[tuple[str, etree._Element]]] = {}
        for row_id in dict.fromkeys(op.rows):
            table, tr = self._row(row_id)
            targets.setdefault(table, []).append((row_id, tr))
        for table, rows in targets.items():
            self._touch(table)
            current = table.findall(W.tr)
            doomed = {id(tr) for _, tr in rows}
            if all(id(tr) in doomed for tr in current):
                raise EditError("That would delete every row of the table; use delete_table.")
            for row_id, tr in rows:
                self._require_pristine(tr, row_id)
                problem = removal_problem(tr)
                if problem:
                    raise EditError(f"Row {row_id} cannot be deleted: {problem}.")
                if self._starts_vertical_merge(tr, current, doomed):
                    raise EditError(
                        f"Row {row_id} starts a vertically merged cell that continues in the "
                        "next row; delete those rows together or edit the text instead."
                    )
            for row_id, tr in rows:
                before = " | ".join(paragraph_view(p).text for p in tr.iter(W.p))
                _remove(tr)
                self._record(idx, "delete_table_row", row_id, before, None)

    def _set_shape_fill(self, idx: int, op: SetShapeFill) -> None:
        node, host, label = find_drawing(self.pkg, self.index, op.target)
        if not self._attached(host):
            raise EditError(f"The paragraph holding {label} was removed earlier in this plan.")
        if not recolor_drawing(node, op.color):
            raise EditError(f"{label} has no filled area (it is transparent); to colour its "
                            "text use format_text on the text box paragraph.")
        self._touch(host)
        self._record(idx, "set_shape_fill", self._label(host), None,
                     f"{label}: fill #{op.color.upper()}")

    def _reorder_table_rows(self, idx: int, op: ReorderTableRows) -> None:
        if len(set(op.order)) != len(op.order):
            raise EditError("reorder_table_rows: each row id may appear only once in `order`.")
        resolved = [self._row(row_id) for row_id in op.order]
        table = resolved[0][0]
        if any(t is not table for t, _ in resolved):
            raise EditError("reorder_table_rows works on one table at a time; use one operation "
                            "per table.")
        rows = [tr for _, tr in resolved]
        for row_id, tr in zip(op.order, rows):
            if any(True for _ in tr.iter(W.vMerge)):
                raise EditError(f"Row {row_id} is part of a vertically merged cell; rows with "
                                "merged cells cannot be reordered.")
        current = table.findall(W.tr)
        position = {id(tr): n for n, tr in enumerate(current)}
        slots = sorted(rows, key=lambda tr: position[id(tr)])
        if all(a is b for a, b in zip(slots, rows)):
            raise EditError("Those rows are already in that order.")

        def first_cell(tr: etree._Element) -> str:
            p = tr.find(f"{W.tc}/{W.p}")
            text = re.sub(r"⟦[^⟧]*⟧\s*", "", paragraph_view(p).text if p is not None else "")
            text = text.strip(" -")
            return text if len(text) <= 28 else text[:27].rstrip() + "…"

        marks = []
        for tr in slots:
            mark = etree.Element("reorder-slot")
            tr.addprevious(mark)
            marks.append(mark)
        for tr in rows:
            table.remove(tr)
        for mark, tr in zip(marks, rows):
            mark.addprevious(tr)
            table.remove(mark)
        self._touch(table)
        table_id = self._ids.get(table) or op.order[0].split(".")[0]
        order = " / ".join(first_cell(tr) for tr in rows)
        self._record(idx, "reorder_table_rows", table_id, None,
                     f"{len(rows)} rows in a new order: "
                     + (order if len(order) <= 160 else order[:159] + "…"))

    @staticmethod
    def _starts_vertical_merge(tr: etree._Element, rows: list[etree._Element],
                               doomed: set[int]) -> bool:
        restarts = [tc for tc in tr.findall(W.tc)
                    if (tc.find(W.tcPr) is not None and tc.find(W.tcPr).find(W.vMerge) is not None
                        and tc.find(W.tcPr).find(W.vMerge).get(W.val) == "restart")]
        if not restarts:
            return False
        later = [r for r in rows[rows.index(tr) + 1:] if id(r) not in doomed]
        if not later:
            return False
        for tc in later[0].findall(W.tc):
            tcpr = tc.find(W.tcPr)
            vm = tcpr.find(W.vMerge) if tcpr is not None else None
            if vm is not None and vm.get(W.val) in (None, "continue"):
                return True
        return False

    def _insert_table_row(self, idx: int, op: InsertTableRow) -> None:
        table, anchor = self._row(op.row)
        if table in self._cols_changed:
            raise EditError("This plan already changed this table's columns; add rows in a "
                            "separate request.")
        self._rows_inserted.add(table)
        self._touch(table)
        _, template = self._row(op.format_like_row) if op.format_like_row else (table, anchor)
        if any(child.tag not in (W.tc, qn("w:trPr"), qn("w:tblPrEx")) for child in template):
            raise EditError("The template row contains content controls or custom XML; pick "
                            "another row as format_like_row.")
        cells = template.findall(W.tc)
        if len(op.cells) != len(cells):
            raise EditError(f"The template row has {len(cells)} cells but {len(op.cells)} cell "
                            "texts were given; give exactly one text per cell.")
        new_tr = new_row_skeleton(template)
        texts = []
        for tc, cell_text in zip(cells, op.cells):
            new_tc = new_cell_skeleton(tc)
            # the cell's first *original* paragraph (not one added earlier in this plan)
            tpl_p = self._cell_template(tc)
            lines = cell_text.replace("\r\n", "\n").split("\n")
            for line in lines:
                p = self._make_paragraph(tpl_p, _check_inline_text(line, "cell text"))
                self._new_id(p)
                new_tc.append(p)
            new_tr.append(new_tc)
            texts.append(cell_text)
        if op.position == "after":
            anchor.addnext(new_tr)
        else:
            anchor.addprevious(new_tr)
        self.result.inserted += 1
        self._record(idx, "insert_table_row", f"{op.row} ({op.position})", None,
                     " | ".join(texts))

    def _insert_table(self, idx: int, op: InsertTable) -> None:
        target = self._block(op.target_id, ("paragraph", "table")).element
        template_p = self._block(op.format_like).element
        template_t = (self._table_looks[self._block(op.table_like, ("table",)).element]
                      if op.table_like else None)
        tbl = new_table_skeleton(self.pkg, template_t, len(op.rows[0]))
        widths = table_grid_widths(tbl)
        for r, row in enumerate(op.rows):
            header = op.header and r == 0
            tr = new_table_row(header)
            for width, text in zip(widths, row):
                tc = new_table_cell(width)
                for line in text.replace("\r\n", "\n").split("\n"):
                    p = self._make_paragraph(template_p, _check_inline_text(line, "cell text"))
                    self._new_id(p)
                    if header:
                        for run in p.findall(W.r):
                            apply_props(run, {"bold": True})
                    tc.append(p)
                tr.append(tc)
            tbl.append(tr)
        if op.position == "after":
            target.addnext(tbl)
        else:
            target.addprevious(tbl)
        self._ensure_spacers(tbl, tbl)
        self.result.inserted += 1
        self._record(idx, "insert_table", f"{op.target_id} ({op.position})", None,
                     f"table {len(op.rows)}x{len(widths)}: "
                     + " / ".join(" | ".join(r) for r in op.rows[:5])
                     + (" / …" if len(op.rows) > 5 else ""))

    def _delete_table(self, idx: int, op: DeleteTable) -> None:
        block = self._block(op.table_id, ("table",))
        el = block.element
        self._require_pristine(el, op.table_id)
        problem = removal_problem(el)
        if problem:
            raise EditError(f"{op.table_id} cannot be deleted: {problem}.")
        prev, nxt = el.getprevious(), el.getnext()
        if prev is not None and nxt is not None and prev.tag == W.tbl and nxt.tag == W.tbl:
            raise EditError(f"Deleting {op.table_id} would merge the tables around it.")
        before = f"table with {len(el.findall(W.tr))} rows"
        _remove(el)
        self._deleted[op.table_id] = idx
        self._record(idx, "delete_table", op.table_id, before, None)


    # ------------------------------------------------------------ structure
    def _ensure_spacers(self, first: etree._Element, last: etree._Element) -> None:
        """Word needs a paragraph between two tables and after a table that ends the body,
        a header/footer or a cell; add an empty one where a placed table needs it."""
        nxt, prv = last.getnext(), first.getprevious()
        if last.tag == W.tbl and (nxt is None or nxt.tag in (W.sectPr, W.tbl)):
            last.addnext(etree.Element(W.p, nsmap=_W_NSMAP))
        if first.tag == W.tbl and prv is not None and prv.tag == W.tbl:
            first.addprevious(etree.Element(W.p, nsmap=_W_NSMAP))

    def _check_containers(self, containers: list[etree._Element]) -> None:
        """Refuse results Word would repair: touching tables, cells or headers/footers left
        without a final paragraph, a body that ends with a table."""
        for c in containers:
            if c.getparent() is None and c.tag not in (qn("w:hdr"), qn("w:ftr")):
                continue  # detached
            kids = [k for k in c if k.tag in (W.p, W.tbl)]
            for a, b in zip(kids, kids[1:]):
                if a.tag == W.tbl and b.tag == W.tbl and a.getnext() is b:
                    raise EditError("That would leave two tables touching (Word would merge "
                                    "them); keep a paragraph between them.")
            if c.tag == W.tc and (not kids or kids[-1].tag != W.p):
                raise EditError("That would leave a table cell without a final paragraph.")
            if c.tag in (W.body, qn("w:hdr"), qn("w:ftr")) and kids and kids[-1].tag != W.p:
                raise EditError("That would leave the document (or a header/footer) ending "
                                "with a table.")

    def _blocks(self, ids: list[str], kinds=("paragraph", "table")) -> list[etree._Element]:
        els = [self._block(b, kinds).element for b in dict.fromkeys(ids)]
        root = self._root_of(els[0])
        order = {id(e): i for i, e in enumerate(root.iter())}
        if any(self._root_of(e) is not root for e in els):
            raise EditError("All blocks of one operation must be in the same part (body, or "
                            "one header/footer).")
        return sorted(els, key=lambda e: order[id(e)])

    def _consecutive(self, els: list[etree._Element]) -> None:
        for a, b in zip(els, els[1:]):
            nxt = a.getnext()
            while nxt is not None and nxt.tag not in (W.p, W.tbl):
                nxt = nxt.getnext()
            if nxt is not b:
                raise EditError("The paragraphs must be consecutive (one directly after the "
                                "other, in the same container).")

    @staticmethod
    def _has_section_break(el: etree._Element) -> bool:
        ppr = el.find(W.pPr) if el.tag == W.p else None
        return ppr is not None and ppr.find(W.sectPr) is not None

    # ------------------------------------------------------- move / duplicate
    def _move_blocks(self, idx: int, op: MoveBlocks) -> None:
        els = self._blocks(op.block_ids)
        target = self._block(op.target_id, ("paragraph", "table")).element
        if self._root_of(target) is not self._root_of(els[0]):
            raise EditError("Blocks can only be moved within the same part (body, or one "
                            "header/footer).")
        for el in els:
            if el is target or any(a is el for a in target.iterancestors()):
                raise EditError("The target is one of the blocks being moved.")
            if el in self._page_breaks_at:
                # A real failure: "move this to a new page at the end" inserted the break
                # first, so the break stayed behind and the text landed with no break.
                bid, where = self._page_breaks_at[el]
                raise EditError(
                    f"This plan puts a page break {where} {bid} and then moves {bid} away, so "
                    "the break would stay behind. Move the blocks FIRST, then insert the page "
                    f"break {where} {bid} (it is placed wherever {bid} is by then).")
            if self._has_section_break(el):
                raise EditError(f"{self._label(el)} carries a section break and cannot move.")
        if all(a.getnext() is b for a, b in zip(els, els[1:])) and (
                (op.position == "after" and els[0].getprevious() is target)
                or (op.position == "before" and els[-1].getnext() is target)):
            raise EditError("Those blocks are already right there, so moving them changes "
                            "nothing. To start them on a new page use insert_page_break alone.")
        sources = {id(el.getparent()): el.getparent() for el in els}
        texts = [paragraph_view(el).text if el.tag == W.p else f"table {self._label(el)}"
                 for el in els]
        prev = els[0].getprevious()
        if prev is not None and prev.tag == W.p and not any(prev is e for e in els) \
                and paragraph_view(prev).text.strip() == PAGE_BREAK_TEXT:
            self._left_breaks[els[0]] = prev
        for el in els:
            _remove(el)
        anchor = target
        if op.position == "after":
            for el in els:
                anchor.addnext(el)
                anchor = el
        else:
            for el in els:
                target.addprevious(el)
        self._ensure_spacers(els[0], els[-1])
        self._check_containers(list(sources.values()) + [target.getparent()])
        for el, text in zip(els, texts):
            self._record(idx, "move_blocks", self._label(el), text,
                         f"{text[:60]} → {op.position} {op.target_id}")

    def _duplicate_blocks(self, idx: int, op: DuplicateBlocks) -> None:
        els = self._blocks(op.block_ids)
        for el in els:
            original = self._original(el)
            if original is el or _c14n(original) != _c14n(el):
                raise EditError(f"{self._label(el)} was changed earlier in this plan; "
                                "duplicate it first, then edit the copy.")
            labels = {pc.label for p in ([el] if el.tag == W.p else el.iter(W.p))
                      for pc in paragraph_view(p).pieces if pc.kind == "protected"}
            bad = labels & {"FOOTNOTE", "ENDNOTE", "TRACKED_CHANGE"}
            if bad:
                raise EditError(f"{self._label(el)} contains {', '.join(sorted(bad)).lower()} "
                                "which cannot be duplicated.")
        copies = [sanitize_copy(copy.deepcopy(el)) for el in els]
        for cp in copies:  # every drawing needs its own id
            for d in cp.iter(qn("wp:docPr")):
                d.set("id", str(self._next_docpr))
                self._next_docpr += 1
        if op.target_id:
            target = self._block(op.target_id, ("paragraph", "table")).element
            if self._root_of(target) is not self._root_of(els[0]):
                raise EditError("Copies must stay in the same part as the originals.")
            position = op.position
        else:
            target, position = els[-1], "after"
        anchor = target
        if position == "after":
            for cp in copies:
                anchor.addnext(cp)
                anchor = cp
        else:
            for cp in copies:
                target.addprevious(cp)
        self._ensure_spacers(copies[0], copies[-1])
        self._check_containers([target.getparent()])
        for cp in copies:
            for p_el in ([cp] if cp.tag == W.p else cp.iter(W.p)):
                self._new_id(p_el)
            self._record(idx, "duplicate_blocks", self._label(cp), None,
                         paragraph_view(cp).text if cp.tag == W.p else "copy of a table")

    # ------------------------------------------------------- paragraph format
    def _set_paragraph_format(self, idx: int, op: SetParagraphFormat) -> None:
        style = None
        if op.style:
            style = resolve_paragraph_style(self.pkg, op.style)
            if style is None:
                names = ", ".join(sorted(n[:1].upper() + n[1:]
                                         for n in self.pkg.paragraph_styles.values())[:40])
                raise EditError(f"There is no paragraph style {op.style!r} in this document. "
                                f"Available: {names}.")
        if not (style or op.align or op.remove_numbering or op.shading):
            raise EditError("set_paragraph_format needs style, align, shading or "
                            "remove_numbering.")
        for bid in dict.fromkeys(op.block_ids):
            el = self._block(bid).element
            ppr = el.find(W.pPr)
            if ppr is None:
                ppr = etree.Element(W.pPr)
                el.insert(0, ppr)
            if style:
                ppr_set(ppr, W.pStyle, style)
            if op.align:
                ppr_set(ppr, qn("w:jc"), JC[op.align])
            if op.remove_numbering:
                ppr_set(ppr, W.numPr, None)
            if op.shading:
                ppr_set(ppr, qn("w:shd"), None)
                if op.shading != "none":
                    shd = shading_element(op.shading)
                    rank = _PPR_RANK.get(shd.tag, len(_PPR_ORDER))
                    at = next((i for i, c in enumerate(ppr)
                               if _PPR_RANK.get(c.tag, len(_PPR_ORDER)) > rank), len(ppr))
                    ppr.insert(at, shd)
            self._touch(el)
            label = ", ".join(x for x in (f"style={self.pkg.paragraph_styles.get(style, style)}"
                                          if style else "", f"align={op.align}" if op.align else "",
                                          f"background={op.shading}" if op.shading else "",
                                          "no numbering" if op.remove_numbering else "") if x)
            text = paragraph_view(el).text
            self._record(idx, "set_paragraph_format", bid, text, f"{text[:80]} ({label})")

    # ----------------------------------------------------------- split / merge
    def _split_paragraph(self, idx: int, op: SplitParagraph) -> None:
        if op.occurrence == "all":
            raise EditError('occurrence="all" is not supported for split_paragraph.')
        _, el, pos = self._matches(op.block_id, op.at, op.occurrence)[0]
        view = paragraph_view(el)
        if pos == 0:
            raise EditError("The split point is the start of the paragraph; nothing to split.")
        pc = view.piece_at(pos)
        if pc.kind == "text" and pc.container is el and pc.start < pos:
            _split_run_at(pc, pos)
            view = paragraph_view(el)
            pc = view.piece_at(pos)
        node = pc.run if pc.run is not None else pc.node
        while node.getparent() is not el:
            node = node.getparent()
        starts = [p_.start for p_ in view.pieces
                  if (p_.run if p_.run is not None else p_.node) is node
                  or any(a is node for a in (p_.run if p_.run is not None else p_.node)
                         .iterancestors())]
        if not starts or min(starts) != pos or pc.label == "FIELD":
            raise EditError("Cannot split inside a link, field or other protected element; "
                            "choose a split point in plain text.")
        before_kids = []
        for child in el:
            if child is node:
                break
            if child.tag != W.pPr:
                before_kids.append(child)
        fld = sum(1 for k in before_kids for f in k.iter(W.fldChar)
                  if f.get(W.fldCharType) == "begin") - sum(
            1 for k in before_kids for f in k.iter(W.fldChar) if f.get(W.fldCharType) == "end")
        if fld:
            raise EditError("Cannot split inside a field; choose another split point.")
        original = view.text
        new_p = etree.Element(W.p, nsmap=_W_NSMAP)
        ppr = without_sectpr(el.find(W.pPr))
        if ppr is not None:
            new_p.append(ppr)
        for child in before_kids:
            new_p.append(child)
        el.addprevious(new_p)
        for part, at_end in ((new_p, True), (el, False)):  # one space at the cut goes away
            v = paragraph_view(part)
            if not v.text:
                continue
            i = len(v.text) - 1 if at_end else 0
            pc2 = v.piece_at(i)
            if v.text[i] == " " and pc2 is not None and pc2.kind == "text":
                self._replace_range(part, i, i + 1, "", self._label(part))
        self._new_id(new_p)
        self._touch(el)
        self._record(idx, "split_paragraph", op.block_id, original,
                     f"{paragraph_view(new_p).text} ¶ {paragraph_view(el).text}")

    def _merge_paragraphs(self, idx: int, op: MergeParagraphs) -> None:
        ids = list(dict.fromkeys(op.block_ids))
        els = [self._block(b).element for b in ids]
        self._consecutive(els)
        if any(self._has_section_break(e) for e in els):
            raise EditError("One of these paragraphs carries a section break; it cannot be "
                            "merged.")
        sep = _check_inline_text(op.separator, "separator") if op.separator else ""
        first = els[0]
        before = " ¶ ".join(paragraph_view(e).text for e in els)
        for bid, el in zip(ids[1:], els[1:]):
            a, b = paragraph_view(first).text, paragraph_view(el).text
            if merge_separator_needed(a, b, sep):
                self._insert_at(first, len(a), sep, "left", ids[0])
            for child in [c for c in el if c.tag != W.pPr]:
                first.append(child)
            _remove(el)
            self._deleted[bid] = idx
        self._touch(first)
        self._record(idx, "merge_paragraphs", ids[0], before, paragraph_view(first).text)

    def _insert_page_break(self, idx: int, op: InsertPageBreak) -> None:
        target = self._block(op.target_id, ("paragraph", "table")).element
        left = self._left_breaks.get(target)
        if op.position == "before" and left is not None and self._attached(left):
            # A real failure: "I wanted it at the end" moved the text and added a new break,
            # leaving the break from the previous request behind (two breaks, one orphaned).
            raise EditError(
                f"{self._label(left)} is a page break that stood right before {op.target_id} and "
                "would stay behind at the old place. Move it together with the blocks (list it "
                "first in move_blocks) instead of inserting a new page break.")
        neighbour = target.getprevious() if op.position == "before" else target.getnext()
        if any(e is not None and e.tag == W.p and paragraph_view(e).text.strip() == PAGE_BREAK_TEXT
               for e in (target, neighbour)):
            raise EditError(f"There is already a page break right {op.position} {op.target_id}; "
                            "a second one would only add an empty page.")
        p_el = page_break_paragraph()
        if op.position == "after":
            target.addnext(p_el)
        else:
            target.addprevious(p_el)
        self._new_id(p_el)
        self._page_breaks_at[target] = (op.target_id, op.position)
        near = (paragraph_view(target).text if target.tag == W.p else "a table").strip()
        near = near if len(near) <= 40 else near[:39] + "…"
        # say where: the conversation history (and the next request) needs to know
        self._record(idx, "insert_page_break", f"{op.target_id} ({op.position})", None,
                     f"page break {op.position} “{near}”")

    # ------------------------------------------------------------- columns
    def _regular_rows(self, table_id: str) -> tuple[etree._Element, list[list[etree._Element]]]:
        tbl = self._block(table_id, ("table",)).element
        if tbl in self._rows_inserted or tbl in self._cols_changed:
            raise EditError("This plan already changed this table's rows or columns; change "
                            "its columns in a separate request.")
        rows = []
        for tr in tbl.findall(W.tr):
            if any(c.tag not in (W.tc, qn("w:trPr"), qn("w:tblPrEx")) for c in tr):
                raise EditError("This table has content controls in its rows; columns cannot "
                                "be changed.")
            cells = tr.findall(W.tc)
            for tc in cells:
                tcpr = tc.find(W.tcPr)
                if tcpr is not None and (tcpr.find(W.vMerge) is not None or (
                        tcpr.find(W.gridSpan) is not None
                        and tcpr.find(W.gridSpan).get(W.val, "1") != "1")):
                    raise EditError("This table has merged cells; its columns cannot be "
                                    "changed safely.")
            rows.append(cells)
        grid = tbl.find(qn("w:tblGrid"))
        ncols = {len(r) for r in rows}
        if len(ncols) != 1 or grid is None or len(grid) != next(iter(ncols)):
            raise EditError("This table's rows have different numbers of cells; its columns "
                            "cannot be changed safely.")
        return tbl, rows

    def _insert_table_column(self, idx: int, op: InsertTableColumn) -> None:
        tbl, rows = self._regular_rows(op.table_id)
        if op.column >= len(rows[0]):
            raise EditError(f"{op.table_id} has only {len(rows[0])} columns (0-{len(rows[0]) - 1}).")
        if len(op.cells) != len(rows):
            raise EditError(f"{op.table_id} has {len(rows)} rows; give exactly one text per row.")
        grid = tbl.find(qn("w:tblGrid"))
        new_col = copy.deepcopy(grid[op.column])
        if op.position == "after":
            grid[op.column].addnext(new_col)
        else:
            grid[op.column].addprevious(new_col)
        for cells, text in zip(rows, op.cells):
            tc = cells[op.column]
            new_tc = new_cell_skeleton(tc)
            tpl_p = self._cell_template(tc)
            for line in text.replace("\r\n", "\n").split("\n"):
                p_el = self._make_paragraph(tpl_p, _check_inline_text(line, "cell text"))
                self._new_id(p_el)
                new_tc.append(p_el)
            if op.position == "after":
                tc.addnext(new_tc)
            else:
                tc.addprevious(new_tc)
        self._cols_changed.add(tbl)
        self._touch(tbl)
        self._record(idx, "insert_table_column", op.table_id, None,
                     f"column {op.position} {op.column}: " + " | ".join(op.cells[:6]))

    def _delete_table_columns(self, idx: int, op: DeleteTableColumns) -> None:
        tbl, rows = self._regular_rows(op.table_id)
        self._require_pristine(tbl, op.table_id)
        cols = sorted(set(op.columns), reverse=True)
        if any(c >= len(rows[0]) for c in cols):
            raise EditError(f"{op.table_id} has only {len(rows[0])} columns (0-{len(rows[0]) - 1}).")
        if len(cols) >= len(rows[0]):
            raise EditError("That would delete every column; use delete_table.")
        for cells in rows:
            for c in cols:
                problem = removal_problem(cells[c])
                if problem:
                    raise EditError(f"Column {c} cannot be deleted: {problem}.")
        grid = tbl.find(qn("w:tblGrid"))
        for c in cols:
            for cells in rows:
                _remove(cells[c])
            grid.remove(grid[c])
        self._cols_changed.add(tbl)
        self._touch(tbl)
        self._record(idx, "delete_table_columns", op.table_id,
                     f"columns {', '.join(str(c) for c in sorted(cols))}", None)

    def _blocks_to_table(self, idx: int, op: BlocksToTable) -> None:
        els = self._blocks(op.block_ids)
        self._consecutive(els)
        if any(self._has_section_break(e) for e in els):
            raise EditError("A section-break paragraph cannot go into a table.")
        template_t = (self._table_looks[self._block(op.table_like, ("table",)).element]
                      if op.table_like else None)
        # Blank spacer lines would each take a cell and shift every following pair out of
        # its column ("name | description" becoming "name | (empty)"): remove them instead.
        blanks = [e for e in els if is_blank_paragraph(e)]
        content = [e for e in els if not any(e is b for b in blanks)]
        if not content:
            raise EditError("blocks_to_table was given only blank paragraphs.")
        for e in blanks:
            self._require_pristine(e, self._label(e))
        tbl = new_table_skeleton(self.pkg, template_t, op.columns)
        widths = table_grid_widths(tbl)
        parent = els[0].getparent()
        els[0].addprevious(tbl)
        for e in blanks:
            parent.remove(e)
        cells: list[etree._Element | None] = list(content) + [None] * (-len(content) % op.columns)
        for r in range(0, len(cells), op.columns):
            tr = new_table_row(False)
            for c, el in enumerate(cells[r:r + op.columns]):
                tc = new_table_cell(widths[c])
                tc.append(el if el is not None else etree.Element(W.p, nsmap=_W_NSMAP))
                if el is not None and el.tag == W.tbl:  # a cell must end with a paragraph
                    tc.append(etree.Element(W.p, nsmap=_W_NSMAP))
                tr.append(tc)
            tbl.append(tr)
        self._ensure_spacers(tbl, tbl)
        self._check_containers([parent])
        self.result.inserted += 1
        dropped = f", {len(blanks)} blank line(s) removed" if blanks else ""
        self._record(idx, "blocks_to_table", self._label(els[0]), None,
                     f"table {len(cells) // op.columns}x{op.columns} from {len(content)} "
                     f"block(s){dropped}")

    # ------------------------------------------------------------ hyperlinks
    def _hyperlink_style(self, run: etree._Element) -> None:
        if "Hyperlink" in self.pkg.style_names:
            _set_rpr_prop(run, W.rStyle, "Hyperlink")
        else:
            apply_props(run, {"color": "0563C1", "underline": True})

    def _insert_hyperlink(self, idx: int, op: InsertHyperlink) -> None:
        rid = None
        for bid, el, pos in self._ordered_for_mutation(
                self._matches(op.block_id, op.find, op.occurrence)):
            start, end = pos, pos + len(op.find)
            view = paragraph_view(el)
            for pc in view.pieces_in(start, end):
                if pc.kind != "text" or pc.container is not el:
                    raise EditError(f"{op.find!r} in {bid} is already (part of) a link or a "
                                    "protected element.")
            last = view.piece_at(end - 1)
            _split_run_at(last, end)
            first = paragraph_view(el).piece_at(start)
            _split_run_at(first, start)
            view = paragraph_view(el)
            runs = []
            for pc in view.pieces_in(start, end):
                if pc.run not in runs:
                    runs.append(pc.run)
            group = []
            node = runs[0]
            while node is not None:
                group.append(node)
                if node is runs[-1]:
                    break
                node = node.getnext()
            rid = rid or self.pkg.add_relationship(HYPERLINK_REL, op.url, external=True)
            link = etree.Element(W.hyperlink)
            link.set(R_ID, rid)
            self._created_links.add(link)
            runs[0].addprevious(link)
            for node in group:
                link.append(node)
            for run in link.iter(W.r):
                self._hyperlink_style(run)
            self._touch(el)
            self._record(idx, "insert_hyperlink", bid, op.find, f"{op.find} → {op.url}")

    def _find_link(self, op) -> tuple[str, etree._Element, etree._Element]:
        if op.occurrence == "all":
            raise EditError('occurrence="all" is not supported for hyperlink edits.')
        bid, el, pos = self._matches(op.block_id, op.find, op.occurrence)[0]
        pc = paragraph_view(el).piece_at(pos)
        link = pc.container if pc is not None else None
        if link is None or link.tag != W.hyperlink or link.getparent() is not el:
            raise EditError(f"{op.find!r} in {bid} is not inside a hyperlink.")
        if link in self._created_links:
            raise EditError("That link was created earlier in this plan; create it with the "
                            "right address instead.")
        return bid, el, link

    def _remove_hyperlink(self, idx: int, op: RemoveHyperlink) -> None:
        bid, el, link = self._find_link(op)
        text = "".join(t.text or "" for t in link.iter(W.t))
        for run in link.iter(W.r):
            rpr = run.find(W.rPr)
            if rpr is None:
                continue
            for tag, vals in ((W.rStyle, ("Hyperlink",)), (W.color, ("0563C1", "0000FF")),
                              (W.u, ("single",))):
                for found in rpr.findall(tag):
                    if (found.get(W.val) or "") in vals:
                        rpr.remove(found)
        for child in list(link):
            link.addprevious(child)
        _remove(link)
        self._touch(el)
        self._record(idx, "remove_hyperlink", bid, text, f"{text} (no longer a link)")

    def _set_hyperlink_url(self, idx: int, op: SetHyperlinkUrl) -> None:
        bid, el, link = self._find_link(op)
        link.set(R_ID, self.pkg.add_relationship(HYPERLINK_REL, op.url, external=True))
        link.attrib.pop(qn("w:anchor"), None)
        self._touch(el)
        text = "".join(t.text or "" for t in link.iter(W.t))
        self._record(idx, "set_hyperlink_url", bid, text, f"{text} → {op.url}")

    # ------------------------------------------------------- headers/footers
    def _create_header_footer(self, idx: int, op: CreateHeaderFooter) -> None:
        ref_tag = qn("w:headerReference") if op.kind == "header" else qn("w:footerReference")
        sects = list(self.pkg.body.iter(W.sectPr))
        lacking = [s for s in sects if not any(
            r.tag == ref_tag and (r.get(W.type) or "default") == "default" for r in s)]
        if not lacking:
            have = ", ".join(h.label for h in self.pkg.hf_parts if h.kind == op.kind)
            raise EditError(f"The document already has a {op.kind} ({have}); edit its "
                            f"paragraphs ({have}.p0, ...) instead.")
        text = _check_inline_text(op.text, "text") if op.text else ""
        if not text and not op.page_numbers:
            raise EditError("Give the header/footer some text or page_numbers=true.")
        style = op.kind.capitalize() if op.kind.capitalize() in self.pkg.paragraph_styles \
            else None
        root = build_header_footer(op.kind, text, op.page_numbers, op.align, style)
        name = self.pkg.new_part_name(op.kind)
        self.pkg.add_part(name, root, HEADER_CT if op.kind == "header" else FOOTER_CT)
        rid = self.pkg.add_relationship(HEADER_REL if op.kind == "header" else FOOTER_REL,
                                        name.rsplit("/", 1)[-1])
        for sect in lacking:
            ref = etree.Element(ref_tag)
            ref.set(W.type, "default")
            ref.set(R_ID, rid)
            refs = (qn("w:headerReference"),) if op.kind == "header" else \
                (qn("w:headerReference"), qn("w:footerReference"))
            at = 0
            while at < len(sect) and sect[at].tag in refs:
                at += 1
            sect.insert(at, ref)
        label = f"{'hdr' if op.kind == 'header' else 'ftr'}{len(self.pkg.hf_parts) + 1}"
        self.pkg.hf_parts.append(HeaderFooterPart(label, op.kind, name, root, ["new"],
                                                  b"", created=True))
        self._record(idx, "create_header_footer", op.kind, None,
                     (text + (" [page number]" if op.page_numbers else "")).strip())


def apply_plan(pkg: DocxPackage, plan: EditPlan) -> ApplyResult:
    """Apply ``plan`` to ``pkg`` in place (callers pass a copy)."""
    return DocumentEditor(pkg).apply(plan)
