"""Document layer: package I/O, text model, edit operations, verification."""

from .model import build_index, paragraph_view, render_outline
from .ops import (
    DeleteParagraph,
    DeleteText,
    DocumentEditor,
    EditError,
    EditPlan,
    FormatText,
    InsertParagraph,
    InsertText,
    ReplaceText,
    apply_plan,
)
from .package import DocxError, DocxPackage
from .verify import VerificationReport, verify_edit

__all__ = [
    "DeleteParagraph",
    "DeleteText",
    "DocumentEditor",
    "DocxError",
    "DocxPackage",
    "EditError",
    "EditPlan",
    "FormatText",
    "InsertParagraph",
    "InsertText",
    "ReplaceText",
    "VerificationReport",
    "apply_plan",
    "build_index",
    "paragraph_view",
    "render_outline",
    "verify_edit",
]
