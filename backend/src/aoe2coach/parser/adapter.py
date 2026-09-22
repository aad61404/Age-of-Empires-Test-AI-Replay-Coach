"""Isolate mgz raw operations from the public replay schema."""

from pathlib import Path
from typing import Any, Protocol

from aoe2coach.parser.models import Event, ParsedReplay
from aoe2coach.spike import inspect_replay


class ReplayParser(Protocol):
    def parse(self, path: Path) -> ParsedReplay: ...


def normalize(report: dict[str, Any]) -> ParsedReplay:
    """Preserve every action and chat, without assigning ambiguous attack semantics."""
    events: list[Event] = []
    kinds = {
        "BUILD": "BUILD_COMMAND",
        "WALL": "BUILD_COMMAND",
        "QUEUE": "QUEUE_COMMAND",
        "DE_QUEUE": "QUEUE_COMMAND",
        "RESEARCH": "RESEARCH_COMMAND",
        "MOVE": "MOVE_COMMAND",
        "ORDER": "TARGET_COMMAND",
        "DE_ATTACK_MOVE": "ATTACK_MOVE_COMMAND",
        "RESIGN": "RESIGN",
        "ERROR": "UNKNOWN",
    }
    for row in report["operations"]:
        op = row["operation"]
        if op not in ("ACTION", "CHAT"):
            continue
        raw_type, payload = row["payload"] if op == "ACTION" else ("CHAT", row["payload"])
        fields = payload if isinstance(payload, dict) else {}
        entity_id = next(
            (fields[key] for key in ("building_id", "unit_id", "technology_id") if key in fields),
            None,
        )
        events.append(
            Event.model_validate(
                {
                    "time_ms": row["time_ms"],
                    "offset": row["offset"],
                    "kind": "CHAT" if op == "CHAT" else kinds.get(raw_type, "OTHER"),
                    "raw_type": raw_type,
                    "player_id": fields.get("player_id"),
                    "entity_id": entity_id,
                    "payload": payload,
                }
            )
        )
    return ParsedReplay.model_validate(
        {
            **{k: v for k, v in report.items() if k not in ("schema", "operations")},
            "events": events,
        }
    )


class AocMgzAdapter:
    def parse(self, path: Path) -> ParsedReplay:
        return normalize(inspect_replay(path, include_all_operations=False))
