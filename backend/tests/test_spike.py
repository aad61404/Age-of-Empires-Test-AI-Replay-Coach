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
