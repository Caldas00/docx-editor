"""LangGraph routing tests with a scripted LLM (no network)."""

from pathlib import Path

import pytest
from fake_llm import ScriptedLLM, call, submit
from langchain_core.messages import AIMessage, ToolMessage

from docx_agent.config import Settings
from docx_agent.document import DocxPackage
from docx_agent.document.model import build_index, paragraph_view
from docx_agent.service import EditService

GOOD = {"op": "replace_text", "block_id": "t0.r2.c1.p0", "find": "6 of 12",
        "replace_with": "7 of 12"}
BAD = {"op": "replace_text", "block_id": "t0.r2.c1.p0", "find": "6 of 13",
       "replace_with": "7 of 12"}


@pytest.fixture()
def paths(tmp_path, session_note_bytes):
    src = tmp_path / "in.docx"
    src.write_bytes(session_note_bytes)
    return src, tmp_path / "out.docx"


def service(script, **settings) -> tuple[EditService, ScriptedLLM]:
    llm = ScriptedLLM(script=list(script), seen=[])
    return EditService(llm, Settings(**settings)), llm


def text_of(path: Path, block_id: str) -> str:
    pkg = DocxPackage(path.read_bytes())
    return paragraph_view(build_index(pkg).get(block_id).element).text


def test_happy_path(paths):
    src, out = paths
    svc, llm = service([submit(GOOD)])
    res = svc.start(src, "change session number to 7", out)
    assert res.status == "done"
    assert res.verification["passed"]
    assert text_of(out, "t0.r2.c1.p0") == "7 of 12"
    assert not out.with_suffix(".candidate.docx").exists()
    # the planner saw the outline and the instruction, and tools were forced
    system, human = llm.seen[0][:2]
    assert "[t0.r2.c1.p0]" in system.content and human.content == "change session number to 7"
    assert llm.bound["tool_choice"] == "required"


def test_explore_then_submit(paths):
    src, out = paths
    svc, llm = service([call("search_document", query="session number"), submit(GOOD)])
    res = svc.start(src, "x", out)
    assert res.status == "done"
    tool_result = llm.seen[1][-1]
    assert isinstance(tool_result, ToolMessage) and "Session number" in tool_result.content


def test_engine_error_is_fed_back_and_corrected(paths):
    src, out = paths
    svc, llm = service([submit(BAD), submit(GOOD)])
    res = svc.start(src, "x", out)
    assert res.status == "done"
    feedback = llm.seen[1][-1]
    assert isinstance(feedback, ToolMessage) and "not found" in feedback.content
    assert "Closest text: '6 of 12'" in feedback.content


def test_schema_error_is_fed_back(paths):
    src, out = paths
    svc, llm = service([call("submit_edit_plan", summary="x", operations=[{"op": "explode"}]),
                        submit(GOOD)])
    assert svc.start(src, "x", out).status == "done"
    assert "Invalid plan arguments" in llm.seen[1][-1].content


def test_gives_up_after_max_attempts_and_writes_nothing(paths):
    src, out = paths
    svc, _ = service([submit(BAD) for _ in range(3)], max_plan_attempts=3)
    res = svc.start(src, "x", out)
    assert res.status == "failed"
    assert "not found" in res.message
    assert not out.exists() and not out.with_suffix(".candidate.docx").exists()


def test_clarification_interrupt_and_resume(paths):
    src, out = paths
    svc, llm = service([
        call("ask_clarification", question="Which date?", options=["12 Nov", "19 Nov"]),
        submit(GOOD),
    ])
    res = svc.start(src, "change the date", out)
    assert res.status == "needs_clarification"
    assert res.question == "Which date?" and res.options == ["12 Nov", "19 Nov"]
    assert not out.exists()
    res2 = svc.resume(res.thread_id, "12 Nov")
    assert res2.status == "done"
    answer = llm.seen[1][-1]
    assert isinstance(answer, ToolMessage) and "12 Nov" in answer.content


def test_decline(paths):
    src, out = paths
    svc, _ = service([call("cannot_complete", reason="Images cannot be edited.")])
    res = svc.start(src, "make the chart bigger", out)
    assert res.status == "declined" and res.message == "Images cannot be edited."
    assert not out.exists()


def test_nudge_when_model_answers_in_prose(paths):
    src, out = paths
    svc, llm = service([AIMessage(content="Sure, I will do it."), submit(GOOD)])
    assert svc.start(src, "x", out).status == "done"
    assert "must respond by calling exactly one tool" in llm.seen[1][-1].content


def test_step_limit(paths):
    src, out = paths
    svc, _ = service([call("search_document", query="x") for _ in range(5)], max_planner_steps=3)
    res = svc.start(src, "x", out)
    assert res.status == "failed"


def test_unreadable_input(tmp_path):
    bad = tmp_path / "bad.docx"
    bad.write_bytes(b"nope")
    svc, _ = service([])
    res = svc.start(bad, "x", tmp_path / "o.docx")
    assert res.status == "failed" and "Could not open" in res.message


def test_empty_instruction(paths):
    src, out = paths
    svc, _ = service([])
    assert svc.start(src, "   ", out).status == "failed"


def test_selection_is_given_to_the_planner(paths):
    src, out = paths
    svc, llm = service([submit(GOOD)])
    res = svc.start(src, "change this to 7 of 12", out,
                    selection={"text": "6 of 12", "blocks": ["t0.r2.c1.p0"]})
    assert res.status == "done"
    human = llm.seen[0][1].content
    assert '<selection blocks="t0.r2.c1.p0">\n6 of 12\n</selection>' in human


def test_token_usage_is_summed_over_calls(paths):
    src, out = paths
    first = call("search_document", query="session")
    first.usage_metadata = {"input_tokens": 1000, "output_tokens": 20, "total_tokens": 1020,
                            "input_token_details": {"cache_read": 0}}
    second = submit(GOOD)
    second.usage_metadata = {"input_tokens": 1100, "output_tokens": 80, "total_tokens": 1180,
                             "input_token_details": {"cache_read": 1000}}
    svc, _ = service([first, second])
    res = svc.start(src, "x", out)
    assert res.usage == {"input": 2100, "output": 100, "cached": 1000}
