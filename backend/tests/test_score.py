"""Gap scoring is the only place where silent wrongness would be invisible.

A crash is obvious. A health score that is quietly 20 points off looks
completely plausible on screen and would survive the entire demo without
anyone noticing. These tests pin the behaviour that matters.
"""

from app.contracts import GapSeverity
from app.pipeline.score import (
    classify_severity,
    compute_gap_score,
    compute_health_score,
)


def test_high_demand_zero_coverage_is_critical():
    score = compute_gap_score(
        market_demand=0.9,
        curriculum_coverage=0.0,
        prerequisite_distance=1,
        trend_slope=None,
    )
    assert score > 0.7
    assert classify_severity(score) == GapSeverity.CRITICAL


def test_full_coverage_yields_no_meaningful_gap():
    """A skill the curriculum already teaches is not a gap, however much
    the market wants it."""
    score = compute_gap_score(
        market_demand=0.9,
        curriculum_coverage=1.0,
        prerequisite_distance=0,
        trend_slope=None,
    )
    assert score < 0.2


def test_coverage_monotonically_reduces_the_gap():
    scores = [
        compute_gap_score(0.8, coverage, 1, None)
        for coverage in (0.0, 0.25, 0.5, 0.75, 1.0)
    ]
    assert scores == sorted(scores, reverse=True)


def test_demand_monotonically_increases_the_gap():
    scores = [
        compute_gap_score(demand, 0.0, 1, None)
        for demand in (0.0, 0.25, 0.5, 0.75, 1.0)
    ]
    assert scores == sorted(scores)


def test_unreachable_prerequisites_reduce_actionability():
    """Adding a skill whose prerequisites are already satisfied is cheap.
    One needing three missing prerequisites is not, and should rank lower."""
    near = compute_gap_score(0.8, 0.0, prerequisite_distance=1, trend_slope=None)
    far = compute_gap_score(0.8, 0.0, prerequisite_distance=5, trend_slope=None)
    assert near > far


def test_rising_trend_increases_urgency():
    flat = compute_gap_score(0.5, 0.2, 1, trend_slope=0.0)
    rising = compute_gap_score(0.5, 0.2, 1, trend_slope=0.8)
    assert rising > flat


def test_absent_forecaster_behaves_exactly_like_zero_slope():
    """The forecaster is off the critical path. If it is cut, the numbers
    on screen must not shift."""
    assert compute_gap_score(0.5, 0.2, 1, None) == compute_gap_score(
        0.5, 0.2, 1, 0.0
    )


def test_score_stays_within_unit_range_at_extremes():
    extremes = [
        compute_gap_score(1.0, 0.0, 0, 1.0),
        compute_gap_score(0.0, 1.0, 99, -1.0),
        compute_gap_score(1.0, 1.0, 0, 1.0),
        compute_gap_score(0.0, 0.0, 99, 0.0),
    ]
    assert all(0.0 <= s <= 1.0 for s in extremes)


def test_out_of_range_inputs_are_clamped_not_propagated():
    """Upstream similarity values have occasionally exceeded 1.0 through
    floating point drift. That must not leak into the score."""
    assert 0.0 <= compute_gap_score(1.5, -0.3, 1, 2.0) <= 1.0


def test_negative_prerequisite_distance_does_not_explode():
    assert 0.0 <= compute_gap_score(0.5, 0.0, -3, None) <= 1.0


def test_severity_thresholds_partition_the_range():
    assert classify_severity(0.9) == GapSeverity.CRITICAL
    assert classify_severity(0.5) == GapSeverity.HIGH
    assert classify_severity(0.3) == GapSeverity.MODERATE
    assert classify_severity(0.05) == GapSeverity.LOW


def test_no_gaps_means_perfect_health():
    assert compute_health_score([]) == 100.0


def test_health_score_is_bounded():
    assert 0.0 <= compute_health_score([0.9, 0.8, 0.7]) <= 100.0
    assert 0.0 <= compute_health_score([1.0] * 50) <= 100.0


def test_more_severe_gaps_lower_health():
    assert compute_health_score([0.9, 0.9, 0.9]) < compute_health_score([0.1])


def test_worst_gaps_dominate_the_health_score():
    """A few critical gaps must not be averaged away by a long tail of
    trivial ones, which is what a plain mean would do."""
    one_critical = compute_health_score([0.95])
    critical_plus_trivia = compute_health_score([0.95] + [0.01] * 20)
    assert critical_plus_trivia < one_critical + 15.0


def test_health_score_is_order_independent():
    assert compute_health_score([0.1, 0.9, 0.5]) == compute_health_score(
        [0.9, 0.5, 0.1]
    )
