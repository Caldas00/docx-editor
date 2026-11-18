# How this was built

Built with an AI coding agent (Claude Code). The agent's work is never trusted on its word: it
has to pass mechanical checks.

- **Design first, deterministic core first.** The architecture was fixed before any code. The
  document engine was built and tested with no model in the loop; the LLM came last.
- **Verifier against an oracle.** The verifier compares the result with a second, independent
  implementation (`oracle.py`), never with what the engine says it did. Mutation tests make
  sure the verifier catches broken outputs, and fuzzing found about a dozen interaction bugs.
- **Every bug becomes a test.** Behavioural bugs get an eval case (`evals/cases.json`) before
  the prompt is fixed; engine bugs get a unit test. The rules are in [`CLAUDE.md`](../CLAUDE.md).
- **Evals choose the model.** They showed `gpt-6-luna` passing the suite at about 1 % of
  `gpt-5.5`'s cost.
- **Quality gate.** `scripts/check.sh` (lint plus offline tests) runs before every commit and
  in CI.
