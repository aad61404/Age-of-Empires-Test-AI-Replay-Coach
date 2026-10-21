"""Deterministic baseline coach and grounding validation."""

from aoe2coach.ai.models import CoachingObservation, CoachingReport, EvidenceRef
from aoe2coach.analyzer.diff import DiffResult, MetricDelta


class GroundingError(ValueError):
    """A coaching claim references evidence not present in the diff."""


class RuleBasedCoachProvider:
    """Offline baseline that proves the report contract without an LLM dependency."""

    name = "rule-based"

    def explain(self, diff: DiffResult) -> CoachingReport:
        significant = [delta for delta in diff.deltas if delta.significant]
        observations = [self._observation(delta) for delta in significant]
        if observations:
            summary = (
                f"Found {len(observations)} timing difference(s) at or above "
                f"{diff.significance_threshold_ms / 1000:g} seconds."
            )
        else:
            summary = (
                "No comparable timing difference reached the configured significance threshold."
            )
        report = CoachingReport(
            provider=self.name,
            generated_by_model=False,
            source_a=diff.source_a,
            source_b=diff.source_b,
            player_a=diff.player_a,
            player_b=diff.player_b,
            summary=summary,
            observations=observations,
            limitations=[
                "Replay events are player commands, not confirmed completion or game state.",
                "Timing order and metric differences do not establish causality.",
                *diff.warnings,
            ],
        )
        validate_grounding(report, diff)
        return report

    @staticmethod
    def _observation(delta: MetricDelta) -> CoachingObservation:
        if delta.delta is None or delta.value_a is None or delta.value_b is None:
            raise GroundingError(f"Significant metric {delta.metric} lacks comparable values.")
        direction = "later" if delta.delta > 0 else "earlier"
        seconds = abs(delta.delta) / 1000
        evidence = EvidenceRef(
            metric=delta.metric,
            value_a=delta.value_a,
            value_b=delta.value_b,
            delta=delta.delta,
            unit=delta.unit,
        )
        return CoachingObservation(
            title=delta.metric.replace("_", " ").removesuffix(" ms").title(),
            observation=(
                f"Replay A issued this command {seconds:g} seconds {direction} than Replay B."
            ),
            evidence=[evidence],
            suggested_review=(
                "Review the preceding command window and resource-allocation decisions; "
                "the replay alone does not prove the cause."
            ),
        )


def validate_grounding(report: CoachingReport, diff: DiffResult) -> None:
    """Require every evidence reference to exactly match a calculated metric delta."""
    known = {
        (delta.metric, delta.value_a, delta.value_b, delta.delta, delta.unit)
        for delta in diff.deltas
        if delta.delta is not None
    }
    for observation in report.observations:
        if not observation.evidence:
            raise GroundingError(f"Observation has no evidence: {observation.title}")
        for evidence in observation.evidence:
            key = (
                evidence.metric,
                evidence.value_a,
                evidence.value_b,
                evidence.delta,
                evidence.unit,
            )
            if key not in known:
                raise GroundingError(
                    f"Unsupported evidence for {observation.title}: {evidence.metric}"
                )
