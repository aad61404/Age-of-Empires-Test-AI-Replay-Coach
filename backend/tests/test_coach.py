"""Verify provider-neutral coaching output and strict evidence grounding."""

from copy import deepcopy

import pytest

from aoe2coach.ai.coach import GroundingError, RuleBasedCoachProvider, validate_grounding
from aoe2coach.ai.models import CoachingObservation, EvidenceRef
from aoe2coach.analyzer.diff import compare_metrics
from aoe2coach.analyzer.metrics import PlayerMetrics


def metrics(
    *, source: str, feudal: int | None = 600_000, stable: int | None = 660_000
) -> PlayerMetrics:
    return PlayerMetrics.model_validate(
        {
            "source": {"file": source, "sha256": source},
            "parser": {"name": "test", "package_version": "1"},
            "status": "ok",
            "player": {"id": 1, "name": source, "civilization": "Franks"},
            "duration_ms": 1_200_000,
            "counted_commands": 400,
            "apm": 20.0,
            "feudal_research_command_ms": feudal,
            "castle_research_command_ms": None,
            "imperial_research_command_ms": None,
            "first_barracks_command_ms": 300_000,
            "first_stable_command_ms": stable,
            "first_archery_range_command_ms": None,
            "first_queue_command_ms": 700_000,
            "warnings": [],
        }
    )


def test_rule_based_report_is_grounded_and_explicitly_not_ai() -> None:
    diff = compare_metrics(
        metrics(source="a", feudal=660_000, stable=750_000),
        metrics(source="b"),
    )
    report = RuleBasedCoachProvider().explain(diff)
    assert report.provider == "rule-based"
    assert report.generated_by_model is False
    assert len(report.observations) == 2
    assert report.observations[0].evidence[0].delta == 60_000
    assert any("do not establish causality" in item for item in report.limitations)


def test_no_significant_difference_produces_no_claims() -> None:
    diff = compare_metrics(metrics(source="a"), metrics(source="b"))
    report = RuleBasedCoachProvider().explain(diff)
    assert report.observations == []
    assert report.summary.startswith("No comparable")


def test_validator_rejects_unsupported_evidence() -> None:
    diff = compare_metrics(
        metrics(source="a", feudal=660_000),
        metrics(source="b"),
    )
    report = deepcopy(RuleBasedCoachProvider().explain(diff))
    report.observations.append(
        CoachingObservation(
            title="Invented claim",
            observation="Unsupported",
            evidence=[
                EvidenceRef(
                    metric="invented",
                    value_a=1,
                    value_b=2,
                    delta=-1,
                    unit="commands",
                )
            ],
            suggested_review="None",
        )
    )
    with pytest.raises(GroundingError, match="Unsupported evidence"):
        validate_grounding(report, diff)
