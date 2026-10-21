"""Verify deterministic corpus compatibility reporting."""

from pathlib import Path

import pytest

from aoe2coach.audit import audit_corpus
from aoe2coach.parser.models import Event, ParsedReplay


def replay(path: Path) -> ParsedReplay:
    status = "partial" if path.stem == "b" else "ok"
    return ParsedReplay.model_validate(
        {
            "source": {"file": path.name, "sha256": path.stem},
            "parser": {
                "name": "aoe2rec-py" if status == "partial" else "mgz",
                "package_version": "1",
                "game_version": "DE",
                "save_version": 70.0,
            },
            "status": status,
            "last_time_ms": 1000,
            "operation_counts": {},
            "action_counts": {},
            "warnings": ["decode"] if status == "partial" else [],
            "events": [
                Event(
                    time_ms=100,
                    offset=1,
                    kind="UNKNOWN" if status == "partial" else "MOVE_COMMAND",
                    raw_type="ERROR" if status == "partial" else "MOVE",
                    player_id=None if status == "partial" else 1,
                    payload={},
                )
            ],
        }
    )


def test_audit_summarizes_status_parser_and_event_quality(tmp_path: Path) -> None:
    (tmp_path / "b.aoe2record").write_bytes(b"b")
    (tmp_path / "a.aoe2record").write_bytes(b"a")
    result = audit_corpus(tmp_path, parser=replay)
    assert result.total == 2
    assert result.ok == 1
    assert result.partial == 1
    assert result.failed == 0
    assert result.parser_counts == {"aoe2rec-py": 1, "mgz": 1}
    assert result.game_version_counts == {"DE": 2}
    assert [entry.file for entry in result.entries] == ["a.aoe2record", "b.aoe2record"]
    assert result.entries[1].unknown_event_count == 1
    assert result.entries[1].assigned_event_count == 0


def test_recursive_mode_finds_nested_replay(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "a.aoe2record").write_bytes(b"a")
    assert audit_corpus(tmp_path, recursive=True, parser=replay).total == 1
    with pytest.raises(ValueError, match="No .aoe2record"):
        audit_corpus(tmp_path, parser=replay)


def test_empty_corpus_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="No .aoe2record"):
        audit_corpus(tmp_path, parser=replay)
