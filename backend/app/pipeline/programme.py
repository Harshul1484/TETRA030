"""Programme-level analysis, above the individual course.

A dean does not audit one course, they audit a degree. Everything here
answers a question at that altitude:

  What is missing across the entire programme, not just one syllabus?
  Which course should teach a missing skill, given what each already covers?
  How long until a gap could realistically be closed?
  Where does the curriculum teach something students cannot yet absorb?

The last one is the sharpest. If a programme teaches CSS but no course
teaches HTML, that is a structural defect rather than a market gap, and it
is exactly the kind of finding an accreditation body exists to catch.
"""

import logging

from app.db.neo4j_client import session

logger = logging.getLogger(__name__)

# A skill must appear in at least this share of postings to count as a
# programme-level gap, matching the floor used for individual courses.
MIN_DEMAND_SHARE = 0.03

# How far a skill can sit from a course's existing content before placing it
# there stops being sensible. Beyond this the course would be teaching
# something unrelated to what it already covers.
MAX_PLACEMENT_DISTANCE = 3

PROGRAMME_GAPS_QUERY = """
// Everything the programme teaches, across every course.
MATCH (:Course)-[:HAS_OUTCOME]->(:Outcome)-[:TEACHES]->(t:Skill)
WITH collect(DISTINCT t.canonical_name) AS taught

MATCH (total:JobPosting)
WITH taught, count(DISTINCT total) AS postings_total

MATCH (j:JobPosting)-[r:REQUIRES]->(g:Skill)
WHERE NOT g.canonical_name IN taught
WITH taught, postings_total, g,
     count(DISTINCT j) AS postings_requiring,
     avg(r.importance) AS importance
WHERE toFloat(postings_requiring) / postings_total >= $min_share

RETURN g.canonical_name AS skill,
       g.category AS category,
       postings_requiring,
       postings_total,
       coalesce(importance, 0.5) AS importance
ORDER BY postings_requiring DESC
LIMIT $limit
"""

PLACEMENT_QUERY = """
// For a missing skill, how close is each course to being able to teach it?
// Distance is measured from what the course already teaches, so a course
// covering Docker is a better home for Kubernetes than one covering
// accounting.
//
// `category_overlap` counts how many of the course's existing skills share
// the target's subject area. Graph distance alone leaves ties, and a tie
// broken arbitrarily put CI/CD in an Artificial Intelligence course because
// both touch Data Structures. Subject overlap breaks those ties sensibly.
MATCH (c:Course)
OPTIONAL MATCH (c)-[:HAS_OUTCOME]->(:Outcome)-[:TEACHES]->(t:Skill)
WITH c, collect(DISTINCT t) AS taught, collect(DISTINCT t.canonical_name) AS names
WHERE size(taught) > 0

MATCH (target:Skill {canonical_name: $skill})
WITH c, taught, names, target,
     size([x IN taught WHERE x.category = target.category]) AS category_overlap

OPTIONAL MATCH path = shortestPath((known:Skill)-[:PREREQUISITE_OF*1..3]-(target))
WHERE known IN taught AND known <> target

WITH c, names, category_overlap,
     CASE WHEN path IS NULL THEN 99 ELSE length(path) END AS distance,
     [n IN nodes(path) WHERE n IN taught | n.canonical_name] AS bridge

RETURN c.code AS course_code,
       c.title AS course_title,
       min(distance) AS distance,
       category_overlap,
       size(names) AS skills_taught,
       collect(bridge)[0] AS via
ORDER BY distance ASC, category_overlap DESC, skills_taught DESC
"""

STRUCTURAL_DEFECTS_QUERY = """
// Skills the programme teaches whose prerequisites nothing in the
// programme covers. Students are being asked to absorb material they have
// no foundation for. This is a curriculum defect, not a market gap.
MATCH (:Course)-[:HAS_OUTCOME]->(:Outcome)-[:TEACHES]->(t:Skill)
WITH collect(DISTINCT t.canonical_name) AS taught

UNWIND taught AS name
MATCH (sk:Skill {canonical_name: name})
MATCH (prereq:Skill)-[:PREREQUISITE_OF]->(sk)
WHERE NOT prereq.canonical_name IN taught

MATCH (c:Course)-[:HAS_OUTCOME]->(:Outcome)-[:TEACHES]->(sk)

RETURN sk.canonical_name AS skill,
       collect(DISTINCT prereq.canonical_name) AS missing_prerequisites,
       collect(DISTINCT c.code) AS taught_in
ORDER BY size(missing_prerequisites) DESC
LIMIT $limit
"""

COVERAGE_QUERY = """
MATCH (c:Course)-[:HAS_OUTCOME]->(:Outcome)-[:TEACHES]->(s:Skill)
RETURN s.canonical_name AS skill,
       s.category AS category,
       count(DISTINCT c) AS course_count,
       collect(DISTINCT c.code) AS courses
ORDER BY course_count DESC
"""


def fetch_programme_gaps(limit: int = 25) -> list[dict]:
    with session() as s:
        return [
            dict(row)
            for row in s.run(
                PROGRAMME_GAPS_QUERY, min_share=MIN_DEMAND_SHARE, limit=limit
            )
        ]


def fetch_placement(skill: str) -> list[dict]:
    with session() as s:
        return [dict(row) for row in s.run(PLACEMENT_QUERY, skill=skill)]


def fetch_structural_defects(limit: int = 15) -> list[dict]:
    with session() as s:
        return [dict(row) for row in s.run(STRUCTURAL_DEFECTS_QUERY, limit=limit)]


def fetch_coverage() -> list[dict]:
    with session() as s:
        return [dict(row) for row in s.run(COVERAGE_QUERY)]


def estimate_effort(distance: int) -> dict:
    """Translate prerequisite distance into planning language.

    Every gap currently reads as equally urgent, and it is not. A skill one
    hop from existing content can be slotted into the next revision. One
    four hops away needs foundational work first, which in a semester system
    means years rather than months.

    The semester figures are deliberately coarse. They describe the shape of
    the work, not a schedule anyone should hold a department to.
    """
    if distance <= 1:
        return {
            "effort": "immediate",
            "semesters": 1,
            "detail": "can be added to an existing unit in the next revision",
        }
    if distance == 2:
        return {
            "effort": "short term",
            "semesters": 2,
            "detail": "one intermediate topic needed first",
        }
    if distance <= MAX_PLACEMENT_DISTANCE:
        return {
            "effort": "medium term",
            "semesters": 3,
            "detail": "a short chain of groundwork must be laid",
        }
    return {
        "effort": "long term",
        "semesters": 4,
        "detail": "no path from current content, needs foundational work",
    }


def best_placement(skill: str) -> dict | None:
    """Which course is the natural home for a missing skill.

    Returns the course whose existing content sits closest to the skill in
    the prerequisite graph. A course teaching Docker is a better home for
    Kubernetes than one teaching accounting, and the graph knows that
    without anyone encoding it.

    Where several courses are equally close and none has a stronger subject
    overlap, the alternatives are returned rather than one being picked
    arbitrarily. A tool that manufactures certainty it does not have is
    worse than one that says two options are equivalent and lets the
    committee choose.
    """
    candidates = fetch_placement(skill)
    if not candidates:
        return None

    best = candidates[0]
    if best["distance"] > MAX_PLACEMENT_DISTANCE:
        return {
            "skill": skill,
            "course_code": None,
            "alternatives": [],
            "reason": "no course in the programme is close enough to host this",
            **estimate_effort(best["distance"]),
        }

    # Equally close, equally related. These are genuine ties.
    tied = [
        c
        for c in candidates
        if c["distance"] == best["distance"]
        and c["category_overlap"] == best["category_overlap"]
    ]

    via = [name for name in (best.get("via") or []) if name]
    if via:
        reason = f"closest existing content is {', '.join(via)}"
    else:
        reason = "this course covers the nearest related material"

    if len(tied) > 1:
        reason += f"; {len(tied) - 1} other course"
        reason += "s are" if len(tied) > 2 else " is"
        reason += " equally close"

    return {
        "skill": skill,
        "course_code": best["course_code"],
        "course_title": best["course_title"],
        "distance": best["distance"],
        "via": via,
        "alternatives": [c["course_code"] for c in tied[1:4]],
        "confident": len(tied) == 1,
        "reason": reason,
        **estimate_effort(best["distance"]),
    }


def build_programme_report(limit: int = 20) -> dict:
    """The whole-degree view: what is missing, where it should go, and what
    the curriculum already teaches without foundation."""
    gaps = fetch_programme_gaps(limit=limit)

    placements = []
    for gap in gaps:
        try:
            placement = best_placement(gap["skill"])
        except Exception as exc:
            logger.warning("Placement failed for %s: %s", gap["skill"], exc)
            placement = None

        total = max(gap["postings_total"], 1)
        placements.append(
            {
                "skill": gap["skill"],
                "category": gap["category"] or "general",
                "postings_requiring": gap["postings_requiring"],
                "postings_total": total,
                "demand_share": round(gap["postings_requiring"] / total, 4),
                "placement": placement,
            }
        )

    try:
        defects = fetch_structural_defects()
    except Exception as exc:
        logger.warning("Structural defect query failed: %s", exc)
        defects = []

    return {
        "gaps": placements,
        "structural_defects": defects,
        "gap_count": len(placements),
        "defect_count": len(defects),
    }
