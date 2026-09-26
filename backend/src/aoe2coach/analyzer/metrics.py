"""Conservative metrics derived from replay commands, not completed game state."""

from typing import Literal

from aoe2coach.analyzer.timeline import PlayerTimeline
from aoe2coach.parser.models import Model, ParserMeta, Player, Source


class PlayerMetrics(Model):
    schema_version: Literal["aoe2coach.metrics.v1"] = "aoe2coach.metrics.v1"
    source: Source
    parser: ParserMeta
    status: Literal["ok", "partial"]
    player: Player
    duration_ms: int
    counted_commands: int
    apm: float | None
    feudal_research_command_ms: int | None
    castle_research_command_ms: int | None
    imperial_research_command_ms: int | None
    first_barracks_command_ms: int | None
    first_stable_command_ms: int | None
    first_archery_range_command_ms: int | None
    first_queue_command_ms: int | None
    warnings: list[str]


COUNTED_KINDS = {
    "BUILD_COMMAND",
    "QUEUE_COMMAND",
    "RESEARCH_COMMAND",
    "MOVE_COMMAND",
    "TARGET_COMMAND",
    "ATTACK_MOVE_COMMAND",
    "OTHER",
}


def calculate_metrics(timeline: PlayerTimeline) -> PlayerMetrics:
    """Calculate command timings and raw APM with an explicit counting policy."""
    counted = sum(event.kind in COUNTED_KINDS for event in timeline.events)
    apm = round(counted * 60_000 / timeline.last_time_ms, 2) if timeline.last_time_ms else None

    def first(kind: str, name: str | None = None) -> int | None:
        return next(
            (
                event.time_ms
                for event in timeline.events
                if event.kind == kind and (name is None or event.entity_name == name)
            ),
            None,
        )

    warnings = list(timeline.warnings)
    warnings.append(
        "APM counts decoded player commands except chat, resign, and unknown decode errors; "
        "it is not effective APM."
    )
    warnings.append(
        "Research, building, and queue timings are command times, not completion times."
    )
    if timeline.last_time_ms == 0:
        warnings.append("APM is unavailable because replay duration is zero.")

    return PlayerMetrics(
        source=timeline.source,
        parser=timeline.parser,
        status=timeline.status,
        player=timeline.player,
        duration_ms=timeline.last_time_ms,
        counted_commands=counted,
        apm=apm,
        feudal_research_command_ms=first("RESEARCH_COMMAND", "Feudal Age"),
        castle_research_command_ms=first("RESEARCH_COMMAND", "Castle Age"),
        imperial_research_command_ms=first("RESEARCH_COMMAND", "Imperial Age"),
        first_barracks_command_ms=first("BUILD_COMMAND", "Barracks"),
        first_stable_command_ms=first("BUILD_COMMAND", "Stable"),
        first_archery_range_command_ms=first("BUILD_COMMAND", "Archery Range"),
        first_queue_command_ms=first("QUEUE_COMMAND"),
        warnings=warnings,
    )
