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
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Literal

from lxml import etree

from .ns import MC, M, W, qn
from .package import DocxPackage

PieceKind = Literal["text", "protected"]

# Protected elements that a deletion/replacement may remove when it covers them
# completely (they carry no state beyond their own position).
REMOVABLE_LABELS = frozenset({"TAB", "BR", "NBHYPHEN"})

IMAGE = "⟦IMAGE⟧"

_WP_DOCPR = qn("wp:docPr")
_WP_EXTENT = qn("wp:extent")
_PIC = qn("pic:pic")
_A_BLIP = qn("a:blip")
_V_IMAGEDATA = qn("v:imagedata")
_V_SHAPE = qn("v:shape")
_EMU_PER_PX = 9525


@dataclass(frozen=True)
class ImageInfo:
    """What the agent is told about a drawing: a stable reference and its size."""

    ref: str | None  # e.g. "18" (from wp:docPr/@id); None when the drawing has no id
    is_picture: bool  # a picture (deletable) vs. a shape/text box (always protected)
    name: str
    description: str
    width_px: int | None
    height_px: int | None

    @property
    def placeholder(self) -> str:
        kind = "IMAGE" if self.is_picture else "SHAPE"
        return f"⟦{kind}#{self.ref}⟧" if self.ref else f"⟦{kind}⟧"

    @property
    def label(self) -> str:
        return "IMAGE" if self.is_picture else "SHAPE"

    def describe(self) -> str:
        size = f" {self.width_px}x{self.height_px}px" if self.width_px and self.height_px else ""
        text = self.description or self.name
        what = "" if self.is_picture else " shape"
        return f"{self.placeholder}{what}{size}" + (f" {json.dumps(text, ensure_ascii=False)}"
                                                     if text else "")


def _pt_or_px(style: str, key: str) -> int | None:
    m = re.search(rf"{key}:\s*([\d.]+)(pt|px|in)?", style)
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2) or "px"
    return round(value * {"pt": 96 / 72, "px": 1, "in": 96}[unit])


def image_info(node: etree._Element) -> ImageInfo:
    """Describe a w:drawing, w:pict or mc:AlternateContent run child."""
    if node.tag == MC.AlternateContent:
        choice = node.find(qn("mc:Choice"))
        node = choice if choice is not None else node
    docpr = node.find(".//" + _WP_DOCPR)
    is_picture = any(node.find(".//" + t) is not None for t in (_PIC, _A_BLIP, _V_IMAGEDATA))
    width = height = None
    ext = node.find(".//" + _WP_EXTENT)
    if ext is not None and (ext.get("cx") or "").isdigit() and (ext.get("cy") or "").isdigit():
        width = round(int(ext.get("cx")) / _EMU_PER_PX)
        height = round(int(ext.get("cy")) / _EMU_PER_PX)
    ref = None
    name = descr = ""
    if docpr is not None:
        raw = docpr.get("id") or ""
        ref = re.sub(r"[^0-9A-Za-z_-]", "", raw) or None
        name, descr = docpr.get("name") or "", docpr.get("descr") or docpr.get("title") or ""
    else:
        shape = node.find(".//" + _V_SHAPE)
        if shape is not None:
            style = shape.get("style") or ""
            width, height = _pt_or_px(style, "width"), _pt_or_px(style, "height")
            raw = shape.get("id") or ""
            ref = re.sub(r"[^0-9A-Za-z_-]", "", raw) or None
            name = shape.get("alt") or ""
    return ImageInfo(ref, is_picture, name, descr, width, height)


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
                    if br_type == "column":  # moves the text to the next column, not page
                        add("⟦COLUMN BREAK⟧", "protected", run, child, container, "COLUMN_BREAK")
                    else:
                        add("⟦PAGE BREAK⟧", "protected", run, child, container, "PAGE_BREAK")
            elif tag == W.noBreakHyphen:
                add("-", "protected", run, child, container, prot or "NBHYPHEN")
            elif tag in (W.drawing, W.pict) or (
                    tag == MC.AlternateContent
                    and child.find(".//" + W.drawing) is not None):
                info = image_info(child)
                add(info.placeholder, "protected", run, child, container,
                    prot or info.label)
            elif tag in (W.object, MC.AlternateContent):
                add("⟦OBJECT⟧", "protected", run, child, container, "OBJECT")
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
BlockKind = Literal["paragraph", "table", "part"]


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
    host: str | None = None  # for a text box part: the id of the paragraph that holds it


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
            # The verifier treats block-level custom XML as one opaque unit, so the
            # paragraphs inside are listed but not editable.
            _walk_container(child, prefix, out, depth, "inside a custom XML element", counters)


TXBX = qn("w:txbxContent")
_WPS_CNVPR = "{http://schemas.microsoft.com/office/word/2010/wordprocessingShape}cNvPr"
_WP_DOCPR = qn("wp:docPr")


def text_boxes(body: etree._Element) -> list[tuple[str, etree._Element]]:
    """Editable text boxes in the body: ("tb1", w:txbxContent) in document order.

    The VML copy Word keeps for old readers (inside mc:Fallback) is not listed: it is kept
    in sync with the DrawingML copy. Text boxes inside content controls, custom XML or
    another text box stay read-only, like the text around them.
    """
    out: list[tuple[str, etree._Element]] = []
    for box in body.iter(TXBX):
        if any(a.tag in (MC.Fallback, W.sdt, W.customXml, TXBX) for a in box.iterancestors()):
            continue
        out.append((f"tb{len(out) + 1}", box))
    return out


def text_box_key(box: etree._Element) -> tuple[str, str, int]:
    """Identifies a text box across versions of the document, whatever moved around it:
    the drawing's id, the shape's id inside a group, and its place in that drawing."""
    drawing = next((a for a in box.iterancestors() if a.tag == W.drawing), None)
    docpr = drawing.find(".//" + _WP_DOCPR) if drawing is not None else None
    shape = next((a for a in box.iterancestors()
                  if a.tag.endswith("}wsp") and a.find(_WPS_CNVPR) is not None), None)
    shape_id = shape.find(_WPS_CNVPR).get("id", "") if shape is not None else ""
    boxes = [b for b in drawing.iter(TXBX)] if drawing is not None else [box]
    return (docpr.get("id", "") if docpr is not None else "", shape_id,
            next((i for i, b in enumerate(boxes) if b is box), 0))


def text_box_fallback(box: etree._Element) -> etree._Element | None:
    """The VML copy of a DrawingML text box (same place in mc:Fallback), if there is one."""
    alt = next((a for a in box.iterancestors() if a.tag == MC.AlternateContent), None)
    if alt is None:
        return None
    choice, fallback = alt.find(MC.Choice), alt.find(MC.Fallback)
    if choice is None or fallback is None:
        return None
    mine = list(choice.iter(TXBX))
    theirs = list(fallback.iter(TXBX))
    if len(mine) != len(theirs):
        return None
    k = next((i for i, b in enumerate(mine) if b is box), None)
    return theirs[k] if k is not None else None


def build_index(pkg: DocxPackage) -> DocumentIndex:
    """Body blocks first (p0, t0, ...), then each header/footer part (hdr1.p0, ftr1.t0...),
    then each text box in the body (tb1.p0, ...)."""
    blocks: list[Block] = []
    _walk_container(pkg.body, "", blocks, 0, None, {"p": 0, "t": 0})
    for hf in pkg.hf_parts:
        blocks.append(Block(hf.label, "part", hf.root, depth=0))
        _walk_container(hf.root, f"{hf.label}.", blocks, 1, None, {"p": 0, "t": 0})
    hosts = {id(b.element): b.id for b in blocks if b.kind == "paragraph"}
    for label, box in text_boxes(pkg.body):
        host = next((hosts[id(a)] for a in box.iterancestors() if id(a) in hosts), None)
        blocks.append(Block(label, "part", box, depth=0, host=host))
        _walk_container(box, f"{label}.", blocks, 1, None, {"p": 0, "t": 0})
    return DocumentIndex(blocks)


def part_roots(pkg: DocxPackage) -> list[etree._Element]:
    """Containers the agent edits: the body, then every header/footer part."""
    return [pkg.body] + [hf.root for hf in pkg.hf_parts]


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
    props = run_props(run)
    return (props["bold"], props["italic"], props["underline"])


FORMAT_PROPS = ("bold", "italic", "underline", "strike", "color", "highlight", "font_size")


def run_props(run: etree._Element | None) -> dict:
    """Directly applied run formatting, normalised:
    bold/italic/underline/strike -> bool, color -> "RRGGBB" | None,
    highlight -> Word highlight name | None, font_size -> points | None."""
    out = {"bold": False, "italic": False, "underline": False, "strike": False,
           "color": None, "highlight": None, "font_size": None}
    rpr = run.find(W.rPr) if run is not None else None
    if rpr is None:
        return out
    out["bold"] = _on(rpr.find(W.b))
    out["italic"] = _on(rpr.find(W.i))
    u = rpr.find(W.u)
    out["underline"] = u is not None and u.get(W.val, "single") != "none"
    out["strike"] = _on(rpr.find(W.strike))
    color = rpr.find(W.color)
    val = (color.get(W.val) or "") if color is not None else ""
    if re.fullmatch(r"[0-9A-Fa-f]{6}", val):
        out["color"] = val.upper()
    hl = rpr.find(W.highlight)
    if hl is not None and hl.get(W.val) not in (None, "none"):
        out["highlight"] = hl.get(W.val)
    sz = rpr.find(W.sz)
    if sz is not None and (sz.get(W.val) or "").isdigit():
        out["font_size"] = int(sz.get(W.val)) / 2
    return out


def _note_key(prop: str, value) -> str | None:
    """Label of a formatting span in the outline, or None if not worth showing."""
    if value in (None, False):
        return None
    if prop == "color":
        return None if value in ("000000",) else f"color #{value}"
    if prop == "highlight":
        return f"highlight {value}"
    if prop == "font_size":
        return None  # sizes are noise in the outline; available through run formatting
    return prop


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
    texts = [p for p in view.pieces if p.kind == "text"]
    if not "".join(p.text for p in texts).strip():
        return link_notes
    props = [run_props(p.run) for p in texts]
    whole: list[str] = []
    for prop in FORMAT_PROPS:
        keys = [_note_key(prop, pr[prop]) for pr in props]
        visible = [(k, pc) for k, pc in zip(keys, texts) if pc.text.strip()]
        if visible and all(k == visible[0][0] for k, _ in visible) and visible[0][0]:
            # the whole paragraph has it (hyperlink underline/colour excluded from "all")
            whole.append(visible[0][0])
            continue
        cur_key, cur = None, ""
        for key, pc in zip(keys, texts):
            if pc.container.tag == W.hyperlink and prop in ("underline", "color"):
                key = None  # link styling is reported as link=
            if key is not None and key == cur_key:
                cur += pc.text
                continue
            if cur_key and cur.strip():
                spans.append((cur_key, cur))
            cur_key, cur = key, pc.text if key else ""
        if cur_key and cur.strip():
            spans.append((cur_key, cur))
    notes = [f"all {', '.join(whole)}"] if whole else []
    notes += [f"{name}={json.dumps(text, ensure_ascii=False)}" for name, text in spans]
    return notes + link_notes


def protected_notes(view: ParagraphView) -> list[str]:
    labels = []
    images = []
    for p in view.pieces:
        if p.kind != "protected":
            continue
        if p.label in ("IMAGE", "SHAPE"):
            images.append(image_info(p.node).describe())
        elif p.label not in ("TAB", "BR", "NBHYPHEN"):
            labels.append(f"{p.label.lower() if p.label else 'protected'}="
                          f"{json.dumps(p.text, ensure_ascii=False)}")
    if images:
        labels.append("images: " + ", ".join(images))
    return labels


def paragraph_shading(pkg: DocxPackage, p: etree._Element) -> str | None:
    """The paragraph's background colour (direct or from its style chain), as RRGGBB."""
    def fill_of(ppr: etree._Element | None) -> str | None | bool:
        shd = ppr.find(qn("w:shd")) if ppr is not None else None
        if shd is None:
            return False  # not set here
        fill = (shd.get(qn("w:fill")) or "").upper()
        return fill if re.fullmatch(r"[0-9A-F]{6}", fill) and shd.get(W.val) != "nil" else None
    direct = fill_of(p.find(W.pPr))
    if direct is not False:
        return direct or None
    ps = p.find(f"{W.pPr}/{qn('w:pStyle')}")
    sid = ps.get(W.val) if ps is not None else None
    seen: set[str] = set()
    styles = pkg.style_elements
    while sid and sid not in seen and sid in styles:
        seen.add(sid)
        found = fill_of(styles[sid].find(W.pPr))
        if found is not False:
            return found or None
        based = styles[sid].find(qn("w:basedOn"))
        sid = based.get(W.val) if based is not None else None
    return None


def describe_block(pkg: DocxPackage, block: Block, max_text: int | None = None) -> str:
    indent = "  " * block.depth
    if block.kind == "part":
        if block.element.tag == TXBX:
            where = f" in {block.host}" if block.host else ""
            return (f"[{block.id}] TEXT BOX{where} (a shape's text; edit it like any "
                    "paragraph) - its paragraphs follow")
        hf = next((h for h in pkg.hf_parts if h.root is block.element), None)
        kind = hf.kind.upper() if hf else "PART"
        uses = "; ".join(hf.uses) if hf else ""
        return f"[{block.id}] {kind} ({uses}) - its paragraphs follow"
    if block.kind == "table":
        headers = [i for i, tr in enumerate(block.element.findall(W.tr))
                   if tr.find(qn("w:trPr")) is not None
                   and tr.find(qn("w:trPr")).find(qn("w:tblHeader")) is not None]
        head = f"; header row(s): {', '.join(f'{block.id}.r{i}' for i in headers)}" \
            if headers else ""
        return (f"{indent}[{block.id}] TABLE {block.rows} rows x {block.cols} cols "
                f"(rows {block.id}.r0-{block.id}.r{max(block.rows - 1, 0)}{head})")
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
    fill = paragraph_shading(pkg, block.element)
    if fill:
        notes.insert(0, f"shading #{fill}")  # a coloured box behind the paragraph
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
