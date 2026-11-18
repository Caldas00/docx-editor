"""Independent replay of an EditPlan on plain text.

The XML editor (``ops.py``) and this oracle implement the same operation
semantics in two unrelated ways: the editor performs run surgery on XML, the
oracle edits Python strings and flat lists of blocks (one list for the body and
one per header/footer part). The verifier compares the edited document against
the oracle's prediction, so a bug in the run surgery (lost text, duplicated
text, text moved into the wrong run, a row removed from the wrong table, a
paragraph moved to the wrong place) shows up as a mismatch instead of a silently
corrupted document.

Besides the expected text, the oracle tracks the *origin* of every character (the
original paragraph and index it comes from, or ``None`` if it was inserted) and
any formatting the plan explicitly forces on it, plus every original element the
plan removes or copies, so element counts can be checked exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from lxml import etree

from .model import (
    Piece,
    build_index,
    image_info,
    paragraph_view,
    run_props,
    text_box_key,
    text_boxes,
)
from .ns import W, qn
from .ops import (
    _ROW_ID,
    BlocksToTable,
    CreateHeaderFooter,
    DeleteImages,
    DeleteParagraph,
    DeleteTable,
    DeleteTableColumns,
    DeleteTableRows,
    DeleteText,
    DuplicateBlocks,
    EditPlan,
    FormatText,
    InsertHyperlink,
    InsertPageBreak,
    InsertParagraph,
    InsertTable,
    InsertTableColumn,
    InsertTableRow,
    InsertText,
    MergeParagraphs,
    MoveBlocks,
    RemoveHyperlink,
    ReorderTableRows,
    ReplaceText,
    RestyleText,
    SetHyperlinkUrl,
    SetParagraphFormat,
    SetShapeFill,
    SplitParagraph,
    cell_template_paragraph,
    find_all,
    find_drawing,
    first_free_docpr_id,
    image_selected,
    is_blank_paragraph,
    merge_separator_needed,
    normalise_image_refs,
    normalise_prop,
    page_break_text,
    props_match,
    resolve_paragraph_style,
)
from .package import DocxPackage

ItemKind = Literal["p", "tbl", "tr", "tc", "tbl_end", "sectPr", "other"]
_STRUCT_END = ("sectPr", "tbl", "tr", "tc", "tbl_end")


class OracleError(Exception):
    """The plan cannot be replayed - the editor and oracle disagree."""


@dataclass(eq=False)
class StreamItem:
    kind: ItemKind
    element: etree._Element
    owner: etree._Element | None = None  # tr -> its table, tc -> its row


def stream_of(root: etree._Element) -> list[StreamItem]:
    """Flatten a body / header / footer into a sequence covering every child."""
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

    walk(root, False)
    return out


def document_stream(pkg: DocxPackage) -> list[StreamItem]:
    return stream_of(pkg.body)


def part_streams(pkg: DocxPackage) -> dict[str, list[StreamItem]]:
    """"body", every original header/footer part (keyed by part name), then every text box
    in the body (keyed "textbox:<docPr id>:<shape id>:<n>", stable across versions)."""
    out = {"body": stream_of(pkg.body)}
    for hf in pkg.hf_parts:
        if not hf.created:
            out[hf.part_name] = stream_of(hf.root)
    for _, box in text_boxes(pkg.body):
        out[text_box_name(box)] = stream_of(box)
    return out


def text_box_name(box: etree._Element) -> str:
    return "textbox:" + ":".join(map(str, text_box_key(box)))


@dataclass
class OChar:
    ch: str
    origin: int | None  # index in the source paragraph's original text, None = inserted
    forced: dict = field(default_factory=dict)
    src: etree._Element | None = None  # original paragraph the character comes from


@dataclass(eq=False)
class Expected:
    kind: ItemKind
    before: StreamItem | None  # None for anything the plan creates
    block_id: str | None = None
    editable: bool = True
    chars: list[OChar] | None = None
    modified: bool = False
    template: etree._Element | None = None  # what a new p / tr / tc copies its look from
    spec: dict = field(default_factory=dict)  # details for created/restructured items
    ppr_set: dict = field(default_factory=dict)  # requested paragraph property changes
    copy_of: etree._Element | None = None  # duplicated from this original element

    @property
    def text(self) -> str:
        return "".join(c.ch for c in self.chars or [])

    @property
    def element(self) -> etree._Element | None:
        return self.before.element if self.before else None


def _spacer() -> Expected:
    return Expected("p", None, None, True, [], True, None, spec={"spacer": True})


class Oracle:
    def __init__(self, pkg: DocxPackage) -> None:
        self.pkg = pkg
        index = build_index(pkg)
        self.index = index
        ids = {b.element: b for b in index.blocks}
        self.lists: dict[str, list[Expected]] = {}
        self.pieces: dict[etree._Element, list[Piece]] = {}
        self.removed: list[etree._Element] = []  # original elements the plan deletes
        self.copied: list[etree._Element] = []  # original elements the plan duplicates
        self.added_tables = 0
        self.added_links = 0
        self._next_docpr = first_free_docpr_id(pkg)
        self.created_parts: list[dict] = []  # new headers/footers
        self.deleted: set[str] = set()
        self._pid = {b.element: b.id for b in index.blocks if b.kind == "paragraph"}
        for name, items in part_streams(pkg).items():
            self.lists[name] = self._entries(items, ids)

    def _entries(self, items: list[StreamItem], ids: dict) -> list[Expected]:
        out: list[Expected] = []
        table_ids: dict[etree._Element, str | None] = {}
        row_numbers: dict[etree._Element, int] = {}
        for item in items:
            block = ids.get(item.element)
            if item.kind == "p":
                view = paragraph_view(item.element)
                self.pieces[item.element] = [pc for pc in view.pieces for _ in pc.text]
                out.append(Expected(
                    "p", item, block.id if block else None,
                    editable=bool(block and block.editable),
                    chars=[OChar(c, i, {}, item.element) for i, c in enumerate(view.text)],
                ))
            elif item.kind == "tbl":
                table_ids[item.element] = block.id if block else None
                row_numbers[item.element] = 0
                out.append(Expected("tbl", item, table_ids[item.element],
                                    editable=bool(block and block.editable)))
            elif item.kind == "tr":
                tid = table_ids.get(item.owner)
                n = row_numbers[item.owner]
                row_numbers[item.owner] = n + 1
                out.append(Expected("tr", item, f"{tid}.r{n}" if tid else None))
            else:
                out.append(Expected(item.kind, item))
        return out

    @property
    def entries(self) -> list[Expected]:
        return self.lists["body"]

    # ---------------------------------------------------------------- lookup
    def piece(self, c: OChar) -> Piece | None:
        if c.origin is None or c.src is None:
            return None
        return self.pieces[c.src][c.origin]

    def _list_of(self, e: Expected) -> list[Expected]:
        for lst in self.lists.values():
            if any(x is e for x in lst):
                return lst
        raise OracleError("oracle: entry is not in the document any more")

    @staticmethod
    def _pos(lst: list[Expected], e: Expected) -> int:
        return next(i for i, x in enumerate(lst) if x is e)

    def _entry(self, block_id: str, kinds=("p",)) -> Expected:
        for lst in self.lists.values():
            for e in lst:
                if e.block_id == block_id and e.kind in kinds:
                    return e
        raise OracleError(f"oracle: block {block_id} not found")

    def _scope(self, block_id: str | None) -> list[Expected]:
        if block_id is not None:
            return [self._entry(block_id)]
        return [e for lst in self.lists.values() for e in lst if e.kind == "p" and e.editable]

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

    @staticmethod
    def _is_table_end(e: Expected, table: Expected) -> bool:
        if e.kind != "tbl_end":
            return False
        if table.before is None:
            return e.spec.get("table") is table
        return e.before is not None and e.before.element is table.before.element

    @staticmethod
    def _row_table(row: Expected):
        return row.before.owner if row.before else row.spec.get("table_el")

    def _span(self, start: Expected) -> tuple[list[Expected], int, int]:
        """(list, i, j): the entries of a paragraph, table (tbl..tbl_end), row or cell."""
        lst = self._list_of(start)
        i = self._pos(lst, start)
        if start.kind == "p":
            return lst, i, i + 1
        if start.kind == "tbl":
            j = next(k for k in range(i + 1, len(lst)) if self._is_table_end(lst[k], start))
            return lst, i, j + 1
        if start.kind == "tr":
            table = self._row_table(start)
            for k in range(i + 1, len(lst)):
                e = lst[k]
                if e.kind == "tbl_end" and e.before is not None and e.before.element is table:
                    return lst, i, k
                if e.kind == "tr" and self._row_table(e) is table:
                    return lst, i, k
        if start.kind == "tc":
            row = start.before.owner if start.before else start.spec.get("row_el")
            table = row.getparent() if row is not None else None
            for k in range(i + 1, len(lst)):
                e = lst[k]
                if e.kind == "tc" and (e.before.owner if e.before else e.spec.get("row_el")) is row:
                    return lst, i, k
                if e.kind == "tr" and self._row_table(e) is table:
                    return lst, i, k
                if e.kind == "tbl_end" and e.before is not None and e.before.element is table:
                    return lst, i, k
        raise OracleError("oracle: cannot find the extent of this block")

    def _row(self, row_id: str) -> Expected:
        if _ROW_ID.match(row_id.strip()) is None:
            raise OracleError(f"oracle: bad row id {row_id}")
        return self._entry(row_id, ("tr",))

    def _forget(self, entries: list[Expected]) -> None:
        for e in entries:
            self.added_links -= e.spec.get("links_added", 0)
            if e.spec.get("copy_root"):
                k = next(i for i, x in enumerate(self.copied) if x is e.copy_of)
                del self.copied[k]
            if e.kind == "p" and e.block_id:
                self.deleted.add(e.block_id)
            if e.kind == "tbl" and e.before is None and e.copy_of is None:
                self.added_tables -= 1

    @staticmethod
    def _spacers(lst: list[Expected], i: int, j: int) -> None:
        """Mirror of the editor's rule: an empty paragraph keeps tables apart and ends a
        body/cell. [i, j) is a block of entries that was just placed."""
        if j <= i:
            return
        if lst[j - 1].kind == "tbl_end" and (j == len(lst) or lst[j].kind in _STRUCT_END):
            lst.insert(j, _spacer())
        if lst[i].kind == "tbl" and i > 0 and lst[i - 1].kind == "tbl_end":
            lst.insert(i, _spacer())

    def _insert_at(self, target: Expected, position: str, new: list[Expected]) -> None:
        lst, i, j = self._span(target)
        at = j if position == "after" else i
        lst[at:at] = new
        self._spacers(lst, at, at + len(new))

    def _rows_and_cells(self, table: Expected) -> list[list[Expected]]:
        lst, i, j = self._span(table)
        el = table.before.element
        rows: list[list[Expected]] = []
        for k in range(i + 1, j):
            e = lst[k]
            if e.kind == "tr" and e.before is not None and e.before.owner is el:
                rows.append([])
            elif e.kind == "tc" and e.before is not None and rows \
                    and e.before.owner.getparent() is el:
                rows[-1].append(e)
        return rows

    @staticmethod
    def _grid(table: Expected) -> list[str | None]:
        if "grid" in table.spec:
            return list(table.spec["grid"])
        grid = table.before.element.find(qn("w:tblGrid"))
        return [g.get(W.w_attr) for g in grid] if grid is not None else []

    def _new_cell_entries(self, tc: etree._Element, text: str) -> list[Expected]:
        out = [Expected("tc", None, template=tc)]
        tpl_p = cell_template_paragraph(tc)  # first paragraph of the original cell
        for line in text.replace("\r\n", "\n").split("\n"):
            out.append(Expected("p", None, None, True, [OChar(c, None) for c in line],
                                True, tpl_p))
        return out

    def _segments(self, block_ids: list[str]) -> list[tuple[list[Expected], int, int]]:
        spans = [self._span(self._entry(b, ("p", "tbl"))) for b in dict.fromkeys(block_ids)]
        return sorted(spans, key=lambda s: s[1])

    def _is_text(self, c: OChar) -> bool:
        pc = self.piece(c)
        return pc is None or pc.kind == "text"

    # ---------------------------------------------------------------- replay
    def run(self, plan: EditPlan) -> dict[str, list[Expected]]:
        for op in plan.operations:
            getattr(self, f"_op_{op.op}")(op)
        return self.lists

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
        new = [Expected("p", None, None, True, [OChar(c, None) for c in line], True, template)
               for line in op.text.replace("\r\n", "\n").split("\n")]
        lst, i, j = self._span(target)
        at = j if op.position == "after" else i
        lst[at:at] = new

    def _op_delete_paragraph(self, op: DeleteParagraph) -> None:
        e = self._entry(op.block_id)
        self._list_of(e).remove(e)
        self._forget([e])
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
            # a run is restyled when it holds visible text whose formatting - as it is at this
            # point of the plan - matches; every character of that run then gets the new one
            current: dict[int, dict] = {}
            for c in e.chars:
                pc = self.piece(c)
                if pc is not None and c.src is e.element and pc.run is not None:
                    current.setdefault(id(pc.run), {k: v for k, v in c.forced.items()
                                                    if k not in ("link", "unlink")})
            runs = set()
            for pc in self.pieces[e.element]:
                if pc.kind != "text" or pc.run is None or not pc.text.strip():
                    continue
                props = run_props(pc.run)
                props.update({k: normalise_prop(k, v)
                              for k, v in current.get(id(pc.run), {}).items()})
                if props_match(props, match):
                    runs.add(id(pc.run))
            hit = False
            for c in e.chars:
                pc = self.piece(c)
                if pc is not None and c.src is e.element and id(pc.run) in runs:
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
                pc = self.piece(c)
                if pc is not None and image_selected(pc, refs, op.max_size_px):
                    if pc.node not in gone:
                        gone.append(pc.node)
                else:
                    kept.append(c)
            if gone:
                e.chars = kept
                e.modified = True
                self.removed.extend(gone)

    # ------------------------------------------------------------------ tables
    def _op_delete_table_rows(self, op: DeleteTableRows) -> None:
        for row_id in dict.fromkeys(op.rows):
            row = self._row(row_id)
            lst, i, j = self._span(row)
            self._forget(lst[i:j])
            self.removed.append(row.element)
            del lst[i:j]

    def _op_reorder_table_rows(self, op: ReorderTableRows) -> None:
        spans = [self._span(self._row(row_id)) for row_id in op.order]
        lst = spans[0][0]
        segments = [lst[i:j] for _, i, j in spans]  # in their new order
        slots = sorted(spans, key=lambda s: s[1])
        for (_, i, _j), seg in zip(slots, segments):
            if seg[0] is not lst[i]:
                seg[0].spec["moved"] = True  # the row landed somewhere else
        for k in reversed(range(len(slots))):  # back to front keeps earlier indices valid
            _, i, j = slots[k]
            lst[i:j] = segments[k]

    def _op_set_shape_fill(self, op: SetShapeFill) -> None:
        node, host, _ = find_drawing(self.pkg, self.index, op.target)
        e = self._entry(self._pid[host])
        span = next(((pc.start, pc.end) for pc in paragraph_view(host).pieces if pc.node is node),
                    None)
        if span is None:
            raise OracleError(f"oracle: drawing {op.target} not found in its paragraph")
        for oc in e.chars:
            if oc.src is host and oc.origin is not None and span[0] <= oc.origin < span[1]:
                oc.forced["fill"] = op.color.upper()
        e.modified = True

    def _op_insert_table_row(self, op: InsertTableRow) -> None:
        anchor = self._row(op.row)
        template = (self._row(op.format_like_row) if op.format_like_row else anchor).element
        new: list[Expected] = [Expected("tr", None, template=template,
                                        spec={"table_el": anchor.before.owner})]
        for tc, text in zip(template.findall(W.tc), op.cells):
            new.extend(self._new_cell_entries(tc, text))
        lst, i, j = self._span(anchor)
        at = j if op.position == "after" else i
        lst[at:at] = new

    def _op_delete_table(self, op: DeleteTable) -> None:
        table = self._entry(op.table_id, ("tbl",))
        lst, i, j = self._span(table)
        self._forget(lst[i:j])
        self.removed.append(table.element)
        del lst[i:j]

    def _new_table(self, ncols: int, template_t) -> Expected:
        return Expected("tbl", None, template=template_t, spec={"ncols": ncols})

    def _op_insert_table(self, op: InsertTable) -> None:
        target = self._entry(op.target_id, ("p", "tbl"))
        template_p = self._entry(op.format_like).element
        template_t = self._entry(op.table_like, ("tbl",)).element if op.table_like else None
        table = self._new_table(len(op.rows[0]), template_t)
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
        new.append(Expected("tbl_end", None, spec={"table": table}))
        self._insert_at(target, op.position, new)
        self.added_tables += 1

    def _op_insert_table_column(self, op: InsertTableColumn) -> None:
        table = self._entry(op.table_id, ("tbl",))
        grid = self._grid(table)
        for cells, text in zip(self._rows_and_cells(table), op.cells):
            cell = cells[op.column]
            lst, i, j = self._span(cell)
            new = self._new_cell_entries(cell.before.element, text)
            new[0].spec["row_el"] = cell.before.owner
            at = j if op.position == "after" else i
            lst[at:at] = new
        grid.insert(op.column + (1 if op.position == "after" else 0), grid[op.column])
        table.spec["grid"] = grid
        table.modified = True

    def _op_delete_table_columns(self, op: DeleteTableColumns) -> None:
        table = self._entry(op.table_id, ("tbl",))
        rows = self._rows_and_cells(table)
        grid = self._grid(table)
        for col in sorted(set(op.columns), reverse=True):
            for cells in rows:
                lst, i, j = self._span(cells[col])
                self._forget(lst[i:j])
                self.removed.append(cells[col].before.element)
                del lst[i:j]
            del grid[col]
        table.spec["grid"] = grid
        table.modified = True

    def _op_blocks_to_table(self, op: BlocksToTable) -> None:
        template_t = self._entry(op.table_like, ("tbl",)).element if op.table_like else None
        spans = self._segments(op.block_ids)
        lst = spans[0][0]
        at = spans[0][1]
        moved: list[list[Expected]] = []
        for _, i, j in spans:
            e = lst[i]
            if j == i + 1 and e.kind == "p" and not e.chars and is_blank_paragraph(e.element):
                self._forget([e])  # blank spacer lines are removed, not given a cell
                self.removed.append(e.element)
            else:
                moved.append(lst[i:j])
        for _, i, j in sorted(spans, key=lambda s: -s[1]):
            del lst[i:j]
        table = self._new_table(op.columns, template_t)
        table.spec["converted"] = True
        new: list[Expected] = [table]
        cells: list[list[Expected] | None] = moved + [None] * (-len(moved) % op.columns)
        for r in range(0, len(cells), op.columns):
            new.append(Expected("tr", None, spec={"header": False, "table": table}))
            for c, seg in enumerate(cells[r:r + op.columns]):
                new.append(Expected("tc", None, spec={"table": table, "col": c}))
                if seg is None:
                    new.append(_spacer())
                    continue
                new.extend(seg)
                if seg[0].kind == "tbl":  # a nested table needs a paragraph after it
                    new.append(_spacer())
        new.append(Expected("tbl_end", None, spec={"table": table}))
        lst[at:at] = new
        self._spacers(lst, at, at + len(new))
        self.added_tables += 1

    # -------------------------------------------------- moving / duplicating
    def _op_move_blocks(self, op: MoveBlocks) -> None:
        spans = self._segments(op.block_ids)
        moved: list[Expected] = []
        for lst, i, j in spans:
            moved.extend(lst[i:j])
        for e in moved:
            e.spec["moved"] = True
        for lst, i, j in sorted(spans, key=lambda s: -s[1]):
            del lst[i:j]
        self._insert_at(self._entry(op.target_id, ("p", "tbl")), op.position, moved)

    def _op_duplicate_blocks(self, op: DuplicateBlocks) -> None:
        spans = self._segments(op.block_ids)
        copies: list[Expected] = []
        for lst, i, j in spans:
            tables: list[Expected] = []
            # copies get fresh drawing ids, in document order (as the editor assigns them)
            new_ids: dict[etree._Element, str] = {}
            for d in lst[i].element.iter(qn("wp:docPr")):
                new_ids[d] = str(self._next_docpr)
                self._next_docpr += 1
            for n, e in enumerate(lst[i:j]):
                copy = Expected(e.kind, None, None, True, copy_of=e.element,
                                spec={"copy": True, "copy_root": n == 0})
                if e.kind == "p":
                    copy.chars = self._copy_chars(e.chars, new_ids)
                    copy.modified = True
                elif e.kind == "tbl":
                    tables.append(copy)
                elif e.kind == "tbl_end":
                    copy.spec["table"] = tables.pop()
                copies.append(copy)
            self.copied.append(lst[i].element)
        if op.target_id:
            self._insert_at(self._entry(op.target_id, ("p", "tbl")), op.position, copies)
        else:
            lst, _, j = spans[-1]
            lst[j:j] = copies
            self._spacers(lst, j, j + len(copies))

    def _copy_chars(self, chars: list[OChar], new_ids: dict) -> list[OChar]:
        """Characters of a duplicated paragraph; picture placeholders carry the new id."""
        out: list[OChar] = []
        k = 0
        while k < len(chars):
            c = chars[k]
            pc = self.piece(c)
            docpr = pc.node.find(".//" + qn("wp:docPr")) if pc is not None and \
                pc.kind == "protected" else None
            if docpr is None or docpr not in new_ids:
                out.append(OChar(c.ch, c.origin, dict(c.forced), c.src))
                k += 1
                continue
            m = k
            while m < len(chars) and self.piece(chars[m]) is pc:
                m += 1
            old = image_info(pc.node).placeholder
            text = "".join(x.ch for x in chars[k:m])
            text = text.replace(old, old.replace(f"#{docpr.get('id')}", f"#{new_ids[docpr]}"))
            out.extend(OChar(ch, None) for ch in text)
            k = m
        return out

    # ----------------------------------------- paragraphs: style / split / merge
    def _op_set_paragraph_format(self, op: SetParagraphFormat) -> None:
        style = resolve_paragraph_style(self.pkg, op.style) if op.style else None
        for bid in dict.fromkeys(op.block_ids):
            e = self._entry(bid)
            if style:
                e.ppr_set["style"] = style
            if op.align:
                e.ppr_set["align"] = op.align
            if op.remove_numbering:
                e.ppr_set["remove_numbering"] = True
            if op.shading:
                e.ppr_set["shading"] = op.shading.upper()
            e.modified = True

    def _op_split_paragraph(self, op: SplitParagraph) -> None:
        (e, pos), = self._matches(op.block_id, op.at, op.occurrence)[:1]
        first, rest = e.chars[:pos], e.chars[pos:]
        if first and first[-1].ch == " " and self._is_text(first[-1]):
            first = first[:-1]
        if rest and rest[0].ch == " " and self._is_text(rest[0]):
            rest = rest[1:]
        lst = self._list_of(e)
        new = Expected("p", None, None, True, first, True, e.element, spec={"split": True},
                       ppr_set=dict(e.ppr_set))
        lst.insert(self._pos(lst, e), new)
        e.chars = rest
        e.modified = True

    def _op_merge_paragraphs(self, op: MergeParagraphs) -> None:
        ids = list(dict.fromkeys(op.block_ids))
        first = self._entry(ids[0])
        lst = self._list_of(first)
        for bid in ids[1:]:
            other = self._entry(bid)
            if merge_separator_needed(first.text, other.text, op.separator):
                first.chars.extend(OChar(c, None) for c in op.separator)
            first.chars.extend(other.chars)
            first.spec["links_added"] = first.spec.get("links_added", 0) + \
                other.spec.get("links_added", 0)
            lst.remove(other)
            self.deleted.add(bid)
        first.modified = True

    def _op_insert_page_break(self, op: InsertPageBreak) -> None:
        target = self._entry(op.target_id, ("p", "tbl"))
        chars = [OChar(c, None) for c in page_break_text()]
        new = Expected("p", None, None, True, chars, True, None, spec={"page_break": True})
        lst, i, j = self._span(target)
        at = j if op.position == "after" else i
        lst[at:at] = [new]

    # --------------------------------------------------------------- hyperlinks
    def _op_insert_hyperlink(self, op: InsertHyperlink) -> None:
        for e, pos in self._matches(op.block_id, op.find, op.occurrence):
            self.added_links += 1
            e.spec["links_added"] = e.spec.get("links_added", 0) + 1
            for c in e.chars[pos:pos + len(op.find)]:
                c.forced["link"] = op.url
            e.modified = True

    def _link_chars(self, e: Expected, pos: int) -> list[OChar]:
        pc = self.piece(e.chars[pos])
        link = pc.container if pc is not None else None
        if link is None or link.tag != W.hyperlink:
            raise OracleError("oracle: not inside a hyperlink")
        out = []
        for c in e.chars:
            p = self.piece(c)
            if p is not None and p.container is link:
                out.append(c)
        return out

    def _op_remove_hyperlink(self, op: RemoveHyperlink) -> None:
        (e, pos), = self._matches(op.block_id, op.find, op.occurrence)[:1]
        for c in self._link_chars(e, pos):
            c.forced["unlink"] = True
        self.added_links -= 1
        e.modified = True

    def _op_set_hyperlink_url(self, op: SetHyperlinkUrl) -> None:
        (e, pos), = self._matches(op.block_id, op.find, op.occurrence)[:1]
        for c in self._link_chars(e, pos):
            c.forced["link"] = op.url
        e.modified = True

    # ---------------------------------------------------------- headers/footers
    def _op_create_header_footer(self, op: CreateHeaderFooter) -> None:
        self.created_parts.append({"kind": op.kind, "text": op.text,
                                   "page_numbers": op.page_numbers, "align": op.align})


def replay(pkg: DocxPackage, plan: EditPlan) -> Oracle:
    oracle = Oracle(pkg)
    oracle.run(plan)
    return oracle


def expected_document(pkg: DocxPackage, plan: EditPlan) -> tuple[list[Expected], set[str]]:
    oracle = replay(pkg, plan)
    return oracle.entries, oracle.deleted
