"""Regression tests for issues found in code review."""

import time
from pathlib import Path

import pytest
from fake_llm import ScriptedLLM, call, submit
from helpers import P, R, pkg_of, plan, run_plan, texts
from langchain_core.messages import AIMessage, ToolMessage

from docx_agent.config import Settings
from docx_agent.document import EditError, apply_plan
from docx_agent.document.model import build_index
from docx_agent.document.ops import _suggest
from docx_agent.document.render import render_preview, render_redline
from docx_agent.service import EditService

GOOD = {"op": "replace_text", "block_id": "t0.r2.c1.p0", "find": "6 of 12", "replace_with": "7 of 12"}
BAD = {"op": "replace_text", "block_id": "t0.r2.c1.p0", "find": "nope", "replace_with": "x"}


def test_preview_does_not_inject_attribute_values():
    evil = '&quot;&gt;&lt;img src=x onerror=alert(1)&gt;'
    body = P(R("text", f'<w:color w:val="{evil}"/>'))
    body += f'<w:tbl><w:tr><w:tc><w:tcPr><w:shd w:val="clear" w:fill="{evil}"/></w:tcPr>' \
            + P(R("cell")) + "</w:tc></w:tr></w:tbl>" + P("")
    html = render_preview(pkg_of(body))
    assert "onerror" not in html and "<img" not in html
    ok = render_preview(pkg_of(P(R("red", '<w:color w:val="FF0000"/>'))))
    assert "color:#FF0000" in ok


@pytest.fixture()
def paths(tmp_path, session_note_bytes):
    src = tmp_path / "in.docx"
    src.write_bytes(session_note_bytes)
    return src, tmp_path / "out.docx"


def test_llm_exception_becomes_failed_outcome(paths):
    src, out = paths

    def boom(_messages):
        raise RuntimeError("insufficient_quota")

    svc = EditService(ScriptedLLM(script=[boom], seen=[]), Settings())
    res = svc.start(src, "x", out)
    assert res.status == "failed" and "insufficient_quota" in res.message
    assert not out.exists()


def test_every_tool_call_gets_an_answer(paths):
    src, out = paths
    two_calls = AIMessage(content="", tool_calls=[
        {"name": "submit_edit_plan", "args": {"summary": "s", "operations": [BAD]},
         "id": "c1", "type": "tool_call"},
        {"name": "search_document", "args": {"query": "x"}, "id": "c2", "type": "tool_call"},
    ])
    llm = ScriptedLLM(script=[two_calls, submit(GOOD)], seen=[])
    res = EditService(llm, Settings()).start(src, "x", out)
    assert res.status == "done"
    answered = {m.tool_call_id for m in llm.seen[1] if isinstance(m, ToolMessage)}
    assert {"c1", "c2"} <= answered


def test_finished_threads_are_forgotten(paths):
    src, out = paths
    svc = EditService(ScriptedLLM(script=[submit(GOOD)], seen=[]), Settings())
    res = svc.start(src, "x", out)
    assert svc.agent.graph.get_state({"configurable": {"thread_id": res.thread_id}}).values == {}


def test_clarification_thread_is_kept_until_answered(paths):
    src, out = paths
    svc = EditService(ScriptedLLM(script=[call("ask_clarification", question="Which?"),
                                          submit(GOOD)], seen=[]), Settings())
    res = svc.start(src, "x", out)
    assert svc.resume(res.thread_id, "the session number").status == "done"


def test_format_text_range_ending_on_a_tab_only_formats_the_range():
    pkg = pkg_of(P("<w:r><w:t>Name:</w:t><w:tab/><w:t>Ana</w:t></w:r>"))
    out, _ = run_plan(pkg, {"op": "format_text", "block_id": "p0", "find": "Name:\t",
                            "bold": True})
    assert texts(out)["p0"] == "Name:\tAna"


def test_custom_xml_blocks_are_read_only():
    pkg = pkg_of('<w:customXml w:element="x">' + P(R("inside")) + "</w:customXml>" + P(R("out")))
    assert not build_index(pkg).get("p0").editable
    with pytest.raises(EditError, match="read-only"):
        run_plan(pkg, {"op": "replace_text", "block_id": "p0", "find": "inside",
                       "replace_with": "x"})


def test_paragraph_after_final_table_cannot_be_deleted():
    pkg = pkg_of(P(R("intro")) + "<w:tbl><w:tr><w:tc>" + P(R("c")) + "</w:tc></w:tr></w:tbl>"
                 + P(R("last")))
    with pytest.raises(EditError, match="final table"):
        run_plan(pkg, {"op": "delete_paragraph", "block_id": "p1"})


def test_near_miss_suggestion_is_fast_on_large_documents():
    texts_ = [(f"p{i}", "The client reported improved sleep over the past two weeks. " * 8)
              for i in range(2000)]
    t0 = time.perf_counter()
    _suggest(texts_, "the client reportd improved")
    assert time.perf_counter() - t0 < 3


def test_deleted_cell_paragraph_is_shown_in_its_own_cell():
    cell = lambda inner: f"<w:tc>{inner}</w:tc>"  # noqa: E731
    body = P(R("before")) + f"<w:tbl><w:tr>{cell(P(R('A1')))}" \
        f"{cell(P(R('B1')) + P(R('B2 gone')))}</w:tr></w:tbl>" + P(R("after"))
    before = pkg_of(body)
    p = plan({"op": "delete_paragraph", "block_id": "t0.r0.c1.p1"})
    after = before.copy()
    apply_plan(after, p)
    html = render_redline(before, after, p)
    cells = html.split("<td")
    assert "B2 gone" in cells[2] and "B2 gone" not in cells[1]


def test_samples_command_runs_without_dev_dependencies(tmp_path: Path):
    from docx_agent.samples import SAMPLES, write_samples
    assert len(write_samples(tmp_path)) == len(SAMPLES)
