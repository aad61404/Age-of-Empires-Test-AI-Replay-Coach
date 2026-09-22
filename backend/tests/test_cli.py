"""Verify the installed CLI's basic entry points."""

from typer.testing import CliRunner

from aoe2coach.cli.main import app

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "doctor" in result.output


def test_doctor() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "mgz:" in result.output
    assert "Use spike to inspect a replay." in result.output
