"""A scripted chat model for deterministic graph tests."""

from __future__ import annotations

import itertools
from collections.abc import Callable
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

_ids = itertools.count(1)


def call(name: str, **args: Any) -> AIMessage:
    """An AIMessage that calls one tool."""
    return AIMessage(content="", tool_calls=[{"name": name, "args": args,
                                              "id": f"call_{next(_ids)}", "type": "tool_call"}])


def submit(*ops: dict, summary: str = "test edit") -> AIMessage:
    return call("submit_edit_plan", summary=summary, operations=list(ops))


class ScriptedLLM(BaseChatModel):
    """Returns the scripted responses in order and records every prompt."""

    script: list[Any]
    seen: list[list[BaseMessage]] = []
    bound: dict[str, Any] = {}

    def bind_tools(self, tools, **kwargs):  # type: ignore[override]
        self.bound = {"tools": tools, **kwargs}
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.seen.append(list(messages))
        if not self.script:
            raise AssertionError("ScriptedLLM ran out of responses")
        nxt = self.script.pop(0)
        msg = nxt(messages) if isinstance(nxt, Callable) else nxt
        return ChatResult(generations=[ChatGeneration(message=msg)])

    @property
    def _llm_type(self) -> str:
        return "scripted"
