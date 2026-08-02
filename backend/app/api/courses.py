"""Course listing, gap reports, and augmentation."""

import logging

from fastapi import APIRouter, HTTPException

from app.api.deps import get_augmenter, get_pipeline
from app.contracts import AugmentProposal, GapReport
from app.db.queries import (
    fetch_courses,
    fetch_domain_postings,
    fetch_prerequisite_chain,
)
from app.pipeline.roadmap import build_roadmap

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


@router.get("/courses/{course_code}/roadmap")
def course_roadmap(course_code: str) -> dict:
    """A teaching sequence, ordered by prerequisite dependency.

    The gap report says what is missing. This says what to do about it and in
    what order, because some gaps cannot be taught until others are in place.
    Nothing here is course-specific: the sequence comes from the graph, so an
    uploaded syllabus is treated exactly like a seeded one.
    """
    report = course_gaps(course_code)
    plan = build_roadmap(course_code, report.gaps)
    plan["course_title"] = report.course_title
    return plan


@router.get("/courses/{course_code}/evidence")
def course_evidence(course_code: str, limit: int = 25) -> dict:
    """The job postings a course's audit was measured against.

    Every figure in the gap report reduces to a count of postings. Listing
    them turns that count from an assertion into something the reader can
    check, which matters most where the count is low enough to withhold the
    findings entirely.
    """
    report = course_gaps(course_code)
    categories = [c for c in report.scored_against if c != "all categories"]
    postings = fetch_domain_postings(categories, limit=limit)

    return {
        "course_code": report.course_code,
        "course_title": report.course_title,
        "scored_against": report.scored_against,
        "domain_postings": report.domain_postings,
        "evidence_thin": report.evidence_thin,
        "postings": postings,
    }


@router.post("/augment/{course_code}", response_model=AugmentProposal)
def augment_course(course_code: str) -> AugmentProposal:
    """Propose modifications for a course. This is the third mandated component."""
    report = course_gaps(course_code)
    return get_augmenter().propose(report)
