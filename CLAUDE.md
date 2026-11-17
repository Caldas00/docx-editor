# Working rules for coding agents in this repo

- Run `scripts/check.sh` (ruff + offline pytest) before every commit. It must be green.
- The integrity verifier (`src/docx_agent/document/verify.py`) is a safety net. Never weaken a
  check to make a test pass; fix the engine instead. If a check really is wrong, change it
  together with a mutation test in `tests/test_verify.py` showing it still catches the bad
  case.
- Every behavioural bug found with the real model gets a case in `evals/cases.json` before it
  is fixed (usually in `agent/prompts.py`). Re-run `uv run python evals/run.py` and record the
  results.
- Every engine bug gets a unit test in `tests/test_ops.py` reproducing it with minimal XML
  (see `tests/helpers.py`).
- Only `word/document.xml` may be rewritten. Never re-serialise other package parts.
- The LLM never edits XML or runs code; it only produces an `EditPlan`. Keep that boundary.
- Sample documents must stay synthetic. No real personal or health data.
- If you change the edit semantics, regenerate the examples with
  `uv run python scripts/make_examples.py` (the replay tests compare against them).
