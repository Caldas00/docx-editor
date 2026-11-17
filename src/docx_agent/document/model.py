"""A text-addressable view over WordprocessingML.

The agent never sees XML. It sees *blocks* (paragraphs and tables) with stable
ids, and each paragraph is exposed as a plain string - its *view text*.

Internally a paragraph's view text is the concatenation of *pieces*. Each piece
maps a span of the view text back to the XML node that produced it:

* ``text`` pieces come from ``<w:t>`` elements in ordinary runs (also runs inside
  hyperlinks / smart tags). These are the only pieces whose characters can be
  rewritten.
* ``protected`` pieces are everything else that is visible: tabs, line breaks,
  images, symbols, footnote references, field results, tracked insertions,
  content controls, equations. Edits that overlap a protected piece are refused
  (a few simple ones - tabs and soft line breaks - may be *removed* by a
  deletion that fully covers them).

Hidden content (field instructions, tracked deletions, bookmarks, comment range
markers, ``rPr``...) produces no pieces and is never touched.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Literal

from lxml import etree

from .ns import MC, M, W
from .package import DocxPackage

PieceKind = Literal["text", "protected"]

# Protected elements that a deletion/replacement may remove when it covers them
# completely (they carry no state beyond their own position).
REMOVABLE_LABELS = frozenset({"TAB", "BR", "NBHYPHEN"})

IMAGE = "⟦IMAGE⟧"


@dataclass
class Piece:
    start: int
    text: str
    kind: PieceKind
    run: etree._Element | None
    node: etree._Element  # the run child (w:t, w:tab, w:drawing...) or container
    container: etree._Element  # parent element of the run (w:p, w:hyperlink, ...)
    label: str | None = None  # for protected pieces: TAB, BR, IMAGE, FIELD, ...

    @property
    def end(self) -> int:
        return self.start + len(self.text)

    @property
    def editable(self) -> bool:
        return self.kind == "text"

    @property
    def removable(self) -> bool:
        return self.kind == "protected" and self.label in REMOVABLE_LABELS


@dataclass
class ParagraphView:
    element: etree._Element
    pieces: list[Piece]

    @property
    def text(self) -> str:
        return "".join(p.text for p in self.pieces)

    def pieces_in(self, start: int, end: int) -> list[Piece]:
        """Pieces overlapping the half-open range [start, end)."""
        return [p for p in self.pieces if p.start < end and p.end > start and p.text]

    def piece_at(self, offset: int) -> Piece | None:
        for p in self.pieces:
            if p.start <= offset < p.end:
                return p
        return None


class _FieldTracker:
    """Tracks complex-field state (begin / separate / end) while walking runs."""

    def __init__(self) -> None:
        self.stack: list[str] = []

    def feed(self, fld_char: etree._Element) -> None:
        kind = fld_char.get(W.fldCharType)
        if kind == "begin":
            self.stack.append("instr")
        elif kind == "separate" and self.stack:
            self.stack[-1] = "result"
        elif kind == "end" and self.stack:
            self.stack.pop()

    @property
    def in_instruction(self) -> bool:
        return bool(self.stack) and self.stack[-1] == "instr"

    @property
    def in_field(self) -> bool:
        return bool(self.stack)


_EDITABLE_CONTAINERS = {W.hyperlink, W.smartTag, W.customXml, W.dir, W.bdo}


def paragraph_view(p: etree._Element) -> ParagraphView:
    pieces: list[Piece] = []
    pos = 0
    fields = _FieldTracker()

    def add(text: str, kind: PieceKind, run, node, container, label=None) -> None:
        nonlocal pos
        if not text:
            return
        pieces.append(Piece(pos, text, kind, run, node, container, label))
        pos += len(text)

    def handle_run(run: etree._Element, container: etree._Element, ctx: str | None) -> None:
        for child in run:
            tag = child.tag
            if tag == W.rPr:
                continue
            if tag == W.fldChar:
                fields.feed(child)
                continue
            if fields.in_instruction:
                continue  # field code (e.g. "PAGE \* MERGEFORMAT") is not visible text
            prot = ctx or ("FIELD" if fields.in_field else None)
            if tag == W.t:
                text = child.text or ""
                if prot:
                    add(text, "protected", run, child, container, prot)
                else:
                    add(text, "text", run, child, container)
            elif tag in (W.tab, W.ptab):
                add("\t", "protected", run, child, container, prot or "TAB")
            elif tag in (W.br, W.cr):
                br_type = child.get(W.type)
                if br_type in (None, "textWrapping") or tag == W.cr:
                    add("\n", "protected", run, child, container, prot or "BR")
                else:
                    add("⟦PAGE BREAK⟧", "protected", run, child, container, "PAGE_BREAK")
            elif tag == W.noBreakHyphen:
                add("-", "protected", run, child, container, prot or "NBHYPHEN")
            elif tag in (W.drawing, W.pict):
                add(IMAGE, "protected", run, child, container, "IMAGE")
            elif tag == W.object:
                add("⟦OBJECT⟧", "protected", run, child, container, "OBJECT")
            elif tag == MC.AlternateContent:
                is_img = child.find(".//" + W.drawing) is not None
                add(IMAGE if is_img else "⟦OBJECT⟧", "protected", run, child, container,
                    "IMAGE" if is_img else "OBJECT")
            elif tag == W.sym:
                add("⟦SYMBOL⟧", "protected", run, child, container, "SYMBOL")
            elif tag == W.footnoteReference:
                add("⟦FOOTNOTE⟧", "protected", run, child, container, "FOOTNOTE")
            elif tag == W.endnoteReference:
                add("⟦ENDNOTE⟧", "protected", run, child, container, "ENDNOTE")
            elif tag == W.instrText or tag == W.softHyphen or tag == W.lastRenderedPageBreak:
                continue
            else:
                # Unknown run content (ruby, embedded objects, ...): keep it opaque.
                text = "".join(child.itertext())
                if text:
                    add(text, "protected", run, child, container, "OBJECT")

    def walk(container: etree._Element, ctx: str | None) -> None:
        for child in container:
            tag = child.tag
            if tag == W.pPr:
                continue
            if tag == W.r:
                handle_run(child, container, ctx)
            elif tag in _EDITABLE_CONTAINERS:
                walk(child, ctx)
            elif tag in (W.ins, W.moveTo):
                walk(child, ctx or "TRACKED_CHANGE")
            elif tag in (W.del_, W.moveFrom):
                continue  # deleted text is not part of the visible document
            elif tag == W.sdt:
                content = child.find(W.sdtContent)
                if content is not None:
                    walk(content, ctx or "CONTENT_CONTROL")
            elif tag == W.fldSimple:
                walk(child, ctx or "FIELD")
            elif tag in (M.oMath, M.oMathPara):
                add("⟦EQUATION⟧", "protected", None, child, container, "EQUATION")
            # bookmarks, comment ranges, proofErr, permStart... carry no text

    walk(p, None)
    return ParagraphView(p, pieces)


# --------------------------------------------------------------------- blocks
BlockKind = Literal["paragraph", "table"]


@dataclass
class Block:
    id: str
    kind: BlockKind
    element: etree._Element
    editable: bool = True  # False for paragraphs inside block-level content controls
    depth: int = 0  # nesting depth (0 = body, 1 = inside a table cell, ...)
    rows: int = 0
    cols: int = 0
    readonly_reason: str | None = None


@dataclass
class DocumentIndex:
    blocks: list[Block] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._by_id = {b.id: b for b in self.blocks}
        self._by_element = {id(b.element): b for b in self.blocks}

    def get(self, block_id: str) -> Block | None:
        return self._by_id.get(block_id)

    def id_of(self, element: etree._Element) -> str | None:
        b = self._by_element.get(id(element))
        return b.id if b else None

    def paragraphs(self) -> Iterator[Block]:
        return (b for b in self.blocks if b.kind == "paragraph")


def _walk_container(
    container: etree._Element,
    prefix: str,
    out: list[Block],
    depth: int,
    readonly_reason: str | None,
    counters: dict[str, int],
) -> None:
    """Assign ids to paragraphs/tables inside ``container`` in document order."""
    for child in container:
        tag = child.tag
        if tag == W.p:
            pid = f"{prefix}p{counters['p']}"
            counters["p"] += 1
            out.append(
                Block(pid, "paragraph", child, editable=readonly_reason is None,
                      depth=depth, readonly_reason=readonly_reason)
            )
        elif tag == W.tbl:
            tid = f"{prefix}t{counters['t']}"
            counters["t"] += 1
            rows = child.findall(W.tr)
            ncols = max((len(r.findall(W.tc)) for r in rows), default=0)
            out.append(Block(tid, "table", child, editable=readonly_reason is None,
                             depth=depth, rows=len(rows), cols=ncols,
                             readonly_reason=readonly_reason))
            for ri, row in enumerate(rows):
                for ci, cell in enumerate(row.findall(W.tc)):
                    _walk_container(cell, f"{tid}.r{ri}.c{ci}.", out, depth + 1,
                                    readonly_reason, {"p": 0, "t": 0})
        elif tag == W.sdt:
            content = child.find(W.sdtContent)
            if content is not None:
                _walk_container(content, prefix, out, depth, "inside a content control", counters)
        elif tag == W.customXml:
            _walk_container(child, prefix, out, depth, readonly_reason, counters)


def build_index(pkg: DocxPackage) -> DocumentIndex:
    blocks: list[Block] = []
    _walk_container(pkg.body, "", blocks, 0, None, {"p": 0, "t": 0})
    return DocumentIndex(blocks)


# ------------------------------------------------------------- descriptions
def paragraph_style(pkg: DocxPackage, p: etree._Element) -> str:
    ppr = p.find(W.pPr)
    sid = None
    if ppr is not None:
        ps = ppr.find(W.pStyle)
        if ps is not None:
            sid = ps.get(W.val)
    sid = sid or pkg.default_paragraph_style
    if sid is None:
        return "Normal"
    name = pkg.style_names.get(sid, sid)
    # Built-in style names are stored lower-case ("heading 1"); show them as Word does.
    return name[:1].upper() + name[1:]


def list_level(p: etree._Element) -> int | None:
    ppr = p.find(W.pPr)
    if ppr is None:
        return None
    num = ppr.find(W.numPr)
    if num is None:
        return None
    lvl = num.find(W.ilvl)
    try:
        return int(lvl.get(W.val, "0")) if lvl is not None else 0
    except ValueError:
        return 0


def _on(el: etree._Element | None) -> bool:
    if el is None:
        return False
    return el.get(W.val, "true") not in ("0", "false", "off", "none")


def run_flags(run: etree._Element | None) -> tuple[bool, bool, bool]:
    """Directly applied (bold, italic, underline) on a run."""
    if run is None:
        return (False, False, False)
    rpr = run.find(W.rPr)
    if rpr is None:
        return (False, False, False)
    return (_on(rpr.find(W.b)), _on(rpr.find(W.i)), _on(rpr.find(W.u)))


def formatting_notes(view: ParagraphView) -> list[str]:
    """Human readable notes about mixed inline formatting, e.g. bold="Risk:"."""
    spans: list[tuple[str, str]] = []
    links: list[str] = []
    cur_link: etree._Element | None = None
    for pc in view.pieces:
        if pc.container.tag == W.hyperlink:
            if pc.container is cur_link:
                links[-1] += pc.text
            else:
                links.append(pc.text)
                cur_link = pc.container
        else:
            cur_link = None
    link_notes = [f"link={json.dumps(t, ensure_ascii=False)}" for t in links if t.strip()]
    texts = [p for p in view.pieces if p.kind == "text" and p.container.tag != W.hyperlink]
    if not texts:
        return link_notes
    flags = [run_flags(p.run) for p in texts]
    if len(set(flags)) <= 1:
        f = flags[0]
        whole = [n for n, on in zip(("bold", "italic", "underline"), f) if on]
        return ([f"all {', '.join(whole)}"] if whole else []) + link_notes
    names = ("bold", "italic", "underline")
    for idx, name in enumerate(names):
        cur = ""
        for piece, f in zip(texts, flags):
            if f[idx]:
                cur += piece.text
            elif cur:
                spans.append((name, cur))
                cur = ""
        if cur:
            spans.append((name, cur))
    return [f"{name}={json.dumps(text, ensure_ascii=False)}" for name, text in spans
            if text.strip()] + link_notes


def protected_notes(view: ParagraphView) -> list[str]:
    labels = []
    for p in view.pieces:
        if p.kind == "protected" and p.label not in ("TAB", "BR", "NBHYPHEN", "IMAGE"):
            labels.append(f"{p.label.lower() if p.label else 'protected'}={json.dumps(p.text, ensure_ascii=False)}")
    return labels


def describe_block(pkg: DocxPackage, block: Block, max_text: int | None = None) -> str:
    indent = "  " * block.depth
    if block.kind == "table":
        return f"{indent}[{block.id}] TABLE {block.rows} rows x {block.cols} cols"
    view = paragraph_view(block.element)
    text = view.text
    if max_text is not None and len(text) > max_text:
        text = text[:max_text] + "…"
    style = paragraph_style(pkg, block.element)
    meta = style
    lvl = list_level(block.element)
    if lvl is not None:
        meta += f", list level {lvl}"
    line = f"{indent}[{block.id}] ({meta}) {json.dumps(text, ensure_ascii=False)}"
    notes = formatting_notes(view) + protected_notes(view)
    if not block.editable:
        notes.append(f"READ-ONLY: {block.readonly_reason}")
    if notes:
        line += "  {" + "; ".join(notes) + "}"
    return line


def render_outline(pkg: DocxPackage, index: DocumentIndex | None = None,
                   max_chars: int | None = None) -> tuple[str, bool]:
    """Render the document for the LLM. Returns (outline, truncated)."""
    index = index or build_index(pkg)
    lines: list[str] = []
    used = 0
    for block in index.blocks:
        line = describe_block(pkg, block)
        if max_chars is not None and used + len(line) > max_chars:
            lines.append(f"... (outline truncated - {len(index.blocks) - len(lines)} more blocks; "
                         "use the search_document / read_blocks tools)")
            return "\n".join(lines), True
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines), False
