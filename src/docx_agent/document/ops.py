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
from pydantic import BaseModel, ConfigDict, Field

from .model import (
    Block,
    DocumentIndex,
    ParagraphView,
    Piece,
    _walk_container,
    build_index,
    paragraph_view,
)
from .ns import XML_SPACE, W, qn
from .package import DocxPackage

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
        description="Exact text to delete. Include one adjacent space so no double space is left.",
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


class FormatText(_Op):
    """Change bold/italic/underline of an exact piece of text."""

    op: Literal["format_text"]
    block_id: str | None = Field(description="Paragraph id. Null = whole document.")
    find: str = Field(min_length=1)
    bold: bool | None = Field(default=None, description="true/false to set, null to leave as is.")
    italic: bool | None = None
    underline: bool | None = None
    occurrence: Occurrence = Field(default=None, description=_OCC_DESC)


EditOp = Annotated[
    ReplaceText | DeleteText | InsertText | InsertParagraph | DeleteParagraph | FormatText,
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
        self._new_counter = 0
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
            raise EditError(f"There is no block with id {block_id!r}.")
        if block.kind not in kinds:
            raise EditError(f"{block_id} is a {block.kind}, expected a {' or '.join(kinds)}.")
        if not block.editable:
            raise EditError(f"{block_id} is read-only ({block.readonly_reason}).")
        return block

    def _current_paragraphs(self) -> list[tuple[str, etree._Element]]:
        blocks: list[Block] = []
        _walk_container(self.pkg.body, "", blocks, 0, None, {"p": 0, "t": 0})
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
            raise EditError(f"Text {needle!r} was not found in {where}.{_suggest(texts, needle)}")
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
        for idx, op in enumerate(plan.operations):
            try:
                self._apply_one(idx, op)
            except EditError as exc:
                exc.op_index = idx
                raise
        return self.result

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
                    raise EditError(
                        f"Deleting {op.find!r} in {bid}: {problem}. Include exactly one "
                        "adjacent space in `find`."
                    )
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
            self._record(idx, "insert_text", op.block_id, before, paragraph_view(el).text)
        elif isinstance(op, InsertParagraph):
            self._insert_paragraph(idx, op)
        elif isinstance(op, DeleteParagraph):
            self._delete_paragraph(idx, op)
        elif isinstance(op, FormatText):
            self._format_text(idx, op)
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
            self._new_counter += 1
            self._ids[p] = f"new{self._new_counter}"
            self._record(idx, "insert_paragraph", self._ids[p], None, paragraph_view(p).text)
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

    def _make_paragraph(self, template: etree._Element, text: str) -> etree._Element:
        p = etree.Element(W.p)
        ppr = template.find(W.pPr)
        if ppr is not None:
            p.append(_strip_revision_markup(copy.deepcopy(ppr)))
        run = etree.SubElement(p, W.r)
        rpr = self._dominant_rpr(template)
        if rpr is not None:
            run.append(rpr)
        run.append(_new_t(text))
        return p

    # ------------------------------------------------------ delete paragraph
    def _delete_paragraph(self, idx: int, op: DeleteParagraph) -> None:
        block = self._block(op.block_id)
        el = block.element
        view = paragraph_view(el)
        blockers = sorted({pc.label or "protected" for pc in view.pieces
                           if pc.kind == "protected" and pc.label not in ("TAB", "BR", "NBHYPHEN")})
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
        props = {k: v for k, v in (("bold", op.bold), ("italic", op.italic),
                                   ("underline", op.underline)) if v is not None}
        if not props:
            raise EditError("format_text needs at least one of bold/italic/underline.")
        label = f"{op.find} ({', '.join(f'{k}={v}' for k, v in props.items())})"
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
                if "bold" in props:
                    _set_rpr_prop(run, W.b, None if props["bold"] else "0")
                if "italic" in props:
                    _set_rpr_prop(run, W.i, None if props["italic"] else "0")
                if "underline" in props:
                    _set_rpr_prop(run, W.u, "single" if props["underline"] else "none")
            if paragraph_view(el).text != text_before:  # pragma: no cover - defensive
                raise EditError("internal error: formatting changed the text")
            self._record(idx, "format_text", bid, op.find, label)


def apply_plan(pkg: DocxPackage, plan: EditPlan) -> ApplyResult:
    """Apply ``plan`` to ``pkg`` in place (callers pass a copy)."""
    return DocumentEditor(pkg).apply(plan)
