"""Small FastAPI app: upload or pick a document, give instructions, see a redline.

Run with ``docx-agent serve`` (or ``uvicorn docx_agent.web.app:app``).
Local demo: sessions live in memory and in ``.runs/web``; there is no auth.
"""

from __future__ import annotations

import hashlib
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
from ..conversation import format_history
from ..document import DocxError, DocxPackage, EditPlan
from ..document.render import page_setup, render_preview, render_redline
from ..pricing import estimate_cost
from ..service import EditOutcome, EditService
from . import exact

STATIC = Path(__file__).parent / "static"
ROOT = Path(__file__).resolve().parents[3]
SAMPLES_DIR = Path(os.getenv("DOCX_AGENT_SAMPLES", ROOT / "samples" / "input"))
# Sessions live in memory, so each server process gets its own folder and only ever
# cleans up that folder (several servers can run side by side).
RUNS_DIR = Path(os.getenv("DOCX_AGENT_RUNS", ROOT / ".runs" / "web")) / f"server-{uuid.uuid4().hex[:8]}"
MAX_UPLOAD = 20 * 1024 * 1024

SAMPLE_INFO: dict[str, dict[str, Any]] = {
    "session_note.docx": {
        "title": "Session progress note",
        "suggestions": [
            "Update the session number to 7 of 12.",
            "The clinician is now Dr. Ana Costa — update her name everywhere.",
            "Add 'Grounding exercise (5-4-3-2-1)' as another intervention used.",
            "Change the date to 20 November 2026.",
        ],
    },
    "api_reference.docx": {
        "title": "API reference",
        "suggestions": [
            "Make all the green text purple.",
            "Remove the emojis.",
            "Remove the set_date and set_modality rows from the table.",
            "Add a row for void close() - 'Signs and closes the note.' after is_closed().",
        ],
    },
    "referral_letter.docx": {
        "title": "Referral letter",
        "suggestions": [
            "Address the letter to Dr. Rui Almeida instead.",
            "In the summary table, change the anxiety status from Moderate to Mild.",
            "Remove the word 'persistent'.",
        ],
    },
    "intake_form.docx": {
        "title": "Client intake form",
        "suggestions": [
            "Change the preferred name to Sam.",
            "Make the consent sentence italic.",
        ],
    },
}


@dataclass
class Version:
    path: Path
    turn: int | None = None  # index of the conversation turn that produced it
    redline_html: str | None = None


@dataclass
class DocSession:
    id: str
    name: str
    dir: Path
    versions: list[Version] = field(default_factory=list)
    turns: list[dict[str, Any]] = field(default_factory=list)  # the chat, oldest first
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def current(self) -> Version:
        return self.versions[-1]


class Selection(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    blocks: list[str] = Field(default_factory=list, max_length=60)


class EditRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=2000)
    selection: Selection | None = None


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
    sample = SAMPLE_INFO.get(s.name)
    return {
        "id": s.id,
        "name": s.name,
        "version": v_idx,
        "latest": len(s.versions) - 1,
        "preview_html": render_preview(pkg),
        "page": page_setup(pkg),
        "redline_html": version.redline_html,
        "turn": version.turn,
        "turns": s.turns,
        "suggestions": sample["suggestions"] if sample else [],
    }


def _outcome_fields(outcome: EditOutcome) -> dict[str, Any]:
    data = outcome.to_dict()
    model = get_service().settings.model
    data["model"] = model
    data["cost"] = estimate_cost(model, outcome.usage)
    return data


def _record(s: DocSession, turn: dict[str, Any], outcome: EditOutcome, seconds: float,
            out_path: Path) -> dict[str, Any]:
    """Store an outcome in its conversation turn (and a new version when applied)."""
    turn["seconds"] = round(seconds, 1)
    turn.update({k: v for k, v in _outcome_fields(outcome).items() if k != "thread_id"})
    if outcome.status == "needs_clarification":
        # The answer arrives as the next chat message, which starts a new run that sees
        # the question in the conversation, so this interrupted run is not resumed.
        get_service().forget(outcome.thread_id)
    if outcome.status == "done":
        before = DocxPackage(s.current.path.read_bytes())
        after = DocxPackage(out_path.read_bytes())
        redline = render_redline(before, after, EditPlan.model_validate(outcome.plan))
        s.versions.append(Version(out_path, turn["index"], redline))
        turn["version"] = len(s.versions) - 1
    else:
        out_path.unlink(missing_ok=True)
    return {"turn": turn, "session": _state(s)}


# ---------------------------------------------------------------- routes
def _asset_version(name: str) -> str:
    return hashlib.sha256((STATIC / name).read_bytes()).hexdigest()[:10]


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    # Browsers (Safari especially) keep serving a stale app.css/app.js from cache after
    # an update. Version the URLs by content and never cache the page itself.
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    for name in ("app.css", "app.js"):
        page = page.replace(f'/static/{name}"', f'/static/{name}?v={_asset_version(name)}"')
    return HTMLResponse(page, headers={"Cache-Control": "no-cache"})


@app.get("/api/config")
def config() -> dict[str, Any]:
    samples = [{"name": name, "title": info["title"]} for name, info in SAMPLE_INFO.items()
               if (SAMPLES_DIR / name).exists()]
    return {"model": get_settings().model, "samples": samples,
            "has_api_key": bool(os.getenv("OPENAI_API_KEY")),
            "exact_pages": exact.engine()}  # "libreoffice" / None


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
        selection = req.selection.model_dump() if req.selection else None
        history = format_history(s.turns)  # earlier turns: the conversation memory
        turn = {"index": len(s.turns), "instruction": req.instruction, "selection": selection,
                "status": "running", "version": None}
        s.turns.append(turn)
        out_path = s.dir / f"v{len(s.versions)}-{uuid.uuid4().hex[:6]}.docx"
        started = time.perf_counter()
        outcome = get_service().start(s.current.path, req.instruction, out_path,
                                      selection=selection, history=history)
        return _record(s, turn, outcome, time.perf_counter() - started, out_path)
    finally:
        s.lock.release()


@app.post("/api/sessions/{sid}/undo")
def undo(sid: str) -> dict[str, Any]:
    s = _session(sid)
    if len(s.versions) <= 1:
        raise HTTPException(409, "Nothing to undo.")
    version = s.versions.pop()
    if version.turn is not None:
        s.turns[version.turn]["undone"] = True
    return _state(s)


@app.get("/api/sessions/{sid}/pdf")
def version_pdf(sid: str, version: int | None = None) -> FileResponse:
    """The version laid out by LibreOffice (see exact.py), cached next to the version."""
    s = _session(sid)
    idx = len(s.versions) - 1 if version is None else version
    if not 0 <= idx < len(s.versions):
        raise HTTPException(404, "Unknown version.")
    path = s.versions[idx].path
    pdf = path.with_suffix(".pdf")
    if not pdf.exists():
        if exact.engine() is None:
            raise HTTPException(501, "LibreOffice is not installed, so exact pages are off.")
        if not exact.to_pdf(path, pdf):
            raise HTTPException(502, "LibreOffice could not lay out this document.")
    return FileResponse(pdf, media_type="application/pdf")


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
