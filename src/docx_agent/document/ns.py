"""OOXML namespace helpers."""

from __future__ import annotations

NSMAP: dict[str, str] = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "v": "urn:schemas-microsoft-com:vml",
    "xml": "http://www.w3.org/XML/1998/namespace",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
}


def qn(tag: str) -> str:
    """Turn ``"w:p"`` into Clark notation ``"{namespace}p"``."""
    prefix, local = tag.split(":", 1)
    return f"{{{NSMAP[prefix]}}}{local}"


class W:
    """Pre-computed Clark names for the WordprocessingML tags we touch."""

    body = qn("w:body")
    p = qn("w:p")
    pPr = qn("w:pPr")
    pStyle = qn("w:pStyle")
    numPr = qn("w:numPr")
    ilvl = qn("w:ilvl")
    r = qn("w:r")
    rPr = qn("w:rPr")
    rStyle = qn("w:rStyle")
    t = qn("w:t")
    tab = qn("w:tab")
    ptab = qn("w:ptab")
    br = qn("w:br")
    cr = qn("w:cr")
    noBreakHyphen = qn("w:noBreakHyphen")
    softHyphen = qn("w:softHyphen")
    sym = qn("w:sym")
    drawing = qn("w:drawing")
    pict = qn("w:pict")
    object = qn("w:object")
    fldChar = qn("w:fldChar")
    fldCharType = qn("w:fldCharType")
    instrText = qn("w:instrText")
    fldSimple = qn("w:fldSimple")
    hyperlink = qn("w:hyperlink")
    smartTag = qn("w:smartTag")
    customXml = qn("w:customXml")
    dir = qn("w:dir")
    bdo = qn("w:bdo")
    ins = qn("w:ins")
    del_ = qn("w:del")
    moveTo = qn("w:moveTo")
    moveFrom = qn("w:moveFrom")
    sdt = qn("w:sdt")
    sdtContent = qn("w:sdtContent")
    footnoteReference = qn("w:footnoteReference")
    endnoteReference = qn("w:endnoteReference")
    commentReference = qn("w:commentReference")
    commentRangeStart = qn("w:commentRangeStart")
    commentRangeEnd = qn("w:commentRangeEnd")
    bookmarkStart = qn("w:bookmarkStart")
    bookmarkEnd = qn("w:bookmarkEnd")
    lastRenderedPageBreak = qn("w:lastRenderedPageBreak")
    tbl = qn("w:tbl")
    tr = qn("w:tr")
    tc = qn("w:tc")
    sectPr = qn("w:sectPr")
    b = qn("w:b")
    bCs = qn("w:bCs")
    i = qn("w:i")
    iCs = qn("w:iCs")
    u = qn("w:u")
    strike = qn("w:strike")
    highlight = qn("w:highlight")
    color = qn("w:color")
    sz = qn("w:sz")
    val = qn("w:val")
    type = qn("w:type")
    id = qn("w:id")
    name = qn("w:name")
    style = qn("w:style")
    styleId = qn("w:styleId")
    styleType = qn("w:type")
    default = qn("w:default")
    gridSpan = qn("w:gridSpan")
    vMerge = qn("w:vMerge")
    tcPr = qn("w:tcPr")


class M:
    oMath = qn("m:oMath")
    oMathPara = qn("m:oMathPara")


class MC:
    AlternateContent = qn("mc:AlternateContent")


XML_SPACE = qn("xml:space")
R_EMBED = qn("r:embed")
R_ID = qn("r:id")
