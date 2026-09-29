"""aoe2rec-py adapter: covers replay versions mgz cannot yet parse (validated against de-66.6).

`offset` is the operation's ordinal position in this chapter, not a file byte position —
aoe2rec-py does not expose per-operation byte offsets the way mgz does.
Only the first chapter is parsed; a restored/resumed game's later chapters are ignored.
BUILD_COMMAND / WALL entity_id and entity_name are unavailable: aoe2rec-py 0.1.x has not
decoded that action's payload into named fields yet, only a raw byte blob.
"SPECIAL"-style order actions (aoe2rec-py's "Order") are reported as OTHER, not
TARGET_COMMAND: cross-checking against mgz on de-66.6 showed they correspond to mgz's
SPECIAL operation, not ORDER.
"""

import hashlib
import json
from collections import Counter
from importlib.metadata import version
from pathlib import Path
from typing import Any

from aoe2rec_py import aoe2rec_py  # type: ignore[import-untyped]

from aoe2coach.parser.models import (
    Event,
    MatchInfo,
    ParsedReplay,
    ParseError,
    ParserMeta,
    Player,
    Source,
)

DATASET_ID = 100

KINDS = {
    "Build": "BUILD_COMMAND",
    "Wall": "BUILD_COMMAND",
    "DeQueue": "QUEUE_COMMAND",
    "Research": "RESEARCH_COMMAND",
    "Move": "MOVE_COMMAND",
    "Resign": "RESIGN",
}


def _load_reference() -> tuple[dict[str, Any], dict[str, Any]]:
    """Load the DE dataset and constants aoe2rec-py needs no header-derived version to find."""
    import pkgutil

    dataset = json.loads(pkgutil.get_data("aocref", f"data/datasets/{DATASET_ID}.json") or b"{}")
    consts = json.loads(pkgutil.get_data("aocref", "data/constants.json") or b"{}")
    return dataset, consts


def _json_safe(value: Any) -> Any:
    """Rust tuples (e.g. fixed-size arrays) aren't valid JSON; lists are."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _kind_for(raw_type: str) -> str:
    if raw_type in KINDS:
        return KINDS[raw_type]
    if raw_type.startswith("Unknown") or raw_type.startswith("DeUnknown"):
        return "UNKNOWN"
    return "OTHER"


def _entity_id(raw_type: str, fields: dict[str, Any]) -> int | None:
    if raw_type == "DeQueue":
        return fields.get("unit_id")
    if raw_type == "Research":
        return fields.get("technology_type")
    return None


def _entity_name(raw_type: str, entity_id: int | None, dataset: dict[str, Any]) -> str | None:
    if entity_id is None:
        return None
    table = "technologies" if raw_type == "Research" else "objects"
    name = dataset.get(table, {}).get(str(entity_id))
    return name if isinstance(name, str) else None


def _build_match(
    zheader: dict[str, Any], dataset: dict[str, Any], consts: dict[str, Any]
) -> MatchInfo:
    settings = zheader["game_settings"]
    speed_key = str(round(settings["speed"] * 100))
    map_id = settings["resolved_map_id"]
    civs = dataset.get("civilizations", {})
    players = [
        Player(
            id=index + 1,
            name=player["name"],
            civilization=civs.get(str(player["civ_id"]), {}).get(
                "name", f"civ_id_{player['civ_id']}"
            ),
        )
        for index, player in enumerate(settings["players"])
    ]
    return MatchInfo(
        map=dataset.get("maps", {}).get(str(map_id), f"map_id_{map_id}"),
        speed=consts.get("speeds", {}).get(speed_key, f"speed_{speed_key}"),
        duration_seconds=0.0,  # filled in after events are walked
        players=players,
    )


BASE_WARNINGS = [
    "Action timestamps describe commands, not completion of training/research/building.",
    "Reaching the file boundary does not prove the recorded match finished.",
    "offset is this operation's ordinal position, not a file byte position"
    " (aoe2rec-py limitation).",
    "BUILD_COMMAND/WALL entity_id and entity_name are unavailable"
    " (aoe2rec-py has not decoded that payload).",
    "SPECIAL-style order actions are reported as OTHER, not TARGET_COMMAND.",
]


def normalize_chapter(
    chapter: dict[str, Any],
    dataset: dict[str, Any],
    consts: dict[str, Any],
    *,
    source: Source,
    parser_meta: ParserMeta,
    extra_chapters: int = 0,
) -> ParsedReplay:
    """Turn one aoe2rec-py chapter into the shared replay schema. Pure; no file I/O."""
    warnings = list(BASE_WARNINGS)
    if extra_chapters:
        warnings.append(f"{extra_chapters} additional chapter(s) (restored game) ignored.")

    zheader = chapter["zheader"]
    parser_meta.version = f"{zheader['version_major']}.{zheader['version_minor']}"
    parser_meta.game_version = zheader["game"]
    parser_meta.dataset_id = DATASET_ID

    operation_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    events: list[Event] = []
    last_time_ms = zheader["replay"]["world_time"]
    sync_time_ms = last_time_ms
    unknown_actions = 0

    for index, op in enumerate(chapter["operations"]):
        ((op_name, op_payload),) = op.items()
        operation_counts[op_name] += 1
        if op_name == "Sync":
            sync_time_ms += op_payload["time_increment"]
            continue
        if op_name == "Action":
            raw_type = next(iter(op_payload["action_data"]))
            fields = op_payload["action_data"][raw_type]
            action_counts[raw_type] += 1
            time_ms = op_payload["world_time"]
            kind = _kind_for(raw_type)
            if kind == "UNKNOWN":
                unknown_actions += 1
            entity_id = _entity_id(raw_type, fields)
            events.append(
                Event(
                    time_ms=time_ms,
                    offset=index,
                    kind=kind,  # type: ignore[arg-type]
                    raw_type=raw_type,
                    player_id=fields.get("player_id"),
                    entity_id=entity_id,
                    entity_name=_entity_name(raw_type, entity_id, dataset),
                    payload=_json_safe(fields),
                )
            )
            last_time_ms = max(last_time_ms, time_ms)
        elif op_name == "Chat":
            try:
                chat = json.loads(op_payload["text"])
            except ValueError:
                chat = {}
            events.append(
                Event(
                    time_ms=sync_time_ms,
                    offset=index,
                    kind="CHAT",
                    raw_type="CHAT",
                    player_id=chat.get("player"),
                    entity_id=None,
                    entity_name=None,
                    payload=chat,
                )
            )
            last_time_ms = max(last_time_ms, sync_time_ms)

    status = "partial" if unknown_actions else "ok"
    if unknown_actions:
        warnings.append(f"{unknown_actions} actions could not be decoded by aoe2rec-py.")

    match = _build_match(zheader, dataset, consts)
    match.duration_seconds = last_time_ms / 1000

    return ParsedReplay(
        source=source,
        parser=parser_meta,
        status=status,  # type: ignore[arg-type]
        match=match,
        last_time_ms=last_time_ms,
        operation_counts=dict(operation_counts),
        action_counts=dict(action_counts),
        warnings=warnings,
        events=events,
    )


class AoE2RecAdapter:
    """Parses replays via aoe2rec-py; use when AocMgzAdapter reports status "failed"."""

    def parse(self, path: Path) -> ParsedReplay:
        source = Source(file=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        parser_meta = ParserMeta(name="aoe2rec-py", package_version=version("aoe2rec-py"))
        try:
            data = path.read_bytes()
            chapters = aoe2rec_py.parse_rec(data)["chapters"]
            chapter = chapters[0]
            parser_meta.reference_version = version("aocref")
            dataset, consts = _load_reference()
        except BaseException as exc:
            # aoe2rec-py's Rust core raises pyo3_runtime.PanicException on some header
            # shapes (e.g. team games); it subclasses BaseException, not Exception.
            if isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit)):
                raise
            return ParsedReplay(
                source=source,
                parser=parser_meta,
                status="failed",
                last_time_ms=0,
                operation_counts={},
                action_counts={},
                warnings=list(BASE_WARNINGS),
                error=ParseError(type=type(exc).__name__, message=str(exc)),
                events=[],
            )
        return normalize_chapter(
            chapter,
            dataset,
            consts,
            source=source,
            parser_meta=parser_meta,
            extra_chapters=len(chapters) - 1,
        )
