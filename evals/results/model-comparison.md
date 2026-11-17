# Model comparison (30 cases × 3 runs)

Run on 2026-11-17 with `uv run python evals/run.py --models <model> --repeat 3`. Cost is the
average estimated USD per edit from the token usage the API reports and the list prices in
`src/docx_agent/pricing.py`. Prompt caching cuts the input cost of follow-up calls.

| model | passed | median latency | avg cost / edit | notes |
|---|---|---|---|---|
| **gpt-6-luna** (default) | **90/90** | 2.4 s | **$0.0001** | 89/90 before the colour-name table was added to the prompt (it picked a different purple) |
| gpt-5.4-mini | 90/90 | 2.2 s | $0.0012 | |
| gpt-5-mini | 90/90 | 3.3 s | $0.0007 | |
| gpt-5.5 (previous default) | 30/30 (1 run) | 2.3 s | $0.0118 | about 100× the cost of gpt-6-luna |
| gpt-5.4-nano | 25/30 (1 run) | 2.3 s | $0.0005 | missed formatting and clarification cases |

On the earlier 22-case suite: gpt-5.5 66/66, gpt-5.4-mini 64/66, gpt-4.1 63/66.
`latest.md` holds the per-case results of the most recent run.
