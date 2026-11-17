"""The committed example outputs are reproducible from their plans (no LLM needed),
and the HTML renderer marks exactly what changed."""

import json
from pathlib import Path

import pytest
from helpers import BOLD, P, R, pkg_of, plan

from docx_agent.document import DocxPackage, EditPlan, apply_plan, verify_edit
from docx_agent.document.render import render_preview, render_redline
from docx_agent.document.verify import c14n

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
EXAMPLES = sorted((SAMPLES / "output").glob("*.plan.json"))


@pytest.mark.parametrize("plan_file", EXAMPLES, ids=lambda p: p.stem)
def test_committed_example_replays_exactly(plan_file):
    stem = plan_file.name.removesuffix(".plan.json")
    before = DocxPackage((SAMPLES / "input" / f"{stem}.docx").read_bytes())
    stored = DocxPackage((SAMPLES / "output" / f"{stem}.edited.docx").read_bytes())
    p = EditPlan.model_validate(json.loads(plan_file.read_text()))
    work = before.copy()
    apply_plan(work, p)
    assert verify_edit(before, work.to_bytes(), p).passed
    assert verify_edit(before, stored.to_bytes(), p).passed
    assert c14n(work.document) == c14n(stored.document)


def test_examples_exist():
    assert len(EXAMPLES) >= 3


def test_preview_renders_structure(session_note):
    html = render_preview(session_note)
    assert '<h1 class="para title">Session Progress Note</h1>' in html
    assert "<table" in html and "data:image/png;base64," in html
    assert '<strong>Dr. Maya Ferreira</strong>' in html
    assert 'class="link"' in html


def test_redline_marks_insertions_deletions_and_formatting():
    before = pkg_of(P(R("Risk is ") + R("high", BOLD) + R(" today")) + P(R("drop me")) + P(R("end")))
    p = plan(
        {"op": "replace_text", "block_id": "p0", "find": "high", "replace_with": "low"},
        {"op": "format_text", "block_id": "p0", "find": "today", "italic": True},
        {"op": "delete_paragraph", "block_id": "p1"},
        {"op": "insert_paragraph", "target_id": "p2", "position": "after", "text": "added",
         "format_like": "p2"},
    )
    after = before.copy()
    apply_plan(after, p)
    html = render_redline(before, after, p)
    assert "<del><strong>high</strong></del><ins><strong>low</strong></ins>" in html
    assert 'class="fmt-changed"' in html
    assert "block-del" in html and "<del>drop me</del>" in html
    assert "block-ins" in html and "<ins>added</ins>" in html


def test_redline_trims_unchanged_words():
    before = pkg_of(P(R("Session 6 of 12")))
    p = plan({"op": "replace_text", "block_id": "p0", "find": "6 of 12", "replace_with": "7 of 12"})
    after = before.copy()
    apply_plan(after, p)
    html = render_redline(before, after, p)
    assert "Session <del>6</del><ins>7</ins> of 12" in html
