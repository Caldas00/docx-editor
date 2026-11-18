"""HTML preview of a document, optionally with a redline of an edit.

The look comes from the document itself (see `styles.py`): its fonts, sizes, colours,
spacing, indentation, shading, borders, list and heading numbering, table borders and cell
margins, content controls, text boxes and lines. The web UI then lays it out on pages. It
is still a preview - line breaking differs a little from Word's. The redline reuses the
oracle's character alignment, so what is highlighted is exactly what the plan changed.
"""

from __future__ import annotations

import base64
import html
import mimetypes
import re
from dataclasses import dataclass, field

from lxml import etree

from .model import Piece, build_index, paragraph_view, text_boxes
from .ns import MC, R_EMBED, W, qn
from .ops import EditPlan, is_blank_paragraph
from .oracle import Expected, StreamItem, document_stream, replay, stream_of, text_box_name
from .package import DocxPackage
from .styles import StyleSheet, border_css, is_hidden, run_css
from .styles import _merge as _merge_props

A_BLIP = qn("a:blip")
WP_EXTENT = qn("wp:extent")
WP_ANCHOR = qn("wp:anchor")
TXBX = qn("w:txbxContent")
EMU_PX = 9525


def _emu(value: str | None) -> float:
    return int(value) / EMU_PX if value and value.lstrip("-").isdigit() else 0.0


def _emu_raw(el, attr: str) -> int:
    raw = el.get(attr) if el is not None else None
    return int(raw) if raw and raw.lstrip("-").isdigit() else 0
_WP14 = "{http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
MAX_IMAGE_BYTES = 4 * 1024 * 1024


@dataclass
class _Char:
    ch: str
    piece: Piece
    status: str  # "same" | "ins" | "del" | "fmt"


def _on(el) -> bool:
    return el is not None and el.get(W.val, "true") not in ("0", "false", "off", "none")


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


_PAGE_FIELD = re.compile(r"\s*(PAGE|NUMPAGES|SECTIONPAGES)\b", re.I)


def _page_number_texts(roots: list[etree._Element]) -> dict[etree._Element, tuple[bool, str]]:
    """The w:t elements holding a page-number field's result -> (is it the first one,
    "page" or "numpages").

    Word stores whatever number was on screen when the file was saved ("2", "0", "vi"),
    so the preview shows "#" instead of a stale, misleading number.
    """
    marks: dict[etree._Element, tuple[bool, str]] = {}

    def kind_of(instr: str) -> str:
        return "page" if _PAGE_FIELD.match(instr).group(1).upper() == "PAGE" else "numpages"

    for root in roots:
        for p in root.iter(W.p):
            stack: list[list] = []  # [instruction, in_result, seen_first]
            for el in p.iter(W.fldChar, W.instrText, W.t):
                if el.tag == W.fldChar:
                    kind = el.get(W.fldCharType)
                    if kind == "begin":
                        stack.append(["", False, False])
                    elif kind == "separate" and stack:
                        stack[-1][1] = True
                    elif kind == "end" and stack:
                        stack.pop()
                elif not stack:
                    continue
                elif el.tag == W.instrText and not stack[-1][1]:
                    stack[-1][0] += el.text or ""
                elif el.tag == W.t and stack[-1][1] and _PAGE_FIELD.match(stack[-1][0]):
                    marks[el] = (not stack[-1][2], kind_of(stack[-1][0]))
                    stack[-1][2] = True
            for simple in p.iter(qn("w:fldSimple")):
                instr = simple.get(qn("w:instr")) or ""
                if _PAGE_FIELD.match(instr):
                    for n, t in enumerate(simple.iter(W.t)):
                        marks[t] = (n == 0, kind_of(instr))
    return marks


class Renderer:
    def __init__(self, pkg: DocxPackage, with_ids: bool = True) -> None:
        self.pkg = pkg
        self._img_cache: dict[str, str] = {}
        self._page_fields = _page_number_texts([pkg.body] + [hf.root for hf in pkg.hf_parts])
        self.sheet = StyleSheet(pkg)
        self.page = page_setup(pkg)
        self.overlay: _Overlay | None = None  # the redline marks, for text inside shapes
        self._props: dict[etree._Element, tuple[dict, dict]] = {}
        self.labels = self.sheet.number_labels([pkg.body] + [hf.root for hf in pkg.hf_parts])
        # first block of every section that starts on a new page
        self.break_before: set[etree._Element] = set()
        for n, (blocks, sect) in enumerate(_sections(pkg.body)):
            stype = sect.find(qn("w:type")) if sect is not None else None
            if n and blocks and (stype is None or stype.get(W.val) in (None, "nextPage", "oddPage",
                                                                      "evenPage")):
                self.break_before.add(blocks[0])
        # block ids as data attributes, so the UI can tell the agent what the user selected
        self.ids: dict[etree._Element, str] = (
            {b.element: b.id for b in build_index(pkg).blocks} if with_ids else {})

    # ---------------------------------------------------------------- pieces
    def _image(self, node: etree._Element) -> str:
        blip = node.find(".//" + A_BLIP)
        rid = blip.get(R_EMBED) if blip is not None else None
        root = node
        while root.getparent() is not None:
            root = root.getparent()
        owner = next((hf.part_name for hf in self.pkg.hf_parts if hf.root is root),
                     self.pkg.main_part_name)
        part = self.pkg.resolve_part_from(owner, rid) if rid else None
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

    def props(self, p: etree._Element) -> tuple[dict, dict]:
        if p not in self._props:
            self._props[p] = self.sheet.paragraph_props(p)
        return self._props[p]

    def _run_style(self, run: etree._Element | None) -> tuple[str, bool]:
        """(inline css for what the run adds to its paragraph, is the text hidden)."""
        if run is None:
            return "", False
        p = next((a for a in run.iterancestors() if a.tag == W.p), None)
        base = self.props(p)[1] if p is not None else {}
        if is_hidden(self.sheet.run_props(run, base)):
            return "", True
        layer: dict[str, dict] = {}
        own = run.find(W.rPr)
        rs = own.find(qn("w:rStyle")) if own is not None else None
        if rs is not None and rs.get(W.val) == "Hyperlink" and p is not None and \
                (self.sheet._para_style_id(p) or "").upper().startswith("TOC"):
            rs = None  # Word draws table-of-contents links in the TOC style, not as links
        if rs is not None:
            for st in self.sheet._chain(rs.get(W.val), "r"):
                _merge_props(layer, st.find(W.rPr))
        _merge_props(layer, own)
        return ";".join(run_css(layer, self.sheet)), False

    def _protected_html(self, piece: Piece) -> str:
        if piece.label == "TAB" or piece.text == "\t":  # a tab inside a field is still a tab
            if piece is getattr(self, "_fill_tab", None):
                css, _ = self._run_style(piece.run)
                p = next((a for a in piece.run.iterancestors() if a.tag == W.p), None) \
                    if piece.run is not None else None
                eff = self.sheet.run_props(piece.run, self.props(p)[1]) if p is not None else {}
                u = eff.get("u", {}).get("val")
                line = "border-bottom:1px solid currentColor" if u and u != "none" else ""
                return f'<span class="tab-fill" style="{html.escape(css + ";" + line)}"></span>'
            return '<span class="tab"></span>'
        if piece.label == "BR":
            return "<br>"
        if piece.label == "COLUMN_BREAK":
            return ""  # the layout puts the following text in the next column
        if piece.label == "PAGE_BREAK":
            return '<span class="page-break" title="Page break"></span>'
        if piece.label == "IMAGE":
            return self._image(piece.node)
        if piece.label == "SHAPE":
            return self._shape(piece.node)
        if piece.label == "FIELD" and piece.node in self._page_fields:
            first, kind = self._page_fields[piece.node]
            if not first:
                return ""
            # the page view fills in the real number on each page
            return (f'<span class="field" data-field="{kind}" title="Page number (Word fills '
                    'it in)">#</span>')
        css, hidden = self._run_style(piece.run)
        if hidden:
            return ""
        style = f' style="{html.escape(css)}"' if css else ""
        if piece.label in ("FIELD", "TRACKED_CHANGE", "CONTENT_CONTROL"):
            cls = piece.label.lower().replace("_", "-")
            return f'<span class="{cls}"{style}>{html.escape(piece.text)}</span>'
        return f'<span class="protected"{style}>{html.escape(piece.text)}</span>'

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
            css, hidden = self._run_style(pc.run)
            if hidden:
                i = j
                continue
            if css:
                text = f'<span style="{html.escape(css)}">{text}</span>'
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
    def _same_style(self, a: etree._Element | None, b: etree._Element) -> bool:
        return a is not None and a.tag == W.p and \
            self.sheet._para_style_id(a) == self.sheet._para_style_id(b)

    def _para_open(self, p: etree._Element, extra_cls: str = "") -> tuple[str, str]:
        ppr, rpr = self.props(p)
        label = self.labels.get(p)
        css = self.sheet.paragraph_css(ppr, rpr, self._same_style(p.getprevious(), p),
                                       self._same_style(p.getnext(), p), label)
        cls = ["para"]
        outline = ppr.get("outlineLvl", {}).get("val")
        role = ""
        if outline is not None and outline.isdigit() and int(outline) < 9:
            role = f' role="heading" aria-level="{min(int(outline) + 1, 6)}"'
        if p in self.break_before:  # a section that starts on a new page
            cls.append("break-before")
        if "pageBreakBefore" in ppr and ppr["pageBreakBefore"].get("val", "1") not in ("0", "false"):
            cls.append("break-before")
        if extra_cls:
            cls.append(extra_cls)
        right = [t for t in ppr.get("tabs", {}).get("list", []) if t.get("val") in ("right", "end")]
        if right:  # e.g. a table of contents line: "Title ...... 7"
            cls.append("has-fill")
            leader = right[-1].get("leader")
            if leader in ("dot", "hyphen", "underscore", "middleDot"):
                cls.append(f"leader-{'dot' if leader == 'middleDot' else leader}")
        bid = self.ids.get(p)
        data = f' data-bid="{html.escape(bid)}"' if bid else ""
        style = f' style="{html.escape(";".join(css))}"'
        # a <div>, not a <p>: paragraphs can hold text boxes that hold paragraphs, and the
        # HTML parser would close an outer <p> at the first inner one
        return f'<div class="{" ".join(cls)}"{style}{role}{data}>', "</div>"

    def _label_html(self, p: etree._Element) -> str:
        label = self.labels.get(p)
        if label is None or not label.text:
            return ""
        lv: dict[str, dict] = {}
        _merge_props(lv, label.level.rpr)
        css = run_css(lv, self.sheet)
        ppr, _ = self.props(p)
        ind = dict(ppr.get("ind", {}))
        if label.level.ppr is not None and label.level.ppr.find(qn("w:ind")) is not None:
            for k, v in label.level.ppr.find(qn("w:ind")).attrib.items():
                ind.setdefault(k.rsplit("}", 1)[-1], v)
        raw = str(ind.get("hanging") or "0")
        hanging = int(raw) / 15 if raw.isdigit() else 0
        if label.level.suffix == "tab":
            css.append(f"min-width:{hanging:.1f}px" if hanging > 4 else "margin-right:0.6em")
        elif label.level.suffix == "space":
            css.append("margin-right:0.3em")
        return (f'<span class="num-label" style="{html.escape(";".join(css))}">'
                f"{html.escape(label.text)}</span>")

    def paragraph(self, p: etree._Element, chars: list[_Char] | None = None,
                  extra_cls: str = "") -> str:
        if chars is None:
            chars = [_Char(ch, pc, "same") for pc in paragraph_view(p).pieces for ch in pc.text]
        open_tag, close_tag = self._para_open(p, extra_cls)
        tabs = [c.piece for c in chars if c.piece.text == "\t"]
        self._fill_tab = tabs[-1] if tabs and "has-fill" in open_tag else None
        body = self._chars_html(chars)
        self._fill_tab = None
        return f"{open_tag}{self._label_html(p)}{body or '&nbsp;'}{close_tag}"

    # --------------------------------------------------------- shapes / text boxes
    def _shape(self, node: etree._Element) -> str:
        """A drawing that is not a single picture: a group of shapes, a filled or outlined
        shape, a text box or a line, drawn at its size. Shapes anchored to the page or a
        paragraph carry their position; the web UI places them on the page."""
        branch = node
        if node.tag == MC.AlternateContent:  # prefer the modern drawing over the VML fallback
            for tag in ("mc:Choice", "mc:Fallback"):
                found = node.find(qn(tag))
                if found is not None:
                    branch = found
                    break
        frame = branch.find(".//" + WP_ANCHOR)
        if frame is None:
            frame = branch.find(".//" + qn("wp:inline"))
        ext = frame.find(WP_EXTENT) if frame is not None else None
        w = _emu(ext.get("cx")) if ext is not None else 0
        h = _emu(ext.get("cy")) if ext is not None else 0
        pct_w = branch.find(f".//{_WP14}sizeRelH/{_WP14}pctWidth")
        if pct_w is not None and (pct_w.text or "").isdigit() and int(pct_w.text) > 0:
            w = int(pct_w.text) / 100000 * self.page["width"]
        data = branch.find(f".//{_A}graphicData")
        shape = next((c for c in data if isinstance(c.tag, str)), None) if data is not None else None
        if shape is None:  # VML only (very old files): show any text box it has
            box = branch.find(".//" + TXBX)
            if box is None:
                return ""
            content = (f'<span class="textbox" style="width:{w:.0f}px">'
                       f"{_blocks_html(self, box, self.overlay or _Overlay())}</span>")
        else:
            content = self._draw(shape, w, h)
            if not content:
                return ""
        anchor = branch.find(".//" + WP_ANCHOR)
        if anchor is None:
            return f'<span class="drawing" style="width:{w:.1f}px;height:{h:.1f}px">{content}</span>'
        return self._anchored(anchor, content, w, h)

    def _draw(self, shape: etree._Element, w: float, h: float) -> str:
        """One shape, picture or group, `w` x `h` px, positioned at 0,0 of its box."""
        kind = shape.tag.rsplit("}", 1)[-1]
        if kind in ("wgp", "grpSp"):
            xfrm = shape.find(f"{{*}}grpSpPr/{_A}xfrm")
            ext, choff, chext = (xfrm.find(f"{_A}{t}") if xfrm is not None else None
                                 for t in ("ext", "chOff", "chExt"))
            cx = _emu_raw(chext, "cx") or _emu_raw(ext, "cx") or 1
            cy = _emu_raw(chext, "cy") or _emu_raw(ext, "cy") or 1
            ox, oy = _emu_raw(choff, "x"), _emu_raw(choff, "y")
            sx, sy = (w * EMU_PX / cx) if w else 1, (h * EMU_PX / cy) if h else 1
            parts = []
            for child in shape:
                if not isinstance(child.tag, str) or child.tag.rsplit("}", 1)[-1] not in (
                        "wsp", "pic", "grpSp"):
                    continue
                cxf = child.find(f".//{_A}xfrm")
                off, cext = (cxf.find(f"{_A}{t}") if cxf is not None else None
                             for t in ("off", "ext"))
                left = (_emu_raw(off, "x") - ox) * sx / EMU_PX
                top = (_emu_raw(off, "y") - oy) * sy / EMU_PX
                cw, ch = _emu_raw(cext, "cx") * sx / EMU_PX, _emu_raw(cext, "cy") * sy / EMU_PX
                inner = self._draw(child, cw, ch)
                if inner:
                    parts.append(f'<span class="shape-part" style="left:{left:.1f}px;top:{top:.1f}px;'
                                 f'width:{cw:.1f}px;height:{ch:.1f}px">{inner}</span>')
            return (f'<span class="shape-group" style="width:{w:.1f}px;height:{h:.1f}px">'
                    f'{"".join(parts)}</span>') if parts else ""
        if kind == "pic":
            return self._image(shape).replace("<img ", f'<img style="width:{w:.1f}px;height:{h:.1f}px" ', 1) \
                if shape.find(".//" + A_BLIP) is not None else ""
        if kind != "wsp":
            return ""
        sppr = shape.find("{*}spPr")
        geoms = [g.get("prst") for g in shape.iter(f"{_A}prstGeom")]
        css = [f"width:{w:.1f}px", f"height:{h:.1f}px"]
        fill = self._fill(sppr.find(f"{_A}solidFill") if sppr is not None else None)
        if fill:
            css.append(f"background-color:{fill}")
        line = sppr.find(f"{_A}ln") if sppr is not None else None
        stroke = None
        if line is not None and line.find(f"{_A}noFill") is None:
            stroke = self._fill(line.find(f"{_A}solidFill"))
            lw = max(int(line.get("w", "9525") or 9525) / EMU_PX, 0.75)
        if geoms and all(g in ("line", "straightConnector1") for g in geoms) or \
                (h <= 4 and not fill and shape.find(".//" + TXBX) is None):
            color = stroke or fill or "#7f7f7f"
            return f'<span class="shape-line" style="width:{w:.1f}px;border-top:1px solid {color}"></span>'
        if stroke:
            css.append(f"outline:{lw:.1f}px solid {stroke};outline-offset:-{lw:.1f}px")
        if geoms and geoms[0] in ("roundRect",):
            css.append("border-radius:8px")
        elif geoms and geoms[0] in ("ellipse",):
            css.append("border-radius:50%")
        box = shape.find(f".//{TXBX}")
        inner = ""
        if box is not None:
            body = shape.find("{*}bodyPr")
            ins = {k: (int(body.get(k)) / EMU_PX if body is not None and (body.get(k) or "").isdigit()
                       else d) for k, d in (("lIns", 9.6), ("tIns", 4.8), ("rIns", 9.6), ("bIns", 4.8))}
            css.append(f"padding:{ins['tIns']:.1f}px {ins['rIns']:.1f}px {ins['bIns']:.1f}px "
                       f"{ins['lIns']:.1f}px")
            anchor_v = body.get("anchor") if body is not None else None
            css.append("justify-content:" + {"b": "flex-end", "ctr": "center"}.get(anchor_v or "",
                                                                                 "flex-start"))
            inner = _blocks_html(self, box, self.overlay or _Overlay())
        if not (fill or stroke or inner):
            return ""
        return f'<span class="textbox" style="{";".join(css)}">{inner}</span>'

    def _fill(self, solid: etree._Element | None) -> str | None:
        """A DrawingML solid fill as CSS (rgb, theme scheme colour, luminance changes)."""
        if solid is None:
            return None
        clr = next((c for c in solid if isinstance(c.tag, str)), None)
        if clr is None:
            return None
        name = clr.tag.rsplit("}", 1)[-1]
        if name == "srgbClr":
            base = clr.get("val")
        elif name == "schemeClr":
            slot = {"tx1": "dk1", "bg1": "lt1", "tx2": "dk2", "bg2": "lt2"}.get(clr.get("val"),
                                                                            clr.get("val"))
            base = self.sheet.colors.get(slot or "")
        elif name == "sysClr":
            base = clr.get("lastClr")
        elif name == "prstClr":
            base = {"black": "000000", "white": "FFFFFF", "red": "FF0000", "green": "008000",
                    "blue": "0000FF", "gray": "808080"}.get(clr.get("val") or "")
        else:
            base = None
        if not base or not _HEX.fullmatch(base):
            return None
        mods = {c.tag.rsplit("}", 1)[-1]: int(c.get("val", "0")) for c in clr
                if isinstance(c.tag, str) and (c.get("val") or "").lstrip("-").isdigit()}
        if "lumMod" in mods or "lumOff" in mods or "tint" in mods or "shade" in mods:
            import colorsys
            r, g, b = (int(base[i:i + 2], 16) / 255 for i in (0, 2, 4))
            hue, light, sat = colorsys.rgb_to_hls(r, g, b)
            light = light * mods.get("lumMod", 100000) / 100000 + mods.get("lumOff", 0) / 100000
            if "tint" in mods:
                light = light * mods["tint"] / 100000 + (1 - mods["tint"] / 100000)
            if "shade" in mods:
                light = light * mods["shade"] / 100000
            rgb = colorsys.hls_to_rgb(hue, min(1, max(0, light)), sat)
            base = "".join(f"{round(c * 255):02X}" for c in rgb)
        alpha = mods.get("alpha")
        if alpha is not None and alpha < 100000:
            r, g, b = (int(base[i:i + 2], 16) for i in (0, 2, 4))
            return f"rgba({r},{g},{b},{alpha / 100000:.2f})"
        return f"#{base}"

    def _anchored(self, anchor: etree._Element, content: str, w: float, h: float) -> str:
        def axis(tag: str) -> tuple[str, str, str]:
            pos = anchor.find(".//" + qn(f"wp:position{tag}"))
            if pos is None:
                return "", "", ""
            rel = pos.get("relativeFrom") or ""
            off = pos.find(qn("wp:posOffset"))
            pct = pos.find(f"{_WP14}pct{'PosH' if tag == 'H' else 'PosV'}Offset")
            align = pos.find(qn("wp:align"))
            size = self.page["width"] if tag == "H" else self.page["height"]
            if pct is not None and (pct.text or "").lstrip("-").isdigit():
                return rel, f"{int(pct.text) / 100000 * size:.1f}", ""
            if off is not None and (off.text or "").lstrip("-").isdigit():
                return rel, f"{int(off.text) / EMU_PX:.1f}", ""
            return rel, "", (align.text or "") if align is not None else ""
        rh, x, ah = axis("H")
        rv, y, av = axis("V")
        wrap = next((c.tag.rsplit("}", 1)[-1] for c in anchor if isinstance(c.tag, str)
                     and c.tag.rsplit("}", 1)[-1].startswith("wrap")), "wrapNone")
        absolute = rh in ("page", "margin", "leftMargin", "rightMargin") and \
            rv in ("page", "margin", "topMargin", "bottomMargin")
        # offset of the shape from the paragraph's text area, for shapes kept in the flow
        left = (float(x) - (self.page["left"] if rh == "page" else 0)) if x else 0
        if ah == "center":
            left = (self.page["width"] - self.page["left"] - self.page["right"] - w) / 2
        top = float(y) if y and rv in ("paragraph", "line") else 0
        if not absolute and wrap in ("wrapSquare", "wrapTight", "wrapThrough"):
            side = "right" if ah == "right" or (x and float(x) > 200) else "left"
            return f'<span class="floating" style="float:{side}">{content}</span>'
        if not absolute and wrap == "wrapTopAndBottom":
            return (f'<span class="floating block" style="margin-left:{left:.1f}px;'
                    f'margin-top:{max(top, 0):.1f}px;width:{w:.1f}px;height:{h:.1f}px">'
                    f"{content}</span>")
        attrs = " ".join(f'data-{k}="{html.escape(v)}"' for k, v in
                         (("rh", rh), ("rv", rv), ("x", x), ("y", y), ("ah", ah), ("av", av),
                          ("w", f"{w:.1f}"), ("h", f"{h:.1f}")))
        return f'<span class="anchored" {attrs}>{content}</span>'

    # ------------------------------------------------------------------ tables
    def table_open(self, tbl: etree._Element, extra_cls: str, data: str) -> str:
        tblpr = tbl.find(qn("w:tblPr"))
        css = ["border-collapse:collapse"]
        grid = [int(g.get(W.w_attr)) / 15 for g in tbl.findall(f"{qn('w:tblGrid')}/{qn('w:gridCol')}")
                if (g.get(W.w_attr) or "").isdigit()]
        tw = tblpr.find(qn("w:tblW")) if tblpr is not None else None
        width = None
        if tw is not None and tw.get(qn("w:type")) == "dxa" and (tw.get(W.w_attr) or "").isdigit():
            width = int(tw.get(W.w_attr)) / 15
        elif tw is not None and tw.get(qn("w:type")) == "pct" and (tw.get(W.w_attr) or "").isdigit():
            css.append(f"width:{int(tw.get(W.w_attr)) / 50:.1f}%")
        if width is None and grid:
            width = sum(grid)
        if width:
            css.append(f"width:{width:.1f}px")
        if grid:
            css.append("table-layout:fixed")
        ind = tblpr.find(qn("w:tblInd")) if tblpr is not None else None
        jc = tblpr.find(qn("w:jc")) if tblpr is not None else None
        if jc is not None and jc.get(W.val) == "center":
            css.append("margin-left:auto;margin-right:auto")
        elif ind is not None and (ind.get(W.w_attr) or "").lstrip("-").isdigit():
            css.append(f"margin-left:{int(ind.get(W.w_attr)) / 15:.1f}px")
        cols = "".join(f'<col style="width:{g:.1f}px">' for g in grid)
        cls = "doc-table" + (f" {extra_cls}" if extra_cls else "")
        return f'<table class="{cls}" style="{";".join(css)}"{data}><colgroup>{cols}</colgroup>'

    def cell_attrs(self, tc: etree._Element, r: int, last_row: bool, col: int, span: int,
                   ncols: int, rowspan: int) -> str:
        look = self.sheet.table_look(tc.getparent().getparent())
        parts = self.sheet.cell_parts(tc, look)
        tcpr: dict[str, dict] = {}
        for part in parts:
            _merge_props(tcpr, part.get("tcPr"))
        _merge_props(tcpr, tc.find(W.tcPr))
        css = []
        own = tcpr.get("tcBorders", {})
        edges = {"top": "top" if r == 0 else "insideH",
                 "bottom": "bottom" if last_row else "insideH",
                 "left": "left" if col == 0 else "insideV",
                 "right": "right" if col + span >= ncols else "insideV"}
        for side, edge in edges.items():
            b = own.get(side) or own.get({"left": "start", "right": "end"}.get(side, "")) or \
                look.borders.get(edge) or look.borders.get({"left": "start", "right": "end"}.get(edge, ""))
            rule = border_css(b)
            css.append(f"border-{side}:{rule or 'none'}")
        mar = {**look.margins, **tcpr.get("tcMar", {})}
        for side, default in (("top", 0), ("bottom", 0), ("left", 108), ("right", 108)):
            m = mar.get(side) or mar.get({"left": "start", "right": "end"}.get(side, "")) or {}
            raw = m.get("w")
            twips = int(raw) if (raw or "").isdigit() and m.get("type", "dxa") == "dxa" else default
            css.append(f"padding-{side}:{twips / 15:.1f}px")
        fill = _hex_val(tcpr.get("shd", {}).get("fill"))
        if fill and tcpr.get("shd", {}).get("val") != "nil":
            css.append(f"background-color:#{fill}")
        va = tcpr.get("vAlign", {}).get("val")
        if va in ("center", "bottom"):
            css.append(f"vertical-align:{'middle' if va == 'center' else 'bottom'}")
        attrs = f' style="{";".join(css)}"'
        if span > 1:
            attrs += f' colspan="{span}"'
        if rowspan > 1:
            attrs += f' rowspan="{rowspan}"'
        return attrs


def _hex_val(value: str | None) -> str | None:
    return value if value and _HEX.fullmatch(value) else None


def _grid_layout(tbl: etree._Element) -> tuple[list[list[tuple[etree._Element, int, int]]], int]:
    """Per row: (cell, first grid column, span), and the number of grid columns."""
    rows = []
    ncols = len(tbl.findall(f"{qn('w:tblGrid')}/{qn('w:gridCol')}"))
    for tr in tbl.findall(W.tr):
        trpr = tr.find(qn("w:trPr"))
        before = trpr.find(qn("w:gridBefore")) if trpr is not None else None
        col = int(before.get(W.val)) if before is not None and (before.get(W.val) or "").isdigit() else 0
        cells = []
        for tc in tr.findall(W.tc):
            tcpr = tc.find(W.tcPr)
            gs = tcpr.find(W.gridSpan) if tcpr is not None else None
            span = int(gs.get(W.val)) if gs is not None and (gs.get(W.val) or "").isdigit() else 1
            cells.append((tc, col, span))
            col += span
        ncols = max(ncols, col)
        rows.append(cells)
    return rows, ncols


def _vmerge(tc: etree._Element) -> str | None:
    tcpr = tc.find(W.tcPr)
    vm = tcpr.find(W.vMerge) if tcpr is not None else None
    if vm is None:
        return None
    return "restart" if vm.get(W.val) == "restart" else "continue"


@dataclass
class _Overlay:
    """Redline decorations layered over the rendering of the edited document."""

    para_html: dict[int, str] = field(default_factory=dict)  # id(after p) -> html
    row_cls: dict[int, str] = field(default_factory=dict)  # id(after tr) -> css class
    rows_after: dict[int, list[str]] = field(default_factory=dict)  # deleted rows
    rows_before: dict[int, list[str]] = field(default_factory=dict)
    table_cls: dict[int, str] = field(default_factory=dict)  # id(after tbl) -> css class


def _row_html(r: Renderer, tr: etree._Element, ov: _Overlay, row_id: str | None,
              cls: str = "", deleted: bool = False) -> str:
    tbl = tr.getparent()
    layout, ncols = _grid_layout(tbl)
    rows = tbl.findall(W.tr)
    ri = rows.index(tr) if tr in rows else 0
    cells = []
    for tc, col, span in layout[ri]:
        if _vmerge(tc) == "continue":
            continue
        rowspan = 1
        if _vmerge(tc) == "restart":
            for below in layout[ri + 1:]:
                cont = next((c for c, cc, _s in below if cc == col), None)
                if cont is None or _vmerge(cont) != "continue":
                    break
                rowspan += 1
        last = ri + rowspan - 1 >= len(rows) - 1
        attrs = r.cell_attrs(tc, ri, last, col, span, ncols, rowspan)
        inner = []
        for child in _content_children(tc):
            if child.tag == W.p:
                if deleted:
                    inner.append(r.paragraph(child, chars=_all(child, "del")))
                else:
                    inner.append(ov.para_html.get(id(child)) or r.paragraph(child))
            elif child.tag == W.tbl:
                inner.append(_table_html(r, child, ov, deleted=deleted))
        cells.append(f"<td{attrs}>{''.join(inner)}</td>")
    trpr = tr.find(qn("w:trPr"))
    hgt = trpr.find(qn("w:trHeight")) if trpr is not None else None
    style = (f' style="height:{int(hgt.get(W.val)) / 15:.1f}px"'
             if hgt is not None and (hgt.get(W.val) or "").isdigit() else "")
    data = f' data-row="{html.escape(row_id)}"' if row_id and not deleted else ""
    klass = f' class="{cls}"' if cls else ""
    return f"<tr{klass}{style}{data}>{''.join(cells)}</tr>"


def _table_html(r: Renderer, tbl: etree._Element, ov: _Overlay, extra_cls: str = "",
                deleted: bool = False) -> str:
    tid = r.ids.get(tbl)
    extra_cls = extra_cls or ov.table_cls.get(id(tbl), "")
    rows = []
    for i, tr in enumerate(tbl.findall(W.tr)):
        rid = f"{tid}.r{i}" if tid else None
        rows += ov.rows_before.get(id(tr), [])
        rows.append(_row_html(r, tr, ov, rid, ov.row_cls.get(id(tr), ""), deleted))
        rows += ov.rows_after.get(id(tr), [])
    data = f' data-bid="{html.escape(tid)}"' if tid and not deleted else ""
    return f'{r.table_open(tbl, extra_cls, data)}{"".join(rows)}</table>'


def _content_children(container: etree._Element):
    """Block children, looking through content controls (a cover page or a table of
    contents is often wrapped in one)."""
    for child in container:
        if child.tag == W.sdt:
            content = child.find(W.sdtContent)
            if content is not None:
                yield from _content_children(content)
        elif child.tag in (W.p, W.tbl):
            yield child


def _block_html(r: Renderer, child: etree._Element, ov: _Overlay) -> str:
    if child.tag == W.p:
        return ov.para_html.get(id(child)) or r.paragraph(child)
    return _table_html(r, child, ov)


def _blocks_html(r: Renderer, root: etree._Element, ov: _Overlay) -> str:
    if root.tag != W.body:
        return "".join(_block_html(r, c, ov) for c in _content_children(root))
    out: list[str] = []
    for blocks, sect in _sections(root):
        cols = sect.find(qn("w:cols")) if sect is not None else None
        num = int(cols.get(qn("w:num"))) if cols is not None and (cols.get(qn("w:num")) or "").isdigit() else 1
        if num < 2 or not blocks:
            out.extend(_block_html(r, c, ov) for c in blocks)
        else:
            out.append(_columns_html(r, blocks, cols, num, ov))
    return "".join(out)


def _sections(body: etree._Element) -> list[tuple[list[etree._Element], etree._Element | None]]:
    """The body's blocks grouped by section, each with the sectPr that describes it (a
    section's sectPr sits in its last paragraph; the last one is the body's own)."""
    sections: list[tuple[list[etree._Element], etree._Element | None]] = []
    cur: list[etree._Element] = []
    for child in _content_children(body):
        cur.append(child)
        sp = child.find(f"{W.pPr}/{W.sectPr}") if child.tag == W.p else None
        if sp is not None:
            sections.append((cur, sp))
            cur = []
    if cur or not sections:
        sections.append((cur, body.find(W.sectPr)))
    return sections


def _column_break(p: etree._Element) -> str | None:
    """Where a paragraph breaks to the next column: "start", "end" or None."""
    if p.tag != W.p:
        return None
    text = ""
    for pc in paragraph_view(p).pieces:
        if pc.label == "COLUMN_BREAK":
            return "end" if text.strip() else "start"
        text += pc.text if pc.kind == "text" else ""
    return None


def _columns_html(r: Renderer, blocks: list[etree._Element], cols: etree._Element, num: int,
                  ov: _Overlay) -> str:
    """A section laid out in columns. With explicit column breaks (common in documents
    converted from PDF) each column gets exactly its text; otherwise the text flows."""
    widths = [int(c.get(W.w_attr)) / 15 for c in cols.findall(qn("w:col"))
              if (c.get(W.w_attr) or "").isdigit()]
    gaps = [int(c.get(qn("w:space"))) / 15 if (c.get(qn("w:space")) or "").isdigit() else 0
            for c in cols.findall(qn("w:col"))]
    space = int(cols.get(qn("w:space"))) / 15 if (cols.get(qn("w:space")) or "").isdigit() else 48
    first = " break-before" if blocks[0] in r.break_before else ""
    if not any(_column_break(b) for b in blocks):
        return (f'<div class="section-cols flow{first}" style="column-count:{num};'
                f'column-gap:{space:.1f}px">{"".join(_block_html(r, c, ov) for c in blocks)}</div>')
    columns: list[list[str]] = [[] for _ in range(num)]
    k = 0
    for b in blocks:
        where = _column_break(b)
        if where == "start" and columns[k] and k < num - 1:
            k += 1
        columns[k].append(_block_html(r, b, ov))
        if where == "end" and k < num - 1:
            k += 1
    parts = []
    for i, html_col in enumerate(columns):
        style = f"width:{widths[i]:.1f}px;flex:none" if i < len(widths) else "flex:1"
        if i < num - 1:
            style += f";margin-right:{(gaps[i] if i < len(gaps) and gaps[i] else 0 if widths else space):.1f}px"
        parts.append(f'<div class="col" style="{style}">{"".join(html_col)}</div>')
    return f'<div class="section-cols{first}">{"".join(parts)}</div>'


_USE_ORDER = {"default": 0, "first": 1, "even": 2}
_USE_WORDS = {"first": "first page", "even": "even pages"}
_SHAPE_CHIP = re.compile(r'<span class="shape"[^>]*>shape</span>')
_MARKUP = re.compile(r"<[^>]+>")
_BLOCK_IDS = re.compile(r' data-(?:bid|row)="[^"]*"')
_CHANGE_MARKS = ("<ins", "<del", "block-", "fmt-changed", "row-ins", "row-del", "tbl-")


def _shows_something(fragment: str) -> bool:
    """Is there anything worth showing: text, a picture or a change mark?

    A header that only holds a decorative shape (a line, a logo frame, a text box we
    cannot edit) would otherwise appear as an empty box labelled "shape".
    """
    if "<img" in fragment or any(mark in fragment for mark in _CHANGE_MARKS) or \
            "shape-line" in fragment or "textbox" in fragment:
        return True
    text = _MARKUP.sub("", _SHAPE_CHIP.sub("", fragment))
    return bool(html.unescape(text).strip())


def _hf_label(kind: str, uses: list[str], sections: int) -> str:
    """"Header", "Footer · first page", "Header · section 2, even pages"."""
    quals: list[str] = []
    for use in uses:
        typ, _, sec = use.partition(", section ")
        word = _USE_WORDS.get(typ, "")
        if sections > 1:
            word = f"section {sec}" + (f", {word}" if word else "")
        if word and word not in quals:
            quals.append(word)
    if sections == 1 and any(u.startswith("default") for u in uses):
        quals = []
    return kind.capitalize() + (" · " + "; ".join(quals) if quals else "")


def _body_html(r: Renderer, pkg: DocxPackage, ov: _Overlay,
               created: set[str] | None = None) -> str:
    """Headers, then the body, then footers.

    Only headers/footers with visible content are shown, and variants with the same
    content (default / first page / even pages) are shown once.
    """
    created = created or set()
    sections = max((int(u.rsplit(" ", 1)[-1]) for hf in pkg.hf_parts for u in hf.uses
                    if u.rsplit(" ", 1)[-1].isdigit()), default=1)

    def boxes(kind: str) -> str:
        shown: dict[str, list] = {}  # same content -> [hf, uses, fragment]
        parts = [hf for hf in pkg.hf_parts if hf.kind == kind]
        parts.sort(key=lambda hf: min((_USE_ORDER.get(u.split(",")[0], 3) for u in hf.uses),
                                      default=3))
        for hf in parts:
            # shapes in headers/footers are decoration (lines, frames, watermarks)
            fragment = _SHAPE_CHIP.sub("", _blocks_html(r, hf.root, ov))
            new = hf.part_name in created
            if not new and not _shows_something(fragment):
                continue
            key = hf.part_name if new else _BLOCK_IDS.sub("", fragment)
            if key in shown:
                shown[key][1].extend(hf.uses)
            else:
                shown[key] = [hf, list(hf.uses), fragment]
        out = []
        for hf, uses, fragment in shown.values():
            cls = "hf block-ins" if hf.part_name in created else "hf"
            types = ",".join(dict.fromkeys(u.split(",")[0] for u in uses))
            out.append(f'<div class="{cls}" data-part="{html.escape(hf.label)}" '
                       f'data-kind="{kind}" data-uses="{html.escape(types)}">'
                       f'<span class="hf-label">{html.escape(_hf_label(kind, uses, sections))}'
                       f"</span>{fragment}</div>")
        return "".join(out)

    return boxes("header") + _blocks_html(r, pkg.body, ov) + boxes("footer")


def page_setup(pkg: DocxPackage) -> dict:
    """Page size, margins and header/footer rules of the last section, in CSS px (96 dpi),
    so the web preview can lay the document out on real pages."""
    def px(el, attr: str, default_twips: int) -> float:
        raw = el.get(qn(attr)) if el is not None else None
        try:
            return round(int(raw) / 15, 2)  # 1440 twips per inch, 96 px per inch
        except (TypeError, ValueError):
            return round(default_twips / 15, 2)

    sect = pkg.body.find(W.sectPr)
    size = sect.find(qn("w:pgSz")) if sect is not None else None
    mar = sect.find(qn("w:pgMar")) if sect is not None else None
    width, height = px(size, "w:w", 11906), px(size, "w:h", 16838)  # A4 when missing
    if size is not None and size.get(qn("w:orient")) == "landscape" and height > width:
        width, height = height, width
    settings = pkg.parts.get("word/settings.xml", b"")
    return {
        "width": width, "height": height,
        "top": abs(px(mar, "w:top", 1440)), "bottom": abs(px(mar, "w:bottom", 1440)),
        "left": px(mar, "w:left", 1440), "right": px(mar, "w:right", 1440),
        "header": px(mar, "w:header", 708), "footer": px(mar, "w:footer", 708),
        "title_page": bool(sect is not None and _on(sect.find(qn("w:titlePg")))),
        "even_and_odd": b"evenAndOddHeaders" in settings and b'evenAndOddHeaders w:val="0"'
        not in settings and b'evenAndOddHeaders w:val="false"' not in settings,
    }


def render_preview(pkg: DocxPackage) -> str:
    return _body_html(Renderer(pkg), pkg, _Overlay())


def render_redline(before: DocxPackage, after: DocxPackage, plan: EditPlan) -> str:
    """Render ``after`` with insertions/deletions/formatting changes marked."""
    oracle = replay(before, plan)
    roots = {"body": after.body} | {hf.part_name: hf.root for hf in after.hf_parts} \
        | {text_box_name(box): box for _, box in text_boxes(after.body)}
    pairs: list[tuple[Expected, StreamItem]] = []
    for name, expected in oracle.lists.items():
        actual = stream_of(roots[name]) if name in roots else []
        if [e.kind for e in expected] != [a.kind for a in actual]:
            return render_preview(after)  # verification would have failed; show plain
        pairs.extend(zip(expected, actual))
    r_after = Renderer(after)
    r_before = Renderer(before, with_ids=False)
    ov = _Overlay()
    r_after.overlay = ov
    for exp, act in pairs:
        if exp.kind == "tbl" and exp.before is None and exp.copy_of is None:
            # A whole new table gets one bar on its left, not every cell filled green: blue
            # when existing paragraphs were put into it, green when its content is new.
            ov.table_cls[id(act.element)] = ("tbl-moved" if exp.spec.get("converted")
                                             else "tbl-ins")
        table = exp.spec.get("table") if exp.kind == "tr" else None
        if exp.kind == "tr" and exp.before is None and (table is None or table.before is not None):
            ov.row_cls[id(act.element)] = "row-ins"
        elif exp.kind == "tr" and exp.spec.get("moved"):
            ov.row_cls[id(act.element)] = "row-moved"
        if exp.kind != "p":
            continue
        if exp.before is None and exp.spec.get("split"):
            ov.para_html[id(act.element)] = r_after.paragraph(
                act.element, chars=_merge(exp, None, act.element))
        elif exp.before is None:
            ov.para_html[id(act.element)] = r_after.paragraph(
                act.element, extra_cls="block-ins", chars=_all(act.element, "ins"))
        elif exp.modified:
            cls = "block-moved" if exp.spec.get("moved") else \
                "block-fmt" if exp.ppr_set else ""  # style, alignment or background changed
            ov.para_html[id(act.element)] = r_after.paragraph(
                act.element, chars=_merge(exp, exp.before.element, act.element), extra_cls=cls)
        elif exp.spec.get("moved"):
            ov.para_html[id(act.element)] = r_after.paragraph(act.element,
                                                              extra_cls="block-moved")
    _place_removed(oracle.removed, [e for e, _ in pairs], [a for _, a in pairs],
                   r_before, r_after, ov)
    before_names = set(oracle.lists)
    created = {hf.part_name for hf in after.hf_parts if hf.part_name not in before_names}
    return _body_html(r_after, after, ov, created)


def _all(p: etree._Element, status: str) -> list[_Char]:
    return [_Char(ch, pc, status) for pc in paragraph_view(p).pieces for ch in pc.text]


def _merge(exp: Expected, b_el: etree._Element | None, a_el: etree._Element) -> list[_Char]:
    """Characters of an edited paragraph with their redline status. Characters that came
    from *another* paragraph (merge, split) are shown as unchanged text."""
    b_chars = [(ch, pc) for pc in paragraph_view(b_el).pieces for ch in pc.text] \
        if b_el is not None else []
    a_chars = [(ch, pc) for pc in paragraph_view(a_el).pieces for ch in pc.text]
    chars = exp.chars or []
    own = [oc.origin if (oc.origin is not None and oc.src is b_el) else None for oc in chars]
    # origin of the next kept character at or after each position (to emit deletions
    # before the insertions that replace them: "~~old~~ new", like a redline)
    next_kept = [len(b_chars)] * (len(chars) + 1)
    for i in range(len(chars) - 1, -1, -1):
        next_kept[i] = own[i] if own[i] is not None else next_kept[i + 1]
    out: list[_Char] = []
    k = 0  # next before index not yet emitted
    for i, (oc, (ch, pc)) in enumerate(zip(chars, a_chars)):
        if own[i] is None:
            if oc.origin is None:
                while k < next_kept[i]:
                    out.append(_Char(b_chars[k][0], b_chars[k][1], "del"))
                    k += 1
            out.append(_Char(ch, pc, "ins" if oc.origin is None
                             else ("fmt" if oc.forced else "same")))
            continue
        while k < own[i]:
            out.append(_Char(b_chars[k][0], b_chars[k][1], "del"))
            k += 1
        k = own[i] + 1
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
        elif is_blank_paragraph(el):
            continue  # an empty line: nothing to strike through, only a stray red bar
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

