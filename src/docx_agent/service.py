"""High-level API shared by the CLI and the web app."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from .agent.graph import DocxEditAgent
from .agent.llm import make_llm
from .config import Settings, get_settings

OutcomeStatus = Literal["done", "declined", "failed", "needs_clarification"]


@dataclass
class EditOutcome:
    thread_id: str
    status: OutcomeStatus
    message: str
    output_path: str | None = None
    question: str | None = None
    options: list[str] = field(default_factory=list)
    plan: dict[str, Any] | None = None
    changes: list[dict[str, Any]] = field(default_factory=list)
    verification: dict[str, Any] | None = None
    llm_calls: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EditService:
    """Runs the agent; keeps interrupted runs (clarifications) resumable."""

    def __init__(self, llm: BaseChatModel | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.agent = DocxEditAgent(llm or make_llm(self.settings), self.settings,
                                   checkpointer=InMemorySaver())
        self._config_extra = {"recursion_limit": 4 * self.settings.max_planner_steps + 20}

    def _config(self, thread_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": thread_id}, **self._config_extra}

    def start(self, input_path: str | Path, instruction: str, output_path: str | Path,
              thread_id: str | None = None) -> EditOutcome:
        thread_id = thread_id or uuid.uuid4().hex
        instruction = instruction.strip()
        if not instruction:
            return EditOutcome(thread_id, "failed", "The instruction is empty.")
        self.agent.graph.invoke(
            {"instruction": instruction, "input_path": str(input_path),
             "output_path": str(output_path)},
            self._config(thread_id),
        )
        return self._outcome(thread_id)

    def resume(self, thread_id: str, answer: str) -> EditOutcome:
        self.agent.graph.invoke(Command(resume=answer), self._config(thread_id))
        return self._outcome(thread_id)

    def _outcome(self, thread_id: str) -> EditOutcome:
        snap = self.agent.graph.get_state(self._config(thread_id))
        values = snap.values
        pending = [i for task in snap.tasks for i in task.interrupts]
        common = dict(
            plan=values.get("plan"),
            changes=values.get("changes") or [],
            verification=values.get("verification"),
            llm_calls=values.get("steps", 0),
        )
        if pending:
            payload = pending[0].value or {}
            return EditOutcome(thread_id, "needs_clarification",
                               payload.get("question", "Please clarify."),
                               question=payload.get("question"),
                               options=list(payload.get("options") or []), **common)
        status = values.get("status", "failed")
        if status == "running":  # should not happen: graph ended without a terminal node
            status = "failed"
        return EditOutcome(
            thread_id, status, values.get("message", ""),
            output_path=values.get("output_path") if status == "done" else None,
            **common,
        )
