"""Randomised property test: for hundreds of random (but valid) plans on the
sample documents, either the engine refuses the plan with an EditError, or the
result passes every integrity check. It must never silently corrupt."""

import random

import pytest
from helpers import plan

from docx_agent.document import DocxPackage, EditError, apply_plan, verify_edit
from docx_agent.document.model import build_index, paragraph_view

WORDS = ["alpha", "beta", "gamma", "delta", "sessão", "naïve", "50%", "<tag>", "a & b", "“quoted”"]


COLORS = ["70AD47", "FF0000", "7030A0", "auto"]


def random_op(rng: random.Random, pkg: DocxPackage) -> dict | None:
    index = build_index(pkg)
    blocks = [b for b in index.paragraphs() if b.editable]
    tables = [b for b in index.blocks if b.kind == "table" and b.editable]
    block = rng.choice(blocks)
    text = paragraph_view(block.element).text
    kind = rng.choice(["replace", "replace", "delete", "insert_text", "insert_par",
                       "delete_par", "format", "restyle", "images", "rows", "insert_row",
                       "delete_table"])
    if kind == "restyle":
        return {"op": "restyle_text", "block_id": rng.choice([None, block.id]),
                "match": rng.choice([{"color": rng.choice(COLORS[:2])}, {"bold": True}]),
                "set": rng.choice([{"color": rng.choice(COLORS)}, {"italic": True},
                                   {"font_size": 13, "bold": False}])}
    if kind == "images":
        return rng.choice([{"op": "delete_images", "max_size_px": 16},
                           {"op": "delete_images", "block_id": block.id},
                           {"op": "delete_images", "images": [f"#{rng.randint(1, 9)}"]}])
    if kind in ("rows", "insert_row", "delete_table"):
        if not tables:
            return None
        t = rng.choice(tables)
        rows = [f"{t.id}.r{i}" for i in range(t.rows)]
        if kind == "rows":
            return {"op": "delete_table_rows", "rows": rng.sample(rows, rng.randint(1, len(rows)))}
        if kind == "delete_table":
            return {"op": "delete_table", "table_id": t.id}
        return {"op": "insert_table_row", "row": rng.choice(rows),
                "position": rng.choice(["before", "after"]),
                "cells": [rng.choice(WORDS) for _ in range(t.cols)],
                "format_like_row": rng.choice([None, rng.choice(rows)])}
    if kind == "insert_par":
        return {"op": "insert_paragraph", "target_id": block.id,
                "position": rng.choice(["before", "after"]),
                "text": " ".join(rng.sample(WORDS, 3)),
                "format_like": rng.choice(blocks).id}
    if kind == "delete_par":
        return {"op": "delete_paragraph", "block_id": block.id}
    if not text:
        return None
    a = rng.randrange(len(text))
    b = rng.randrange(a + 1, min(len(text), a + 40) + 1)
    find = text[a:b]
    occ = 1 if text.count(find) > 1 else None
    if kind == "replace":
        return {"op": "replace_text", "block_id": block.id, "find": find,
                "replace_with": rng.choice(WORDS), "occurrence": occ}
    if kind == "delete":
        return {"op": "delete_text", "block_id": block.id, "find": find, "occurrence": occ}
    if kind == "format":
        prop = rng.choice(["bold", "italic", "underline", "strike", "color", "highlight",
                           "font_size"])
        value = {"color": rng.choice(COLORS), "highlight": rng.choice(["yellow", "none"]),
                 "font_size": rng.choice([9, 11.5, 16])}.get(prop, rng.choice([True, False]))
        return {"op": "format_text", "block_id": block.id, "find": find, "occurrence": occ,
                prop: value}
    return {"op": "insert_text", "block_id": block.id,
            "position": rng.choice(["before", "after"]), "anchor": find,
            "text": " " + rng.choice(WORDS), "occurrence": occ}


@pytest.mark.parametrize("doc", ["session_note_bytes", "referral_bytes", "api_reference_bytes"])
def test_random_plans_never_corrupt(doc, request):
    data = request.getfixturevalue(doc)
    rng = random.Random(1234)
    applied = refused = 0
    for _ in range(250):
        pkg = DocxPackage(data)
        ops = [op for op in (random_op(rng, pkg) for _ in range(rng.randint(1, 3))) if op]
        if not ops:
            continue
        try:
            p = plan(*ops)
        except Exception:  # noqa: BLE001 - pydantic rejects e.g. invalid text; not under test
            continue
        work = pkg.copy()
        try:
            apply_plan(work, p)
        except EditError:
            refused += 1
            continue
        report = verify_edit(pkg, work.to_bytes(), p)
        assert report.passed, f"{ops}\n{report.summary()}"
        applied += 1
    print(f"\n{doc}: applied={applied} refused={refused}")
    assert applied > 100, (applied, refused)
