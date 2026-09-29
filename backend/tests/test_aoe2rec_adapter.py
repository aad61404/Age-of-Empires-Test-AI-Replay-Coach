"""Validate the aoe2rec-py adapter's command semantics without a real replay file."""

import json

from aoe2coach.parser.aoe2rec_adapter import normalize_chapter
from aoe2coach.parser.models import ParsedReplay, ParserMeta, Source

DATASET = {
    "civilizations": {"36": {"name": "Burgundians", "id": 7}},
    "maps": {"29": "Arena"},
    "objects": {"83": "Villager"},
    "technologies": {"101": "Wheelbarrow"},
}
CONSTS = {"speeds": {"169": "Standard"}}


def _chapter(operations: list[dict[str, object]]) -> dict[str, object]:
    return {
        "zheader": {
            "version_major": 66,
            "version_minor": 6,
            "game": "VER 9.4",
            "replay": {"world_time": 0},
            "game_settings": {
                "speed": 1.69,
                "resolved_map_id": 29,
                "players": [{"name": "Player1", "civ_id": 36}],
            },
        },
        "operations": operations,
    }


def test_normalize_maps_known_action_kinds_and_resolves_names() -> None:
    chapter = _chapter(
        [
            {"Sync": {"time_increment": 500}},
            {"Action": {"length": 1, "world_time": 500, "action_data": {"Move": {"player_id": 1}}}},
            {
                "Action": {
                    "length": 1,
                    "world_time": 600,
                    "action_data": {"DeQueue": {"player_id": 1, "unit_id": 83}},
                }
            },
            {
                "Action": {
                    "length": 1,
                    "world_time": 700,
                    "action_data": {"Research": {"player_id": 1, "technology_type": 101}},
                }
            },
            {
                "Action": {
                    "length": 1,
                    "world_time": 800,
                    "action_data": {"Resign": {"player_id": 1}},
                }
            },
            {
                "Action": {
                    "length": 1,
                    "world_time": 900,
                    "action_data": {"Formation": {"player_id": 1, "unknown1": (0, 0, 0, 0)}},
                }
            },
            {
                "Action": {
                    "length": 1,
                    "world_time": 1000,
                    "action_data": {"Unknown44": {"player_id": 1}},
                }
            },
            {"Chat": {"text": json.dumps({"player": 1, "message": "gg"})}},
        ]
    )
    result = normalize_chapter(
        chapter,
        DATASET,
        CONSTS,
        source=Source(file="test.aoe2record", sha256="abc"),
        parser_meta=ParserMeta(name="aoe2rec-py", package_version="test"),
    )
    assert [e.kind for e in result.events] == [
        "MOVE_COMMAND",
        "QUEUE_COMMAND",
        "RESEARCH_COMMAND",
        "RESIGN",
        "OTHER",
        "UNKNOWN",
        "CHAT",
    ]
    assert result.events[1].entity_id == 83
    assert result.events[1].entity_name == "Villager"
    assert result.events[2].entity_id == 101
    assert result.events[2].entity_name == "Wheelbarrow"
    assert result.events[4].payload == {"player_id": 1, "unknown1": [0, 0, 0, 0]}  # tuple -> list
    assert result.events[6].player_id == 1
    assert result.status == "partial"  # one Unknown44 action
    assert "1 actions could not be decoded by aoe2rec-py." in result.warnings
    assert result.match is not None
    assert result.match.map == "Arena"
    assert result.match.speed == "Standard"
    assert result.match.players[0].civilization == "Burgundians"
    assert result.last_time_ms == 1000
    assert ParsedReplay.model_validate_json(result.model_dump_json()) == result


def test_normalize_all_known_actions_yields_ok_status() -> None:
    chapter = _chapter(
        [
            {"Action": {"length": 1, "world_time": 100, "action_data": {"Move": {"player_id": 1}}}},
        ]
    )
    result = normalize_chapter(
        chapter,
        DATASET,
        CONSTS,
        source=Source(file="test.aoe2record", sha256="abc"),
        parser_meta=ParserMeta(name="aoe2rec-py", package_version="test"),
    )
    assert result.status == "ok"


def test_normalize_reports_extra_chapters() -> None:
    chapter = _chapter([])
    result = normalize_chapter(
        chapter,
        DATASET,
        CONSTS,
        source=Source(file="test.aoe2record", sha256="abc"),
        parser_meta=ParserMeta(name="aoe2rec-py", package_version="test"),
        extra_chapters=2,
    )
    assert any("2 additional chapter(s)" in warning for warning in result.warnings)
