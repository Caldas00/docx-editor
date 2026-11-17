"""Small FastAPI app: upload or pick a document, give instructions, see a redline.

Run with ``docx-agent serve`` (or ``uvicorn docx_agent.web.app:app``).
Local demo: sessions live in memory and in ``.runs/web``; there is no auth.
"""

from __future__ import annotations

import os
import re
import shutil
import threading
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..config import get_settings
from ..document import DocxError, DocxPackage, EditPlan
from ..document.render import render_preview, render_redline
from ..service import EditOutcome, EditService

STATIC = Path(__file__).parent / "static"
ROOT = Path(__file__).resolve().parents[3]
SAMPLES_DIR = Path(os.getenv("DOCX_AGENT_SAMPLES", ROOT / "samples" / "input"))
RUNS_DIR = Path(os.getenv("DOCX_AGENT_RUNS", ROOT / ".runs" / "web"))
MAX_UPLOAD = 20 * 1024 * 1024

SAMPLE_INFO: dict[str, dict[str, Any]] = {
    "session_note.docx": {
        "title": "Session progress note",
        "description": "Table, lists, image, hyperlink, field, comment, header & footer.",
        "suggestions": [
            "Update the session number to 7 of 12.",
            "The clinician is now Dr. Ana Costa — update her name everywhere.",
            "Add 'Grounding exercise (5-4-3-2-1)' as another intervention used.",
            "Remove the sentence about reviewing again next session.",
            "Make 'two thought records' bold.",
            "Change the date to 20 November 2026.",
        ],
    },
    "referral_letter.docx": {
        "title": "Referral letter",
        "description": "Letterhead image, styled table, mixed bold and italic text.",
        "suggestions": [
            "Address the letter to Dr. Rui Almeida instead.",
            "In the summary table, change the anxiety status from Moderate to Mild.",
            "Remove the word 'persistent'.",
            "Add a sentence at the end of the first paragraph saying the client has consented "
            "to this referral.",
        ],
    },
    "intake_form.docx": {
        "title": "Client intake form",
        "description": "Form table and a free-text answer containing a prompt injection.",
        "suggestions": [
            "Change the preferred name to Sam.",
            "Add 'Prefers morning appointments.' as a new paragraph after the answer 'No.'",
            "Make the consent sentence italic.",
        ],
    },
}


@dataclass
class Version:
    path: Path
    instruction: str | None = None
    outcome: dict[str, Any] | None = None
    redline_html: str | None = None
    seconds: float = 0.0


@dataclass
class DocSession:
    id: str
    name: str
    dir: Path
    versions: list[Version] = field(default_factory=list)
    pending: dict[str, Any] | None = None  # interrupted run awaiting an answer
    lock: threading.Lock = field(default_factory=threading.Lock)
    attempts: list[dict[str, Any]] = field(default_factory=list)  # non-applied outcomes

    @property
    def current(self) -> Version:
        return self.versions[-1]


class EditRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=2000)


class AnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=1000)


class SampleRequest(BaseModel):
    name: str


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    if os.getenv("DOCX_AGENT_KEEP_RUNS") != "1":
        shutil.rmtree(RUNS_DIR, ignore_errors=True)


app = FastAPI(title="Docx Agent", docs_url="/api/docs", openapi_url="/api/openapi.json",
              lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")

_sessions: dict[str, DocSession] = {}
_service: EditService | None = None
_service_lock = threading.Lock()


def get_service() -> EditService:
    global _service
    with _service_lock:
        if _service is None:
            _service = EditService()
        return _service


def set_service(service: EditService | None) -> None:
    """Dependency injection hook (tests use a scripted LLM)."""
    global _service
    _service = service


def _session(sid: str) -> DocSession:
    s = _sessions.get(sid)
    if s is None:
        raise HTTPException(404, "Unknown session - reload the page.")
    return s


def _safe_name(name: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", Path(name).stem).strip() or "document"
    return f"{stem[:80]}.docx"


def _new_session(name: str, data: bytes) -> DocSession:
    try:
        DocxPackage(data)
    except DocxError as exc:
        raise HTTPException(400, str(exc)) from exc
    sid = uuid.uuid4().hex[:12]
    d = RUNS_DIR / sid
    d.mkdir(parents=True, exist_ok=True)
    path = d / "v0.docx"
    path.write_bytes(data)
    s = DocSession(sid, _safe_name(name), d, [Version(path)])
    _sessions[sid] = s
    return s


def _state(s: DocSession, view_version: int | None = None) -> dict[str, Any]:
    v_idx = len(s.versions) - 1 if view_version is None else view_version
    version = s.versions[v_idx]
    pkg = DocxPackage(version.path.read_bytes())
    return {
        "id": s.id,
        "name": s.name,
        "version": v_idx,
        "latest": len(s.versions) - 1,
        "preview_html": render_preview(pkg),
        "redline_html": version.redline_html,
        "outcome": version.outcome,
        "history": [
            {"version": i, "instruction": v.instruction, "summary": (v.outcome or {}).get("message"),
             "seconds": round(v.seconds, 1)}
            for i, v in enumerate(s.versions) if i > 0
        ],
        "pending": s.pending and {"question": s.pending["question"],
                                  "options": s.pending["options"]},
    }


def _handle_outcome(s: DocSession, outcome: EditOutcome, instruction: str, started: float,
                    out_path: Path) -> dict[str, Any]:
    seconds = time.perf_counter() - started + (s.pending or {}).get("elapsed", 0.0)
    result = outcome.to_dict()
    result["seconds"] = round(seconds, 1)
    if outcome.status == "needs_clarification":
        s.pending = {"thread_id": outcome.thread_id, "instruction": instruction,
                     "question": outcome.question, "options": outcome.options,
                     "out_path": str(out_path), "elapsed": seconds}
        return {"outcome": result, "session": _state(s)}
    s.pending = None
    if outcome.status == "done":
        before = DocxPackage(s.current.path.read_bytes())
        after = DocxPackage(out_path.read_bytes())
        redline = render_redline(before, after, EditPlan.model_validate(outcome.plan))
        s.versions.append(Version(out_path, instruction, result, redline, seconds))
    else:
        out_path.unlink(missing_ok=True)
        s.attempts.append({"instruction": instruction, "outcome": result})
    return {"outcome": result, "session": _state(s)}


# ---------------------------------------------------------------- routes
@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/api/config")
def config() -> dict[str, Any]:
    samples = []
    for name, info in SAMPLE_INFO.items():
        if (SAMPLES_DIR / name).exists():
            samples.append({"name": name, **info})
    return {"model": get_settings().model, "samples": samples,
            "has_api_key": bool(os.getenv("OPENAI_API_KEY"))}


@app.post("/api/sessions/sample")
def open_sample(req: SampleRequest) -> dict[str, Any]:
    if req.name not in SAMPLE_INFO or not (SAMPLES_DIR / req.name).exists():
        raise HTTPException(404, "Unknown sample.")
    s = _new_session(req.name, (SAMPLES_DIR / req.name).read_bytes())
    return _state(s)


@app.post("/api/sessions/upload")
async def upload(file: UploadFile = File(...)) -> dict[str, Any]:
    if not (file.filename or "").lower().endswith((".docx", ".docm")):
        raise HTTPException(400, "Please upload a .docx file.")
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "File too large (20 MB max).")
    s = _new_session(file.filename or "document.docx", data)
    return _state(s)


@app.get("/api/sessions/{sid}")
def get_session(sid: str, version: int | None = None) -> dict[str, Any]:
    s = _session(sid)
    if version is not None and not 0 <= version < len(s.versions):
        raise HTTPException(404, "Unknown version.")
    return _state(s, version)


@app.post("/api/sessions/{sid}/edit")
def edit(sid: str, req: EditRequest) -> dict[str, Any]:
    s = _session(sid)
    if not s.lock.acquire(blocking=False):
        raise HTTPException(409, "An edit is already running for this document.")
    try:
        s.pending = None
        out_path = s.dir / f"v{len(s.versions)}-{uuid.uuid4().hex[:6]}.docx"
        started = time.perf_counter()
        outcome = get_service().start(s.current.path, req.instruction, out_path)
        return _handle_outcome(s, outcome, req.instruction, started, out_path)
    finally:
        s.lock.release()


@app.post("/api/sessions/{sid}/answer")
def answer(sid: str, req: AnswerRequest) -> dict[str, Any]:
    s = _session(sid)
    if not s.pending:
        raise HTTPException(409, "No question is pending.")
    if not s.lock.acquire(blocking=False):
        raise HTTPException(409, "An edit is already running for this document.")
    try:
        pending = s.pending
        started = time.perf_counter()
        outcome = get_service().resume(pending["thread_id"], req.answer)
        return _handle_outcome(s, outcome, pending["instruction"], started,
                               Path(pending["out_path"]))
    finally:
        s.lock.release()


@app.post("/api/sessions/{sid}/undo")
def undo(sid: str) -> dict[str, Any]:
    s = _session(sid)
    if len(s.versions) <= 1:
        raise HTTPException(409, "Nothing to undo.")
    s.versions.pop()
    s.pending = None
    return _state(s)


@app.get("/api/sessions/{sid}/download")
def download(sid: str, version: int | None = None) -> FileResponse:
    s = _session(sid)
    idx = len(s.versions) - 1 if version is None else version
    if not 0 <= idx < len(s.versions):
        raise HTTPException(404, "Unknown version.")
    stem = Path(s.name).stem
    suffix = "" if idx == 0 else f".edited-v{idx}"
    return FileResponse(
        s.versions[idx].path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{stem}{suffix}.docx",
    )

