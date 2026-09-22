"""Validate command semantics, lossless payloads and CLI error behavior."""

import json
from pathlib import Path

from typer.testing import CliRunner

from aoe2coach.cli.main import app
from aoe2coach.parser.adapter import normalize
from aoe2coach.parser.models import ParsedReplay


def test_normalization_preserves_ambiguous_and_unknown_actions() -> None:
    rows = [
        ("ORDER", {"player_id": 1, "target_id": 10}),
        ("RESEARCH", {"player_id": 1, "technology_id": 101}),
        ("DE_QUEUE", {"player_id": 2, "unit_id": 83, "amount": 2}),
        ("ERROR", {"hex": "abcd"}),
        ("FUTURE_ACTION", {"new_field": [1, 2]}),
    ]
    result = normalize(
        {
            "source": {"file": "test", "sha256": "abc"},
            "parser": {"name": "mgz", "package_version": "test"},
            "status": "partial",
            "last_time_ms": 1234,
            "operation_counts": {"ACTION": 5, "CHAT": 1},
            "action_counts": {name: 1 for name, _ in rows},
            "warnings": ["decode error"],
            "operations": [
                {"operation": "ACTION", "time_ms": 1234, "offset": i, "payload": [name, payload]}
                for i, (name, payload) in enumerate(rows)
            ]
            + [{"operation": "CHAT", "time_ms": 1234, "offset": 5, "payload": {"hex": "6869"}}],
        }
    )
    assert [e.kind for e in result.events] == [
        "TARGET_COMMAND",
        "RESEARCH_COMMAND",
        "QUEUE_COMMAND",
        "UNKNOWN",
        "OTHER",
        "CHAT",
    ]
    assert result.events[1].entity_id == 101
    assert result.events[2].player_id == 2
    assert result.events[4].payload == {"new_field": [1, 2]}
    assert result.events[5].player_id is None
    assert ParsedReplay.model_validate_json(result.model_dump_json()) == result


def test_parse_invalid_file_writes_failed_report(tmp_path: Path) -> None:
    replay = tmp_path / "bad.aoe2record"
    replay.write_bytes(b"bad replay")
    output = tmp_path / "output.json"
    result = CliRunner().invoke(app, ["parse", str(replay), "-o", str(output)])
    assert result.exit_code == 1
    report = ParsedReplay.model_validate_json(output.read_text())
    assert report.status == "failed"
    assert report.error is not None
    assert report.events == []
    assert "schema_version" in json.loads(output.read_text())


def test_parse_rejects_overwriting_source(tmp_path: Path) -> None:
    replay = tmp_path / "test.aoe2record"
    replay.write_bytes(b"original")
    result = CliRunner().invoke(app, ["parse", str(replay), "-o", str(replay)])
    assert result.exit_code != 0
    assert replay.read_bytes() == b"original"
