"""HTTP API tests (FastAPI TestClient + scripted LLM)."""

import io

import pytest
from fake_llm import ScriptedLLM, call, submit
from fastapi.testclient import TestClient

from docx_agent.config import Settings
from docx_agent.document import DocxPackage
from docx_agent.document.model import build_index, paragraph_view
from docx_agent.service import EditService
from docx_agent.web import app as web

GOOD = {"op": "replace_text", "block_id": "t0.r2.c1.p0", "find": "6 of 12", "replace_with": "7 of 12"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "RUNS_DIR", tmp_path / "runs")
    web._sessions.clear()
    with TestClient(web.app) as c:
        yield c
    web.set_service(None)


def use_script(*script) -> ScriptedLLM:
    llm = ScriptedLLM(script=list(script), seen=[])
    web.set_service(EditService(llm, Settings()))
    return llm


def test_index_and_config(client):
    page = client.get("/")
    assert "Docx Agent" in page.text
    # assets are versioned by content so browsers never run a stale UI after an update
    assert '/static/app.css?v=' in page.text and '/static/app.js?v=' in page.text
    assert page.headers["cache-control"] == "no-cache"
    cfg = client.get("/api/config").json()
    assert {s["name"] for s in cfg["samples"]} >= {"session_note.docx", "referral_letter.docx"}


def test_edit_flow_with_redline_download_and_undo(client):
    use_script(submit(GOOD))
    s = client.post("/api/sessions/sample", json={"name": "session_note.docx"}).json()
    assert s["version"] == 0 and "Session Progress Note" in s["preview_html"]

    r = client.post(f"/api/sessions/{s['id']}/edit",
                    json={"instruction": "session 7",
                          "selection": {"text": "6 of 12", "blocks": ["t0.r2.c1.p0"]}}).json()
    assert r["turn"]["status"] == "done"
    assert r["turn"]["verification"]["passed"]
    assert r["turn"]["selection"]["blocks"] == ["t0.r2.c1.p0"]
    assert r["turn"]["model"] and "cost" in r["turn"]
    assert r["session"]["version"] == 1 and r["session"]["turns"][0]["version"] == 1
    assert "<del>6</del><ins>7</ins>" in r["session"]["redline_html"]

    d = client.get(f"/api/sessions/{s['id']}/download")
    assert d.status_code == 200
    assert d.headers["content-disposition"].endswith('session_note.edited-v1.docx"')
    pkg = DocxPackage(d.content)
    assert paragraph_view(build_index(pkg).get("t0.r2.c1.p0").element).text == "7 of 12"

    u = client.post(f"/api/sessions/{s['id']}/undo").json()
    assert u["version"] == 0 and u["turns"][0]["undone"] is True
    assert client.post(f"/api/sessions/{s['id']}/undo").status_code == 409


def test_answer_is_a_new_message_that_sees_the_question(client):
    llm = use_script(call("ask_clarification", question="Which one?", options=["A", "B"]),
                     submit(GOOD))
    s = client.post("/api/sessions/sample", json={"name": "session_note.docx"}).json()
    r = client.post(f"/api/sessions/{s['id']}/edit", json={"instruction": "change it"}).json()
    assert r["turn"]["status"] == "needs_clarification"
    assert r["turn"]["options"] == ["A", "B"]
    r2 = client.post(f"/api/sessions/{s['id']}/edit", json={"instruction": "A"}).json()
    assert r2["turn"]["status"] == "done" and r2["session"]["version"] == 1
    assert [t["status"] for t in r2["session"]["turns"]] == ["needs_clarification", "done"]
    prompt = llm.seen[1][1].content
    assert "<conversation>" in prompt and "Assistant asked: Which one?" in prompt
    assert prompt.endswith("Current message: A")


def test_history_includes_previous_edits(client):
    llm = use_script(submit(GOOD), submit({"op": "format_text", "block_id": "t0.r2.c1.p0",
                                           "find": "7 of 12", "bold": True}))
    s = client.post("/api/sessions/sample", json={"name": "session_note.docx"}).json()
    client.post(f"/api/sessions/{s['id']}/edit", json={"instruction": "session 7"})
    client.post(f"/api/sessions/{s['id']}/edit", json={"instruction": "make it bold"})
    prompt = llm.seen[1][1].content
    assert 'changed "6 of 12" → "7 of 12"' in prompt


def test_decline_keeps_version(client):
    use_script(call("cannot_complete", reason="Not possible."))
    s = client.post("/api/sessions/sample", json={"name": "session_note.docx"}).json()
    r = client.post(f"/api/sessions/{s['id']}/edit", json={"instruction": "x"}).json()
    assert r["turn"]["status"] == "declined" and r["session"]["version"] == 0
    assert len(r["session"]["turns"]) == 1


def test_upload_validation(client, session_note_bytes):
    bad = client.post("/api/sessions/upload",
                      files={"file": ("x.docx", io.BytesIO(b"nope"), "application/octet-stream")})
    assert bad.status_code == 400
    wrong_ext = client.post("/api/sessions/upload",
                            files={"file": ("x.pdf", io.BytesIO(b"%PDF"), "application/pdf")})
    assert wrong_ext.status_code == 400
    ok = client.post("/api/sessions/upload",
                     files={"file": ("../../evil name!.docx", io.BytesIO(session_note_bytes),
                                     "application/octet-stream")})
    assert ok.status_code == 200 and ok.json()["name"] == "evil name_.docx"


def test_unknown_session_and_sample(client):
    assert client.get("/api/sessions/nope").status_code == 404
    assert client.post("/api/sessions/sample", json={"name": "../secret"}).status_code == 404


def test_exact_pages_endpoint(client, monkeypatch):
    # The "Document" view shows the pages as LibreOffice lays them out (see web/exact.py).
    # Without it the endpoint says so and the UI uses its own layout.
    from docx_agent.web import exact
    s = client.post("/api/sessions/sample", json={"name": "session_note.docx"}).json()
    monkeypatch.setattr(exact, "engine", lambda: None)
    assert client.get("/api/config").json()["exact_pages"] is None
    assert client.get(f"/api/sessions/{s['id']}/pdf").status_code == 501

    monkeypatch.setattr(exact, "engine", lambda: "libreoffice")
    monkeypatch.setattr(exact, "to_pdf", lambda src, dest: False)
    assert client.get(f"/api/sessions/{s['id']}/pdf").status_code == 502

    calls = []
    def fake(src, dest):
        calls.append(src)
        dest.write_bytes(b"%PDF-1.4 fake")
        return True
    monkeypatch.setattr(exact, "to_pdf", fake)
    r = client.get(f"/api/sessions/{s['id']}/pdf?version=0")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    client.get(f"/api/sessions/{s['id']}/pdf?version=0")
    assert len(calls) == 1  # cached next to the version
    assert client.get(f"/api/sessions/{s['id']}/pdf?version=9").status_code == 404


def test_exact_engine_can_be_turned_off(monkeypatch):
    from docx_agent.web import exact
    monkeypatch.setenv("DOCX_AGENT_EXACT", "0")
    assert exact.engine() is None
