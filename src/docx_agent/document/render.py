"""HTML preview of a document, optionally with a redline of an edit.

This is an *approximate* rendering for the web UI (headings, lists, inline
formatting, tables, images, links). The redline reuses the oracle's character
alignment, so what is highlighted is exactly what the plan changed.
"""

from __future__ import annotations

import base64
import html
import mimetypes
import re
from dataclasses import dataclass, field

from lxml import etree

from .model import Piece, build_index, list_level, paragraph_style, paragraph_view
from .ns import R_EMBED, W, qn
from .ops import EditPlan
from .oracle import Expected, document_stream, replay
from .package import DocxPackage

A_BLIP = qn("a:blip")
WP_EXTENT = qn("wp:extent")
MAX_IMAGE_BYTES = 4 * 1024 * 1024


@dataclass
class _Char:
    ch: str
    piece: Piece
    status: str  # "same" | "ins" | "del" | "fmt"


def _on(el) -> bool:
    return el is not None and el.get(W.val, "true") not in ("0", "false", "off", "none")


def _run_css(run: etree._Element | None) -> tuple[list[str], list[str]]:
    """(css declarations, wrapper tags) for a run's direct formatting."""
    css: list[str] = []
    tags: list[str] = []
    if run is None:
        return css, tags
    rpr = run.find(W.rPr)
    if rpr is None:
        return css, tags
    if _on(rpr.find(W.b)):
        tags.append("strong")
    if _on(rpr.find(W.i)):
        tags.append("em")
    u = rpr.find(W.u)
    if u is not None and u.get(W.val, "single") != "none":
        css.append("text-decoration:underline")
    if _on(rpr.find(W.strike)):
        css.append("text-decoration:line-through")
    color = _hex(rpr.find(W.color), W.val)
    if color:
        css.append(f"color:#{color}")
    hl = rpr.find(W.highlight)
    if hl is not None and hl.get(W.val) not in (None, "none"):
        css.append(f"background:{_HIGHLIGHT.get(hl.get(W.val), '#fff59d')}")
    sz = rpr.find(W.sz)
    if sz is not None and (sz.get(W.val) or "").isdigit():
        css.append(f"font-size:{int(sz.get(W.val)) / 2:.1f}pt")
    return css, tags


_HEX = re.compile(r"[0-9A-Fa-f]{6}")


def _hex(el: etree._Element | None, attr: str) -> str | None:
    """A colour attribute, only if it is a plain RRGGBB value (document content is
    untrusted: never copy raw attribute text into HTML)."""
    if el is None:
        return None
    val = el.get(attr) or ""
    return val if _HEX.fullmatch(val) else None


_HIGHLIGHT = {"yellow": "#fff59d", "green": "#c8f7c5", "cyan": "#b2f5ff", "magenta": "#f8c4f5",
              "lightGray": "#e5e7eb", "red": "#fecaca", "blue": "#bfdbfe"}


class Renderer:
    def __init__(self, pkg: DocxPackage, with_ids: bool = True) -> None:
        self.pkg = pkg
        self._img_cache: dict[str, str] = {}
        # block ids as data attributes, so the UI can tell the agent what the user selected
        self.ids: dict[etree._Element, str] = (
            {b.element: b.id for b in build_index(pkg).blocks} if with_ids else {})

    # ---------------------------------------------------------------- pieces
    def _image(self, node: etree._Element) -> str:
        blip = node.find(".//" + A_BLIP)
        rid = blip.get(R_EMBED) if blip is not None else None
        part = self.pkg.resolve_part(rid) if rid else None
        if not part or part not in self.pkg.parts:
            return '<span class="img-placeholder">image</span>'
        if part not in self._img_cache:
            data = self.pkg.parts[part]
            if len(data) > MAX_IMAGE_BYTES:
                return '<span class="img-placeholder">large image</span>'
            mime = mimetypes.guess_type(part)[0] or "image/png"
            self._img_cache[part] = f"data:{mime};base64,{base64.b64encode(data).decode()}"
        width = ""
        ext = node.find(".//" + WP_EXTENT)
        if ext is not None and (ext.get("cx") or "").isdigit():
            width = f' style="width:{min(int(ext.get("cx")) / 9525, 640):.0f}px"'
        return f'<img src="{self._img_cache[part]}" alt="image"{width}>'

    def _protected_html(self, piece: Piece) -> str:
        if piece.label == "TAB":
            return '<span class="tab"></span>'
        if piece.label == "BR":
            return "<br>"
        if piece.label == "PAGE_BREAK":
            return '<span class="page-break" title="Page break"></span>'
        if piece.label == "IMAGE":
            return self._image(piece.node)
        if piece.label == "SHAPE":
            return '<span class="shape" title="Shape or text box (not editable)">shape</span>'
        if piece.label in ("FIELD", "TRACKED_CHANGE", "CONTENT_CONTROL"):
            cls = piece.label.lower().replace("_", "-")
            return f'<span class="{cls}" title="{piece.label.title()} (protected)">' \
                   f"{html.escape(piece.text)}</span>"
        return f'<span class="protected">{html.escape(piece.text)}</span>'

    def _chars_html(self, chars: list[_Char]) -> str:
        out: list[str] = []
        i = 0
        while i < len(chars):
            c = chars[i]
            pc = c.piece
            if pc.kind == "protected":
                j = i
                while j < len(chars) and chars[j].piece is pc and chars[j].status == c.status:
                    j += 1
                inner = self._protected_html(pc)
                out.append(self._wrap_status(inner, c.status))
                i = j
                continue
            j = i
            while (j < len(chars) and chars[j].piece.kind == "text"
                   and chars[j].piece.run is pc.run and chars[j].status == c.status
                   and chars[j].piece.container is pc.container):
                j += 1
            text = html.escape("".join(x.ch for x in chars[i:j]))
            css, tags = _run_css(pc.run)
            for t in tags:
                text = f"<{t}>{text}</{t}>"
            if css:
                text = f'<span style="{";".join(css)}">{text}</span>'
            if pc.container.tag == W.hyperlink:
                text = f'<a class="link">{text}</a>'
            out.append(self._wrap_status(text, c.status))
            i = j
        return "".join(out)

    @staticmethod
    def _wrap_status(inner: str, status: str) -> str:
        if status == "ins":
            return f"<ins>{inner}</ins>"
        if status == "del":
            return f"<del>{inner}</del>"
        if status == "fmt":
            return f'<span class="fmt-changed" title="Formatting changed">{inner}</span>'
        return inner

    # ------------------------------------------------------------- paragraphs
    def _para_open(self, p: etree._Element, extra_cls: str = "") -> tuple[str, str]:
        style = paragraph_style(self.pkg, p)
        low = style.lower()
        cls = ["para"]
        tag = "p"
        if low == "title":
            tag = "h1"
            cls.append("title")
        elif low.startswith("heading"):
            level = "".join(ch for ch in low if ch.isdigit()) or "1"
            tag = f"h{min(int(level) + 1, 6)}"
        elif "quote" in low:
            cls.append("quote")
        lvl = list_level(p)
        if lvl is not None or low.startswith("list"):
            cls.append("list-item")
            cls.append("numbered" if "number" in low else "bulleted")
            cls.append(f"lvl-{lvl or 0}")
        ppr = p.find(W.pPr)
        jc = ppr.find(qn("w:jc")) if ppr is not None else None
        style_attr = ""
        if jc is not None and jc.get(W.val) in ("center", "right", "both"):
            align = {"both": "justify"}.get(jc.get(W.val), jc.get(W.val))
            style_attr = f' style="text-align:{align}"'
        if extra_cls:
            cls.append(extra_cls)
        bid = self.ids.get(p)
        data = f' data-bid="{html.escape(bid)}"' if bid else ""
        return f'<{tag} class="{" ".join(cls)}"{style_attr}{data}>', f"</{tag}>"

    def paragraph(self, p: etree._Element, chars: list[_Char] | None = None,
                  extra_cls: str = "") -> str:
        if chars is None:
            chars = [_Char(ch, pc, "same") for pc in paragraph_view(p).pieces for ch in pc.text]
        open_tag, close_tag = self._para_open(p, extra_cls)
        body = self._chars_html(chars) or "&nbsp;"
        return f"{open_tag}{body}{close_tag}"

    # ------------------------------------------------------------------ tables
    @staticmethod
    def _cell_attrs(tc: etree._Element) -> tuple[str, bool]:
        tcpr = tc.find(W.tcPr)
        attrs, hidden = "", False
        if tcpr is not None:
            span = tcpr.find(W.gridSpan)
            if span is not None and (span.get(W.val) or "").isdigit():
                attrs += f' colspan="{span.get(W.val)}"'
            vm = tcpr.find(W.vMerge)
            if vm is not None and vm.get(W.val) in (None, "continue"):
                hidden = True
            fill = _hex(tcpr.find(qn("w:shd")), qn("w:fill"))
            if fill:
                attrs += f' style="background:#{fill}"'
        return attrs, hidden


@dataclass
class _Overlay:
    """Redline decorations layered over the rendering of the edited document."""

    para_html: dict[int, str] = field(default_factory=dict)  # id(after p) -> html
    row_cls: dict[int, str] = field(default_factory=dict)  # id(after tr) -> css class
    rows_after: dict[int, list[str]] = field(default_factory=dict)  # deleted rows
    rows_before: dict[int, list[str]] = field(default_factory=dict)


def _row_html(r: Renderer, tr: etree._Element, ov: _Overlay, row_id: str | None,
              cls: str = "", deleted: bool = False) -> str:
    cells = []
    for tc in tr.findall(W.tc):
        attrs, hidden = r._cell_attrs(tc)
        if hidden:
            continue
        inner = []
        for child in tc:
            if child.tag == W.p:
                if deleted:
                    inner.append(r.paragraph(child, chars=_all(child, "del")))
                else:
                    inner.append(ov.para_html.get(id(child)) or r.paragraph(child))
            elif child.tag == W.tbl:
                inner.append(_table_html(r, child, ov, deleted=deleted))
        cells.append(f"<td{attrs}>{''.join(inner)}</td>")
    data = f' data-row="{html.escape(row_id)}"' if row_id and not deleted else ""
    klass = f' class="{cls}"' if cls else ""
    return f"<tr{klass}{data}>{''.join(cells)}</tr>"


def _table_html(r: Renderer, tbl: etree._Element, ov: _Overlay, extra_cls: str = "",
                deleted: bool = False) -> str:
    tid = r.ids.get(tbl)
    rows = []
    for i, tr in enumerate(tbl.findall(W.tr)):
        rid = f"{tid}.r{i}" if tid else None
        rows += ov.rows_before.get(id(tr), [])
        rows.append(_row_html(r, tr, ov, rid, ov.row_cls.get(id(tr), ""), deleted))
        rows += ov.rows_after.get(id(tr), [])
    cls = "doc-table" + (f" {extra_cls}" if extra_cls else "")
    data = f' data-bid="{html.escape(tid)}"' if tid and not deleted else ""
    return f'<table class="{cls}"{data}>{"".join(rows)}</table>'


def _body_html(r: Renderer, pkg: DocxPackage, ov: _Overlay) -> str:
    out: list[str] = []
    for child in pkg.body:
        if child.tag == W.p:
            out.append(ov.para_html.get(id(child)) or r.paragraph(child))
        elif child.tag == W.tbl:
            out.append(_table_html(r, child, ov))
    return "".join(out)


def render_preview(pkg: DocxPackage) -> str:
    return _body_html(Renderer(pkg), pkg, _Overlay())


def render_redline(before: DocxPackage, after: DocxPackage, plan: EditPlan) -> str:
    """Render ``after`` with insertions/deletions/formatting changes marked."""
    oracle = replay(before, plan)
    expected = oracle.entries
    actual = document_stream(after)
    if [e.kind for e in expected] != [a.kind for a in actual]:
        return render_preview(after)  # verification would have failed; show plain
    r_after = Renderer(after)
    r_before = Renderer(before, with_ids=False)
    ov = _Overlay()
    for exp, act in zip(expected, actual):
        if exp.kind == "tr" and exp.before is None:
            ov.row_cls[id(act.element)] = "row-ins"
        if exp.kind != "p":
            continue
        if exp.before is None:
            ov.para_html[id(act.element)] = r_after.paragraph(
                act.element, extra_cls="block-ins", chars=_all(act.element, "ins"))
        elif exp.modified:
            ov.para_html[id(act.element)] = r_after.paragraph(
                act.element, chars=_merge(exp, exp.before.element, act.element))
    _place_removed(oracle.removed, expected, actual, r_before, r_after, ov)
    return _body_html(r_after, after, ov)


def _all(p: etree._Element, status: str) -> list[_Char]:
    return [_Char(ch, pc, status) for pc in paragraph_view(p).pieces for ch in pc.text]


def _merge(exp: Expected, b_el: etree._Element, a_el: etree._Element) -> list[_Char]:
    b_chars = [(ch, pc) for pc in paragraph_view(b_el).pieces for ch in pc.text]
    a_chars = [(ch, pc) for pc in paragraph_view(a_el).pieces for ch in pc.text]
    chars = exp.chars or []
    # origin of the next kept character at or after each position (to emit deletions
    # before the insertions that replace them: "~~old~~ new", like a redline)
    next_kept = [len(b_chars)] * (len(chars) + 1)
    for i in range(len(chars) - 1, -1, -1):
        o = chars[i].origin
        next_kept[i] = o if o is not None else next_kept[i + 1]
    out: list[_Char] = []
    k = 0  # next before index not yet emitted
    for i, (oc, (ch, pc)) in enumerate(zip(chars, a_chars)):
        if oc.origin is None:
            while k < next_kept[i]:
                out.append(_Char(b_chars[k][0], b_chars[k][1], "del"))
                k += 1
            out.append(_Char(ch, pc, "ins"))
            continue
        while k < oc.origin:
            out.append(_Char(b_chars[k][0], b_chars[k][1], "del"))
            k += 1
        k = oc.origin + 1
        out.append(_Char(ch, pc, "fmt" if oc.forced else "same"))
    while k < len(b_chars):
        out.append(_Char(b_chars[k][0], b_chars[k][1], "del"))
        k += 1
    return _tidy(out)


_TOKEN = re.compile(r"\w+|\s+|[^\w\s]", re.UNICODE)


def _fmt_key(c: _Char) -> tuple[bytes, str]:
    run = c.piece.run
    rpr = run.find(W.rPr) if run is not None else None
    return (etree.tostring(rpr, method="c14n") if rpr is not None else b"", c.piece.container.tag)


def _tokens(chars: list[_Char]) -> list[list[_Char]]:
    text = "".join(c.ch for c in chars)
    return [chars[m.start():m.end()] for m in _TOKEN.finditer(text)]


def _same_token(a: list[_Char], b: list[_Char]) -> bool:
    return ("".join(c.ch for c in a) == "".join(c.ch for c in b)
            and all(_fmt_key(x) == _fmt_key(y) for x, y in zip(a, b)))


def _tidy(chars: list[_Char]) -> list[_Char]:
    """Display-only: inside each replaced span, show words that are identical (same text
    and same formatting) before and after as unchanged, e.g. ~~6~~7 of 12 rather than
    ~~6 of 12~~7 of 12."""
    out: list[_Char] = []
    i = 0
    while i < len(chars):
        if chars[i].status not in ("del", "ins"):
            out.append(chars[i])
            i += 1
            continue
        j = i
        while j < len(chars) and chars[j].status in ("del", "ins"):
            j += 1
        dels = _tokens([c for c in chars[i:j] if c.status == "del"])
        inss = _tokens([c for c in chars[i:j] if c.status == "ins"])
        pre = 0
        while pre < min(len(dels), len(inss)) and _same_token(dels[pre], inss[pre]):
            pre += 1
        suf = 0
        while (suf < min(len(dels), len(inss)) - pre
               and _same_token(dels[-1 - suf], inss[-1 - suf])):
            suf += 1
        same = lambda toks: [_Char(c.ch, c.piece, "same") for t in toks for c in t]  # noqa: E731
        out += same(inss[:pre])
        out += [c for t in dels[pre:len(dels) - suf] for c in t]
        out += [c for t in inss[pre:len(inss) - suf] for c in t]
        out += same(inss[len(inss) - suf:])
        i = j
    return out


def _place_removed(removed, expected, actual, r_before: Renderer, r_after: Renderer,
                   ov: _Overlay) -> None:
    """Show deleted paragraphs, rows and tables (struck through) next to their nearest
    surviving sibling in the same container. Deleted pictures are shown inline."""
    para_map = {e.before.element: a.element for e, a in zip(expected, actual)
                if e.kind == "p" and e.before is not None}
    row_map = {e.before.element: a.element for e, a in zip(expected, actual)
               if e.kind == "tr" and e.before is not None}
    order = {id(item.element): i for i, item in enumerate(document_stream(r_before.pkg))}
    for el in sorted((x for x in removed if x.tag in (W.p, W.tr, W.tbl)),
                     key=lambda x: order.get(id(x), 0)):
        if el.tag == W.tr:
            html_del = _row_html(r_before, el, _Overlay(), None, "row-del", deleted=True)
            prev = _nearest(el, row_map, "previous")
            if prev is not None:
                ov.rows_after.setdefault(id(row_map[prev]), []).append(html_del)
            else:
                nxt = _nearest(el, row_map, "next")
                if nxt is not None:
                    ov.rows_before.setdefault(id(row_map[nxt]), []).append(html_del)
            continue
        if el.tag == W.tbl:
            html_del = _table_html(r_before, el, _Overlay(), "tbl-del", deleted=True)
        else:
            html_del = r_before.paragraph(el, chars=_all(el, "del"), extra_cls="block-del")
        prev = _nearest(el, para_map, "previous")
        if prev is not None:
            key = id(para_map[prev])
            ov.para_html[key] = (ov.para_html.get(key) or r_after.paragraph(para_map[prev])) \
                + html_del
            continue
        nxt = _nearest(el, para_map, "next")
        if nxt is not None:
            key = id(para_map[nxt])
            ov.para_html[key] = html_del + (ov.para_html.get(key)
                                            or r_after.paragraph(para_map[nxt]))


def _nearest(el: etree._Element, survivors: dict, direction: str):
    node = el.getprevious() if direction == "previous" else el.getnext()
    while node is not None and node not in survivors:
        node = node.getprevious() if direction == "previous" else node.getnext()
    return node

