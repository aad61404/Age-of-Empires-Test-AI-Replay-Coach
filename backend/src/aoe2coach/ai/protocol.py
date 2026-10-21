"""Replaceable coaching provider boundary."""

from typing import Protocol

from aoe2coach.ai.models import CoachingReport
from aoe2coach.analyzer.diff import DiffResult


class CoachProvider(Protocol):
    name: str

    def explain(self, diff: DiffResult) -> CoachingReport: ...
