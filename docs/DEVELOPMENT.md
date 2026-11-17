# How this was built

This project was built with an AI coding agent (Claude Code), driven by a workflow in which
**the agent's work is never trusted on its word: it has to pass mechanical checks I designed
up front**. Here is what that looked like in practice for this case study.

## 1. Workflow

```
architecture discussion  →  vertical slice  →  verification harness  →  evals  →  UI  →  review
        (human)              (agent writes)       (agent + human)         (loop)    (agent)  (human + agent)
```

1. **Design before code.** The architecture (anchors instead of offsets, plan-then-execute,
   deterministic apply and verify nodes, refusing instead of guessing) was discussed and fixed
   before any code was written. The agent got constraints, not a blank page.
2. **Deterministic core first, LLM last.** The document layer (`document/`) was built and
   tested without any model in the loop. The graph was added on top, then tested with a
   scripted fake LLM, and only then connected to the real API.
3. **Test-and-fix loops.** Every change ran the offline suite (`uv run pytest`, about 10 s).
   Failing tests were fixed in the code, never by loosening the test. Several real bugs were
   caught this way, for example:
   - text inserted right after a hyperlink was silently becoming part of the link,
   - inserting into an empty paragraph was flagged by the verifier because the
     paragraph-mark formatting was not an allowed source,
   - an empty `<w:rPr/>` was treated as different from having no `rPr`.
4. **Evals as the outer loop.** `evals/run.py` runs 22 behavioural cases against the real
   model. It was used to:
   - **pick the model.** gpt-4.1, gpt-5.4-mini, gpt-5.4 and gpt-5.5 were compared, each
     repeated 3 times.
   - **tune the prompt.** Each eval failure became a specific prompt rule, and the suite was
     re-run to check the fix without regressions: 16/18 → 22/22.
   - **catch API integration problems.** Reasoning models require the Responses API for tool
     calling; the first eval run surfaced this immediately.
5. **Checking the result for real.**
   - The web UI was driven in a real browser: sample → edit → clarification → answer → redline.
   - The edited `.docx` files were opened in **Microsoft Word** through AppleScript to make
     sure no "repair" prompt appeared, and exported to PDF for a visual check.

6. **Code review pass.** A structured review of the whole package (`/code-review`) found 10
   issues. Among them were an HTML injection through untrusted colour attributes in the
   preview, unanswered parallel tool calls, LLM errors surfacing as raw 500s, and a
   `format_text` edge case at tab boundaries. Each one got a regression test
   (`tests/test_regressions.py`) and a fix, and the full eval suite was re-run afterwards
   (gpt-5.5: 66/66).

## 2. How AI-generated code is verified

The core idea is to make correctness **checkable by a machine**, so that "the agent says it
works" is never the evidence:

| risk | mechanical guard |
|---|---|
| The edit engine corrupts runs or formatting | 9-check runtime verifier on every edit, plus an independent oracle (`oracle.py`) |
| The verifier itself is too lenient | Mutation tests: tamper with correct outputs and require a failure (`test_verify.py`) |
| Edge cases nobody thought of | Seeded fuzzing: 500 random plans, each either refused or verified (`test_fuzz.py`) |
| Graph routing regressions | Scripted-LLM tests for every edge of the graph (`test_graph.py`) |
| Prompt or model regressions | Behavioural evals with outcome assertions (`evals/`) |
| Sample outputs drift from the code | Replay tests that rebuild the committed outputs from their plans |

One rule mattered most: **the verifier is written against the oracle, not against the
engine.** The verifier never asks the editor what it did. It compares the original document,
the result, and a second implementation of the same semantics on plain strings. A bug has to
appear identically in two unrelated implementations to slip through.

## 3. What is custom here (beyond prompting a coding assistant)

- **The eval harness** (`evals/run.py`, `evals/cases.json`): multi-model, repeated runs,
  outcome checks (text, styles, formatting, over-editing, double spaces, verification), and
  Markdown reports kept in `evals/results/`.
- **The scripted LLM** (`tests/fake_llm.py`): deterministic control over every LangGraph path,
  including interrupts.
- **The verification and oracle pair** described above, used both at runtime and as the
  test oracle.
- **Project instructions for the agent** (`CLAUDE.md`): the working rules the coding agent
  follows in this repo. They require running the quality gate before committing, never
  weakening a check to make a test pass, and adding an eval case for every behavioural bug.
- **A quality gate script** (`scripts/check.sh`), also run in CI
  (`.github/workflows/ci.yml`): lint plus the offline tests; `--evals` adds the real-model
  suite.

## 4. What I would automate next

- Run the eval suite nightly against new model versions and alert on regressions.
- Add a review agent that reads the diff together with the eval and fuzz results and has to
  approve before merge.
- Grow the corpus with real-world (anonymised) Word files: documents produced by Word,
  LibreOffice and Google Docs exercise very different XML.
