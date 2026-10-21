"""Provider-neutral, evidence-grounded coaching output contract."""

from typing import Literal

from aoe2coach.parser.models import Model, Player, Source


class EvidenceRef(Model):
    metric: str
    value_a: int | float
    value_b: int | float
    delta: int | float
    unit: Literal["milliseconds", "apm", "commands"]


class CoachingObservation(Model):
    title: str
    observation: str
    evidence: list[EvidenceRef]
    suggested_review: str


class CoachingReport(Model):
    schema_version: Literal["aoe2coach.coach.v1"] = "aoe2coach.coach.v1"
    provider: str
    generated_by_model: bool
    source_a: Source
    source_b: Source
    player_a: Player
    player_b: Player
    summary: str
    observations: list[CoachingObservation]
    limitations: list[str]
