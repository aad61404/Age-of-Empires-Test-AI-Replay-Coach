"""Verify player isolation, ordering and incomplete-data handling."""

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from aoe2coach.analyzer.timeline import extract_timeline, render_text
from aoe2coach.cli.main import app
from aoe2coach.parser.models import Event, ParsedReplay


def sample() -> ParsedReplay:
    return ParsedReplay.model_validate(
        {
            "source": {"file": "test", "sha256": "abc"},
            "parser": {"name": "mgz", "package_version": "test"},
            "status": "partial",
            "last_time_ms": 10000,
            "operation_counts": {},
            "action_counts": {},
            "warnings": ["Missing actions"],
            "match": {
                "map": "Arena",
                "speed": "Standard",
                "duration_seconds": 10,
                "players": [
                    {"id": 1, "name": "A", "civilization": "Maya"},
                    {"id": 2, "name": "B", "civilization": "Turks"},
                ],
            },
            "events": [
                Event(
                    time_ms=t,
                    offset=o,
                    kind="RESEARCH_COMMAND",
                    raw_type="RESEARCH",
                    player_id=p,
                    entity_id=101,
                    payload={},
                )
                for t, o, p in [
                    (9000, 9, 1),
                    (1000, 3, 2),
                    (1000, 2, 1),
                    (1000, 1, 1),
                    (500, 0, None),
                ]
            ],
        }
    )


def test_isolation_sorting_and_quality() -> None:
    replay = sample()
    result = extract_timeline(replay, 1)
    assert [e.offset for e in result.events] == [1, 2, 9]
    assert result.status == "partial"
    assert result.unassigned_event_count == 1
    assert "Missing actions" in result.warnings
    assert replay.warnings == ["Missing actions"]
    assert "00:01.000 | RESEARCH_COMMAND" in render_text(result)


@pytest.mark.parametrize("case", ["missing_player", "failed", "missing_metadata"])
def test_unusable_input(case: str) -> None:
    replay = sample()
    if case == "failed":
        replay.status = "failed"
    if case == "missing_metadata":
        replay.match = None
    with pytest.raises(ValueError):
        extract_timeline(replay, 99 if case == "missing_player" else 1)


def test_cli_partial_output(tmp_path: Path) -> None:
    path = tmp_path / "test.aoe2record"
    path.write_bytes(b"fixture")
    with patch("aoe2coach.cli.main.AocMgzAdapter.parse", return_value=sample()):
        result = CliRunner().invoke(app, ["timeline", str(path), "--player", "1"])
    assert result.exit_code == 1
    assert '"schema_version": "aoe2coach.timeline.v1"' in result.stdout
