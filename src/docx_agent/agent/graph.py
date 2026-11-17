"""The LangGraph agent.

::

    START → load_document → planner ─┬─ search/read ──► explore ──► planner
                                     ├─ ask_clarification ──► clarify (interrupt) ──► planner
                                     ├─ cannot_complete ──► decline ──► END
                                     ├─ (no tool call) ──► nudge ──► planner
                                     └─ submit_edit_plan ──► apply_edits ─┬─ error ──► planner
                                                                          └─ ok ──► verify ─┬─ ok ──► finalize ──► END
                                                                                            └─ fail ──► planner / give_up

The LLM only *plans*. Applying, verifying and saving are deterministic nodes.
Every failure path feeds a precise error back to the planner, bounded by
``max_plan_attempts`` and ``max_planner_steps``.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import interrupt
from pydantic import ValidationError

from ..config import Settings, get_settings
from ..document.model import build_index, render_outline
from ..document.ops import DocumentEditor, EditError, EditPlan
from ..document.package import DocxError, DocxPackage
from ..document.verify import verify_edit
from .prompts import NO_TOOL_NUDGE, SYSTEM_PROMPT
from .tools import (
    CLARIFY,
    DECLINE,
    READ_ONLY_TOOLS,
    SUBMIT,
    AskClarification,
    CannotComplete,
    planner_tools,
    run_read_only_tool,
)

Status = Literal["running", "done", "declined", "failed"]


class AgentState(TypedDict, total=False):
    # inputs
    instruction: str
    input_path: str
    output_path: str
    # working data
    doc_name: str
    messages: Annotated[list[AnyMessage], add_messages]
    steps: int
    attempts: int
    candidate_path: str
    # results
    plan: dict[str, Any] | None
    changes: list[dict[str, Any]]
    verification: dict[str, Any] | None
    status: Status
    message: str


def _format_validation_error(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors()[:6]:
        loc = ".".join(str(x) for x in err["loc"])
        parts.append(f"{loc}: {err['msg']}")
    return "Invalid plan arguments - " + "; ".join(parts)


def _not_executed(call: dict[str, Any]) -> ToolMessage:
    """Every tool call must get a reply, even the ones we do not run (the API rejects a
    history with unanswered tool calls)."""
    return ToolMessage(content="Not executed: only one action per turn is processed.",
                       tool_call_id=call["id"], status="error")


class DocxEditAgent:
    """Builds and owns the compiled graph. ``llm`` is injected (real or fake)."""

    def __init__(self, llm: BaseChatModel, settings: Settings | None = None,
                 checkpointer: Any = None) -> None:
        self.settings = settings or get_settings()
        self.llm = llm.bind_tools(planner_tools(), tool_choice="required",
                                  parallel_tool_calls=False)
        self.graph = self._build(checkpointer)

    # ------------------------------------------------------------------ nodes
    def load_document(self, state: AgentState) -> dict[str, Any]:
        try:
            DocxPackage(Path(state["input_path"]).read_bytes())  # fail fast on bad input
        except (OSError, DocxError) as exc:
            return {"status": "failed", "message": f"Could not open the document: {exc}"}
        return {
            "doc_name": Path(state["input_path"]).name,
            "messages": [HumanMessage(content=state["instruction"])],
            "steps": 0,
            "attempts": 0,
            "status": "running",
            "plan": None,
            "changes": [],
            "verification": None,
        }

    def planner(self, state: AgentState) -> dict[str, Any]:
        # The outline is rebuilt here rather than kept in state, so checkpoints stay small.
        pkg = DocxPackage(Path(state["input_path"]).read_bytes())
        index = build_index(pkg)
        outline, truncated = render_outline(pkg, index, self.settings.outline_chars)
        system = SystemMessage(content=SYSTEM_PROMPT.format(
            doc_name=state["doc_name"],
            n_blocks=len(index.blocks),
            truncated=' truncated="true"' if truncated else "",
            outline=outline,
        ))
        ai = self.llm.invoke([system, *state["messages"]])
        return {"messages": [ai], "steps": state.get("steps", 0) + 1}

    def explore(self, state: AgentState) -> dict[str, Any]:
        ai: AIMessage = state["messages"][-1]
        pkg = DocxPackage(Path(state["input_path"]).read_bytes())
        out = []
        for call in ai.tool_calls:
            if call["name"] not in READ_ONLY_TOOLS:
                out.append(_not_executed(call))
                continue
            try:
                result = run_read_only_tool(pkg, call["name"], call["args"])
            except (ValidationError, ValueError) as exc:
                result = f"Tool error: {exc}"
            out.append(ToolMessage(content=result, tool_call_id=call["id"]))
        return {"messages": out}

    def nudge(self, state: AgentState) -> dict[str, Any]:
        return {"messages": [HumanMessage(content=NO_TOOL_NUDGE)]}

    def apply_edits(self, state: AgentState) -> dict[str, Any]:
        ai: AIMessage = state["messages"][-1]
        call = ai.tool_calls[0]
        attempts = state.get("attempts", 0) + 1

        extra = [_not_executed(c) for c in ai.tool_calls[1:]]

        def reject(msg: str) -> dict[str, Any]:
            return {"messages": [*extra, ToolMessage(content=f"ERROR: {msg}\nNothing was "
                                                     "changed. Submit a corrected plan.",
                                                     tool_call_id=call["id"], status="error")],
                    "attempts": attempts}

        try:
            plan = EditPlan.model_validate(call["args"])
        except ValidationError as exc:
            return reject(_format_validation_error(exc))
        pkg = DocxPackage(Path(state["input_path"]).read_bytes())
        work = pkg.copy()
        try:
            result = DocumentEditor(work).apply(plan)
        except EditError as exc:
            return reject(str(exc))
        candidate = Path(state["output_path"]).with_suffix(".candidate.docx")
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_bytes(work.to_bytes())
        changes = [
            {"op": c.kind, "block_id": c.block_id, "before": c.before, "after": c.after}
            for c in result.changes
        ]
        return {
            "messages": [*extra, ToolMessage(content=f"Applied {len(plan.operations)} operation(s); "
                                     "running integrity verification.", tool_call_id=call["id"])],
            "attempts": attempts,
            "plan": plan.model_dump(mode="json"),
            "changes": changes,
            "candidate_path": str(candidate),
        }

    def verify(self, state: AgentState) -> dict[str, Any]:
        before = DocxPackage(Path(state["input_path"]).read_bytes())
        after_bytes = Path(state["candidate_path"]).read_bytes()
        plan = EditPlan.model_validate(state["plan"])
        report = verify_edit(before, after_bytes, plan)
        update: dict[str, Any] = {"verification": report.to_dict()}
        if not report.passed:
            Path(state["candidate_path"]).unlink(missing_ok=True)
            fails = "\n".join(f"- {c.name}: {c.detail}" for c in report.failures())
            update["messages"] = [HumanMessage(
                content="The edited document FAILED integrity verification and was discarded:\n"
                        f"{fails}\nSubmit a different plan that avoids this (e.g. smaller, "
                        "more targeted operations), or call cannot_complete.")]
        return update

    def clarify(self, state: AgentState) -> dict[str, Any]:
        ai: AIMessage = state["messages"][-1]
        call = ai.tool_calls[0]
        try:
            req = AskClarification.model_validate(call["args"])
            payload = {"question": req.question, "options": req.options[:5]}
        except ValidationError:
            payload = {"question": str(call["args"]), "options": []}
        answer = interrupt(payload)
        return {"messages": [*(_not_executed(c) for c in ai.tool_calls[1:]),
                             ToolMessage(content=f"The user answered: {answer}",
                                         tool_call_id=call["id"])]}

    def decline(self, state: AgentState) -> dict[str, Any]:
        call = state["messages"][-1].tool_calls[0]
        try:
            reason = CannotComplete.model_validate(call["args"]).reason
        except ValidationError:
            reason = "The request cannot be completed."
        return {"status": "declined", "message": reason}

    def finalize(self, state: AgentState) -> dict[str, Any]:
        out = Path(state["output_path"])
        shutil.move(state["candidate_path"], out)
        plan = state.get("plan") or {}
        return {"status": "done", "message": plan.get("summary", "Document edited.")}

    def give_up(self, state: AgentState) -> dict[str, Any]:
        cand = state.get("candidate_path")
        if cand and os.path.exists(cand):
            os.unlink(cand)
        last_error = ""
        for m in reversed(state.get("messages", [])):
            if isinstance(m, (ToolMessage, HumanMessage)) and ("ERROR" in str(m.content)
                                                               or "FAILED" in str(m.content)):
                last_error = str(m.content).splitlines()[0]
                break
        return {"status": "failed",
                "message": "The agent could not produce a safe edit for this instruction. "
                           + (f"Last problem: {last_error}" if last_error else "")}

    # ---------------------------------------------------------------- routing
    def _route_after_load(self, state: AgentState) -> str:
        return "end" if state.get("status") == "failed" else "planner"

    def _route_after_planner(self, state: AgentState) -> str:
        ai = state["messages"][-1]
        if state.get("steps", 0) > self.settings.max_planner_steps:
            return "give_up"
        if not isinstance(ai, AIMessage) or not ai.tool_calls:
            return "nudge"
        name = ai.tool_calls[0]["name"]
        if name == SUBMIT:
            return "apply_edits"
        if name == CLARIFY:
            return "clarify"
        if name == DECLINE:
            return "decline"
        if name in READ_ONLY_TOOLS:
            return "explore"
        return "nudge"

    def _route_after_apply(self, state: AgentState) -> str:
        last = state["messages"][-1]
        if isinstance(last, ToolMessage) and last.status == "error":
            return "give_up" if state["attempts"] >= self.settings.max_plan_attempts else "planner"
        return "verify"

    def _route_after_verify(self, state: AgentState) -> str:
        if (state.get("verification") or {}).get("passed"):
            return "finalize"
        return "give_up" if state["attempts"] >= self.settings.max_plan_attempts else "planner"

    # ------------------------------------------------------------------ build
    def _build(self, checkpointer: Any):
        g = StateGraph(AgentState)
        g.add_node("load_document", self.load_document)
        g.add_node("planner", self.planner)
        g.add_node("explore", self.explore)
        g.add_node("nudge", self.nudge)
        g.add_node("apply_edits", self.apply_edits)
        g.add_node("verify", self.verify)
        g.add_node("clarify", self.clarify)
        g.add_node("decline", self.decline)
        g.add_node("finalize", self.finalize)
        g.add_node("give_up", self.give_up)

        g.add_edge(START, "load_document")
        g.add_conditional_edges("load_document", self._route_after_load,
                                {"planner": "planner", "end": END})
        g.add_conditional_edges("planner", self._route_after_planner, [
            "apply_edits", "clarify", "decline", "explore", "nudge", "give_up"])
        g.add_edge("explore", "planner")
        g.add_edge("nudge", "planner")
        g.add_edge("clarify", "planner")
        g.add_conditional_edges("apply_edits", self._route_after_apply,
                                ["verify", "planner", "give_up"])
        g.add_conditional_edges("verify", self._route_after_verify,
                                ["finalize", "planner", "give_up"])
        g.add_edge("finalize", END)
        g.add_edge("decline", END)
        g.add_edge("give_up", END)
        return g.compile(checkpointer=checkpointer)
