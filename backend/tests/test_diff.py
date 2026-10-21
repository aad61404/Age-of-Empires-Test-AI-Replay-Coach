"""Verify structured replay comparison and its non-causal contract."""

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from aoe2coach.analyzer.diff import compare_metrics
from aoe2coach.analyzer.metrics import PlayerMetrics
from aoe2coach.cli.main import app
from aoe2coach.parser.models import ParsedReplay


def metrics(
    *,
    source: str,
    civilization: str = "Franks",
    status: str = "ok",
    feudal: int | None = 600_000,
    stable: int | None = 660_000,
    queue: int | None = 700_000,
) -> PlayerMetrics:
    return PlayerMetrics.model_validate(
        {
            "source": {"file": source, "sha256": source},
            "parser": {"name": "test", "package_version": "1"},
            "status": status,
            "player": {"id": 1, "name": source, "civilization": civilization},
            "duration_ms": 1_200_000,
            "counted_commands": 400,
            "apm": 20.0,
            "feudal_research_command_ms": feudal,
            "castle_research_command_ms": None,
            "imperial_research_command_ms": None,
            "first_barracks_command_ms": 300_000,
            "first_stable_command_ms": stable,
            "first_archery_range_command_ms": None,
            "first_queue_command_ms": queue,
            "warnings": [],
        }
    )


def failed_replay() -> ParsedReplay:
    return ParsedReplay.model_validate(
        {
            "source": {"file": "failed", "sha256": "x"},
            "parser": {"name": "test", "package_version": "1"},
            "status": "failed",
            "last_time_ms": 0,
            "operation_counts": {},
            "action_counts": {},
            "warnings": [],
            "events": [],
        }
    )


def test_finds_earliest_significant_and_downstream_timings() -> None:
    result = compare_metrics(
        metrics(source="a", feudal=660_000, stable=750_000, queue=790_000),
        metrics(source="b"),
    )
    assert result.earliest_significant_deviation == "feudal_research_command_ms"
    assert result.downstream_differences == [
        "first_stable_command_ms",
        "first_queue_command_ms",
    ]
    feudal = next(delta for delta in result.deltas if delta.metric.startswith("feudal"))
    assert feudal.delta == 60_000
    assert feudal.significant is True
    assert "not causality" in result.warnings[-1]


def test_missing_values_and_partial_quality_are_preserved() -> None:
    result = compare_metrics(
        metrics(source="a", status="partial", feudal=None),
        metrics(source="b", civilization="Britons"),
    )
    assert result.status == "partial"
    feudal = next(delta for delta in result.deltas if delta.metric.startswith("feudal"))
    assert feudal.delta is None
    assert feudal.significant is False
    assert any("different civilizations" in warning for warning in result.warnings)


def test_rejects_negative_threshold() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        compare_metrics(metrics(source="a"), metrics(source="b"), significance_threshold_ms=-1)


def test_cli_reports_unusable_replay(tmp_path: Path) -> None:
    replay_a = tmp_path / "a.aoe2record"
    replay_b = tmp_path / "b.aoe2record"
    replay_a.write_bytes(b"a")
    replay_b.write_bytes(b"b")
    with patch("aoe2coach.cli.main.parse_replay", return_value=failed_replay()):
        result = CliRunner().invoke(app, ["diff", str(replay_a), str(replay_b), "--player", "1"])
    assert result.exit_code == 1
    assert "Diff error" in result.output
