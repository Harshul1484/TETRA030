"""Accreditation documentation, generated from the graph.

Indian engineering programmes are accredited by the NBA against twelve
Programme Outcomes fixed by the National Board of Accreditation. Every
course must map its Course Outcomes to those POs with a correlation level of
1, 2, or 3, and departments assemble that matrix by hand across dozens of
courses. It takes weeks and it is the single most disliked part of the
process.

The mapping is derivable. A course outcome that teaches Algorithms
demonstrably serves PO1 (engineering knowledge) and PO2 (problem analysis);
one that teaches Technical Communication serves PO10. Because the taxonomy
already categorises every skill and the graph already links outcomes to
skills, the matrix falls out of data that exists.

What this does NOT do is claim attainment. Attainment requires assessment
results, which live in a university's examination system. This produces the
mapping and flags where a programme has no coverage of a required outcome,
which is the part that is mechanical and the part that takes the weeks.
"""

import logging

from app.db.neo4j_client import session

logger = logging.getLogger(__name__)

# The twelve NBA Programme Outcomes, verbatim in substance. These are fixed
# by the accreditation body and are not ours to reword.
PROGRAMME_OUTCOMES: dict[str, str] = {
    "PO1": "Engineering knowledge: apply mathematics, science, and engineering fundamentals",
    "PO2": "Problem analysis: identify, formulate, and analyse complex engineering problems",
    "PO3": "Design and development of solutions for complex engineering problems",
    "PO4": "Conduct investigations of complex problems using research methods",
    "PO5": "Modern tool usage: select and apply appropriate techniques and tools",
    "PO6": "The engineer and society: assess societal, health, safety, and legal issues",
    "PO7": "Environment and sustainability: understand the impact of engineering solutions",
    "PO8": "Ethics: apply ethical principles and professional responsibilities",
    "PO9": "Individual and team work: function effectively as an individual and in teams",
    "PO10": "Communication: communicate effectively on complex engineering activities",
    "PO11": "Project management and finance: apply management principles to projects",
    "PO12": "Life-long learning: recognise the need for and engage in independent learning",
}

# Which skill categories evidence which Programme Outcome, and how strongly.
# Level 3 is a substantial correlation, 2 moderate, 1 slight, matching the
# NBA convention. A category maps to a PO only where teaching it genuinely
# demonstrates that outcome, because an inflated matrix is worse than a
# sparse one: an assessor who finds one unsupported claim distrusts all of
# them.
CATEGORY_TO_PO: dict[str, dict[str, int]] = {
    "foundations": {"PO1": 3, "PO2": 3, "PO12": 1},
    "mathematics": {"PO1": 3, "PO2": 3, "PO4": 2},
    "language": {"PO1": 2, "PO3": 3, "PO5": 3},
    "ai": {"PO1": 2, "PO2": 3, "PO3": 3, "PO4": 3, "PO5": 3},
    "data": {"PO1": 2, "PO2": 3, "PO4": 3, "PO5": 3},
    "web": {"PO3": 3, "PO5": 3, "PO2": 1},
    "systems": {"PO1": 3, "PO2": 3, "PO3": 2, "PO5": 2},
    "cloud": {"PO3": 2, "PO5": 3, "PO11": 2},
    "security": {"PO4": 2, "PO6": 3, "PO8": 3, "PO2": 2},
    "engineering": {"PO3": 3, "PO5": 2, "PO9": 2, "PO11": 2, "PO12": 2},
    "professional": {"PO8": 2, "PO9": 3, "PO10": 3, "PO11": 3, "PO12": 3},
}

# A course outcome maps to a PO only when the underlying skill match was at
# least this confident. A weak match producing a level-3 correlation would
# be a fabricated claim in a compliance document.
MIN_MAPPING_CONFIDENCE = 0.35

OUTCOMES_QUERY = """
MATCH (c:Course)-[:HAS_OUTCOME]->(o:Outcome)-[t:TEACHES]->(s:Skill)
WHERE $course_code IS NULL OR c.code = $course_code
RETURN c.code AS course_code,
       c.title AS course_title,
       o.outcome_id AS outcome_id,
       o.text AS outcome_text,
       s.canonical_name AS skill,
       s.category AS category,
       t.confidence AS confidence
ORDER BY c.code, o.outcome_id
"""


def fetch_outcome_rows(course_code: str | None = None) -> list[dict]:
    with session() as s:
        return [dict(r) for r in s.run(OUTCOMES_QUERY, course_code=course_code)]


def map_outcome(category: str, confidence: float) -> dict[str, int]:
    """Programme Outcomes evidenced by a single course outcome.

    Correlation is capped by match confidence: a skill matched at 0.5 cannot
    claim a level-3 correlation, because the evidence underneath it is not
    that strong.
    """
    if confidence < MIN_MAPPING_CONFIDENCE:
        return {}

    base = CATEGORY_TO_PO.get(category, {})
    ceiling = 3 if confidence >= 0.75 else 2 if confidence >= 0.5 else 1
    return {po: min(level, ceiling) for po, level in base.items()}


def build_co_po_matrix(course_code: str | None = None) -> dict:
    """The CO-PO matrix, the central artifact of an NBA submission.

    One row per course outcome, one column per Programme Outcome, cells
    holding the correlation level. Each row carries the skill and confidence
    it was derived from, so an assessor can audit any cell rather than
    taking the number on trust.
    """
    rows = fetch_outcome_rows(course_code)
    if not rows:
        # Reporting twelve uncovered outcomes here would be the most alarming
        # possible finding, and for an unknown course it would be fabricated.
        # The empty case says it has nothing to report rather than implying
        # total non-compliance.
        return {
            "course_code": course_code,
            "programme_outcomes": PROGRAMME_OUTCOMES,
            "outcomes": [],
            "po_coverage": {
                po: {"courses": [], "course_count": 0, "outcome_count": 0}
                for po in PROGRAMME_OUTCOMES
            },
            "uncovered": [],
            "outcome_count": 0,
            "note": (
                "No mapped course outcomes were found. This is not a finding of "
                "non-compliance; there is nothing here to assess."
            ),
        }

    outcomes = []
    coverage: dict[str, list[str]] = {po: [] for po in PROGRAMME_OUTCOMES}

    for row in rows:
        mapping = map_outcome(row["category"] or "", row["confidence"] or 0.0)
        if not mapping:
            continue

        label = f"CO-{row['outcome_id'][-4:]}"
        outcomes.append(
            {
                "course_code": row["course_code"],
                "course_title": row["course_title"],
                "outcome_id": row["outcome_id"],
                "label": label,
                "text": (row["outcome_text"] or "")[:220],
                "skill": row["skill"],
                "category": row["category"],
                "confidence": round(row["confidence"] or 0.0, 3),
                "mapping": mapping,
            }
        )

        for po in mapping:
            coverage[po].append(row["course_code"])

    po_coverage = {
        po: {
            "courses": sorted(set(codes)),
            "course_count": len(set(codes)),
            "outcome_count": len(codes),
        }
        for po, codes in coverage.items()
    }

    return {
        "course_code": course_code,
        "programme_outcomes": PROGRAMME_OUTCOMES,
        "outcomes": outcomes,
        "po_coverage": po_coverage,
        "uncovered": sorted(po for po, v in po_coverage.items() if v["course_count"] == 0),
        "outcome_count": len(outcomes),
    }


def compliance_findings() -> dict:
    """What an assessor would flag, stated the way a report states it.

    Three findings, ordered by how seriously an NBA panel treats them: a
    Programme Outcome with no coverage at all is a major non-conformity; one
    resting on a single course is a risk; weak evidence is an observation.
    """
    matrix = build_co_po_matrix()
    coverage = matrix["po_coverage"]

    major = [
        {
            "po": po,
            "statement": PROGRAMME_OUTCOMES[po],
            "finding": "No course outcome in the programme maps to this Programme Outcome.",
            "severity": "major",
        }
        for po in matrix["uncovered"]
    ]

    single = [
        {
            "po": po,
            "statement": PROGRAMME_OUTCOMES[po],
            "finding": (
                f"Only {data['courses'][0]} evidences this outcome. "
                "A single point of coverage is a risk if that course changes."
            ),
            "severity": "risk",
        }
        for po, data in coverage.items()
        if data["course_count"] == 1
    ]

    weak = [
        {
            "po": po,
            "statement": PROGRAMME_OUTCOMES[po],
            "finding": (
                f"{data['course_count']} courses map to this outcome but none "
                "strongly. Consider deepening coverage."
            ),
            "severity": "observation",
        }
        for po, data in coverage.items()
        if 1 < data["course_count"] <= 2
    ]

    return {
        "findings": major + single + weak,
        "major_count": len(major),
        "risk_count": len(single),
        "observation_count": len(weak),
        "outcomes_mapped": matrix["outcome_count"],
        "pos_covered": sum(1 for v in coverage.values() if v["course_count"] > 0),
        "pos_total": len(PROGRAMME_OUTCOMES),
    }
