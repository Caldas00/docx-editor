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
from docx_agent.conversation import format_history  # noqa: E402
from docx_agent.document import DocxPackage  # noqa: E402
from docx_agent.document.model import (  # noqa: E402
    build_index,
    paragraph_style,
    paragraph_view,
    run_flags,
    run_props,
)
from docx_agent.document.ns import W  # noqa: E402
from docx_agent.pricing import estimate_cost  # noqa: E402
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
    pkg = DocxPackage(out.read_bytes())
    colors = {c.get(W.val, "").upper() for c in pkg.body.iter(W.color)}
    for c in expect.get("colors_absent", []):
        if c.upper() in colors:
            errors.append(f"colour #{c} still present")
    for c in expect.get("colors_present", []):
        if c.upper() not in colors:
            errors.append(f"colour #{c} not applied")
    for needle, color in expect.get("color_of", []):
        hit = False
        for _, _, el in after:
            view = paragraph_view(el)
            pos = view.text.find(needle)
            if pos < 0:
                continue
            hit = True
            got = {run_props(pc.run)["color"] for pc in view.pieces_in(pos, pos + len(needle))
                   if pc.kind == "text" and pc.text.strip()}
            if got != {color.upper()}:
                errors.append(f"{needle!r} has colour {sorted(c or 'none' for c in got)}, "
                              f"wanted #{color}")
        if not hit:
            errors.append(f"missing {needle!r}")
    if "images" in expect:
        n = sum(1 for _ in pkg.body.iter(W.drawing))
        if n != expect["images"]:
            errors.append(f"{n} pictures left (wanted {expect['images']})")
    tables = [b for b in build_index(pkg).blocks if b.kind == "table" and b.depth == 0]
    if "table_rows" in expect and [t.rows for t in tables] != expect["table_rows"]:
        errors.append(f"table rows {[t.rows for t in tables]} (wanted {expect['table_rows']})")
    if expect.get("no_empty_rows"):
        for t in tables:
            for i, tr in enumerate(t.element.findall(W.tr)):
                if not "".join(paragraph_view(q).text for q in tr.iter(W.p)).strip():
                    errors.append(f"{t.id}.r{i} is an empty row")
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
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_cached: int = 0


def run_case(case: dict, model: str) -> Result:
    """Run one case. ``followups`` are later chat messages: each starts a new run on the
    latest version with the conversation so far, exactly like the web UI."""
    settings = Settings(model=model, **case.get("settings", {}))
    service = EditService(make_llm(settings), settings)
    current = SAMPLES / case["doc"]
    steps = [{"instruction": case["instruction"], "selection": case.get("selection"),
              "expect": case["expect"]}] + case.get("followups", [])
    turns: list[dict] = []
    usage = {"input": 0, "output": 0, "cached": 0}
    calls = 0
    errors: list[str] = []
    outcome = None
    with tempfile.TemporaryDirectory() as tmp:
        t0 = time.perf_counter()
        try:
            for n, step in enumerate(steps):
                out = Path(tmp) / f"out{n}.docx"
                outcome = service.start(current, step["instruction"], out,
                                        selection=step.get("selection"),
                                        history=format_history(turns))
                calls += outcome.llm_calls
                for k in usage:
                    usage[k] += (outcome.usage or {}).get(k, 0)
                errors = [f"step {n + 1}: {e}" if len(steps) > 1 else e
                          for e in check(step["expect"], outcome, SAMPLES / case["doc"], out)]
                if errors:
                    break
                if n == 0 and "answer" in case:  # LangGraph interrupt/resume path (CLI)
                    outcome = service.resume(outcome.thread_id, case["answer"])
                    calls += outcome.llm_calls
                    errors = check(case["expect_after"], outcome, SAMPLES / case["doc"], out)
                    if errors:
                        break
                turns.append({"instruction": step["instruction"],
                              "selection": step.get("selection"), **outcome.to_dict()})
                if outcome.status == "done":
                    current = out
        except Exception as exc:  # noqa: BLE001 - an eval run must report, not crash
            return Result(case["id"], model, False, time.perf_counter() - t0, calls,
                          [f"exception: {exc!r}"])
        return Result(case["id"], model, not errors, time.perf_counter() - t0, calls, errors,
                      outcome.message if outcome else "", usage["input"], usage["output"],
                      usage["cached"])


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
        costs = [estimate_cost(m, {"input": r.tokens_in, "output": r.tokens_out,
                                   "cached": r.tokens_cached}) for r in rs]
        cost = sum(c for c in costs if c is not None) / max(len(rs), 1) if any(
            c is not None for c in costs) else None
        cost_txt = f", avg ${cost:.4f}/edit" if cost is not None else ""
        lines += [f"## {m}: {passed}/{len(rs)} passed, median {lat:.1f}s{cost_txt}", "",
                  "| case | ok | s | llm calls | notes |", "|---|---|---|---|---|"]
        for r in rs:
            note = "; ".join(r.errors) if r.errors else r.summary
            lines.append(f"| {r.case} | {'✅' if r.ok else '❌'} | {r.seconds:.1f} | {r.llm_calls} "
                         f"| {note.replace('|', '/')[:160]} |")
        lines.append("")
        print(f"{m}: {passed}/{len(rs)} passed, median {lat:.1f}s{cost_txt}")
        for r in rs:
            if not r.ok:
                print(f"   ✗ {r.case}: {'; '.join(r.errors)}")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (out_dir / f"{stamp}.md").write_text("\n".join(lines))
    (out_dir / "latest.md").write_text("\n".join(lines))
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
