"""Versioned replay contract. Events are commands, never inferred completions."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ParserMeta(Model):
    name: str
    package_version: str
    version: str | None = None
    game_version: str | None = None
    save_version: float | None = None
    log_version: int | None = None


class Source(Model):
    file: str
    sha256: str


class Player(Model):
    id: int
    name: str
    civilization: str


class MatchInfo(Model):
    map: str
    speed: str
    duration_seconds: float
    players: list[Player]


class ParseError(Model):
    type: str
    message: str
    offset: int | None = None


class Event(Model):
    time_ms: int = Field(ge=0)
    offset: int = Field(ge=0)
    kind: Literal[
        "BUILD_COMMAND",
        "QUEUE_COMMAND",
        "RESEARCH_COMMAND",
        "MOVE_COMMAND",
        "TARGET_COMMAND",
        "ATTACK_MOVE_COMMAND",
        "RESIGN",
        "CHAT",
        "OTHER",
        "UNKNOWN",
    ]
    raw_type: str
    player_id: int | None = None
    entity_id: int | None = None
    payload: JsonValue


class ParsedReplay(Model):
    schema_version: Literal["aoe2coach.replay.v1"] = "aoe2coach.replay.v1"
    source: Source
    parser: ParserMeta
    status: Literal["ok", "partial", "failed"]
    match: MatchInfo | None = None
    last_time_ms: int = Field(ge=0)
    operation_counts: dict[str, int]
    action_counts: dict[str, int]
    warnings: list[str]
    error: ParseError | None = None
    metadata_error: ParseError | None = None
    events: list[Event]
