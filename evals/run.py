"""Behavioural evals against the real OpenAI API.

    uv run python evals/run.py                       # default model
    uv run python evals/run.py --models gpt-4.1,gpt-5.4-mini --repeat 2

Each case runs the full agent (plan → apply → verify) on a sample document and
checks the *outcome*: status, required/forbidden text, styles of new
paragraphs, bold/italic of edited text, and how many original paragraphs
changed (to catch over-editing). Results are written to evals/results/.
"""

from __future__ import annotations

import argparse
import difflib
import json
import statistics
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from docx_agent.agent.llm import make_llm  # noqa: E402
from docx_agent.config import Settings  # noqa: E402
from docx_agent.document import DocxPackage  # noqa: E402
from docx_agent.document.model import (  # noqa: E402
    build_index,
    paragraph_style,
    paragraph_view,
    run_flags,
)
from docx_agent.service import EditService  # noqa: E402

SAMPLES = ROOT / "samples" / "input"


def paragraphs(path: Path) -> list[tuple[str, str, object]]:
    pkg = DocxPackage(path.read_bytes())
    return [(paragraph_view(b.element).text, paragraph_style(pkg, b.element), b.element)
            for b in build_index(pkg).paragraphs()]


def changed_count(before: list[str], after: list[str]) -> int:
    sm = difflib.SequenceMatcher(None, before, after, autojunk=False)
    return sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal")


def flagged(paras, needle: str, idx: int) -> bool:
    """Is every character of ``needle`` covered by runs with flag idx (0 bold, 1 italic)?"""
    for text, _, el in paras:
        pos = text.find(needle)
        if pos < 0:
            continue
        view = paragraph_view(el)
        return all(run_flags(pc.run)[idx] for pc in view.pieces_in(pos, pos + len(needle))
                   if pc.kind == "text")
    return False


def check(expect: dict, outcome, src: Path, out: Path) -> list[str]:
    errors = []
    want = expect["status"]
    allowed = want if isinstance(want, list) else [want]
    if outcome.status not in allowed:
        errors.append(f"status {outcome.status!r} not in {allowed} ({outcome.message[:120]})")
        return errors
    if outcome.status != "done":
        return errors
    before = paragraphs(src)
    after = paragraphs(out)
    full = "\n".join(t for t, _, _ in after)
    for s in expect.get("doc_contains", []):
        if s not in full:
            errors.append(f"missing {s!r}")
    for s in expect.get("doc_not_contains", []):
        if s in full:
            errors.append(f"still contains {s!r}")
    for needle, style in expect.get("style_of", []):
        hit = next((st for t, st, _ in after if needle in t), None)
        if hit != style:
            errors.append(f"paragraph with {needle!r} has style {hit!r}, wanted {style!r}")
    for needle in expect.get("bold", []):
        if not flagged(after, needle, 0):
            errors.append(f"{needle!r} is not bold")
    for needle in expect.get("italic", []):
        if not flagged(after, needle, 1):
            errors.append(f"{needle!r} is not italic")
    if "max_changed" in expect:
        n = changed_count([t for t, _, _ in before], [t for t, _, _ in after])
        if n > expect["max_changed"]:
            errors.append(f"{n} paragraphs changed (max {expect['max_changed']})")
    before_text = "\n".join(t for t, _, _ in before)
    if full.count("  ") > before_text.count("  "):
        errors.append("introduced a double space")
    if not (outcome.verification or {}).get("passed"):
        errors.append("verification did not pass")
    return errors


@dataclass
class Result:
    case: str
    model: str
    ok: bool
    seconds: float
    llm_calls: int
    errors: list[str] = field(default_factory=list)
    summary: str = ""


def run_case(case: dict, model: str) -> Result:
    settings = Settings(model=model, **case.get("settings", {}))
    service = EditService(make_llm(settings), settings)
    src = SAMPLES / case["doc"]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out.docx"
        t0 = time.perf_counter()
        try:
            outcome = service.start(src, case["instruction"], out)
            calls = outcome.llm_calls
            errors = check(case["expect"], outcome, src, out)
            if not errors and "answer" in case:
                outcome = service.resume(outcome.thread_id, case["answer"])
                calls = outcome.llm_calls
                errors = check(case["expect_after"], outcome, src, out)
        except Exception as exc:  # noqa: BLE001 - an eval run must report, not crash
            return Result(case["id"], model, False, time.perf_counter() - t0, 0,
                          [f"exception: {exc!r}"])
        return Result(case["id"], model, not errors, time.perf_counter() - t0, calls, errors,
                      outcome.message)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=Settings().model)
    ap.add_argument("--cases", default="", help="comma-separated case ids (default: all)")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    cases = json.loads((Path(__file__).parent / "cases.json").read_text())
    if args.cases:
        wanted = set(args.cases.split(","))
        cases = [c for c in cases if c["id"] in wanted]
    models = args.models.split(",")
    jobs = [(c, m) for m in models for c in cases for _ in range(args.repeat)]
    with ThreadPoolExecutor(args.workers) as pool:
        results = list(pool.map(lambda j: run_case(*j), jobs))

    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(exist_ok=True)
    lines = ["# Eval results", ""]
    for m in models:
        rs = [r for r in results if r.model == m]
        passed = sum(r.ok for r in rs)
        lat = statistics.median(r.seconds for r in rs)
        lines += [f"## {m}: {passed}/{len(rs)} passed, median {lat:.1f}s", "",
                  "| case | ok | s | llm calls | notes |", "|---|---|---|---|---|"]
        for r in rs:
            note = "; ".join(r.errors) if r.errors else r.summary
            lines.append(f"| {r.case} | {'✅' if r.ok else '❌'} | {r.seconds:.1f} | {r.llm_calls} "
                         f"| {note.replace('|', '/')[:160]} |")
        lines.append("")
        print(f"{m}: {passed}/{len(rs)} passed, median {lat:.1f}s")
        for r in rs:
            if not r.ok:
                print(f"   ✗ {r.case}: {'; '.join(r.errors)}")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (out_dir / f"{stamp}.md").write_text("\n".join(lines))
    (out_dir / "latest.md").write_text("\n".join(lines))
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
