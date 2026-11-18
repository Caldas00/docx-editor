from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from documents import (  # noqa: E402
    build_api_reference,
    build_intake_form,
    build_referral_letter,
    build_session_note,
)

from docx_agent.document import DocxPackage  # noqa: E402


@pytest.fixture(scope="session")
def session_note_bytes() -> bytes:
    return build_session_note()


@pytest.fixture(scope="session")
def referral_bytes() -> bytes:
    return build_referral_letter()


@pytest.fixture(scope="session")
def api_reference_bytes() -> bytes:
    return build_api_reference()


@pytest.fixture(scope="session")
def intake_bytes() -> bytes:
    return build_intake_form()


@pytest.fixture()
def session_note(session_note_bytes) -> DocxPackage:
    return DocxPackage(session_note_bytes)


@pytest.fixture()
def referral(referral_bytes) -> DocxPackage:
    return DocxPackage(referral_bytes)
