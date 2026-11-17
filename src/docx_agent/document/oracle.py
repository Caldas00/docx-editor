"""Independent replay of an EditPlan on plain text.

The XML editor (``ops.py``) and this oracle implement the same operation
semantics in two unrelated ways: the editor performs run surgery on XML, the
oracle edits Python strings. The verifier compares the edited document against
the oracle's prediction, so a bug in the run surgery (lost text, duplicated
text, text moved into the wrong run) shows up as a mismatch instead of a
silently corrupted document.

Besides the expected text, the oracle tracks the *origin* of every character
(its index in the original paragraph, or ``None`` if it was inserted) and any
formatting the plan explicitly forces on it. That lets the verifier check
formatting character by character.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from lxml import etree

from .model import build_index, paragraph_view
from .ns import W
from .ops import (
    DeleteParagraph,
    DeleteText,
    EditPlan,
    FormatText,
    InsertParagraph,
    InsertText,
    ReplaceText,
    find_all,
)
from .package import DocxPackage

ItemKind = Literal["p", "tbl", "tbl_end", "sectPr", "other"]


class OracleError(Exception):
    """The plan cannot be replayed - the editor and oracle disagree."""


@dataclass
class StreamItem:
    kind: ItemKind
    element: etree._Element


def document_stream(pkg: DocxPackage) -> list[StreamItem]:
    """Flatten the body into a sequence covering every body/cell child."""
    out: list[StreamItem] = []

    def walk(container: etree._Element, in_cell: bool) -> None:
        for child in container:
            tag = child.tag
            if in_cell and tag == W.tcPr:
                continue
            if tag == W.p:
                out.append(StreamItem("p", child))
            elif tag == W.tbl:
                out.append(StreamItem("tbl", child))
                for tr in child.findall(W.tr):
                    for tc in tr.findall(W.tc):
                        walk(tc, True)
                out.append(StreamItem("tbl_end", child))
            elif tag == W.sectPr:
                out.append(StreamItem("sectPr", child))
            else:
                out.append(StreamItem("other", child))

    walk(pkg.body, False)
    return out


@dataclass
class OChar:
    ch: str
    origin: int | None
    forced: dict[str, bool] = field(default_factory=dict)


@dataclass
class Expected:
    kind: ItemKind
    before: StreamItem | None  # None for inserted paragraphs
    block_id: str | None = None
    editable: bool = True
    chars: list[OChar] | None = None
    modified: bool = False
    template_id: str | None = None

    @property
    def text(self) -> str:
        return "".join(c.ch for c in self.chars or [])


class Oracle:
    def __init__(self, pkg: DocxPackage) -> None:
        index = build_index(pkg)
        ids = {b.element: b for b in index.blocks}
        self.entries: list[Expected] = []
        for item in document_stream(pkg):
            block = ids.get(item.element)
            if item.kind == "p":
                text = paragraph_view(item.element).text
                self.entries.append(Expected(
                    "p", item, block.id if block else None,
                    editable=bool(block and block.editable),
                    chars=[OChar(c, i) for i, c in enumerate(text)],
                ))
            else:
                bid = block.id if (block and item.kind == "tbl") else None
                self.entries.append(Expected(item.kind, item, bid))
        self.deleted: set[str] = set()

    # ---------------------------------------------------------------- lookup
    def _entry(self, block_id: str, kinds=("p",)) -> Expected:
        for e in self.entries:
            if e.block_id == block_id and e.kind in kinds:
                return e
        raise OracleError(f"oracle: block {block_id} not found")

    def _scope(self, block_id: str | None) -> list[Expected]:
        if block_id is not None:
            return [self._entry(block_id)]
        return [e for e in self.entries if e.kind == "p" and e.editable]

    def _matches(self, block_id, needle, occurrence) -> list[tuple[Expected, int]]:
        found = [(e, pos) for e in self._scope(block_id) for pos in find_all(e.text, needle)]
        if not found:
            raise OracleError(f"oracle: {needle!r} not found")
        if occurrence is None:
            if len(found) != 1:
                raise OracleError(f"oracle: {needle!r} is ambiguous")
            return found
        if occurrence == "all":
            return found
        return [found[occurrence - 1]]

    @staticmethod
    def _last_first(matches):
        return sorted(matches, key=lambda m: -m[1])

    # ---------------------------------------------------------------- replay
    def run(self, plan: EditPlan) -> list[Expected]:
        for op in plan.operations:
            if isinstance(op, ReplaceText):
                for e, pos in self._last_first(self._matches(op.block_id, op.find, op.occurrence)):
                    e.chars[pos:pos + len(op.find)] = [OChar(c, None) for c in op.replace_with]
                    e.modified = True
            elif isinstance(op, DeleteText):
                for e, pos in self._last_first(self._matches(op.block_id, op.find, op.occurrence)):
                    del e.chars[pos:pos + len(op.find)]
                    e.modified = True
            elif isinstance(op, InsertText):
                e = self._entry(op.block_id)
                if op.position == "start":
                    pos = 0
                elif op.position == "end":
                    pos = len(e.chars)
                else:
                    (_, at), = self._matches(op.block_id, op.anchor, op.occurrence)[:1]
                    pos = at if op.position == "before" else at + len(op.anchor)
                e.chars[pos:pos] = [OChar(c, None) for c in op.text]
                e.modified = True
            elif isinstance(op, InsertParagraph):
                target = self._entry(op.target_id, ("p", "tbl"))
                i = self.entries.index(target)
                if op.position == "after" and target.kind == "tbl":
                    i = next(j for j in range(i + 1, len(self.entries))
                             if self.entries[j].kind == "tbl_end"
                             and self.entries[j].before.element is target.before.element)
                if op.position == "after":
                    i += 1
                new = [Expected("p", None, None, True, [OChar(c, None) for c in line],
                                True, op.format_like)
                       for line in op.text.replace("\r\n", "\n").split("\n")]
                self.entries[i:i] = new
            elif isinstance(op, DeleteParagraph):
                e = self._entry(op.block_id)
                self.entries.remove(e)
                self.deleted.add(op.block_id)
            elif isinstance(op, FormatText):
                props = {k: v for k, v in (("bold", op.bold), ("italic", op.italic),
                                           ("underline", op.underline)) if v is not None}
                for e, pos in self._matches(op.block_id, op.find, op.occurrence):
                    for c in e.chars[pos:pos + len(op.find)]:
                        c.forced.update(props)
                    e.modified = True
            else:  # pragma: no cover
                raise OracleError(f"oracle: unknown op {op!r}")
        return self.entries


def expected_document(pkg: DocxPackage, plan: EditPlan) -> tuple[list[Expected], set[str]]:
    oracle = Oracle(pkg)
    entries = oracle.run(plan)
    return entries, oracle.deleted
