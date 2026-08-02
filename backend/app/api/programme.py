"""Programme-level endpoints, above the individual course.

These answer the questions a dean or an accreditation body asks: what is
missing across the whole degree, where should it be taught, how long would
it take, what does the curriculum teach without foundation, and what has
changed since the last audit.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from app.pipeline.programme import (
    best_placement,
    build_programme_report,
    fetch_coverage,
    fetch_structural_defects,
)
from app.pipeline.reaudit import capture_snapshot, latest_drift, load_snapshots

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/programme", tags=["programme"])

AUDIT_DIR = Path("/app/data/audits")


@router.get("")
def programme_report(limit: int = Query(default=20, ge=1, le=60)) -> dict:
    """The whole-degree view.

    Gaps here are skills no course teaches, which is a stronger claim than a
    per-course gap and the one a dean actually acts on.
    """
    return build_programme_report(limit=limit)


@router.get("/coverage")
def coverage() -> dict:
    """Which skills the programme teaches, and in how many courses.

    A skill taught in one course is a single point of failure; one taught in
    six may be redundant. Both are worth knowing before revising anything.
    """
    rows = fetch_coverage()
    return {
        "skills": rows,
        "total": len(rows),
        "single_course": sum(1 for r in rows if r["course_count"] == 1),
    }


@router.get("/defects")
def defects(limit: int = Query(default=15, ge=1, le=50)) -> dict:
    """Skills taught without their prerequisites anywhere in the programme.

    This is a structural defect rather than a market gap: students are being
    asked to absorb material they have no foundation for, which is precisely
    what an accreditation review looks for.
    """
    rows = fetch_structural_defects(limit=limit)
    return {"defects": rows, "count": len(rows)}


@router.get("/placement/{skill}")
def placement(skill: str) -> dict:
    """Which course should teach a given skill, and what it would cost."""
    result = best_placement(skill)
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"No placement could be computed for {skill}"
        )
    return result


@router.post("/audit")
def run_audit() -> dict:
    """Record what the market demands right now, and report any drift.

    A single audit cannot show drift, so the response says so explicitly
    rather than fabricating a trend from one data point.
    """
    snapshot = capture_snapshot(AUDIT_DIR)
    drift = latest_drift(AUDIT_DIR)

    return {
        "captured_at": snapshot["captured_at"],
        "postings_total": snapshot["postings_total"],
        "skills_tracked": len(snapshot["demand"]),
        "audit_count": len(load_snapshots(AUDIT_DIR)),
        "drift": drift,
        "note": (
            None
            if drift
            else "First audit recorded. Run again after refreshing market data to see drift."
        ),
    }


@router.get("/audit")
def audit_history() -> dict:
    """Every audit taken, and the drift between the two most recent."""
    snapshots = load_snapshots(AUDIT_DIR)
    return {
        "audits": [
            {
                "captured_at": s["captured_at"],
                "postings_total": s["postings_total"],
                "skills_tracked": len(s.get("demand", {})),
            }
            for s in snapshots
        ],
        "count": len(snapshots),
        "drift": latest_drift(AUDIT_DIR),
    }
