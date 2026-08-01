"""Job market demand and trends.

The trends endpoint returns a valid payload whether or not the forecaster
of the design has shipped. Slope is null until then, and the frontend
renders demand history without a projection. The contract does not change
when the model lands.
"""

from collections import defaultdict

from fastapi import APIRouter, Query

from app.contracts import SkillTrend, TrendPoint
from app.db.queries import fetch_trend_rows

router = APIRouter(prefix="/api", tags=["market"])


@router.get("/market/trends", response_model=list[SkillTrend])
def trends(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[SkillTrend]:
    rows = fetch_trend_rows()

    buckets: dict[str, list[TrendPoint]] = defaultdict(list)
    for row in rows:
        buckets[row["skill"]].append(
            TrendPoint(period=row["period"], frequency=row["frequency"])
        )

    ranked = sorted(
        buckets.items(),
        key=lambda item: sum(point.frequency for point in item[1]),
        reverse=True,
    )[:limit]

    return [
        SkillTrend(
            canonical_skill=skill,
            history=sorted(points, key=lambda p: p.period),
            slope=None,
        )
        for skill, points in ranked
    ]


@router.get("/market/summary")
def summary() -> dict:
    """Corpus-level numbers, so the dashboard can state its own evidence base."""
    from app.db.neo4j_client import session

    with session() as s:
        record = s.run(
            "MATCH (j:JobPosting) "
            "WITH count(j) AS postings, "
            "     min(j.posted_date) AS earliest, "
            "     max(j.posted_date) AS latest "
            "MATCH ()-[r:REQUIRES]->() "
            "WITH postings, earliest, latest, count(r) AS demands "
            "MATCH (s:Skill) WHERE (:JobPosting)-[:REQUIRES]->(s) "
            "RETURN postings, earliest, latest, demands, "
            "       count(DISTINCT s) AS skills_demanded"
        ).single()

    if record is None:
        return {
            "postings": 0,
            "skills_demanded": 0,
            "demands": 0,
            "earliest": None,
            "latest": None,
        }
    return dict(record)
