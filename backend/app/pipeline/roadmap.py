"""Turn a gap report into a teaching sequence.

A ranked list of gaps tells a curriculum committee what is missing. It does
not tell them what to do on Monday, because some gaps cannot be taught until
others are in place: there is no point scheduling Amazon Web Services before
Cloud Computing, or CI/CD before version control.

This module orders the gaps by their prerequisite dependencies and groups
them into teaching stages. Stage one is everything that can be taught
immediately. Stage two is everything unblocked once stage one is done, and
so on. That is a topological layering of the gap subgraph.

Nothing here is specific to any course or institution. The sequence is
derived from the graph, so an uploaded syllabus gets the same treatment as a
seeded one.
"""

import logging

from app.contracts import SkillGap
from app.db.neo4j_client import session

logger = logging.getLogger(__name__)

# How many gaps to sequence. Beyond roughly this many the roadmap stops
# being a plan and becomes a wish list.
DEFAULT_HORIZON = 12

# Gaps per stage. A committee revising a course can absorb a few additions
# per term, not fifteen.
DEFAULT_STAGE_SIZE = 4

PREREQUISITES_QUERY = """
UNWIND $skills AS name
MATCH (target:Skill {canonical_name: name})
OPTIONAL MATCH (prereq:Skill)-[:PREREQUISITE_OF]->(target)
RETURN target.canonical_name AS skill,
       collect(DISTINCT prereq.canonical_name) AS prerequisites
"""

TAUGHT_QUERY = """
MATCH (c:Course {code: $course_code})-[:HAS_OUTCOME]->(:Outcome)-[:TEACHES]->(s:Skill)
RETURN collect(DISTINCT s.canonical_name) AS taught
"""


def fetch_prerequisites(skills: list[str]) -> dict[str, list[str]]:
    if not skills:
        return {}
    with session() as s:
        return {
            row["skill"]: row["prerequisites"]
            for row in s.run(PREREQUISITES_QUERY, skills=skills)
        }


def fetch_taught(course_code: str) -> set[str]:
    with session() as s:
        record = s.run(TAUGHT_QUERY, course_code=course_code).single()
    return set(record["taught"]) if record else set()


def build_roadmap(
    course_code: str,
    gaps: list[SkillGap],
    horizon: int = DEFAULT_HORIZON,
    stage_size: int = DEFAULT_STAGE_SIZE,
) -> dict:
    """Order gaps into stages that respect prerequisite dependencies.

    A skill is placed in a stage only once every prerequisite it depends on
    is either already taught or scheduled in an earlier stage. Skills whose
    prerequisites fall outside the planned set are still scheduled, with the
    missing groundwork named, so the plan never silently drops a gap.
    """
    selected = gaps[:horizon]
    if not selected:
        return {"course_code": course_code, "stages": [], "unscheduled": []}

    names = [gap.canonical_skill for gap in selected]
    by_name = {gap.canonical_skill: gap for gap in selected}

    try:
        prerequisites = fetch_prerequisites(names)
        taught = fetch_taught(course_code)
    except Exception as exc:
        logger.warning("Roadmap graph lookup failed: %s", exc)
        prerequisites, taught = {}, set()

    planned = set(names)
    satisfied = set(taught)
    remaining = list(names)
    stages: list[dict] = []

    while remaining:
        # Everything whose in-plan prerequisites are already satisfied.
        ready = [
            name
            for name in remaining
            if all(
                prereq in satisfied or prereq not in planned
                for prereq in prerequisites.get(name, [])
            )
        ]

        if not ready:
            # A cycle, or a dependency the graph cannot resolve. Rather than
            # loop forever, schedule the highest-demand remaining skill and
            # let the next pass proceed.
            ready = [remaining[0]]
            logger.warning(
                "Roadmap could not order %s cleanly; scheduling by demand",
                remaining[0],
            )

        batch = ready[:stage_size]
        stages.append(
            {
                "stage": len(stages) + 1,
                "skills": [
                    _describe(by_name[name], prerequisites.get(name, []), taught, planned)
                    for name in batch
                ],
            }
        )

        satisfied.update(batch)
        remaining = [name for name in remaining if name not in batch]

    return {
        "course_code": course_code,
        "stages": stages,
        "total_skills": len(names),
        "stage_count": len(stages),
    }


def _describe(
    gap: SkillGap,
    prerequisites: list[str],
    taught: set[str],
    planned: set[str],
) -> dict:
    """One scheduled skill, with the groundwork it depends on named.

    Prerequisites are split three ways so a committee can see which are
    already handled, which this plan covers, and which sit outside it
    entirely and would need separate provision.
    """
    return {
        "skill": gap.canonical_skill,
        "category": gap.category,
        "severity": gap.severity.value,
        "postings_requiring": gap.postings_requiring,
        "postings_total": gap.postings_total,
        "already_taught": sorted(p for p in prerequisites if p in taught),
        "covered_by_plan": sorted(
            p for p in prerequisites if p in planned and p not in taught
        ),
        "outside_plan": sorted(
            p for p in prerequisites if p not in planned and p not in taught
        ),
    }
