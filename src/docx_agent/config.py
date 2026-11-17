"""Runtime settings (environment driven)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "gpt-6-luna"


@dataclass(frozen=True)
class Settings:
    model: str = os.getenv("DOCX_AGENT_MODEL", DEFAULT_MODEL)
    # Planner loop guards
    max_planner_steps: int = int(os.getenv("DOCX_AGENT_MAX_STEPS", "10"))
    max_plan_attempts: int = int(os.getenv("DOCX_AGENT_MAX_ATTEMPTS", "3"))
    # How much of the document outline goes into the prompt before the agent
    # must use search/read tools.
    outline_chars: int = int(os.getenv("DOCX_AGENT_OUTLINE_CHARS", "60000"))
    request_timeout: float = float(os.getenv("DOCX_AGENT_TIMEOUT", "90"))
    reasoning_effort: str = os.getenv("DOCX_AGENT_REASONING_EFFORT", "low")


def get_settings() -> Settings:
    return Settings()
