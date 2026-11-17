"""Conversation memory for multi-turn editing.

Every user message starts a fresh agent run on the *current* version of the document.
The earlier turns are passed along as a compact transcript, so the planner can resolve
"the same colours as the others", "make it bold", "the session date" (as an answer to
its own question) or "you already asked me that". Block ids are deliberately left out:
they refer to older versions of the document.
"""

from __future__ import annotations

import json
from typing import Any

MAX_TURNS = 12
MAX_CHANGES = 8
MAX_TEXT = 160

_OP_WORDS = {
    "replace_text": "changed", "delete_text": "deleted text", "insert_text": "inserted text",
    "insert_paragraph": "added paragraph", "delete_paragraph": "removed paragraph",
    "format_text": "formatted", "restyle_text": "restyled", "delete_images": "removed pictures",
    "delete_table_row": "removed table row", "insert_table_row": "added table row",
    "delete_table": "removed table", "insert_table": "added table",
    "move_blocks": "moved", "duplicate_blocks": "duplicated", "set_paragraph_format":
    "changed paragraph format", "split_paragraph": "split", "merge_paragraphs": "merged",
    "insert_page_break": "added page break", "insert_table_column": "added column",
    "delete_table_columns": "removed columns", "blocks_to_table": "put into a table",
    "insert_hyperlink": "linked", "remove_hyperlink": "unlinked", "set_hyperlink_url":
    "changed link", "create_header_footer": "created header/footer",
}


def _q(text: str | None) -> str:
    text = (text or "").replace("\n", " ").strip()
    if len(text) > MAX_TEXT:
        text = text[:MAX_TEXT] + "…"
    return json.dumps(text, ensure_ascii=False)


def _change_line(change: dict[str, Any]) -> str:
    word = _OP_WORDS.get(change.get("op", ""), change.get("op", "edited"))
    before, after = change.get("before"), change.get("after")
    if change.get("op") in ("format_text", "restyle_text"):
        return f"{word} {_q(after)}"
    if before is None:
        return f"{word} {_q(after)}"
    if after is None:
        return f"{word} {_q(before)}"
    return f"{word} {_q(before)} → {_q(after)}"


def format_history(turns: list[dict[str, Any]]) -> str:
    """Render earlier turns as a short transcript (empty string if there are none)."""
    lines: list[str] = []
    shown = turns[-MAX_TURNS:]
    first = len(turns) - len(shown) + 1
    for n, turn in enumerate(shown, first):
        user = f"{n}. User: {turn.get('instruction', '').strip()}"
        sel = turn.get("selection") or {}
        if (sel.get("text") or "").strip():
            user += f"  [with this text selected: {_q(sel['text'])}]"
        lines.append(user)
        status = turn.get("status")
        message = (turn.get("message") or "").strip()
        if status == "done":
            undone = " (the user later UNDID this edit)" if turn.get("undone") else ""
            lines.append(f"   Assistant applied an edit{undone}: {message}")
            changes = turn.get("changes") or []
            for change in changes[:MAX_CHANGES]:
                lines.append(f"     - {_change_line(change)}")
            if len(changes) > MAX_CHANGES:
                lines.append(f"     - … and {len(changes) - MAX_CHANGES} more changes")
        elif status == "needs_clarification":
            options = "; ".join(_q(o) for o in turn.get("options") or [])
            lines.append(f"   Assistant asked: {turn.get('question') or message}"
                         + (f" Options: {options}" if options else ""))
        elif status in ("declined", "failed"):
            lines.append(f"   Assistant did not change the document: {message}")
    if not lines:
        return ""
    return "<conversation>\n" + "\n".join(lines) + "\n</conversation>\n"
