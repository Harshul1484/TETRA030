"""CO-PO mapping is a compliance document, so its failure mode is not a
crash but a false claim.

An inflated matrix is worse than a sparse one: an assessor who finds one
unsupported correlation distrusts every other cell. These tests pin the
rules that keep a claim honest.
"""

from unittest.mock import patch

from app.pipeline.accreditation import (
    MIN_MAPPING_CONFIDENCE,
    PROGRAMME_OUTCOMES,
    build_co_po_matrix,
    compliance_findings,
    map_outcome,
)


def _row(course="CS101", skill="Algorithms", category="foundations", confidence=0.9):
    return {
        "course_code": course,
        "course_title": "Test Course",
        "outcome_id": f"m-{skill[:6]}",
        "outcome_text": f"Students will learn {skill}",
        "skill": skill,
        "category": category,
        "confidence": confidence,
    }


def _matrix(rows):
    with patch("app.pipeline.accreditation.fetch_outcome_rows", return_value=rows):
        return build_co_po_matrix()


def test_nba_defines_twelve_programme_outcomes():
    """Fixed by the accreditation body. Not ours to add to or reword."""
    assert len(PROGRAMME_OUTCOMES) == 12
    assert list(PROGRAMME_OUTCOMES) == [f"PO{i}" for i in range(1, 13)]


def test_a_foundations_outcome_evidences_engineering_knowledge():
    mapping = map_outcome("foundations", 0.9)
    assert mapping["PO1"] == 3
    assert mapping["PO2"] == 3


def test_a_professional_outcome_evidences_communication_and_teamwork():
    mapping = map_outcome("professional", 0.9)
    assert mapping["PO9"] == 3
    assert mapping["PO10"] == 3


def test_weak_evidence_produces_no_claim():
    """Below the confidence floor the underlying match is unreliable, and an
    unreliable match must not appear in a compliance document at all."""
    assert map_outcome("foundations", MIN_MAPPING_CONFIDENCE - 0.01) == {}


def test_correlation_is_capped_by_match_confidence():
    """A skill matched at 0.5 cannot claim a substantial correlation. The
    evidence underneath it is not that strong."""
    strong = map_outcome("foundations", 0.9)
    moderate = map_outcome("foundations", 0.6)
    weak = map_outcome("foundations", 0.4)

    assert strong["PO1"] == 3
    assert moderate["PO1"] == 2
    assert weak["PO1"] == 1


def test_unknown_category_claims_nothing():
    """A skill category with no defined mapping must not be assigned one by
    guesswork."""
    assert map_outcome("astrology", 0.9) == {}


def test_matrix_records_the_evidence_for_every_row():
    """An assessor must be able to audit any cell, which means the skill and
    confidence behind it travel with the mapping."""
    matrix = _matrix([_row()])
    entry = matrix["outcomes"][0]

    assert entry["skill"] == "Algorithms"
    assert entry["confidence"] == 0.9
    assert entry["mapping"]["PO1"] == 3


def test_an_uncovered_outcome_is_reported_not_hidden():
    """The whole point of the document is to surface what is missing."""
    matrix = _matrix([_row(category="foundations")])

    assert "PO7" in matrix["uncovered"]
    assert matrix["po_coverage"]["PO7"]["course_count"] == 0


def test_coverage_counts_distinct_courses():
    matrix = _matrix(
        [
            _row(course="CS101", skill="Algorithms"),
            _row(course="CS101", skill="Data Structures"),
            _row(course="CS202", skill="Discrete Mathematics"),
        ]
    )
    assert matrix["po_coverage"]["PO1"]["course_count"] == 2
    assert matrix["po_coverage"]["PO1"]["outcome_count"] == 3


def test_empty_programme_reports_every_outcome_as_uncovered():
    matrix = _matrix([])
    assert len(matrix["uncovered"]) == 12
    assert matrix["outcomes"] == []


def test_an_uncovered_outcome_is_a_major_finding():
    """An NBA panel treats a Programme Outcome with no coverage as a major
    non-conformity, not an observation."""
    with patch(
        "app.pipeline.accreditation.fetch_outcome_rows",
        return_value=[_row(category="foundations")],
    ):
        result = compliance_findings()

    majors = [f for f in result["findings"] if f["severity"] == "major"]
    assert any(f["po"] == "PO7" for f in majors)


def test_single_course_coverage_is_a_risk_not_a_failure():
    with patch(
        "app.pipeline.accreditation.fetch_outcome_rows",
        return_value=[_row(course="CS101", category="professional")],
    ):
        result = compliance_findings()

    assert any(f["severity"] == "risk" for f in result["findings"])


def test_findings_report_how_much_of_the_programme_is_covered():
    with patch(
        "app.pipeline.accreditation.fetch_outcome_rows",
        return_value=[_row(category="foundations")],
    ):
        result = compliance_findings()

    assert result["pos_total"] == 12
    assert 0 < result["pos_covered"] < 12
