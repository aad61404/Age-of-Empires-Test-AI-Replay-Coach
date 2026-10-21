"""Deterministic comparison of two command-derived player metric sets."""

from typing import Literal

from aoe2coach.analyzer.metrics import PlayerMetrics
from aoe2coach.parser.models import Model, Player, Source

MetricValue = int | float | None


class MetricDelta(Model):
    metric: str
    value_a: MetricValue
    value_b: MetricValue
    delta: int | float | None
    unit: Literal["milliseconds", "apm", "commands"]
    significant: bool


class DiffResult(Model):
    schema_version: Literal["aoe2coach.diff.v1"] = "aoe2coach.diff.v1"
    status: Literal["ok", "partial"]
    source_a: Source
    source_b: Source
    player_a: Player
    player_b: Player
    significance_threshold_ms: int
    deltas: list[MetricDelta]
    earliest_significant_deviation: str | None
    downstream_differences: list[str]
    warnings: list[str]


METRICS: tuple[tuple[str, Literal["milliseconds", "apm", "commands"]], ...] = (
    ("counted_commands", "commands"),
    ("apm", "apm"),
    ("feudal_research_command_ms", "milliseconds"),
    ("castle_research_command_ms", "milliseconds"),
    ("imperial_research_command_ms", "milliseconds"),
    ("first_barracks_command_ms", "milliseconds"),
    ("first_stable_command_ms", "milliseconds"),
    ("first_archery_range_command_ms", "milliseconds"),
    ("first_queue_command_ms", "milliseconds"),
)


def compare_metrics(
    metrics_a: PlayerMetrics,
    metrics_b: PlayerMetrics,
    *,
    significance_threshold_ms: int = 30_000,
) -> DiffResult:
    """Compare facts without claiming that an earlier deviation caused later ones."""
    if significance_threshold_ms < 0:
        raise ValueError("Significance threshold must be non-negative.")

    deltas: list[MetricDelta] = []
    significant_timings: list[tuple[int, str]] = []
    for metric, unit in METRICS:
        value_a = getattr(metrics_a, metric)
        value_b = getattr(metrics_b, metric)
        delta = value_a - value_b if value_a is not None and value_b is not None else None
        significant = (
            unit == "milliseconds" and delta is not None and abs(delta) >= significance_threshold_ms
        )
        deltas.append(
            MetricDelta(
                metric=metric,
                value_a=value_a,
                value_b=value_b,
                delta=delta,
                unit=unit,
                significant=significant,
            )
        )
        if significant and value_a is not None and value_b is not None:
            significant_timings.append((min(int(value_a), int(value_b)), metric))

    significant_timings.sort()
    earliest = significant_timings[0] if significant_timings else None
    downstream = (
        [metric for time_ms, metric in significant_timings[1:] if time_ms > earliest[0]]
        if earliest is not None
        else []
    )
    warnings = [f"Replay A: {warning}" for warning in metrics_a.warnings]
    warnings.extend(f"Replay B: {warning}" for warning in metrics_b.warnings)
    warnings.append(
        "The earliest deviation and downstream differences describe timing order, not causality."
    )
    if metrics_a.player.civilization != metrics_b.player.civilization:
        warnings.append(
            "Players use different civilizations; direct timing comparison may mislead."
        )

    return DiffResult(
        status="partial" if "partial" in (metrics_a.status, metrics_b.status) else "ok",
        source_a=metrics_a.source,
        source_b=metrics_b.source,
        player_a=metrics_a.player,
        player_b=metrics_b.player,
        significance_threshold_ms=significance_threshold_ms,
        deltas=deltas,
        earliest_significant_deviation=earliest[1] if earliest is not None else None,
        downstream_differences=downstream,
        warnings=warnings,
    )
