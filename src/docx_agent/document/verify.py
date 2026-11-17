"""Post-edit integrity verification.

Given the original package, the edited bytes and the plan, check that the edit
did exactly what the plan says and nothing else:

1. the output re-opens (our parser *and* python-docx as an independent reader),
2. every package part is byte-identical except the main document and the
   headers/footers (checked block by block below); relationships and content types
   only gained what the plan adds (links, new headers/footers), and new
   headers/footers are exactly as planned,
3. the body and every header/footer have the block structure the plan predicts
   (oracle replay),
4. every block the plan did not target is XML-identical (exclusive C14N),
5. edited paragraphs contain exactly the text the oracle predicts,
6. in edited, split, merged and copied paragraphs every original character keeps
   its run formatting and container; inserted characters reuse formatting that was
   already there; only explicitly requested formatting, links and paragraph
   properties changed,
7. new paragraphs, rows, cells, tables, page breaks and copies are exactly what the
   plan's templates predict,
8. counts of images, tables, hyperlinks, fields, bookmarks, comments, notes and
   sections change only by what the plan adds or removes,
9. Word's structural rules still hold.
"""

from __future__ import annotations

import copy
import hashlib
import io
from dataclasses import dataclass, field

from lxml import etree

from .model import paragraph_view, run_props
from .ns import MC, R_ID, W, qn
from .ops import (
    JC,
    EditPlan,
    _strip_revision_markup,
    build_header_footer,
    new_cell_skeleton,
    new_row_skeleton,
    new_table_cell,
    new_table_row,
    new_table_skeleton,
    normalise_prop,
    page_break_paragraph,
    sanitize_copy,
    table_grid_widths,
    without_sectpr,
)
from .oracle import Expected, Oracle, OracleError, StreamItem, replay, stream_of
from .package import (
    FOOTER_CT,
    FOOTER_REL,
    HEADER_CT,
    HEADER_REL,
    HYPERLINK_REL,
    DocxError,
    DocxPackage,
    parse_xml,
)


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


def _shallow_signature(el: etree._Element, skip: tuple[str, ...]) -> str:
    """Hash of an element's attributes and of its children, except the children with
    tags in ``skip`` (those are separate stream items: rows, cells, paragraphs)."""
    parts = [repr(sorted(el.attrib.items())).encode()]
    parts += [c14n(child) for child in el if child.tag not in skip]
    return _h(b"".join(parts))


def item_signature(item: StreamItem) -> str:
    el = item.element
    if item.kind == "tbl":
        return "tbl:" + _shallow_signature(el, (W.tr,))
    if item.kind == "tr":
        return "tr:" + _shallow_signature(el, (W.tc,))
    if item.kind == "tc":  # paragraphs, tables and other children are stream items
        return "tc:" + _h(repr(sorted(el.attrib.items())).encode() + c14n(el.find(W.tcPr)))
    if item.kind == "tbl_end":
        return "tbl_end"
    return item.kind + ":" + _h(c14n(el))


def _container_sig(run: etree._Element | None, p: etree._Element) -> str:
    sig = []
    node = run.getparent() if run is not None else None
    while node is not None and node is not p:
        sig.append(etree.QName(node).localname + repr(sorted(node.attrib.items())))
        node = node.getparent()
    return "/".join(sig)


# rPr children each requested property may change
_PROP_TAGS = {"bold": [W.b], "italic": [W.i], "underline": [W.u], "strike": [W.strike],
              "color": [W.color], "highlight": [W.highlight],
              "font_size": [W.sz, qn("w:szCs")],
              "link": [W.rStyle, W.color, W.u], "unlink": [W.rStyle, W.color, W.u]}
_DOCPR = qn("wp:docPr")


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


def _template_keys(tpl: etree._Element, drop: set[str]) -> set[str]:
    """Run formatting a paragraph copied from ``tpl`` may have (ignoring ``drop`` tags)."""
    keys = {_rpr_key(c.run, drop) for c in char_infos(tpl) if not c.protected}
    if keys:
        return keys
    ppr = tpl.find(W.pPr)
    mark = ppr.find(W.rPr) if ppr is not None else None
    if mark is None:  # empty template: the paragraph-mark formatting is the reference
        return {""}
    return {_rpr_key_of(_strip_revision_markup(copy.deepcopy(mark)), drop)}


def _rpr_key_of(rpr: etree._Element, drop: set[str]) -> str:
    """Like _rpr_key, for a bare rPr element."""
    holder = etree.Element(W.r)
    holder.append(copy.deepcopy(rpr))
    return _rpr_key(holder, drop)


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


def _without_docpr_ids(node: etree._Element) -> etree._Element:
    """Drawing ids are bookkeeping (copies get fresh ones); ignore them when comparing."""
    if node.find(".//" + _DOCPR) is None:
        return node
    node = copy.deepcopy(node)
    for d in node.iter(_DOCPR):
        d.attrib.pop("id", None)
    return node


def char_infos(p: etree._Element) -> list[CharInfo]:
    out: list[CharInfo] = []
    for pc in paragraph_view(p).pieces:
        base = _rpr_key(pc.run) + "@" + _container_sig(pc.run, p)
        if pc.kind == "protected":
            base += "#" + (pc.label or "") + ":" + _h(c14n(_without_docpr_ids(pc.node)))
        for ch in pc.text:
            out.append(CharInfo(ch, pc.run, base, pc.kind == "protected"))
    return out




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
def _ppr_c14n(ppr: etree._Element | None, drop: tuple[str, ...] = ()) -> bytes:
    if ppr is None:
        return b""
    ppr = copy.deepcopy(ppr)
    for tag in drop:
        for found in ppr.findall(tag):
            ppr.remove(found)
    return b"" if len(ppr) == 0 and not ppr.attrib else c14n(ppr)


def _strip_refs(el: etree._Element, new_rel_ids: set[str]) -> etree._Element:
    """Remove references to headers/footers the plan created (sectPr may gain them)."""
    if not new_rel_ids:
        return el
    el = copy.deepcopy(el)
    for tag in (qn("w:headerReference"), qn("w:footerReference")):
        for ref in list(el.iter(tag)):
            if ref.get(R_ID) in new_rel_ids:
                ref.getparent().remove(ref)
    return el


def _rels(pkg: DocxPackage) -> dict[str, tuple]:
    return {r.rel_id: (r.rel_type, r.target, r.external) for r in pkg.relationships.values()}


def _content_types(pkg: DocxPackage) -> set[tuple]:
    root = parse_xml(pkg.parts["[Content_Types].xml"])
    return {(etree.QName(e).localname, tuple(sorted(e.attrib.items()))) for e in root}


def _check_parts(before: DocxPackage, after: DocxPackage, oracle: Oracle, plan: EditPlan,
                 report: VerificationReport) -> set[str]:
    """Check 2. Returns the relationship ids of headers/footers the plan created."""
    problems: list[str] = []
    hf_names = {hf.part_name for hf in before.hf_parts}
    verified_elsewhere = {before.main_part_name, before.rels_part_name, "[Content_Types].xml"} \
        | hf_names
    copied = 0
    for name, data in before.parts.items():
        if name in verified_elsewhere:
            continue
        if after.parts.get(name) != data:
            problems.append(f"{name} changed")
        else:
            copied += 1
    missing = [n for n in before.parts if n not in after.parts]
    if missing:
        problems.append(f"parts disappeared: {missing}")
    # relationships: only additions, of the kinds the plan can add
    b_rels, a_rels = _rels(before), _rels(after)
    for rid, rel in b_rels.items():
        if a_rels.get(rid) != rel:
            problems.append(f"relationship {rid} changed")
    urls = {getattr(op, "url", None) for op in plan.operations} - {None}
    new_rel_ids: set[str] = set()
    new_hf_targets: dict[str, str] = {}
    for rid in set(a_rels) - set(b_rels):
        rel_type, target, external = a_rels[rid]
        if rel_type == HYPERLINK_REL and external and target in urls:
            continue
        if rel_type in (HEADER_REL, FOOTER_REL) and not external:
            new_rel_ids.add(rid)
            new_hf_targets[after.resolve_part(rid) or ""] = rel_type
            continue
        problems.append(f"unexpected new relationship {rid} ({rel_type} -> {target})")
    # content types: only overrides for the new parts
    b_ct, a_ct = _content_types(before), _content_types(after)
    if not b_ct <= a_ct:
        problems.append("[Content_Types].xml lost or changed entries")
    new_parts = [n for n in after.parts if n not in before.parts and n != after.rels_part_name]
    if sorted(new_parts) != sorted(new_hf_targets):
        problems.append(f"unexpected new parts: {sorted(set(new_parts) ^ set(new_hf_targets))}")
    expected = []
    for params in oracle.created_parts:
        style = params["kind"].capitalize()
        style = style if style in before.paragraph_styles else None
        expected.append(c14n(build_header_footer(params["kind"], params["text"],
                                                 params["page_numbers"], params["align"], style)))
    got = []
    for name in new_parts:
        ct = HEADER_CT if new_hf_targets.get(name) == HEADER_REL else FOOTER_CT
        if ("Override", tuple(sorted({"PartName": "/" + name, "ContentType": ct}.items()))) \
                not in a_ct:
            problems.append(f"{name} has no content type")
        got.append(c14n(parse_xml(after.parts[name])))
    if sorted(got) != sorted(expected):
        problems.append("new header/footer content differs from the plan")
    extra_ct = a_ct - b_ct
    if len(extra_ct) != len(new_parts):
        problems.append("[Content_Types].xml gained unexpected entries")
    detail = f"{copied} parts copied byte-for-byte"
    if new_parts:
        detail += f"; {len(new_parts)} new header/footer part(s) as planned"
    report.add("Styles, media, metadata and other parts untouched", not problems,
               detail if not problems else "; ".join(problems[:4]))
    return new_rel_ids


def _actual_streams(after: DocxPackage, oracle: Oracle) -> dict[str, list[StreamItem] | None]:
    by_name = {hf.part_name: hf.root for hf in after.hf_parts}
    out: dict[str, list[StreamItem] | None] = {}
    for name in oracle.lists:
        if name == "body":
            out[name] = stream_of(after.body)
        else:
            root = by_name.get(name)
            out[name] = stream_of(root) if root is not None else None
    return out


def _expected_ppr(exp: Expected) -> tuple[bytes, tuple[str, ...]]:
    """(canonical pPr the paragraph must have, pPr children whose value is checked apart)."""
    drop = []
    if "style" in exp.ppr_set:
        drop.append(W.pStyle)
    if "align" in exp.ppr_set:
        drop.append(qn("w:jc"))
    if exp.ppr_set.get("remove_numbering"):
        drop.append(W.numPr)
    if exp.before is not None:
        base = exp.before.element.find(W.pPr)
    elif exp.copy_of is not None:
        base = sanitize_copy(copy.deepcopy(exp.copy_of)).find(W.pPr)
    else:  # the first half of a split paragraph
        base = without_sectpr(exp.template.find(W.pPr))
    return _ppr_c14n(base, tuple(drop)), tuple(drop)


def _ppr_values_ok(exp: Expected, ppr: etree._Element | None) -> bool:
    def val(tag):
        el = ppr.find(tag) if ppr is not None else None
        return el.get(W.val) if el is not None else None
    if "style" in exp.ppr_set and val(W.pStyle) != exp.ppr_set["style"]:
        return False
    if "align" in exp.ppr_set and val(qn("w:jc")) != JC[exp.ppr_set["align"]]:
        return False
    return not (exp.ppr_set.get("remove_numbering") and ppr is not None
                and ppr.find(W.numPr) is not None)


def _link_ok(after: DocxPackage, run: etree._Element | None, p: etree._Element,
             forced: dict) -> bool:
    parent = run.getparent() if run is not None else None
    if "unlink" in forced and "link" not in forced:
        style = run.find(W.rPr).find(W.rStyle) if run is not None and run.find(W.rPr) is not None \
            else None
        return parent is p and (style is None or style.get(W.val) != "Hyperlink")
    if parent is None or parent.tag != W.hyperlink or parent.getparent() is not p:
        return False
    rel = after.relationships.get(parent.get(R_ID) or "")
    return rel is not None and rel.target == forced["link"] and rel.external


def _char_check(exp: Expected, act_el: etree._Element, after: DocxPackage,
                cache: dict) -> tuple[str | None, int]:
    """Check 6 for one paragraph whose characters come from original paragraphs."""
    def infos(el):
        if el not in cache:
            cache[el] = char_infos(el)
        return cache[el]

    a_chars = char_infos(act_el)
    if len(a_chars) != len(exp.chars or []):
        return None, 0  # reported by the text check
    sources = {oc.src for oc in exp.chars if oc.src is not None}
    base = exp.before.element if exp.before is not None else (
        exp.copy_of if exp.copy_of is not None else exp.template)
    if base is not None:
        sources.add(base)
    allowed = {c.key for src in sources for c in infos(src)}
    for src in sources:
        ppr = src.find(W.pPr)
        mark = ppr.find(W.rPr) if ppr is not None else None
        allowed.add((_mark_key(mark) if mark is not None else "") + "@")
    checked = 0
    for oc, ac in zip(exp.chars, a_chars):
        if oc.origin is None:
            continue
        checked += 1
        bc = infos(oc.src)[oc.origin]
        if oc.forced:
            drop = {t for k in oc.forced for t in _PROP_TAGS[k]}
            linky = "link" in oc.forced or "unlink" in oc.forced
            same_rpr = _rpr_key(bc.run, drop) == _rpr_key(ac.run, drop)
            same_container = linky or (_container_sig(bc.run, oc.src)
                                       == _container_sig(ac.run, act_el))
            got = run_props(ac.run)
            flags_ok = all(got[k] == normalise_prop(k, v) for k, v in oc.forced.items()
                           if k not in ("link", "unlink"))
            if not (same_rpr and same_container and flags_ok
                    and (not linky or _link_ok(after, ac.run, act_el, oc.forced))):
                return f"requested formatting/link not applied cleanly at {oc.ch!r}", checked
        elif bc.key != ac.key:
            return f"formatting of untouched character {oc.ch!r} changed", checked
        allowed.add(ac.key)
    for oc, ac in zip(exp.chars, a_chars):
        if oc.origin is None and ac.key not in allowed and not oc.forced:
            return f"inserted text {oc.ch!r} got formatting not present before", checked
    return None, checked


def verify_edit(before: DocxPackage, after_bytes: bytes, plan: EditPlan) -> VerificationReport:
    report = VerificationReport()

    # 1. output opens ----------------------------------------------------------
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

    # replay the plan on plain text ----------------------------------------------
    try:
        oracle = replay(before, plan)
    except OracleError as exc:
        report.add("Plan replays on plain text", False, str(exc))
        return report

    # 2. package parts -----------------------------------------------------------
    new_rel_ids = _check_parts(before, after, oracle, plan, report)

    # 3. structure of the body and every header/footer ----------------------------
    actual = _actual_streams(after, oracle)
    pairs: list[tuple[Expected, StreamItem]] = []
    bad_parts = []
    for name, exp_list in oracle.lists.items():
        act_list = actual.get(name)
        if act_list is None or [e.kind for e in exp_list] != [a.kind for a in act_list]:
            bad_parts.append(f"{name}: expected {len(exp_list)} blocks, found "
                             f"{len(act_list) if act_list is not None else 'no part'}")
        else:
            pairs.extend(zip(exp_list, act_list))
    n_parts = len(oracle.lists)
    report.add("Block structure matches the plan", not bad_parts,
               f"{len(pairs)} blocks in {n_parts} part(s)" if not bad_parts
               else "; ".join(bad_parts[:2]))
    if bad_parts:
        return report

    # 4. untouched blocks are identical -----------------------------------------
    untouched_bad: list[str] = []
    n_untouched = 0
    for exp, act in pairs:
        if exp.before is None or exp.modified:
            continue
        n_untouched += 1
        act_item = StreamItem(act.kind, _strip_refs(act.element, new_rel_ids), act.owner)
        if item_signature(exp.before) != item_signature(act_item):
            untouched_bad.append(exp.block_id or exp.kind)
    report.add("Untouched blocks are XML-identical", not untouched_bad,
               f"{n_untouched} blocks compared" if not untouched_bad else
               f"changed unexpectedly: {', '.join(untouched_bad[:8])}")

    # 5. text ---------------------------------------------------------------------
    text_bad: list[str] = []
    for exp, act in pairs:
        if exp.kind == "p" and (exp.modified or exp.before is None):
            got = paragraph_view(act.element).text
            if got != exp.text:
                text_bad.append(f"{exp.block_id or 'new paragraph'}: expected {exp.text!r}, "
                                f"got {got!r}")
    report.add("Edited text matches the plan exactly", not text_bad, "; ".join(text_bad[:3]))

    # 6. formatting of edited / split / merged / copied paragraphs -----------------
    fmt_bad: list[str] = []
    n_chars = 0
    cache: dict = {}
    for exp, act in pairs:
        origin_based = exp.kind == "p" and exp.modified and (
            exp.before is not None or exp.copy_of is not None or exp.spec.get("split"))
        if not origin_based:
            continue
        bid = exp.block_id or "new paragraph"
        want, drop = _expected_ppr(exp)
        a_ppr = _strip_refs(act.element, new_rel_ids).find(W.pPr)
        if _ppr_c14n(a_ppr, drop) != want or not _ppr_values_ok(exp, a_ppr):
            fmt_bad.append(f"{bid}: paragraph properties not as planned")
            continue
        problem, checked = _char_check(exp, act.element, after, cache)
        n_chars += checked
        if problem:
            fmt_bad.append(f"{bid}: {problem}")
    report.add("Formatting preserved in edited paragraphs", not fmt_bad,
               f"{n_chars} original characters checked" if not fmt_bad else "; ".join(fmt_bad[:3]))

    # 7. created structures ----------------------------------------------------------
    new_bad: list[str] = []
    n_new = 0
    for exp, act in pairs:
        if exp.kind == "tbl" and exp.before is not None and "grid" in exp.spec:
            grid = act.element.find(qn("w:tblGrid"))
            widths = [g.get(W.w_attr) for g in grid] if grid is not None else []
            same = (_shallow_signature(act.element, (W.tr, qn("w:tblGrid")))
                    == _shallow_signature(exp.before.element, (W.tr, qn("w:tblGrid"))))
            if not same or widths != exp.spec["grid"]:
                new_bad.append(f"{exp.block_id}: columns not changed as planned")
            continue
        if exp.before is not None or exp.kind == "tbl_end":
            continue
        n_new += 1
        tpl = exp.template
        if exp.copy_of is not None and exp.kind != "p":
            want_item = StreamItem(exp.kind, sanitize_copy(copy.deepcopy(exp.copy_of)))
            if item_signature(want_item) != item_signature(act):
                new_bad.append(f"copied {exp.kind}: not identical to its original")
            continue
        if exp.kind == "tbl":
            want = new_table_skeleton(before, tpl, exp.spec["ncols"])
            exp.spec["widths"] = table_grid_widths(want)
            if item_signature(act) != item_signature(StreamItem("tbl", want)):
                new_bad.append("new table: table properties or column grid not as planned")
            continue
        if exp.kind == "tr":
            want = (new_table_row(exp.spec["header"]) if "header" in exp.spec
                    else new_row_skeleton(tpl))
            if item_signature(act) != item_signature(StreamItem("tr", want)):
                new_bad.append("new row: row properties differ from its template row")
            continue
        if exp.kind == "tc":
            if "col" in exp.spec:
                want = new_table_cell(exp.spec["table"].spec["widths"][exp.spec["col"]])
            else:
                want = new_cell_skeleton(tpl)
            if item_signature(act) != item_signature(StreamItem("tc", want)):
                new_bad.append("new cell: cell properties differ from the template cell")
            continue
        if exp.copy_of is not None or exp.spec.get("split"):
            continue  # checked character by character in check 6
        if exp.spec.get("spacer"):
            if act.element.find(W.pPr) is not None or paragraph_view(act.element).text:
                new_bad.append("spacer paragraph is not empty")
            continue
        if exp.spec.get("page_break"):
            if c14n(act.element) != c14n(page_break_paragraph()):
                new_bad.append("page break paragraph not as planned")
            continue
        tpl_ppr = tpl.find(W.pPr)
        want = c14n(_strip_revision_markup(copy.deepcopy(tpl_ppr))) if tpl_ppr is not None else b""
        if c14n(act.element.find(W.pPr)) != want:
            new_bad.append(f"new paragraph {exp.text[:30]!r}: style differs from its template")
            continue
        plain = _template_keys(tpl, set())
        for oc, c in zip(exp.chars or [], char_infos(act.element)):
            if c.protected:
                new_bad.append(f"new paragraph {exp.text[:30]!r}: unexpected content")
                break
            if oc.forced:  # e.g. insert_paragraph followed by format_text on it
                drop = {t for k in oc.forced for t in _PROP_TAGS[k]}
                got = run_props(c.run)
                linky = "link" in oc.forced or "unlink" in oc.forced
                if _rpr_key(c.run, drop) not in _template_keys(tpl, drop) or any(
                        got[k] != normalise_prop(k, v) for k, v in oc.forced.items()
                        if k not in ("link", "unlink")) or (
                        linky and not _link_ok(after, c.run, act.element, oc.forced)):
                    new_bad.append(f"new paragraph {exp.text[:30]!r}: formatting not as planned")
                    break
            elif _rpr_key(c.run) not in plain:
                new_bad.append(f"new paragraph {exp.text[:30]!r}: unexpected run formatting")
                break
    report.add("New paragraphs and rows copy their template's formatting", not new_bad,
               f"{n_new} new block(s)" if not new_bad else "; ".join(new_bad[:3]))

    # 8. element counts (body + original headers/footers) --------------------------
    def total(roots) -> dict[str, int]:
        out: dict[str, int] = {}
        for root in roots:
            for k, v in count_elements(root).items():
                out[k] = out.get(k, 0) + v
        return out

    b_names = {hf.part_name for hf in before.hf_parts}
    before_counts = total([before.body] + [hf.root for hf in before.hf_parts])
    after_counts = total([after.body] + [hf.root for hf in after.hf_parts
                                         if hf.part_name in b_names])
    expected_counts = dict(before_counts)
    removed_ids = {id(el) for el in oracle.removed}
    outermost = [el for el in oracle.removed  # a picture deleted, then its paragraph: count once
                 if not any(id(a) in removed_ids for a in el.iterancestors())]
    for el in outermost:  # paragraphs, rows, cells, tables, pictures the plan deletes
        for k, v in count_elements(el).items():
            expected_counts[k] -= v
    for el in oracle.copied:  # duplicates
        for k, v in count_elements(sanitize_copy(copy.deepcopy(el))).items():
            expected_counts[k] += v
    expected_counts["tables"] += oracle.added_tables
    expected_counts["hyperlinks"] += oracle.added_links
    diffs = [f"{k}: expected {expected_counts[k]}, found {after_counts[k]}"
             for k in before_counts if expected_counts[k] != after_counts[k]]
    present = ", ".join(f"{v} {k}" for k, v in after_counts.items() if v)
    report.add("Images, tables, links, fields, bookmarks, sections preserved", not diffs,
               present if not diffs else "; ".join(diffs))

    # 9. structural sanity ---------------------------------------------------------
    sane = []
    roots_after = [after.body] + [hf.root for hf in after.hf_parts]
    for root in roots_after:
        for tc in root.iter(W.tc):
            kids = [c for c in tc if c.tag in (W.p, W.tbl)]
            if not kids or kids[-1].tag != W.p:
                sane.append("a table cell does not end with a paragraph")
                break
        if root.tag in (qn("w:hdr"), qn("w:ftr")) and root.find(W.p) is None:
            sane.append("a header/footer has no paragraph")
    if before.body.find(W.sectPr) is not None and (len(after.body) == 0
                                                   or after.body[-1].tag != W.sectPr):
        sane.append("body no longer ends with its section properties")
    if _last_block_tag(before.body) == W.p and _last_block_tag(after.body) != W.p:
        sane.append("the document no longer ends with a paragraph")
    if not _adjacent_tables(before.body) and _adjacent_tables(after.body):
        sane.append("two tables are now touching (Word would merge them)")
    report.add("OOXML structure rules hold", not sane, "; ".join(sorted(set(sane))))
    return report


def _adjacent_tables(root: etree._Element) -> bool:
    for container in [root, *root.iter(W.tc)]:
        prev = None
        for child in container:
            if child.tag == W.tbl and prev is not None and prev.tag == W.tbl:
                return True
            if child.tag in (W.p, W.tbl):
                prev = child
    return False


def _last_block_tag(body: etree._Element) -> str | None:
    blocks = [c for c in body if c.tag in (W.p, W.tbl)]
    return blocks[-1].tag if blocks else None
