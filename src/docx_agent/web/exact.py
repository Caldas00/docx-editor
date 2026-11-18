"""Exact pages: let a real layout engine lay the document out.

No HTML imitation lays a .docx out like a word processor (font metrics, line breaking,
floating shapes, fields...), so when LibreOffice is installed the web UI shows *its* pages:
the version is converted to PDF headlessly (`soffice --headless --convert-to pdf`) and the
browser draws that PDF with a selectable text layer. LibreOffice is open source and runs on
any OS without a display; the Docker image ships it, so the app stays self-contained. Without
it, the UI falls back to its own HTML layout. Conversion works on a copy and never changes
the .docx.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

TIMEOUT = 120
_lock = threading.Lock()  # one conversion at a time (LibreOffice uses a single profile)


def _soffice() -> str | None:
    configured = os.environ.get("DOCX_AGENT_SOFFICE")
    for cand in (configured, shutil.which("soffice"), shutil.which("libreoffice"),
                 "/Applications/LibreOffice.app/Contents/MacOS/soffice",
                 "/usr/lib/libreoffice/program/soffice", "/opt/libreoffice/program/soffice"):
        if cand and Path(cand).exists():
            return cand
    return None


def engine() -> str | None:
    """"libreoffice" when it is installed, else None. DOCX_AGENT_EXACT=0 turns it off."""
    if os.environ.get("DOCX_AGENT_EXACT", "1").strip().lower() in ("0", "false", "no"):
        return None
    return "libreoffice" if _soffice() else None


def to_pdf(src: Path, dest: Path) -> bool:
    """Convert `src` (.docx) to `dest` (.pdf). True on success."""
    soffice = _soffice()
    if soffice is None or engine() is None:
        return False
    with _lock:
        if dest.exists():
            return True
        try:
            with tempfile.TemporaryDirectory() as tmp:
                work = Path(tmp) / "document.docx"
                shutil.copyfile(src, work)
                # a private profile: works next to a running LibreOffice and leaves no state
                profile = Path(tmp, "profile").as_uri()
                subprocess.run([soffice, f"-env:UserInstallation={profile}", "--headless",
                                "--norestore", "--convert-to", "pdf", "--outdir", tmp,
                                str(work)], capture_output=True, timeout=TIMEOUT, check=False)
                out = Path(tmp) / "document.pdf"
                if not out.exists() or out.stat().st_size == 0:
                    return False
                shutil.move(str(out), dest)
                return True
        except (OSError, subprocess.SubprocessError):
            return False
