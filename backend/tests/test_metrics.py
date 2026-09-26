"""Verify conservative command metrics and their CLI contract."""

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from aoe2coach.analyzer.metrics import calculate_metrics
from aoe2coach.analyzer.timeline import extract_timeline
from aoe2coach.cli.main import app
from aoe2coach.parser.models import Event, ParsedReplay


def sample(*, duration_ms: int = 120_000, status: str = "ok") -> ParsedReplay:
    rows = [
        (10_000, "BUILD_COMMAND", "BUILD", "Barracks"),
        (20_000, "RESEARCH_COMMAND", "RESEARCH", "Feudal Age"),
        (30_000, "QUEUE_COMMAND", "DE_QUEUE", "Militia"),
        (40_000, "MOVE_COMMAND", "MOVE", None),
        (50_000, "CHAT", "CHAT", None),
        (60_000, "RESIGN", "RESIGN", None),
        (70_000, "UNKNOWN", "ERROR", None),
    ]
    return ParsedReplay.model_validate(
        {
            "source": {"file": "test", "sha256": "abc"},
            "parser": {"name": "mgz", "package_version": "test"},
            "status": status,
            "last_time_ms": duration_ms,
            "operation_counts": {},
            "action_counts": {},
            "warnings": [],
            "match": {
                "map": "Arena",
                "speed": "Standard",
                "duration_seconds": duration_ms / 1000,
                "players": [{"id": 1, "name": "A", "civilization": "Franks"}],
            },
            "events": [
                Event(
                    time_ms=time,
                    offset=index,
                    kind=kind,
                    raw_type=raw_type,
                    player_id=1,
                    entity_name=name,
                    payload={},
                )
                for index, (time, kind, raw_type, name) in enumerate(rows)
            ],
        }
    )


def test_metrics_counting_and_command_timings() -> None:
    result = calculate_metrics(extract_timeline(sample(), 1))
    assert result.counted_commands == 4
    assert result.apm == 2.0
    assert result.feudal_research_command_ms == 20_000
    assert result.first_barracks_command_ms == 10_000
    assert result.first_queue_command_ms == 30_000
    assert result.first_stable_command_ms is None
    assert "not effective APM" in result.warnings[-2]


def test_zero_duration_has_no_apm() -> None:
    result = calculate_metrics(extract_timeline(sample(duration_ms=0), 1))
    assert result.apm is None
    assert result.counted_commands == 4
    assert any("duration is zero" in warning for warning in result.warnings)


def test_cli_preserves_partial_status(tmp_path: Path) -> None:
    replay = tmp_path / "test.aoe2record"
    replay.write_bytes(b"fixture")
    with patch("aoe2coach.cli.main.AocMgzAdapter.parse", return_value=sample(status="partial")):
        result = CliRunner().invoke(app, ["metrics", str(replay), "--player", "1"])
    assert result.exit_code == 1
    assert '"schema_version": "aoe2coach.metrics.v1"' in result.stdout
