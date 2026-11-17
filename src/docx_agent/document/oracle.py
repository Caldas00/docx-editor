"""Independent replay of an EditPlan on plain text.

The XML editor (``ops.py``) and this oracle implement the same operation
semantics in two unrelated ways: the editor performs run surgery on XML, the
oracle edits Python strings and a flat list of blocks. The verifier compares the
edited document against the oracle's prediction, so a bug in the run surgery
(lost text, duplicated text, text moved into the wrong run, a row removed from
the wrong table) shows up as a mismatch instead of a silently corrupted document.

Besides the expected text, the oracle tracks the *origin* of every character
(its index in the original paragraph, or ``None`` if it was inserted) and any
formatting the plan explicitly forces on it, plus every original element the
plan removes (paragraphs, rows, tables, pictures) so element counts can be
checked exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from lxml import etree

from .model import Piece, build_index, paragraph_view, run_props
from .ns import W
from .ops import (
    _ROW_ID,
    DeleteImages,
    DeleteParagraph,
    DeleteTable,
    DeleteTableRows,
    DeleteText,
    EditPlan,
    FormatText,
    InsertParagraph,
    InsertTable,
    InsertTableRow,
    InsertText,
    ReplaceText,
    RestyleText,
    cell_template_paragraph,
    find_all,
    image_selected,
    normalise_image_refs,
    props_match,
)
from .package import DocxPackage

ItemKind = Literal["p", "tbl", "tr", "tc", "tbl_end", "sectPr", "other"]


class OracleError(Exception):
    """The plan cannot be replayed - the editor and oracle disagree."""


@dataclass
class StreamItem:
    kind: ItemKind
    element: etree._Element
    owner: etree._Element | None = None  # tr -> its table, tc -> its row


def document_stream(pkg: DocxPackage) -> list[StreamItem]:
    """Flatten the body into a sequence covering every body/table/cell child."""
    out: list[StreamItem] = []

    def walk(container: etree._Element, in_cell: bool) -> None:
        for child in container:
            tag = child.tag
            if in_cell and tag == W.tcPr:
                continue  # part of the cell's signature
            if tag == W.p:
                out.append(StreamItem("p", child))
            elif tag == W.tbl:
                out.append(StreamItem("tbl", child))
                for tr in child.findall(W.tr):
                    out.append(StreamItem("tr", tr, child))
                    for tc in tr.findall(W.tc):
                        out.append(StreamItem("tc", tc, tr))
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
    forced: dict = field(default_factory=dict)


@dataclass
class Expected:
    kind: ItemKind
    before: StreamItem | None  # None for inserted paragraphs/rows/cells
    block_id: str | None = None
    editable: bool = True
    chars: list[OChar] | None = None
    modified: bool = False
    template: etree._Element | None = None  # for new p / tr / tc: what it copies
    pieces: list[Piece] = field(default_factory=list)  # original piece of each char
    spec: dict = field(default_factory=dict)  # for parts of a new table (see insert_table)

    @property
    def text(self) -> str:
        return "".join(c.ch for c in self.chars or [])

    @property
    def element(self) -> etree._Element | None:
        return self.before.element if self.before else None


class Oracle:
    def __init__(self, pkg: DocxPackage) -> None:
        index = build_index(pkg)
        ids = {b.element: b for b in index.blocks}
        self.entries: list[Expected] = []
        self.removed: list[etree._Element] = []  # original elements the plan deletes
        self.added_tables = 0
        self._pid = {b.element: b.id for b in index.blocks if b.kind == "paragraph"}
        table_ids: dict[etree._Element, str] = {}
        row_numbers: dict[etree._Element, int] = {}
        for item in document_stream(pkg):
            block = ids.get(item.element)
            if item.kind == "p":
                view = paragraph_view(item.element)
                pieces = [pc for pc in view.pieces for _ in pc.text]
                self.entries.append(Expected(
                    "p", item, block.id if block else None,
                    editable=bool(block and block.editable),
                    chars=[OChar(c, i) for i, c in enumerate(view.text)], pieces=pieces,
                ))
            elif item.kind == "tbl":
                bid = block.id if block else None
                table_ids[item.element] = bid
                row_numbers[item.element] = 0
                self.entries.append(Expected("tbl", item, bid, editable=bool(block and block.editable)))
            elif item.kind == "tr":
                tid = table_ids.get(item.owner)
                n = row_numbers[item.owner]
                row_numbers[item.owner] = n + 1
                self.entries.append(Expected("tr", item, f"{tid}.r{n}" if tid else None))
            else:
                self.entries.append(Expected(item.kind, item))

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

    def _span(self, start: Expected) -> tuple[int, int]:
        """[i, j) index range of a table (tbl..tbl_end) or a row (tr..next tr/tbl_end)."""
        i = self.entries.index(start)
        el = start.element
        if start.kind == "tbl":
            j = next(k for k in range(i + 1, len(self.entries))
                     if self.entries[k].kind == "tbl_end" and self.entries[k].element is el)
            return i, j + 1
        table = start.before.owner if start.before else None
        for k in range(i + 1, len(self.entries)):
            e = self.entries[k]
            if e.kind == "tbl_end" and e.element is table:
                return i, k
            if e.kind == "tr" and e.before is not None and e.before.owner is table:
                return i, k
            if e.kind == "tr" and e.before is None and e.template is not None \
                    and getattr(e, "table", None) is table:
                return i, k
        raise OracleError("oracle: unterminated row")

    def _row(self, row_id: str) -> Expected:
        m = _ROW_ID.match(row_id.strip())
        if m is None:
            raise OracleError(f"oracle: bad row id {row_id}")
        return self._entry(row_id, ("tr",))

    def _forget(self, entries: list[Expected]) -> None:
        for e in entries:
            if e.kind == "p" and e.block_id:
                self.deleted.add(e.block_id)
            if e.kind == "tbl" and e.before is None:  # a table this plan created
                self.added_tables -= 1

    # ---------------------------------------------------------------- replay
    def run(self, plan: EditPlan) -> list[Expected]:
        self.deleted: set[str] = set()
        for op in plan.operations:
            getattr(self, f"_op_{op.op}")(op)
        return self.entries

    def _op_replace_text(self, op: ReplaceText) -> None:
        for e, pos in self._last_first(self._matches(op.block_id, op.find, op.occurrence)):
            e.chars[pos:pos + len(op.find)] = [OChar(c, None) for c in op.replace_with]
            e.modified = True

    def _op_delete_text(self, op: DeleteText) -> None:
        for e, pos in self._last_first(self._matches(op.block_id, op.find, op.occurrence)):
            del e.chars[pos:pos + len(op.find)]
            e.modified = True

    def _op_insert_text(self, op: InsertText) -> None:
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

    def _op_insert_paragraph(self, op: InsertParagraph) -> None:
        target = self._entry(op.target_id, ("p", "tbl"))
        template = self._entry(op.format_like).element
        if target.kind == "tbl":
            i, j = self._span(target)
            i = j if op.position == "after" else i
        else:
            i = self.entries.index(target) + (1 if op.position == "after" else 0)
        new = [Expected("p", None, None, True, [OChar(c, None) for c in line], True, template)
               for line in op.text.replace("\r\n", "\n").split("\n")]
        self.entries[i:i] = new

    def _op_delete_paragraph(self, op: DeleteParagraph) -> None:
        e = self._entry(op.block_id)
        self.entries.remove(e)
        self.deleted.add(op.block_id)
        self.removed.append(e.element)

    def _op_format_text(self, op: FormatText) -> None:
        props = op.props()
        for e, pos in self._matches(op.block_id, op.find, op.occurrence):
            for c in e.chars[pos:pos + len(op.find)]:
                c.forced.update(props)
            e.modified = True

    def _op_restyle_text(self, op: RestyleText) -> None:
        match, new = op.match.props(), op.set.props()
        for e in self._scope(op.block_id):
            if e.before is None:
                continue
            # a run is restyled when it holds visible text with the matching formatting;
            # every character of that run (spaces, tabs) then gets the new formatting
            runs = {id(pc.run) for pc in e.pieces
                    if pc.kind == "text" and pc.run is not None and pc.text.strip()
                    and props_match(run_props(pc.run), match)}
            hit = False
            for c in e.chars:
                if c.origin is not None and id(e.pieces[c.origin].run) in runs:
                    c.forced.update(new)
                    hit = True
            if hit:
                e.modified = True

    def _op_delete_images(self, op: DeleteImages) -> None:
        refs = normalise_image_refs(op.images) if op.images is not None else None
        for e in self._scope(op.block_id):
            if e.before is None:
                continue
            kept, gone = [], []
            for c in e.chars:
                pc = e.pieces[c.origin] if c.origin is not None else None
                if pc is not None and image_selected(pc, refs, op.max_size_px):
                    if pc.node not in gone:
                        gone.append(pc.node)
                else:
                    kept.append(c)
            if gone:
                e.chars = kept
                e.modified = True
                self.removed.extend(gone)

    def _op_delete_table_rows(self, op: DeleteTableRows) -> None:
        for row_id in dict.fromkeys(op.rows):
            row = self._row(row_id)
            i, j = self._span(row)
            self._forget(self.entries[i:j])
            self.removed.append(row.element)
            del self.entries[i:j]

    def _op_insert_table_row(self, op: InsertTableRow) -> None:
        anchor = self._row(op.row)
        template = (self._row(op.format_like_row) if op.format_like_row else anchor).element
        table = anchor.before.owner
        new: list[Expected] = []
        row = Expected("tr", None, template=template)
        row.table = table  # type: ignore[attr-defined]
        new.append(row)
        for tc, text in zip(template.findall(W.tc), op.cells):
            new.append(Expected("tc", None, template=tc))
            tpl_p = next((q for q in tc.findall(W.p)
                          if self._pid.get(q) not in self.deleted),
                         cell_template_paragraph(tc))
            for line in text.replace("\r\n", "\n").split("\n"):
                new.append(Expected("p", None, None, True, [OChar(c, None) for c in line],
                                    True, tpl_p))
        i, j = self._span(anchor)
        at = j if op.position == "after" else i
        self.entries[at:at] = new

    def _op_insert_table(self, op: InsertTable) -> None:
        target = self._entry(op.target_id, ("p", "tbl"))
        template_p = self._entry(op.format_like).element
        template_t = self._entry(op.table_like, ("tbl",)).element if op.table_like else None
        if target.kind == "tbl":
            i, j = self._span(target)
            at = j if op.position == "after" else i
        else:
            at = self.entries.index(target) + (1 if op.position == "after" else 0)
        table = Expected("tbl", None, template=template_t, spec={"ncols": len(op.rows[0])})
        new = [table]
        for r, row in enumerate(op.rows):
            header = op.header and r == 0
            new.append(Expected("tr", None, spec={"header": header, "table": table}))
            for c, text in enumerate(row):
                new.append(Expected("tc", None, spec={"table": table, "col": c}))
                for line in text.replace("\r\n", "\n").split("\n"):
                    forced = {"bold": True} if header else {}
                    chars = [OChar(ch, None, dict(forced)) for ch in line]
                    new.append(Expected("p", None, None, True, chars, True, template_p))
        new.append(Expected("tbl_end", None))
        # an empty paragraph keeps tables apart and ends a body/cell (as the editor does)
        nxt = self.entries[at] if at < len(self.entries) else None
        prv = self.entries[at - 1] if at > 0 else None
        spacer = lambda: Expected("p", None, None, True, [], True, None, spec={"spacer": True})  # noqa: E731
        if nxt is None or nxt.kind in ("sectPr", "tbl", "tr", "tc", "tbl_end"):
            new.append(spacer())
        if prv is not None and prv.kind == "tbl_end":
            new.insert(0, spacer())
        self.entries[at:at] = new
        self.added_tables += 1

    def _op_delete_table(self, op: DeleteTable) -> None:
        table = self._entry(op.table_id, ("tbl",))
        i, j = self._span(table)
        self._forget(self.entries[i:j])
        self.removed.append(table.element)
        del self.entries[i:j]


def expected_document(pkg: DocxPackage, plan: EditPlan) -> tuple[list[Expected], set[str]]:
    oracle = Oracle(pkg)
    entries = oracle.run(plan)
    return entries, oracle.deleted


def replay(pkg: DocxPackage, plan: EditPlan) -> Oracle:
    oracle = Oracle(pkg)
    oracle.run(plan)
    return oracle
