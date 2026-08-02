"""Accreditation endpoints.

The CO-PO matrix is the central artifact of an NBA submission and is
normally assembled by hand across every course in a programme. These
endpoints produce it from the graph, along with the findings an assessor
would raise.
"""

from fastapi import APIRouter, Query

from app.pipeline.accreditation import (
    PROGRAMME_OUTCOMES,
    build_co_po_matrix,
    compliance_findings,
)

router = APIRouter(prefix="/api/accreditation", tags=["accreditation"])


@router.get("/matrix")
def co_po_matrix(course: str | None = Query(default=None)) -> dict:
    """Course Outcome to Programme Outcome correlations.

    Pass `course` for a single course, or omit it for the whole programme.
    Every cell carries the skill and confidence it was derived from, so an
    assessor can audit any claim rather than taking the number on trust.
    """
    return build_co_po_matrix(course)


@router.get("/findings")
def findings() -> dict:
    """What an assessor would flag.

    Ordered by how seriously an NBA panel treats them: an uncovered
    Programme Outcome is a major non-conformity, one resting on a single
    course is a risk, and thin coverage is an observation.
    """
    return compliance_findings()


@router.get("/outcomes")
def programme_outcomes() -> dict:
    """The twelve NBA Programme Outcomes, for reference."""
    return {"programme_outcomes": PROGRAMME_OUTCOMES, "count": len(PROGRAMME_OUTCOMES)}
