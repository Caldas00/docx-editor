"""Run the real agent on the sample documents and store the results in samples/output.

    uv run python scripts/make_examples.py

For each example it writes the edited .docx, the plan (replayable without an LLM via
``docx-agent apply``) and a Markdown summary with the verification report.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from docx_agent.service import EditService  # noqa: E402

EXAMPLES = [
    ("session_note.docx",
     "The clinician is now Dr. Ana Costa - update her name everywhere. Also change the session "
     "number to 7 of 12 and add 'Grounding exercise (5-4-3-2-1)' as another intervention used."),
    ("referral_letter.docx",
     "Address the letter to Dr. Rui Almeida, change the anxiety status in the summary table from "
     "Moderate to Mild, and remove the word 'persistent'."),
    ("intake_form.docx", "Change the preferred name to Sam."),
]


def main() -> None:
    inp = ROOT / "samples" / "input"
    out = ROOT / "samples" / "output"
    out.mkdir(parents=True, exist_ok=True)
    service = EditService()
    lines = ["# Example runs", "",
             f"Generated with `scripts/make_examples.py` (model `{service.settings.model}`).", ""]
    for name, instruction in EXAMPLES:
        stem = Path(name).stem
        target = out / f"{stem}.edited.docx"
        res = service.start(inp / name, instruction, target)
        if res.status != "done":
            raise SystemExit(f"{name}: {res.status} - {res.message}")
        (out / f"{stem}.plan.json").write_text(json.dumps(res.plan, indent=2, ensure_ascii=False) + "\n")
        lines += [f"## {name}", "", f"**Instruction:** {instruction}", "",
                  f"**Result:** {res.message}  ", f"Input: `samples/input/{name}` → output: "
                  f"`samples/output/{target.name}` · plan: `samples/output/{stem}.plan.json`", "",
                  "| change | block | before | after |", "|---|---|---|---|"]
        for c in res.changes:
            b = (c["before"] or "").replace("|", "/").replace("\n", " ")
            a = (c["after"] or "").replace("|", "/").replace("\n", " ")
            lines.append(f"| {c['op']} | `{c['block_id']}` | {b} | {a} |")
        lines += ["", "Verification:", ""]
        lines += [f"- {'✅' if ch['passed'] else '❌'} {ch['name']}"
                  + (f" — {ch['detail']}" if ch["detail"] else "")
                  for ch in res.verification["checks"]]
        lines.append("")
        print(f"{name}: {res.message}")
    (out / "EXAMPLES.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
