"""Post-edit integrity verification.

Given the original package, the edited bytes and the plan, check that the edit
did exactly what the plan says and nothing else:

1. the output re-opens (our parser *and* python-docx as an independent reader),
2. every package part except the main document is byte-identical,
3. the document has the block structure the plan predicts (oracle replay),
4. every paragraph/table/section the plan did not target is XML-identical
   (exclusive C14N) to the original,
5. edited paragraphs contain exactly the text the oracle predicts,
6. in edited paragraphs, paragraph properties are unchanged and every original
   character keeps its run formatting; inserted characters reuse formatting
   that already existed in the paragraph; only explicitly requested formatting
   changed,
7. new paragraphs copy the formatting of the paragraph named in `format_like`,
8. counts of images, tables, hyperlinks, fields, bookmarks, comments, notes and
   sections are preserved.
"""

from __future__ import annotations

import copy
import hashlib
import io
from dataclasses import dataclass, field

from lxml import etree

from .model import _on, paragraph_view
from .ns import MC, W
from .ops import EditPlan, _strip_revision_markup
from .oracle import Expected, OracleError, StreamItem, document_stream, expected_document
from .package import DocxError, DocxPackage


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class VerificationReport:
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(c.passed for c in self.checks)

    def add(self, name: str, passed: bool, detail: str = "") -> Check:
        c = Check(name, passed, detail)
        self.checks.append(c)
        return c

    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.passed]

    def summary(self) -> str:
        lines = [f"{'PASS' if c.passed else 'FAIL'}  {c.name}" + (f" - {c.detail}" if c.detail else "")
                 for c in self.checks]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {"passed": self.passed,
                "checks": [{"name": c.name, "passed": c.passed, "detail": c.detail}
                           for c in self.checks]}


# ------------------------------------------------------------------ hashing
def c14n(el: etree._Element | None) -> bytes:
    if el is None:
        return b""
    return etree.tostring(el, method="c14n", exclusive=True, with_comments=False)


def _h(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def table_signature(tbl: etree._Element) -> str:
    """Hash of a table's structure *without* the paragraphs/tables inside cells
    (those are separate stream items)."""
    parts: list[bytes] = []
    for child in tbl:
        if child.tag != W.tr:
            parts.append(c14n(child))
            continue
        parts.append(b"<tr " + repr(sorted(child.attrib.items())).encode() + b">")
        for cell in child:
            if cell.tag != W.tc:
                parts.append(c14n(cell))
                continue
            parts.append(b"<tc " + repr(sorted(cell.attrib.items())).encode() + b">")
            for inner in cell:
                if inner.tag not in (W.p, W.tbl):
                    parts.append(c14n(inner))
    return _h(b"".join(parts))


def item_signature(item: StreamItem) -> str:
    if item.kind in ("tbl", "tbl_end"):
        return item.kind + ":" + table_signature(item.element)
    return item.kind + ":" + _h(c14n(item.element))


def _container_sig(run: etree._Element | None, p: etree._Element) -> str:
    sig = []
    node = run.getparent() if run is not None else None
    while node is not None and node is not p:
        sig.append(etree.QName(node).localname + repr(sorted(node.attrib.items())))
        node = node.getparent()
    return "/".join(sig)


_TOGGLE_TAGS = {"bold": W.b, "italic": W.i, "underline": W.u}


def _rpr_key(run: etree._Element | None, drop: set[str] | None = None) -> str:
    if run is None:
        return ""
    rpr = run.find(W.rPr)
    if rpr is None:
        return ""
    if drop:
        rpr = copy.deepcopy(rpr)
        for tag in drop:
            for el in rpr.findall(tag):
                rpr.remove(el)
    if len(rpr) == 0 and not rpr.attrib:
        return ""  # an empty <w:rPr/> is the same as no rPr
    return _h(c14n(rpr))


def _mark_key(mark_rpr: etree._Element) -> str:
    """Key of a run whose rPr was copied from the paragraph mark (pPr/rPr)."""
    stripped = _strip_revision_markup(copy.deepcopy(mark_rpr))
    if len(stripped) == 0 and not stripped.attrib:
        return ""
    return _h(c14n(stripped))


@dataclass
class CharInfo:
    ch: str
    run: etree._Element | None
    key: str  # rPr + container + (protected node identity)
    protected: bool


def char_infos(p: etree._Element) -> list[CharInfo]:
    out: list[CharInfo] = []
    for pc in paragraph_view(p).pieces:
        base = _rpr_key(pc.run) + "@" + _container_sig(pc.run, p)
        if pc.kind == "protected":
            base += "#" + (pc.label or "") + ":" + _h(c14n(pc.node))
        for ch in pc.text:
            out.append(CharInfo(ch, pc.run, base, pc.kind == "protected"))
    return out


def _flag(run: etree._Element | None, prop: str) -> bool:
    if run is None:
        return False
    rpr = run.find(W.rPr)
    if rpr is None:
        return False
    el = rpr.find(_TOGGLE_TAGS[prop])
    if prop == "underline":
        return el is not None and el.get(W.val, "single") != "none"
    return _on(el)


# ------------------------------------------------------------------- counts
_COUNTED = {
    "images": [W.drawing, W.pict],
    "embedded objects": [W.object, MC.AlternateContent],
    "tables": [W.tbl],
    "hyperlinks": [W.hyperlink],
    "fields": [W.fldChar, W.fldSimple],
    "bookmarks": [W.bookmarkStart, W.bookmarkEnd],
    "comment anchors": [W.commentRangeStart, W.commentRangeEnd, W.commentReference],
    "footnote/endnote refs": [W.footnoteReference, W.endnoteReference],
    "section breaks": [W.sectPr],
    "tracked changes": [W.ins, W.del_],
}


def count_elements(root: etree._Element) -> dict[str, int]:
    return {name: sum(1 for tag in tags for _ in root.iter(tag)) for name, tags in _COUNTED.items()}


# ------------------------------------------------------------------- verify
def verify_edit(before: DocxPackage, after_bytes: bytes, plan: EditPlan) -> VerificationReport:
    report = VerificationReport()

    # 1. output opens ----------------------------------------------------
    try:
        after = DocxPackage(after_bytes)
    except DocxError as exc:
        report.add("Output is a valid .docx", False, str(exc))
        return report
    try:
        import docx  # python-docx as an independent reader

        docx.Document(io.BytesIO(after_bytes))
        report.add("Output is a valid .docx", True, "re-opened with lxml and python-docx")
    except Exception as exc:  # noqa: BLE001 - any failure here is a verification failure
        report.add("Output is a valid .docx", False, f"python-docx could not open it: {exc}")
        return report

    # 2. other parts byte-identical -----------------------------------------
    names_before = [i.filename for i in before._infos]
    names_after = [i.filename for i in after._infos]
    changed = [n for n in names_before
               if n != before.main_part_name and before.parts[n] != after.parts.get(n)]
    ok = names_before == names_after and not changed
    detail = (f"{len(names_before) - 1} parts copied byte-for-byte" if ok else
              f"changed parts: {changed or 'part list differs'}")
    report.add("Styles, headers/footers, media and all other parts untouched", ok, detail)

    # 3. replay -------------------------------------------------------------
    try:
        expected, deleted = expected_document(before, plan)
    except OracleError as exc:
        report.add("Plan replays on plain text", False, str(exc))
        return report
    actual = document_stream(after)
    kinds_ok = [e.kind for e in expected] == [a.kind for a in actual]
    report.add(
        "Block structure matches the plan", kinds_ok,
        f"{len(actual)} blocks" if kinds_ok else
        f"expected {len(expected)} blocks, found {len(actual)}",
    )
    if not kinds_ok:
        return report

    # 4. untouched blocks identical ---------------------------------------
    untouched_bad: list[str] = []
    n_untouched = 0
    for exp, act in zip(expected, actual):
        if exp.before is None or exp.modified:
            continue
        n_untouched += 1
        if item_signature(exp.before) != item_signature(act):
            untouched_bad.append(exp.block_id or exp.kind)
    report.add(
        "Untouched blocks are XML-identical", not untouched_bad,
        f"{n_untouched} blocks compared" if not untouched_bad else
        f"changed unexpectedly: {', '.join(untouched_bad[:8])}",
    )

    # 5. text matches -------------------------------------------------------
    text_bad: list[str] = []
    for exp, act in zip(expected, actual):
        if exp.kind == "p" and (exp.modified or exp.before is None):
            got = paragraph_view(act.element).text
            if got != exp.text:
                text_bad.append(f"{exp.block_id or 'new paragraph'}: expected {exp.text!r}, got {got!r}")
    report.add("Edited text matches the plan exactly", not text_bad, "; ".join(text_bad[:3]))

    # 6. formatting inside edited paragraphs ------------------------------
    fmt_bad: list[str] = []
    n_chars = 0
    for exp, act in zip(expected, actual):
        if exp.kind != "p" or exp.before is None or not exp.modified:
            continue
        bid = exp.block_id or "?"
        b_el, a_el = exp.before.element, act.element
        if c14n(b_el.find(W.pPr)) != c14n(a_el.find(W.pPr)):
            fmt_bad.append(f"{bid}: paragraph properties changed")
            continue
        b_chars = char_infos(b_el)
        a_chars = char_infos(a_el)
        if len(a_chars) != len(exp.chars or []):
            continue  # already reported by the text check
        kept_keys = set()
        for oc, ac in zip(exp.chars, a_chars):
            if oc.origin is None:
                continue
            n_chars += 1
            bc = b_chars[oc.origin]
            if oc.forced:
                drop = {_TOGGLE_TAGS[k] for k in oc.forced}
                same = (_rpr_key(bc.run, drop) + _container_sig(bc.run, b_el)
                        == _rpr_key(ac.run, drop) + _container_sig(ac.run, a_el))
                flags_ok = all(_flag(ac.run, k) == v for k, v in oc.forced.items())
                if not (same and flags_ok):
                    fmt_bad.append(f"{bid}: requested formatting not applied cleanly at {oc.ch!r}")
                    break
            elif bc.key != ac.key:
                fmt_bad.append(f"{bid}: formatting of untouched character {oc.ch!r} changed")
                break
            kept_keys.add(ac.key)
        allowed = {c.key for c in b_chars} | kept_keys
        mark = b_el.find(W.pPr)
        mark = mark.find(W.rPr) if mark is not None else None
        allowed.add((_mark_key(mark) if mark is not None else "") + "@")
        for oc, ac in zip(exp.chars, a_chars):
            if oc.origin is None and ac.key not in allowed:
                fmt_bad.append(f"{bid}: inserted text {oc.ch!r} got formatting not present before")
                break
    report.add(
        "Formatting preserved in edited paragraphs", not fmt_bad,
        f"{n_chars} original characters checked" if not fmt_bad else "; ".join(fmt_bad[:3]),
    )

    # 7. new paragraphs follow their template ------------------------------
    templates = {e.block_id: e.before.element for e in expected_document_templates(before)}
    new_bad: list[str] = []
    n_new = 0
    for exp, act in zip(expected, actual):
        if exp.before is not None or exp.kind != "p":
            continue
        n_new += 1
        tpl = templates.get(exp.template_id)
        if tpl is None:
            new_bad.append(f"template {exp.template_id} missing")
            continue
        tpl_ppr = tpl.find(W.pPr)
        want = c14n(_strip_revision_markup(copy.deepcopy(tpl_ppr))) if tpl_ppr is not None else b""
        if c14n(act.element.find(W.pPr)) != want:
            new_bad.append(f"new paragraph {exp.text[:30]!r}: style differs from {exp.template_id}")
            continue
        allowed = {_rpr_key(c.run) for c in char_infos(tpl) if not c.protected}
        if not allowed:  # empty template: the paragraph-mark formatting is the reference
            mark = tpl_ppr.find(W.rPr) if tpl_ppr is not None else None
            allowed = {_mark_key(mark) if mark is not None else ""}
        for c in char_infos(act.element):
            if c.protected or _rpr_key(c.run) not in allowed:
                new_bad.append(f"new paragraph {exp.text[:30]!r}: unexpected run formatting")
                break
    report.add(
        "New paragraphs copy their template's formatting", not new_bad,
        f"{n_new} new paragraph(s)" if not new_bad else "; ".join(new_bad[:3]),
    )

    # 8. element counts ----------------------------------------------------
    before_counts = count_elements(before.body)
    removed = {k: 0 for k in before_counts}
    for e in _deleted_elements(before, deleted):
        for k, v in count_elements(e).items():
            removed[k] += v
    after_counts = count_elements(after.body)
    diffs = [f"{k}: {before_counts[k] - removed[k]} -> {after_counts[k]}"
             for k in before_counts if before_counts[k] - removed[k] != after_counts[k]]
    present = ", ".join(f"{v} {k}" for k, v in after_counts.items() if v)
    report.add("Images, tables, links, fields, bookmarks, sections preserved", not diffs,
               present if not diffs else "; ".join(diffs))

    # 9. structural sanity -------------------------------------------------
    sane = []
    for tc in after.body.iter(W.tc):
        kids = [c for c in tc if c.tag in (W.p, W.tbl)]
        if not kids or kids[-1].tag != W.p:
            sane.append("a table cell does not end with a paragraph")
            break
    if before.body.find(W.sectPr) is not None and (len(after.body) == 0 or after.body[-1].tag != W.sectPr):
        sane.append("body no longer ends with its section properties")
    report.add("OOXML structure rules hold", not sane, "; ".join(sane))
    return report


def expected_document_templates(pkg: DocxPackage) -> list[Expected]:
    from .oracle import Oracle

    return [e for e in Oracle(pkg).entries if e.kind == "p" and e.block_id]


def _deleted_elements(pkg: DocxPackage, deleted: set[str]) -> list[etree._Element]:
    if not deleted:
        return []
    from .model import build_index

    idx = build_index(pkg)
    return [b.element for b in idx.blocks if b.id in deleted]
