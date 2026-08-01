"""Gap scoring: how urgent and how actionable is a missing skill.

Four signals feed the score. Weights are a first estimate and are meant to
be tuned against real seeded data; the tests pin behaviour (monotonicity,
bounds, coverage gating) rather than exact constants, so tuning is safe.
"""

from app.contracts import GapSeverity

W_DEMAND = 0.45
W_COVERAGE = 0.35
W_REACHABILITY = 0.10
W_TREND = 0.10

# Floor on the coverage gate. Without a floor, a fully covered skill would
# score exactly zero and drop out of the ranking entirely, hiding the fact
# that the curriculum covers something the market wants.
COVERAGE_GATE_FLOOR = 0.15

CRITICAL_THRESHOLD = 0.65
HIGH_THRESHOLD = 0.45
MODERATE_THRESHOLD = 0.25


def compute_gap_score(
    market_demand: float,
    curriculum_coverage: float,
    prerequisite_distance: int,
    trend_slope: float | None,
) -> float:
    """Higher means a more urgent, more actionable gap.

    Reachability rewards skills close to what is already taught: adding a
    skill whose prerequisites are satisfied is cheap, while one needing
    three missing prerequisites is expensive and ranks lower.

    A None trend slope is treated exactly as zero, so cutting the
    forecaster never shifts the numbers already on screen.
    """
    demand = _clamp(market_demand)
    coverage_deficit = 1.0 - _clamp(curriculum_coverage)
    reachability = 1.0 / (1.0 + max(prerequisite_distance, 0))
    trend = _clamp(trend_slope if trend_slope is not None else 0.0)

    raw = (
        W_DEMAND * demand
        + W_COVERAGE * coverage_deficit
        + W_REACHABILITY * reachability
        + W_TREND * trend
    )

    # Coverage gates the whole score: a skill the curriculum already teaches
    # cannot register as a large gap however much the market wants it.
    gate = COVERAGE_GATE_FLOOR + (1.0 - COVERAGE_GATE_FLOOR) * coverage_deficit
    return round(_clamp(raw * gate), 4)


def classify_severity(score: float) -> GapSeverity:
    if score >= CRITICAL_THRESHOLD:
        return GapSeverity.CRITICAL
    if score >= HIGH_THRESHOLD:
        return GapSeverity.HIGH
    if score >= MODERATE_THRESHOLD:
        return GapSeverity.MODERATE
    return GapSeverity.LOW


# How many of the worst gaps dominate the health score. Beyond this, extra
# gaps still hurt but with sharply diminishing effect.
HEALTH_FOCUS_COUNT = 5

# Each successive gap in the focus window counts less than the one before.
RANK_DECAY = 0.55

# How much the gaps outside the focus window contribute.
TAIL_WEIGHT = 0.35


def compute_health_score(gap_scores: list[float]) -> float:
    """100 means no gaps.

    Dominated by the worst offenders. A normalized weighted mean was tried
    first and was actively wrong: adding twenty trivial gaps to one critical
    gap raised the score from 5 to 73, so making a curriculum worse made it
    look healthier. Dividing by the weight sum let a long tail of near-zero
    scores dilute the average.

    Instead the top gaps are combined with a decaying weight and the result
    is not renormalized, so additional gaps can only ever lower the score.
    """
    if not gap_scores:
        return 100.0

    ordered = sorted((_clamp(s) for s in gap_scores), reverse=True)

    # Rank decay, tuned so the score spreads across a usable range. An
    # uncapped compounding penalty was tried first and saturated almost
    # immediately: three critical gaps scored 0.3 out of 100, which cannot
    # distinguish a mediocre curriculum from a catastrophic one and reads
    # as a broken tool to anyone looking at it.
    penalty = 0.0
    remaining = 1.0
    for rank, score in enumerate(ordered[:HEALTH_FOCUS_COUNT]):
        contribution = remaining * score * (RANK_DECAY**rank)
        penalty += contribution
        remaining -= contribution

    # The long tail past the focus window contributes a small residual so
    # that many minor gaps remain visible in the score.
    tail = ordered[HEALTH_FOCUS_COUNT:]
    if tail:
        penalty += remaining * (sum(tail) / len(tail)) * TAIL_WEIGHT

    return round(_clamp(1.0 - penalty) * 100.0, 1)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
