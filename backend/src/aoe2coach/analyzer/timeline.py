"""Player timelines preserve replay quality and do not infer completion times."""

from typing import Literal

from aoe2coach.parser.models import Event, Model, ParsedReplay, ParserMeta, Player, Source


class PlayerTimeline(Model):
    schema_version: Literal["aoe2coach.timeline.v1"] = "aoe2coach.timeline.v1"
    source: Source
    parser: ParserMeta
    status: Literal["ok", "partial"]
    player: Player
    last_time_ms: int
    warnings: list[str]
    unassigned_event_count: int
    events: list[Event]


def extract_timeline(replay: ParsedReplay, player_id: int) -> PlayerTimeline:
    """Sort attributable events by game time, preserving source order for ties."""
    if replay.status == "failed":
        raise ValueError("Cannot build a timeline from a failed parse.")
    if replay.match is None:
        raise ValueError("Player metadata is unavailable; cannot select a player reliably.")
    player = next((p for p in replay.match.players if p.id == player_id), None)
    if player is None:
        available = ", ".join(str(p.id) for p in replay.match.players)
        raise ValueError(f"Player {player_id} not found. Available player IDs: {available}")
    unassigned = sum(e.player_id is None for e in replay.events)
    warnings = list(replay.warnings)
    if unassigned:
        warnings.append(f"{unassigned} replay events have no player ID and are excluded.")
    return PlayerTimeline(
        source=replay.source,
        parser=replay.parser,
        status=replay.status,
        player=player,
        last_time_ms=replay.last_time_ms,
        warnings=warnings,
        unassigned_event_count=unassigned,
        events=sorted(
            (e for e in replay.events if e.player_id == player_id),
            key=lambda e: (e.time_ms, e.offset),
        ),
    )


def render_text(timeline: PlayerTimeline) -> str:
    """Readable command timeline with reference names and original IDs."""
    lines = [f"{timeline.player.name} ({timeline.player.civilization}) — {timeline.status}"]
    lines.extend(f"Warning: {warning}" for warning in timeline.warnings)
    lines.append("Game time | Command | Entity (ID)")
    for event in timeline.events:
        seconds, milliseconds = divmod(event.time_ms, 1000)
        minutes, seconds = divmod(seconds, 60)
        entity = str(event.entity_id) if event.entity_id is not None else "-"
        if event.entity_name is not None:
            entity = f"{event.entity_name} ({entity})"
        lines.append(
            f"{minutes:02}:{seconds:02}.{milliseconds:03} | "
            f"{event.kind} ({event.raw_type}) | {entity}"
        )
    return "\n".join(lines)
