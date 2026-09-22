"""Development environment diagnostics for the replay pipeline."""

import json
import platform
from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import typer

from aoe2coach.parser.adapter import AocMgzAdapter
from aoe2coach.spike import inspect_replay

app = typer.Typer(help="AoE2 Replay Coach — development foundation.")


@app.callback()
def main() -> None:
    """AoE2 Replay Coach command-line tools."""


@app.command()
def doctor() -> None:
    """Report the Python runtime and installed pipeline dependencies."""
    typer.echo(f"Python: {platform.python_version()} ({platform.machine()})")
    for package in ("aoe2coach", "mgz", "pydantic", "typer"):
        typer.echo(f"{package}: {version(package)}")
    typer.echo("Environment ready. Use spike to inspect a replay.")


@app.command()
def spike(
    replay: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """Inspect raw replay operations and metadata (experimental)."""
    if output is not None and output.resolve() == replay.resolve():
        raise typer.BadParameter("Output must not overwrite the input replay.")
    try:
        report = inspect_replay(replay)
        encoded = json.dumps(report, ensure_ascii=False, indent=2)
        if output is None:
            typer.echo(encoded)
        else:
            output.write_text(encoded + "\n", encoding="utf-8")
            typer.echo(f"{report['status']}: {output}", err=True)
    except OSError as exc:
        typer.echo(f"File error: {exc}", err=True)
        raise typer.Exit(1) from exc
    if report["status"] != "ok":
        raise typer.Exit(1)


@app.command()
def parse(
    replay: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """Parse a replay into versioned command-based JSON. Partial data exits with code 1."""
    if output is not None and output.resolve() == replay.resolve():
        raise typer.BadParameter("Output must not overwrite the input replay.")
    try:
        result = AocMgzAdapter().parse(replay)
        encoded = result.model_dump_json(indent=2)
        if output is None:
            typer.echo(encoded)
        else:
            output.write_text(encoded + "\n", encoding="utf-8")
            typer.echo(f"{result.status}: {output}", err=True)
    except OSError as exc:
        typer.echo(f"File error: {exc}", err=True)
        raise typer.Exit(1) from exc
    if result.status != "ok":
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
