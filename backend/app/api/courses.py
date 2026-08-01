"""Course listing, gap reports, and augmentation."""

import logging

from fastapi import APIRouter, HTTPException

from app.api.deps import get_augmenter, get_pipeline
from app.contracts import AugmentProposal, GapReport
from app.db.queries import fetch_courses, fetch_prerequisite_chain

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["courses"])


@router.get("/courses")
def list_courses() -> list[dict]:
    """Courses with their health scores.

    The score is recomputed per course rather than stored, so it always
    reflects the current graph. With a handful of courses this is fast
    enough; a larger deployment would cache it.
    """
    courses = fetch_courses()
    summaries = []

    for course in courses:
        try:
            report = get_pipeline().build_report(course["code"], course["title"])
            summaries.append(
                {
                    "code": course["code"],
                    "title": course["title"],
                    "department": course.get("department") or "",
                    "skills_taught": course.get("skills_taught", 0),
                    "health_score": report.health_score,
                    "gap_count": len(report.gaps),
                    "critical_gaps": sum(
                        1 for gap in report.gaps if gap.severity.value == "critical"
                    ),
                }
            )
        except Exception as exc:
            logger.warning("Report failed for %s: %s", course["code"], exc)
            summaries.append(
                {
                    "code": course["code"],
                    "title": course["title"],
                    "department": course.get("department") or "",
                    "skills_taught": course.get("skills_taught", 0),
                    "health_score": None,
                    "gap_count": 0,
                    "critical_gaps": 0,
                }
            )

    return summaries


@router.get("/courses/{course_code}/gaps", response_model=GapReport)
def course_gaps(course_code: str) -> GapReport:
    known = {c["code"]: c["title"] for c in fetch_courses()}
    if course_code not in known:
        raise HTTPException(status_code=404, detail=f"Unknown course: {course_code}")
    return get_pipeline().build_report(course_code, known[course_code])


@router.get("/skills/{skill}/prerequisites")
def skill_prerequisites(skill: str) -> dict:
    """The dependency chain behind a skill.

    This is what turns "you are missing X" into "here is what X costs",
    and it is the clearest demonstration of why the ontology is a graph.
    """
    chain = fetch_prerequisite_chain(skill)
    by_hop: dict[int, list[str]] = {}
    for row in chain:
        by_hop.setdefault(row["hops"], []).append(row["prerequisite"])

    return {
        "skill": skill,
        "total_prerequisites": len(chain),
        "max_depth": max(by_hop) if by_hop else 0,
        "by_hop": [
            {"hops": hop, "prerequisites": sorted(names)}
            for hop, names in sorted(by_hop.items())
        ],
    }


@router.post("/augment/{course_code}", response_model=AugmentProposal)
def augment_course(course_code: str) -> AugmentProposal:
    """Propose modifications for a course. This is the third mandated component."""
    report = course_gaps(course_code)
    return get_augmenter().propose(report)
