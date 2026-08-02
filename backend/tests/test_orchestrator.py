"""Gap report construction.

These tests cover the logic that turns raw graph rows into a ranked,
evidence-backed report. They use fabricated rows rather than a live graph,
so they run anywhere and pin behaviour precisely.
"""

from unittest.mock import patch

from app.contracts import GapSeverity
from app.pipeline.orchestrator import (
    UNREACHABLE_DISTANCE,
    _build_evidence,
    _derive_course_code,
)


def _row(skill, requiring=10, total=100, distance=1, coverage=None, category="data"):
    return {
        "skill": skill,
        "category": category,
        "postings_requiring": requiring,
        "postings_total": total,
        "market_importance": 0.7,
        "prerequisite_distance": distance,
        "sample_evidence": "requires " + skill,
        "coverage_confidence": coverage or [],
    }


def _build(rows):
    """Build a report from fabricated rows, bypassing the graph."""
    from app.pipeline.orchestrator import Pipeline

    with patch.object(Pipeline, "__init__", lambda self: None):
        pipeline = Pipeline()
        with patch(
            "app.pipeline.orchestrator.fetch_course_gaps", return_value=rows
        ), patch("app.pipeline.orchestrator.fetch_courses", return_value=[]):
            return pipeline.build_report("CS301", "Test Course")


def _build_with_domain(rows, categories):
    """Build a report where the course's own taught categories are known.

    `_course_domain` reads these from the graph rather than from the gap
    rows, because a discipline the corpus barely covers produces almost no
    rows and was therefore invisible.
    """
    from app.pipeline.orchestrator import Pipeline

    with patch.object(Pipeline, "__init__", lambda self: None):
        pipeline = Pipeline()
        with patch(
            "app.pipeline.orchestrator.fetch_course_gaps", return_value=rows
        ), patch(
            "app.pipeline.orchestrator.fetch_courses", return_value=[]
        ), patch(
            "app.pipeline.orchestrator.fetch_course_categories",
            return_value=categories,
        ):
            return pipeline.build_report("CE303", "Structural Analysis")


def test_thin_evidence_withholds_findings_and_score():
    """A subject area the corpus barely covers cannot be audited.

    Ranking cannot manufacture evidence: with two civil postings against
    hundreds of software ones, any sort surfaces Cloud Computing. Both the
    findings and the score are withheld rather than presented as a verdict.
    """
    report = _build_with_domain(
        [
            _row("Cloud Computing", requiring=40, total=100, category="cloud"),
            _row("Estimation and Costing", requiring=2, total=100, category="civil"),
        ],
        [{"category": "civil", "skills": 5, "weight": 4.2}],
    )

    assert report.evidence_thin is True
    assert report.health_score is None
    assert report.evidence_note is not None
    assert all(gap.category == "civil" for gap in report.gaps)


def test_sufficient_evidence_still_scores_and_ranks():
    """The floor must not silence a subject area the corpus does cover."""
    report = _build_with_domain(
        [
            _row("Kubernetes", requiring=40, total=100, category="cloud"),
            _row("Terraform", requiring=25, total=100, category="cloud"),
        ],
        [{"category": "cloud", "skills": 4, "weight": 3.6}],
    )

    assert report.evidence_thin is False
    assert report.health_score is not None
    assert len(report.gaps) == 2


def test_evidence_states_real_numbers():
    evidence = _build_evidence(47, 312, 0.0, 1)
    assert "47 of 312 postings require this" in evidence
    assert "no outcome in this course covers it" in evidence


def test_evidence_reports_partial_coverage():
    assert "only 40%" in _build_evidence(10, 100, 0.4, 1)


def test_evidence_omits_reachability():
    """The frontend renders reachability as its own colour-coded line.
    Repeating it in the evidence string made every gap card read as if it
    were saying the same thing twice."""
    for distance in (1, 3, UNREACHABLE_DISTANCE):
        evidence = _build_evidence(10, 100, 0.0, distance)
        assert "prerequisite" not in evidence
        assert "postings require this" in evidence


def test_report_ranks_technical_skills_above_soft_skills():
    """Soft skills appear in nearly every posting, so raw frequency puts
    them above every technical gap. "Add teamwork to your database course"
    is not advice a curriculum committee can act on."""
    report = _build(
        [
            _row("Team Collaboration", requiring=90, category="professional"),
            _row("Vector Databases", requiring=30, category="data"),
        ]
    )

    assert report.gaps[0].canonical_skill == "Vector Databases"


def test_soft_skills_still_appear_in_the_report():
    """Down-weighted, not censored. They are genuine market signal."""
    report = _build(
        [
            _row("Team Collaboration", requiring=90, category="professional"),
            _row("Vector Databases", requiring=30, category="data"),
        ]
    )

    assert "Team Collaboration" in {g.canonical_skill for g in report.gaps}


def test_taught_skills_rank_below_missing_ones():
    report = _build(
        [
            _row("SQL", requiring=50, coverage=[0.9]),
            _row("Vector Databases", requiring=40, coverage=[]),
        ]
    )

    assert report.gaps[0].canonical_skill == "Vector Databases"


def test_unreachable_distance_is_penalized_not_treated_as_adjacent():
    """A distance of 99 means unreachable. Passing it straight into the
    reachability term would make it look infinitely far and zero out that
    signal, so it maps to a finite penalty."""
    reachable = _build([_row("A", distance=1)]).gaps[0]
    unreachable = _build([_row("B", distance=UNREACHABLE_DISTANCE)]).gaps[0]

    assert unreachable.prerequisite_distance == UNREACHABLE_DISTANCE
    assert reachable.prerequisite_distance == 1


def test_empty_graph_yields_perfect_health():
    report = _build([])
    assert report.health_score == 100.0
    assert report.gaps == []


def test_severity_is_assigned_from_the_score():
    report = _build([_row("Critical Skill", requiring=95, total=100, distance=1)])
    assert report.gaps[0].severity in set(GapSeverity)


def test_coverage_uses_the_strongest_signal():
    """A skill taught by several outcomes is covered to the degree of the
    best one, not the average.

    0.9 is above COVERED_THRESHOLD, so the skill is treated as taught and
    withheld from the findings. It still has to reach the score, which is
    what a perfect health score demonstrates here.
    """
    strongest = _build([_row("SQL", coverage=[0.2, 0.9, 0.5])])
    weakest = _build([_row("SQL", coverage=[0.2])])

    assert strongest.gaps == []
    assert strongest.health_score > weakest.health_score


def test_partial_coverage_is_still_reported_as_a_gap():
    """Coverage below the threshold means the syllabus touches a skill
    without teaching it to the depth the market asks for, which is a finding
    rather than a pass."""
    report = _build([_row("SQL", coverage=[0.2, 0.4])])
    assert [gap.canonical_skill for gap in report.gaps] == ["SQL"]
    assert report.gaps[0].curriculum_coverage == 0.4


def test_course_code_derived_from_messy_filenames():
    assert _derive_course_code("CS301_Database_Systems") == "CS301 DATABASE SYSTEMS"
    assert _derive_course_code("cs 301 - databases") == "CS 301 DATABASES"
    assert _derive_course_code("") == "COURSE"


def test_zero_postings_does_not_divide_by_zero():
    """A skill no posting demands is filtered out by the demand floor rather
    than reported as a gap, and the empty corpus must not raise."""
    report = _build([_row("Skill", requiring=0, total=0)])
    assert report.gaps == []
    assert 0.0 <= report.health_score <= 100.0


def test_long_tail_skills_are_filtered_out():
    """43 of 170 demanded skills in the real corpus were named by exactly one
    posting. One employer wanting a niche tool is not evidence a degree
    programme is failing."""
    report = _build(
        [
            _row("Widely Demanded", requiring=40, total=100),
            _row("One Posting Only", requiring=1, total=100),
        ]
    )
    assert [gap.canonical_skill for gap in report.gaps] == ["Widely Demanded"]


def test_taught_skills_survive_the_demand_floor():
    """A skill the course teaches still counts toward coverage even if the
    corpus barely mentions it.

    It must not be listed as a gap, which told a structural analysis course
    its gap was Hydrology, a subject it teaches. Its contribution shows in
    the score being higher than the uncovered skill alone would give.
    """
    taught = _build(
        [
            _row("Widely Demanded", requiring=40, total=100),
            _row("Niche But Taught", requiring=1, total=100, coverage=[0.8]),
        ]
    )
    untaught = _build([_row("Widely Demanded", requiring=40, total=100)])

    assert [gap.canonical_skill for gap in taught.gaps] == ["Widely Demanded"]
    assert taught.health_score > untaught.health_score


def test_report_names_what_it_scored_against():
    """The denominator must be inspectable. A score against the whole market
    and a score against one subject area are very different claims."""
    report = _build([_row("Vector Databases", requiring=40, category="data")])
    assert report.scored_against
