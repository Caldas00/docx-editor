"""How a document's paragraphs, runs and tables look, as CSS, for the web preview.

Word decides formatting in layers: document defaults, then the table style (for text in a
table), the paragraph style and its `basedOn` chain, the character style, and finally the
direct formatting on the paragraph or run. This module resolves those layers for the
properties that decide what a page looks like - fonts (including theme fonts), sizes,
colours, bold/italic/caps, hidden text, shading, alignment, indentation, spacing, line
spacing, paragraph borders, table borders/shading/cell margins and list numbering - and
turns them into CSS. It only reads the package; nothing here changes the document.
"""

from __future__ import annotations

import colorsys
import html
import re
from dataclasses import dataclass, field

from lxml import etree

from .ns import W, qn
from .package import DocxPackage, parse_xml

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_HEX = re.compile(r"[0-9A-Fa-f]{6}")
_TWIP_PX = 1 / 15  # 1440 twips per inch, 96 px per inch

# Character runs of these elements are merged attribute by attribute (Word merges e.g.
# spacing="before" from a style with spacing="after" from the paragraph).
_MERGED = {"spacing", "ind", "rFonts", "numPr", "shd", "pBdr", "tabs"}

_HIGHLIGHT = {
    "yellow": "#ffff00", "green": "#00ff00", "cyan": "#00ffff", "magenta": "#ff00ff",
    "blue": "#0000ff", "red": "#ff0000", "darkBlue": "#000080", "darkCyan": "#008080",
    "darkGreen": "#008000", "darkMagenta": "#800080", "darkRed": "#800000",
    "darkYellow": "#808000", "darkGray": "#808080", "lightGray": "#c0c0c0", "black": "#000000",
    "white": "#ffffff",
}
_BORDER_STYLE = {"single": "solid", "thick": "solid", "double": "double", "dotted": "dotted",
                 "dashed": "dashed", "dotDash": "dashed", "dotDotDash": "dashed",
                 "triple": "double", "wave": "solid", "dashSmallGap": "dashed",
                 "thinThickSmallGap": "double", "thickThinSmallGap": "double"}
# Symbol / Wingdings bullets are private-use code points; show a look-alike.
_BULLETS = {"": "•", "": "▪", "": "➢", "": "❖", "": "✓",
            "": "□", "": "o", "": "➢", "": "◆", "": "-"}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _attrs(el: etree._Element) -> dict[str, str]:
    return {_local(k): v for k, v in el.attrib.items()}


def _int(value, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _on(props: dict, key: str) -> bool | None:
    """Toggle property: True, False, or None when not set."""
    if key not in props:
        return None
    return props[key].get("val", "true") not in ("0", "false", "off", "none")


def _color(value: str | None) -> str | None:
    return f"#{value}" if value and _HEX.fullmatch(value) else None


def _merge(target: dict[str, dict], container: etree._Element | None) -> None:
    """Layer a pPr/rPr/tblPr/tcPr onto `target` (later layers win)."""
    if container is None:
        return
    for child in container:
        if not isinstance(child.tag, str):
            continue
        name = _local(child.tag)
        if name in ("pBdr", "tblBorders", "tcBorders", "tblCellMar", "tcMar"):
            sides = target.setdefault(name, {})
            for side in child:
                if isinstance(side.tag, str):
                    sides[_local(side.tag)] = _attrs(side)
        elif name == "numPr":
            num = target.setdefault("numPr", {})
            for sub in child:
                if isinstance(sub.tag, str):
                    num[_local(sub.tag)] = sub.get(W.val)
        elif name == "tabs":
            target["tabs"] = {"list": [_attrs(t) for t in child if isinstance(t.tag, str)]}
        elif name == "rFonts":
            fonts = target.setdefault("rFonts", {})
            new = _attrs(child)
            for plain, themed in (("ascii", "asciiTheme"), ("hAnsi", "hAnsiTheme"),
                                  ("eastAsia", "eastAsiaTheme"), ("cs", "cstheme")):
                if plain in new and themed not in new:  # an explicit font beats an inherited
                    fonts.pop(themed, None)              # theme font
            fonts.update(new)
        elif name in _MERGED:
            target.setdefault(name, {}).update(_attrs(child))
        else:
            target[name] = _attrs(child)


@dataclass
class _Level:
    start: int = 1
    fmt: str = "decimal"
    text: str = "%1."
    suffix: str = "tab"
    ppr: etree._Element | None = None
    rpr: etree._Element | None = None


@dataclass
class _Label:
    text: str
    level: _Level


@dataclass
class TableLook:
    """Resolved table formatting: borders, cell margins, conditional (first row...) parts."""
    borders: dict[str, dict] = field(default_factory=dict)
    margins: dict[str, dict] = field(default_factory=dict)
    conditional: dict[str, dict[str, dict]] = field(default_factory=dict)  # type -> layers
    look: dict[str, str] = field(default_factory=dict)
    style_ppr: dict[str, dict] = field(default_factory=dict)
    style_rpr: dict[str, dict] = field(default_factory=dict)


class StyleSheet:
    def __init__(self, pkg: DocxPackage) -> None:
        self.pkg = pkg
        self.styles: dict[str, etree._Element] = {}
        self.default_para: str | None = None
        self.default_table: str | None = None
        self.doc_ppr: dict[str, dict] = {}
        self.doc_rpr: dict[str, dict] = {}
        root = self._part("word/styles.xml")
        if root is not None:
            defaults = root.find(qn("w:docDefaults"))
            if defaults is not None:
                _merge(self.doc_ppr, defaults.find(f"{qn('w:pPrDefault')}/{W.pPr}"))
                _merge(self.doc_rpr, defaults.find(f"{qn('w:rPrDefault')}/{W.rPr}"))
            for st in root.findall(qn("w:style")):
                sid = st.get(qn("w:styleId"))
                if not sid:
                    continue
                self.styles[sid] = st
                if st.get(qn("w:default")) in ("1", "true"):
                    if st.get(qn("w:type")) == "paragraph":
                        self.default_para = sid
                    elif st.get(qn("w:type")) == "table":
                        self.default_table = sid
        self.fonts, self.colors = self._theme()
        self._levels: dict[str, dict[int, _Level]] = {}  # abstractNumId -> levels
        self._nums: dict[str, tuple[str, dict[int, int], dict[int, _Level]]] = {}
        self._read_numbering()
        self._chain_cache: dict[tuple[str, str], list[etree._Element]] = {}
        self._table_cache: dict[etree._Element, TableLook] = {}

    # ----------------------------------------------------------------- parts
    def _part(self, name: str) -> etree._Element | None:
        data = self.pkg.parts.get(name)
        if not data:
            return None
        try:
            return parse_xml(data)
        except Exception:  # noqa: BLE001 - a broken optional part only costs fidelity
            return None

    def _theme(self) -> tuple[dict[str, str], dict[str, str]]:
        theme = next((n for n in self.pkg.parts if re.fullmatch(r"word/theme/theme\d*\.xml", n)),
                     None)
        root = self._part(theme) if theme else None
        fonts = {}
        for kind in ("major", "minor"):
            font = root.find(f".//{A}{kind}Font") if root is not None else None
            for script in ("latin", "ea", "cs"):
                el = font.find(f"{A}{script}") if font is not None else None
                fonts[f"{kind}-{script}"] = (el.get("typeface") if el is not None else "") or ""
        colors = {}
        scheme = root.find(f".//{A}clrScheme") if root is not None else None
        for slot in (scheme if scheme is not None else []):
            if not isinstance(slot.tag, str):
                continue
            rgb = slot.find(f"{A}srgbClr")
            sys_clr = slot.find(f"{A}sysClr")
            value = rgb.get("val") if rgb is not None else \
                sys_clr.get("lastClr") if sys_clr is not None else None
            if value and _HEX.fullmatch(value):
                colors[_local(slot.tag)] = value.upper()
        return fonts, colors

    def color(self, props: dict) -> str | None:
        """A colour attribute set: the theme colour (with tint/shade) wins over `val`,
        as in Word; `val` is only a cached fallback."""
        theme = props.get("themeColor") or props.get("themeFill")
        base = None
        if theme:
            slot = {"text1": "dk1", "background1": "lt1", "text2": "dk2", "background2": "lt2",
                    "dark1": "dk1", "light1": "lt1", "dark2": "dk2", "light2": "lt2",
                    "hyperlink": "hlink", "followedHyperlink": "folHlink"}.get(theme, theme)
            base = self.colors.get(slot)
        if base is None:
            return _color(props.get("val") if "val" in props else props.get("fill"))
        r, g, b = (int(base[i:i + 2], 16) / 255 for i in (0, 2, 4))
        hue, light, sat = colorsys.rgb_to_hls(r, g, b)
        tint = props.get("themeTint") or props.get("themeFillTint")
        shade = props.get("themeShade") or props.get("themeFillShade")
        # Word lightens/darkens theme colours on the HSL luminance, not on RGB
        if tint and re.fullmatch(r"[0-9A-Fa-f]{1,2}", tint):
            t = int(tint, 16) / 255
            light = light * t + (1 - t)
        if shade and re.fullmatch(r"[0-9A-Fa-f]{1,2}", shade):
            light = light * int(shade, 16) / 255
        rgb = colorsys.hls_to_rgb(hue, min(1, max(0, light)), sat)
        return "#" + "".join(f"{round(c * 255):02X}" for c in rgb)

    def _read_numbering(self) -> None:
        root = self._part("word/numbering.xml")
        if root is None:
            return
        for ab in root.findall(qn("w:abstractNum")):
            aid = ab.get(qn("w:abstractNumId"))
            levels = {}
            for lvl in ab.findall(qn("w:lvl")):
                levels[_int(lvl.get(qn("w:ilvl")))] = self._level(lvl)
            link = ab.find(qn("w:numStyleLink"))
            self._levels[aid] = levels
            if link is not None and not levels:  # levels live in a numbering style
                self._levels[aid] = {"link": link.get(W.val)}  # type: ignore[dict-item]
        for num in root.findall(qn("w:num")):
            nid = num.get(qn("w:numId"))
            ab = num.find(qn("w:abstractNumId"))
            starts: dict[int, int] = {}
            overrides: dict[int, _Level] = {}
            for ov in num.findall(qn("w:lvlOverride")):
                ilvl = _int(ov.get(qn("w:ilvl")))
                so = ov.find(qn("w:startOverride"))
                if so is not None:
                    starts[ilvl] = _int(so.get(W.val), 1)
                lvl = ov.find(qn("w:lvl"))
                if lvl is not None:
                    overrides[ilvl] = self._level(lvl)
            self._nums[nid] = (ab.get(W.val) if ab is not None else "", starts, overrides)

    @staticmethod
    def _level(lvl: etree._Element) -> _Level:
        def val(tag: str, default: str) -> str:
            el = lvl.find(qn(f"w:{tag}"))
            return el.get(W.val, default) if el is not None else default
        return _Level(start=_int(val("start", "1"), 1), fmt=val("numFmt", "decimal"),
                      text=val("lvlText", ""), suffix=val("suff", "tab"),
                      ppr=lvl.find(W.pPr), rpr=lvl.find(W.rPr))

    def _abstract_levels(self, aid: str, depth: int = 0) -> dict[int, _Level]:
        levels = self._levels.get(aid, {})
        link = levels.get("link") if isinstance(levels, dict) else None  # type: ignore[call-overload]
        if isinstance(link, str) and depth < 3:
            st = self.styles.get(link)
            num = st.find(f"{W.pPr}/{W.numPr}/{W.numId}") if st is not None else None
            target = self._nums.get(num.get(W.val)) if num is not None else None
            return self._abstract_levels(target[0], depth + 1) if target else {}
        return levels  # type: ignore[return-value]

    # ---------------------------------------------------------------- styles
    def _chain(self, sid: str | None, kind: str) -> list[etree._Element]:
        """The style and its basedOn ancestors, base first."""
        if not sid:
            return []
        key = (sid, kind)
        if key not in self._chain_cache:
            chain, seen = [], set()
            cur = sid
            while cur and cur not in seen and cur in self.styles:
                seen.add(cur)
                st = self.styles[cur]
                chain.append(st)
                based = st.find(qn("w:basedOn"))
                cur = based.get(W.val) if based is not None else None
            self._chain_cache[key] = list(reversed(chain))
        return self._chain_cache[key]

    def _para_style_id(self, p: etree._Element) -> str | None:
        ps = p.find(f"{W.pPr}/{qn('w:pStyle')}")
        sid = ps.get(W.val) if ps is not None else None
        return sid if sid in self.styles else self.default_para

    def table_of(self, el: etree._Element) -> etree._Element | None:
        for anc in el.iterancestors():
            if anc.tag == W.tbl:
                return anc
            if anc.tag in (W.body, qn("w:txbxContent"), qn("w:hdr"), qn("w:ftr")):
                return None
        return None

    def paragraph_props(self, p: etree._Element) -> tuple[dict, dict]:
        """(pPr, rPr) layers for a paragraph: what its text looks like before run formatting."""
        ppr: dict[str, dict] = {}
        rpr: dict[str, dict] = {}
        _merge(ppr, None)
        for k, v in self.doc_ppr.items():
            ppr[k] = dict(v)
        for k, v in self.doc_rpr.items():
            rpr[k] = dict(v)
        sid = self._para_style_id(p)
        table = self.table_of(p)
        look = self.table_look(table) if table is not None else None
        style_first = sid != self.default_para  # table styles override only the default style
        if look is not None and not style_first:
            ppr.update({k: dict(v) for k, v in look.style_ppr.items()})
            rpr.update({k: dict(v) for k, v in look.style_rpr.items()})
        for st in self._chain(sid, "p"):
            _merge(ppr, st.find(W.pPr))
            _merge(rpr, st.find(W.rPr))
        if look is not None and style_first:
            for k, v in look.style_ppr.items():
                ppr.setdefault(k, dict(v))
            for k, v in look.style_rpr.items():
                rpr.setdefault(k, dict(v))
        if look is not None:  # first row / banding of the table style
            for part in self.cell_parts(p, look):
                _merge(rpr, part.get("rPr"))
                _merge(ppr, part.get("pPr"))
        _merge(ppr, p.find(W.pPr))
        return ppr, rpr

    def run_props(self, run: etree._Element, base_rpr: dict) -> dict:
        rpr = {k: dict(v) for k, v in base_rpr.items()}
        own = run.find(W.rPr)
        rs = own.find(qn("w:rStyle")) if own is not None else None
        if rs is not None:
            for st in self._chain(rs.get(W.val), "r"):
                _merge(rpr, st.find(W.rPr))
        _merge(rpr, own)
        return rpr

    # ----------------------------------------------------------------- tables
    def table_look(self, tbl: etree._Element) -> TableLook:
        key = tbl
        if key in self._table_cache:
            return self._table_cache[key]
        look = TableLook()
        tblpr = tbl.find(qn("w:tblPr"))
        ts = tblpr.find(qn("w:tblStyle")) if tblpr is not None else None
        sid = ts.get(W.val) if ts is not None and ts.get(W.val) in self.styles else \
            self.default_table
        props: dict[str, dict] = {}
        for st in self._chain(sid, "t"):
            _merge(props, st.find(qn("w:tblPr")))
            _merge(look.style_ppr, st.find(W.pPr))
            _merge(look.style_rpr, st.find(W.rPr))
            for cond in st.findall(qn("w:tblStylePr")):
                kind = cond.get(qn("w:type"))
                layers = look.conditional.setdefault(kind, {})
                for tag in ("pPr", "rPr", "tcPr", "tblPr"):
                    el = cond.find(qn(f"w:{tag}"))
                    if el is not None:
                        layers[tag] = el
        _merge(props, tblpr)
        look.borders = props.get("tblBorders", {})
        look.margins = props.get("tblCellMar", {})
        tl = tblpr.find(qn("w:tblLook")) if tblpr is not None else None
        if tl is not None:
            look.look = _attrs(tl)
            raw = tl.get(W.val)
            if raw and re.fullmatch(r"[0-9A-Fa-f]{4}", raw):  # older files: a bit mask
                bits = int(raw, 16)
                look.look.setdefault("firstRow", "1" if bits & 0x20 else "0")
                look.look.setdefault("lastRow", "1" if bits & 0x40 else "0")
                look.look.setdefault("firstColumn", "1" if bits & 0x80 else "0")
                look.look.setdefault("lastColumn", "1" if bits & 0x100 else "0")
                look.look.setdefault("noHBand", "1" if bits & 0x200 else "0")
        self._table_cache[key] = look
        return look

    def cell_parts(self, el: etree._Element, look: TableLook) -> list[dict]:
        """Conditional table-style parts (first row, banding...) that apply to the cell
        holding `el`, weakest first."""
        if not look.conditional:
            return []
        tc = next((a for a in ([el] + list(el.iterancestors())) if a.tag == W.tc), None)
        if tc is None:
            return []
        tr = tc.getparent()
        tbl = tr.getparent() if tr is not None else None
        if tbl is None or tbl.tag != W.tbl:
            return []
        rows = tbl.findall(W.tr)
        r = rows.index(tr) if tr in rows else 0
        cells = tr.findall(W.tc)
        c = cells.index(tc) if tc in cells else 0
        on = lambda k: look.look.get(k, "0") in ("1", "true", "on")  # noqa: E731
        kinds = []
        if not on("noHBand"):
            first_body = 1 if on("firstRow") else 0
            if r >= first_body:
                kinds.append("band1Horz" if (r - first_body) % 2 == 0 else "band2Horz")
        if on("firstColumn") and c == 0:
            kinds.append("firstCol")
        if on("lastColumn") and c == len(cells) - 1:
            kinds.append("lastCol")
        if on("lastRow") and r == len(rows) - 1:
            kinds.append("lastRow")
        if on("firstRow") and r == 0:
            kinds.append("firstRow")
        return [look.conditional[k] for k in kinds if k in look.conditional]

    # -------------------------------------------------------------- numbering
    def number_labels(self, roots: list[etree._Element]) -> dict[etree._Element, _Label]:
        """List and heading numbers ("2", "3.1", "a)", "•") for every numbered paragraph,
        counted in document order."""
        out: dict[etree._Element, _Label] = {}
        counters: dict[str, list[int]] = {}
        started: set[str] = set()
        for root in roots:
            for p in root.iter(W.p):
                ppr, _ = self.paragraph_props(p)
                num = ppr.get("numPr", {})
                nid, ilvl = num.get("numId"), _int(num.get("ilvl"), 0)
                if not nid or nid == "0" or nid not in self._nums:
                    continue
                aid, starts, overrides = self._nums[nid]
                levels = {**self._abstract_levels(aid), **overrides}
                if ilvl not in levels:
                    continue
                key = aid if not starts else f"num:{nid}"
                count = counters.setdefault(key, [lv.start - 1 if (lv := levels.get(i)) else 0
                                                  for i in range(9)])
                if key not in started:
                    for i, s in starts.items():
                        if 0 <= i < 9:
                            count[i] = s - 1
                    started.add(key)
                count[ilvl] += 1
                for deeper in range(ilvl + 1, 9):  # a new item restarts the levels below it
                    lv = levels.get(deeper)
                    count[deeper] = (lv.start - 1) if lv else 0
                level = levels[ilvl]
                text = level.text
                if level.fmt == "bullet":
                    text = "".join(_BULLETS.get(ch, ch) for ch in text) or "•"
                else:
                    text = re.sub(r"%([1-9])", lambda m, c=count, lv=levels: _format_number(
                        c[int(m.group(1)) - 1],
                        lv[int(m.group(1)) - 1].fmt if int(m.group(1)) - 1 in lv else "decimal"),
                        text)
                out[p] = _Label(text, level)
        return out

    # -------------------------------------------------------------------- css
    def font_stack(self, rfonts: dict) -> str | None:
        name = rfonts.get("ascii") or rfonts.get("hAnsi")
        theme = rfonts.get("asciiTheme") or rfonts.get("hAnsiTheme")
        if theme:
            kind = "major" if theme.startswith("major") else "minor"
            script = "cs" if theme.endswith("Bidi") else "ea" if "EastAsia" in theme else "latin"
            name = self.fonts.get(f"{kind}-{script}") or (
                "Times New Roman" if script != "latin" else self.fonts.get(f"{kind}-latin"))
        if not name:
            return None
        return _font_family(name)

    def line_factor(self, rfonts: dict) -> float:
        """Word's single line height as a multiple of the font size (ascent + descent + line
        gap of the font, which is what Word uses)."""
        stack = (self.font_stack(rfonts) or "").lower()
        for key, factor in (("calibri", 1.22), ("carlito", 1.22), ("cambria", 1.172),
                            ("courier", 1.133), ("consolas", 1.17), ("times", 1.15),
                            ("arial", 1.15), ("helvetica", 1.15), ("verdana", 1.215),
                            ("tahoma", 1.207), ("georgia", 1.136), ("segoe", 1.33),
                            ("garamond", 1.12), ("aptos", 1.2)):
            if key in stack.split(",")[0]:
                return factor
        return 1.17

    def paragraph_css(self, ppr: dict, rpr: dict, prev_same: bool, next_same: bool,
                      label: _Label | None) -> list[str]:
        css = run_css(rpr, self, inherit=False)
        jc = ppr.get("jc", {}).get("val")
        align = {"center": "center", "right": "right", "end": "right", "both": "justify",
                 "distribute": "justify"}.get(jc or "")
        if align:
            css.append(f"text-align:{align}")
        ind = dict(ppr.get("ind", {}))
        if label is not None and label.level.ppr is not None:
            lvl_ind = label.level.ppr.find(qn("w:ind"))
            if lvl_ind is not None:  # the list level's indent unless the paragraph sets one
                for k, v in _attrs(lvl_ind).items():
                    ind.setdefault(k, v)
        left = _int(ind.get("left", ind.get("start")))
        right = _int(ind.get("right", ind.get("end")))
        hanging, first = _int(ind.get("hanging")), _int(ind.get("firstLine"))
        if left:
            css.append(f"margin-left:{left * _TWIP_PX:.1f}px")
        if right:
            css.append(f"margin-right:{right * _TWIP_PX:.1f}px")
        if hanging:
            css.append(f"text-indent:-{hanging * _TWIP_PX:.1f}px")
        elif first:
            css.append(f"text-indent:{first * _TWIP_PX:.1f}px")
        spacing = ppr.get("spacing", {})
        contextual = _on(ppr, "contextualSpacing")
        before = 0 if contextual and prev_same else _int(spacing.get("before"))
        after = 0 if contextual and next_same else _int(spacing.get("after"))
        if spacing.get("beforeAutospacing") in ("1", "true"):
            before = 280
        if spacing.get("afterAutospacing") in ("1", "true"):
            after = 280
        css.append(f"margin-top:{before * _TWIP_PX:.1f}px")
        css.append(f"margin-bottom:{after * _TWIP_PX:.1f}px")
        line, rule = spacing.get("line"), spacing.get("lineRule", "auto")
        single = self.line_factor(rpr.get("rFonts", {}))  # Word's "single" for this font
        if line and rule == "exact":
            css.append(f"line-height:{_int(line) / 20:.1f}pt")
        elif line and rule == "atLeast":
            css.append(f"line-height:max({single:.3f}em,{_int(line) / 20:.1f}pt)")
        else:
            css.append(f"line-height:{_int(line, 240) / 240 * single:.3f}")
        shd = ppr.get("shd", {})
        fill = _color(shd.get("fill"))
        if fill and shd.get("val") != "nil":
            css.append(f"background-color:{fill}")
        for side, edge in (("top", "top"), ("bottom", "bottom"), ("left", "left"),
                           ("right", "right")):
            b = ppr.get("pBdr", {}).get(side)
            rule_css = border_css(b)
            if rule_css:
                css.append(f"border-{edge}:{rule_css}")
                css.append(f"padding-{edge}:{_int(b.get('space')) * 1.33:.1f}px")
        return css


def border_css(b: dict | None) -> str | None:
    if not b or b.get("val") in (None, "nil", "none"):
        return None
    width = max(_int(b.get("sz"), 4) / 8, 0.5) * (2 if b.get("val") == "thick" else 1)
    color = _color(b.get("color")) or "#000000"
    style = _BORDER_STYLE.get(b.get("val") or "", "solid")
    if style == "double":
        width = max(width, 2.25)
    return f"{width:.2f}pt {style} {color}"


def run_css(rpr: dict, sheet: StyleSheet, inherit: bool = True) -> list[str]:
    """CSS for run properties. `inherit=False` emits defaults too (for the paragraph)."""
    css: list[str] = []
    fonts = sheet.font_stack(rpr.get("rFonts", {}))
    if fonts:
        css.append(f"font-family:{fonts}")
    sz = rpr.get("sz", {}).get("val")
    if sz:
        size = _int(sz, 22) / 2
        if rpr.get("vertAlign", {}).get("val") in ("superscript", "subscript"):
            size *= 0.65
        css.append(f"font-size:{size:.1f}pt")
    b = _on(rpr, "b")
    if b is not None or not inherit:
        css.append(f"font-weight:{700 if b else 400}")
    i = _on(rpr, "i")
    if i is not None or not inherit:
        css.append(f"font-style:{'italic' if i else 'normal'}")
    if _on(rpr, "caps"):
        css.append("text-transform:uppercase")
    elif _on(rpr, "smallCaps"):
        css.append("font-variant:small-caps")
    deco = []
    u = rpr.get("u", {}).get("val")
    if u and u != "none":
        deco.append("underline")
    if _on(rpr, "strike") or _on(rpr, "dstrike"):
        deco.append("line-through")
    if deco:
        css.append(f"text-decoration:{' '.join(deco)}")
        if u in ("double", "dotted", "dash", "wave"):
            css.append(f"text-decoration-style:{ {'dash': 'dashed', 'wave': 'wavy'}.get(u, u)}")
    color_props = rpr.get("color", {})
    color = sheet.color(color_props) if color_props.get("val") != "auto" or \
        color_props.get("themeColor") else None
    if color:
        css.append(f"color:{color}")
    hl = rpr.get("highlight", {}).get("val")
    shd = rpr.get("shd", {})
    if hl and hl != "none":
        css.append(f"background-color:{_HIGHLIGHT.get(hl, '#ffff00')}")
    elif _color(shd.get("fill")) and shd.get("val") != "nil":
        css.append(f"background-color:{_color(shd.get('fill'))}")
    va = rpr.get("vertAlign", {}).get("val")
    if va == "superscript":
        css.append("vertical-align:super")
    elif va == "subscript":
        css.append("vertical-align:sub")
    spacing = rpr.get("spacing", {}).get("val")
    if spacing and _int(spacing):
        css.append(f"letter-spacing:{_int(spacing) * _TWIP_PX:.2f}px")
    return css


def is_hidden(rpr: dict) -> bool:
    # webHidden only hides text in Word's *web* view; on the page it is shown
    return bool(_on(rpr, "vanish"))


def _font_family(name: str) -> str:
    low = name.lower()
    alias = {"calibri": '"Calibri", "Carlito"', "calibri light": '"Calibri Light", "Calibri", '
             '"Carlito"', "cambria": '"Cambria", "Caladea"', "times new roman":
             '"Times New Roman", Times', "courier new": '"Courier New", Courier',
             "arial": "Arial, Helvetica", "consolas": "Consolas, Menlo"}.get(low)
    generic = ("monospace" if any(k in low for k in ("courier", "consolas", "mono", "menlo"))
               else "serif" if any(k in low for k in ("times", "cambria", "georgia", "garamond",
                                                      "serif", "book", "minion", "palatino"))
               else "sans-serif")
    safe = html.escape(name.replace('"', "").replace(";", ""), quote=True)
    return f'{alias or chr(34) + safe + chr(34)}, {generic}'


def _format_number(n: int, fmt: str) -> str:
    if fmt in ("none",):
        return ""
    if fmt in ("upperRoman", "lowerRoman"):
        out = _roman(n)
        return out if fmt == "upperRoman" else out.lower()
    if fmt in ("upperLetter", "lowerLetter"):
        if n <= 0:
            return ""
        letter = chr(ord("A") + (n - 1) % 26) * ((n - 1) // 26 + 1)
        return letter if fmt == "upperLetter" else letter.lower()
    if fmt == "decimalZero":
        return f"{n:02d}"
    if fmt == "ordinal":
        return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"
    return str(n)


def _roman(n: int) -> str:
    if n <= 0:
        return str(n)
    out = ""
    for value, sym in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
                       (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"),
                       (4, "IV"), (1, "I")):
        while n >= value:
            out += sym
            n -= value
    return out
