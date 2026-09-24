"""Exercise error reporting and game-clock semantics without external downloads."""

import json
from pathlib import Path
from unittest.mock import patch

from mgz import fast  # type: ignore[import-untyped]
from typer.testing import CliRunner

from aoe2coach.cli.main import app
from aoe2coach.spike import inspect_replay


def test_invalid_replay_returns_json_and_failure(tmp_path: Path) -> None:
    replay = tmp_path / "bad.aoe2record"
    replay.write_bytes(b"not a replay")
    result = CliRunner().invoke(app, ["spike", str(replay)])
    assert result.exit_code == 1
    report = json.loads(result.stdout)
    assert report["status"] == "failed"
    assert "error" in report
    assert report["parser"]["package_version"]


def test_input_cannot_be_overwritten(tmp_path: Path) -> None:
    replay = tmp_path / "sample.aoe2record"
    replay.write_bytes(b"original")
    result = CliRunner().invoke(app, ["spike", str(replay), "-o", str(replay)])
    assert result.exit_code != 0
    assert replay.read_bytes() == b"original"


def test_clock_and_undecoded_action(tmp_path: Path) -> None:
    replay = tmp_path / "sample.aoe2record"
    replay.write_bytes(b"xx")
    header = {
        "version": "DE",
        "game_version": "test",
        "save_version": 66.6,
        "log_version": 5,
        "map": {"restore_time": 1000},
    }
    operations = iter(
        [
            (fast.Operation.SYNC, (500, None, None)),
            (fast.Operation.ACTION, (fast.Action.ERROR, {"raw": b"x"})),
        ]
    )

    def operation(handle):  # type: ignore[no-untyped-def]
        handle.read(1)
        return next(operations)

    with (
        patch("aoe2coach.spike.parse_header", return_value=header),
        patch("aoe2coach.spike.fast.meta"),
        patch("aoe2coach.spike.fast.operation", side_effect=operation),
        patch("aoe2coach.spike.parse_match", side_effect=RuntimeError("unsupported")),
    ):
        report = inspect_replay(replay)
    assert report["last_time_ms"] == 1500
    assert report["status"] == "partial"
    assert report["action_counts"] == {"ERROR": 1}
    assert report["operations"][1]["payload"][1]["raw"] == {"hex": "78"}


def test_names_use_header_dataset_and_preserve_unknown_ids(tmp_path: Path) -> None:
    from aoe2coach.parser.adapter import normalize

    replay = tmp_path / "sample.aoe2record"
    replay.write_bytes(b"xxx")
    header = {
        "version": "DE",
        "game_version": "test",
        "save_version": 66.6,
        "log_version": 5,
        "map": {"restore_time": 0},
        "mod": [11],
    }
    operations = iter(
        [
            (fast.Operation.ACTION, (fast.Action.BUILD, {"building_id": 70})),
            (fast.Operation.ACTION, (fast.Action.RESEARCH, {"technology_id": 70})),
            (fast.Operation.ACTION, (fast.Action.DE_QUEUE, {"unit_id": 999999})),
        ]
    )

    def operation(handle):  # type: ignore[no-untyped-def]
        handle.read(1)
        return next(operations)

    dataset = {"objects": {"70": "House"}, "technologies": {"70": "Different technology"}}
    with (
        patch("aoe2coach.spike.parse_header", return_value=header),
        patch("aoe2coach.spike.get_dataset", return_value=(101, dataset)) as lookup,
        patch("aoe2coach.spike.fast.meta"),
        patch("aoe2coach.spike.fast.operation", side_effect=operation),
        patch("aoe2coach.spike.parse_match", side_effect=RuntimeError("unsupported")),
    ):
        result = normalize(inspect_replay(replay))
    lookup.assert_called_once_with("DE", [11])
    assert [e.entity_name for e in result.events] == ["House", "Different technology", None]
    assert result.events[2].entity_id == 999999
    assert result.events[0].payload == {"building_id": 70}
    assert result.parser.dataset_id == 101
    assert result.parser.reference_version
