"""Approximate OpenAI list prices, used to show the cost of each edit.

USD per 1M tokens (standard tier): (input, cached input, output). Source:
developers.openai.com/api/docs/pricing, checked 2026-11-17. Unknown models show no cost.
"""

from __future__ import annotations

PRICES: dict[str, tuple[float, float, float]] = {
    "gpt-6-luna": (0.10, 0.01, 0.50),
    "gpt-6.1-sol": (2.00, 0.10, 10.00),
    "gpt-5.5": (5.00, 0.50, 30.00),
    "gpt-5.4": (2.50, 0.25, 15.00),
    "gpt-5.4-mini": (0.75, 0.075, 4.50),
    "gpt-5.4-nano": (0.20, 0.02, 1.25),
    "gpt-5-mini": (0.25, 0.025, 2.00),
    "gpt-5-nano": (0.05, 0.005, 0.40),
    "gpt-4.1": (2.00, 0.50, 8.00),
    "gpt-4.1-mini": (0.40, 0.10, 1.60),
}


def estimate_cost(model: str, usage: dict[str, int]) -> float | None:
    """Estimated USD cost of the token ``usage`` ({input, output, cached})."""
    price = PRICES.get(model)
    if price is None or not usage:
        return None
    p_in, p_cached, p_out = price
    cached = usage.get("cached", 0)
    fresh = max(usage.get("input", 0) - cached, 0)
    return (fresh * p_in + cached * p_cached + usage.get("output", 0) * p_out) / 1_000_000
