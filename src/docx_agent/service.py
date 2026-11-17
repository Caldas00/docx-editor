"""High-level API shared by the CLI and the web app."""

from __future__ import annotations

import logging
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

log = logging.getLogger(__name__)

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
    usage: dict[str, int] = field(default_factory=dict)  # tokens: input / output / cached

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
              thread_id: str | None = None,
              selection: dict[str, Any] | None = None) -> EditOutcome:
        thread_id = thread_id or uuid.uuid4().hex
        instruction = instruction.strip()
        if not instruction:
            return EditOutcome(thread_id, "failed", "The instruction is empty.")
        return self._run(thread_id, {"instruction": instruction, "input_path": str(input_path),
                                     "output_path": str(output_path),
                                     "selection": selection})

    def resume(self, thread_id: str, answer: str) -> EditOutcome:
        return self._run(thread_id, Command(resume=answer))

    def _run(self, thread_id: str, graph_input: Any) -> EditOutcome:
        try:
            self.agent.graph.invoke(graph_input, self._config(thread_id))
        except Exception as exc:  # noqa: BLE001 - LLM/API/network errors become an outcome
            log.exception("edit run %s failed", thread_id)
            values = self.agent.graph.get_state(self._config(thread_id)).values
            cand = values.get("candidate_path")
            if cand:
                Path(cand).unlink(missing_ok=True)
            self._forget(thread_id)
            return EditOutcome(thread_id, "failed",
                               f"The edit run failed ({type(exc).__name__}: "
                               f"{str(exc)[:300]}). Nothing was changed.")
        outcome = self._outcome(thread_id)
        if outcome.status != "needs_clarification":
            self._forget(thread_id)  # finished runs need no checkpoints
        return outcome

    def _forget(self, thread_id: str) -> None:
        checkpointer = self.agent.graph.checkpointer
        if checkpointer is not None and hasattr(checkpointer, "delete_thread"):
            checkpointer.delete_thread(thread_id)

    def _outcome(self, thread_id: str) -> EditOutcome:
        snap = self.agent.graph.get_state(self._config(thread_id))
        values = snap.values
        pending = [i for task in snap.tasks for i in task.interrupts]
        common = dict(
            plan=values.get("plan"),
            changes=values.get("changes") or [],
            verification=values.get("verification"),
            llm_calls=values.get("steps", 0),
            usage=dict(values.get("usage") or {}),
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
