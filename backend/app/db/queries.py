"""Graph queries behind the gap report.

GAP_QUERY is the reason this system uses a graph database. It asks, in one
traversal: which skills does the market demand, that this course does not
teach, and how far is each from what the course already covers? The last
clause is a variable-length path search that a relational schema answers
only with a recursive CTE that degrades with every hop.
"""

from app.db.neo4j_client import session

GAP_QUERY = """
// What the course already teaches.
MATCH (c:Course {code: $course_code})
OPTIONAL MATCH (c)-[:HAS_OUTCOME]->(:Outcome)-[t:TEACHES]->(taught:Skill)
WITH c,
     collect(DISTINCT taught) AS taught_skills,
     collect(DISTINCT {name: taught.canonical_name, confidence: t.confidence}) AS coverage

// Total corpus size, for the evidence denominator.
MATCH (total:JobPosting)
WITH c, taught_skills, coverage, count(DISTINCT total) AS postings_total

// What the market demands.
MATCH (j:JobPosting)-[r:REQUIRES]->(demanded:Skill)
WITH c, taught_skills, coverage, postings_total, demanded,
     count(DISTINCT j) AS postings_requiring,
     avg(r.importance) AS avg_importance,
     collect(r.evidence)[0] AS sample_evidence

// How far is this skill from what the course already covers? A skill one
// hop from existing content is a cheap addition; one that needs three
// missing prerequisites is a different conversation.
//
// `known <> demanded` is required, not defensive. When the course already
// teaches the demanded skill, start and end become the same node and
// shortestPath raises rather than returning zero. That case is common: it
// is every skill the curriculum already covers.
OPTIONAL MATCH path = shortestPath(
    (known:Skill)-[:PREREQUISITE_OF|RELATED_TO*1..3]-(demanded)
)
WHERE known IN taught_skills AND known <> demanded

WITH demanded, postings_requiring, postings_total, avg_importance,
     sample_evidence, coverage,
     CASE WHEN path IS NULL THEN 99 ELSE length(path) END AS distance

RETURN demanded.canonical_name AS skill,
       demanded.category AS category,
       postings_requiring,
       postings_total,
       coalesce(avg_importance, 0.5) AS market_importance,
       min(distance) AS prerequisite_distance,
       sample_evidence,
       [entry IN coverage WHERE entry.name = demanded.canonical_name |
        entry.confidence] AS coverage_confidence
ORDER BY postings_requiring DESC
LIMIT $limit
"""

COURSES_QUERY = """
MATCH (c:Course)
OPTIONAL MATCH (c)-[:HAS_OUTCOME]->(o:Outcome)-[:TEACHES]->(s:Skill)
RETURN c.code AS code,
       c.title AS title,
       c.department AS department,
       count(DISTINCT s) AS skills_taught
ORDER BY c.code
"""

SUBGRAPH_QUERY = """
MATCH (c:Course)-[:HAS_OUTCOME]->(:Outcome)-[:TEACHES]->(taught:Skill)
WITH collect(DISTINCT taught.canonical_name) AS taught_names

MATCH (j:JobPosting)-[r:REQUIRES]->(s:Skill)
WITH taught_names, s, count(DISTINCT j) AS demand
ORDER BY demand DESC
LIMIT $skill_limit

RETURN s.canonical_name AS skill,
       s.category AS category,
       demand,
       s.canonical_name IN taught_names AS is_taught
"""

SUBGRAPH_EDGES_QUERY = """
MATCH (a:Skill)-[:PREREQUISITE_OF]->(b:Skill)
WHERE a.canonical_name IN $names AND b.canonical_name IN $names
RETURN a.canonical_name AS source, b.canonical_name AS target
"""

TRENDS_QUERY = """
MATCH (j:JobPosting)-[:REQUIRES]->(s:Skill)
WHERE j.posted_date IS NOT NULL
RETURN s.canonical_name AS skill,
       substring(j.posted_date, 0, 7) AS period,
       count(*) AS frequency
ORDER BY skill, period
"""

PREREQUISITE_CHAIN_QUERY = """
MATCH path = (p:Skill)-[:PREREQUISITE_OF*1..4]->(t:Skill {canonical_name: $skill})
RETURN DISTINCT p.canonical_name AS prerequisite,
       min(length(path)) AS hops
ORDER BY hops, prerequisite
"""


def fetch_course_gaps(course_code: str, limit: int = 40) -> list[dict]:
    with session() as s:
        return [
            dict(record)
            for record in s.run(GAP_QUERY, course_code=course_code, limit=limit)
        ]


def fetch_courses() -> list[dict]:
    with session() as s:
        return [dict(record) for record in s.run(COURSES_QUERY)]


def fetch_prerequisite_chain(skill: str) -> list[dict]:
    """The chain that turns 'you are missing X' into 'here is what X costs'."""
    with session() as s:
        return [
            dict(record)
            for record in s.run(PREREQUISITE_CHAIN_QUERY, skill=skill)
        ]


def fetch_subgraph(skill_limit: int = 60) -> dict:
    """Nodes and edges for the graph explorer, ranked by market demand."""
    with session() as s:
        nodes = [dict(r) for r in s.run(SUBGRAPH_QUERY, skill_limit=skill_limit)]
        names = [n["skill"] for n in nodes]
        edges = [
            dict(r) for r in s.run(SUBGRAPH_EDGES_QUERY, names=names)
        ]
    return {"nodes": nodes, "edges": edges}


def fetch_trend_rows() -> list[dict]:
    with session() as s:
        return [dict(record) for record in s.run(TRENDS_QUERY)]
