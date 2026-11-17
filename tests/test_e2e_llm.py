"""End-to-end tests against the real OpenAI API.

Deselected by default; run with ``uv run pytest -m llm``. The broader behavioural suite
lives in ``evals/`` (``uv run python evals/run.py``).
"""

import os

import pytest

from docx_agent.document import DocxPackage
from docx_agent.document.model import build_index, paragraph_view
from docx_agent.service import EditService

pytestmark = [
    pytest.mark.llm,
    pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set"),
]


def all_text(path) -> str:
    pkg = DocxPackage(path.read_bytes())
    return "\n".join(paragraph_view(b.element).text for b in build_index(pkg).paragraphs())


@pytest.fixture(scope="module")
def service():
    return EditService()


def test_replace_insert_and_verify(service, tmp_path, session_note_bytes):
    src = tmp_path / "in.docx"
    src.write_bytes(session_note_bytes)
    out = tmp_path / "out.docx"
    res = service.start(src, "Change the session number to 7 of 12 and add 'Grounding "
                             "exercise' as another intervention used.", out)
    assert res.status == "done", res.message
    assert res.verification["passed"]
    text = all_text(out)
    assert "7 of 12" in text and "Grounding exercise" in text


def test_out_of_scope_is_declined(service, tmp_path, session_note_bytes):
    src = tmp_path / "in.docx"
    src.write_bytes(session_note_bytes)
    res = service.start(src, "Make the chart twice as big.", tmp_path / "out.docx")
    assert res.status in ("declined", "needs_clarification")
    assert not (tmp_path / "out.docx").exists()
