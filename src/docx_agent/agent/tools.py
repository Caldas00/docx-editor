"""Tools exposed to the planner LLM.

Two read-only tools let the planner inspect the document; three *terminal*
tools end the planning step and decide the next node in the graph:

* ``submit_edit_plan``  -> apply + verify
* ``ask_clarification`` -> human-in-the-loop interrupt
* ``cannot_complete``   -> finish without editing

None of the tools execute code or touch the filesystem: they only call the
document layer in :mod:`docx_agent.document`.
"""

from __future__ import annotations

from typing import Any

from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import BaseModel, Field

from ..document.model import build_index, describe_block, paragraph_view
from ..document.ops import EditPlan
from ..document.package import DocxPackage

SUBMIT = "submit_edit_plan"
CLARIFY = "ask_clarification"
DECLINE = "cannot_complete"
SEARCH = "search_document"
READ = "read_blocks"

TERMINAL_TOOLS = {SUBMIT, CLARIFY, DECLINE}
READ_ONLY_TOOLS = {SEARCH, READ}


class SearchDocument(BaseModel):
    """Find blocks whose text contains a query (case-insensitive)."""

    query: str = Field(min_length=1)


class ReadBlocks(BaseModel):
    """Return the full, untruncated lines for the given block ids."""

    block_ids: list[str] = Field(min_length=1, max_length=50)


class AskClarification(BaseModel):
    """Ask the user to resolve a genuine ambiguity before editing."""

    question: str = Field(description="Short question for the user, written in English.")
    options: list[str] = Field(
        default_factory=list,
        description="Concrete choices in English to offer, if any (max 5).",
    )


class CannotComplete(BaseModel):
    """Stop without editing and tell the user why."""

    reason: str = Field(description="Concise explanation for the user, written in English.")


def _tool(schema: type[BaseModel], name: str, description: str | None = None) -> dict[str, Any]:
    tool = convert_to_openai_tool(schema)
    tool["function"]["name"] = name
    if description:
        tool["function"]["description"] = description
    return tool


def planner_tools() -> list[dict[str, Any]]:
    return [
        _tool(EditPlan, SUBMIT,
              "Submit the complete list of edit operations that fulfils the instruction. "
              "Write the plan summary in English. "
              "They are applied in order and then verified."),
        _tool(AskClarification, CLARIFY),
        _tool(CannotComplete, DECLINE),
        _tool(SearchDocument, SEARCH),
        _tool(ReadBlocks, READ),
    ]


def run_read_only_tool(pkg: DocxPackage, name: str, args: dict[str, Any]) -> str:
    index = build_index(pkg)
    if name == SEARCH:
        q = SearchDocument.model_validate(args).query.lower()
        hits = [describe_block(pkg, b, max_text=400) for b in index.paragraphs()
                if q in paragraph_view(b.element).text.lower()]
        if not hits:
            return f"No block contains {q!r}."
        more = f"\n... {len(hits) - 30} more" if len(hits) > 30 else ""
        return "\n".join(hits[:30]) + more
    if name == READ:
        ids = ReadBlocks.model_validate(args).block_ids
        lines = []
        for bid in ids:
            block = index.get(bid)
            lines.append(describe_block(pkg, block) if block else f"[{bid}] does not exist")
        return "\n".join(lines)
    raise ValueError(f"unknown read-only tool {name}")
