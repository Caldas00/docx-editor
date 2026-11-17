"""Command line interface: ``docx-agent --help``."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .document import DocxError, DocxPackage, EditError, EditPlan, render_outline, verify_edit
from .document.ops import DocumentEditor

app = typer.Typer(add_completion=False, no_args_is_help=True,
                  help="LangGraph agent that edits existing .docx files from natural-language "
                       "instructions while preserving everything it was not asked to change.")
console = Console()


def _print_report(report: dict | None) -> None:
    if not report:
        return
    table = Table(title="Integrity verification", show_header=False, box=None)
    for c in report["checks"]:
        mark = "[green]✔[/]" if c["passed"] else "[red]✘[/]"
        table.add_row(mark, c["name"], f"[dim]{c['detail']}[/]")
    console.print(table)


def _print_changes(changes: list[dict]) -> None:
    for ch in changes:
        console.print(f"[bold cyan]{ch['op']}[/] [dim]{ch['block_id']}[/]")
        if ch.get("before") is not None:
            console.print(f"  [red]- {ch['before']}[/]")
        if ch.get("after") is not None:
            console.print(f"  [green]+ {ch['after']}[/]")


@app.command()
def edit(
    input: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="Input .docx")],
    instruction: Annotated[str, typer.Argument(help="What to change, in natural language")],
    output: Annotated[Path | None, typer.Option("-o", "--output", help="Output .docx")] = None,
    model: Annotated[str | None, typer.Option(help="OpenAI model (default from env)")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print the outcome as JSON")] = False,
) -> None:
    """Edit INPUT according to INSTRUCTION and write the result to --output."""
    from .agent.llm import make_llm
    from .config import get_settings
    from .service import EditService

    settings = get_settings()
    output = output or input.with_name(f"{input.stem}.edited.docx")
    service = EditService(make_llm(settings, model), settings)
    with console.status("Planning edit…", spinner="dots"):
        outcome = service.start(input, instruction, output)
    while outcome.status == "needs_clarification":
        if as_json or not sys.stdin.isatty():
            break
        console.print(Panel(outcome.question or "", title="The agent needs clarification"))
        for i, opt in enumerate(outcome.options, 1):
            console.print(f"  {i}. {opt}")
        answer = typer.prompt("Your answer")
        if answer.isdigit() and 1 <= int(answer) <= len(outcome.options):
            answer = outcome.options[int(answer) - 1]
        with console.status("Planning edit…", spinner="dots"):
            outcome = service.resume(outcome.thread_id, answer)

    if as_json:
        console.print_json(json.dumps(outcome.to_dict(), default=str))
    else:
        colour = {"done": "green", "declined": "yellow"}.get(outcome.status, "red")
        console.print(Panel(outcome.message or outcome.status,
                            title=f"[{colour}]{outcome.status}[/]"))
        _print_changes(outcome.changes if outcome.status == "done" else [])
        _print_report(outcome.verification)
        if outcome.output_path:
            console.print(f"Saved → [bold]{outcome.output_path}[/]")
    raise typer.Exit(0 if outcome.status == "done" else 1)


@app.command()
def outline(input: Annotated[Path, typer.Argument(exists=True, dir_okay=False)]) -> None:
    """Print the block outline the agent sees."""
    try:
        pkg = DocxPackage(input.read_bytes())
    except DocxError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(2) from exc
    text, _ = render_outline(pkg)
    console.print(text, markup=False, highlight=False)


@app.command()
def apply(
    input: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    plan_file: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="EditPlan JSON")],
    output: Annotated[Path, typer.Option("-o", "--output")],
) -> None:
    """Apply a saved EditPlan deterministically (no LLM) and verify it."""
    pkg = DocxPackage(input.read_bytes())
    plan = EditPlan.model_validate_json(plan_file.read_text())
    work = pkg.copy()
    try:
        result = DocumentEditor(work).apply(plan)
    except EditError as exc:
        console.print(f"[red]Plan rejected:[/] {exc}")
        raise typer.Exit(1) from exc
    data = work.to_bytes()
    report = verify_edit(pkg, data, plan)
    _print_changes([{"op": c.kind, "block_id": c.block_id, "before": c.before, "after": c.after}
                    for c in result.changes])
    _print_report(report.to_dict())
    if not report.passed:
        console.print("[red]Verification failed - output not written.[/]")
        raise typer.Exit(1)
    output.write_bytes(data)
    console.print(f"Saved → [bold]{output}[/]")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the web UI."""
    import uvicorn

    uvicorn.run("docx_agent.web.app:app", host=host, port=port)


@app.command()
def samples(directory: Path = Path("samples/input")) -> None:
    """(Re)generate the synthetic sample documents."""
    from .samples import write_samples

    for p in write_samples(directory):
        console.print(str(p))


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
