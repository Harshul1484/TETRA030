"""Neo4j schema and taxonomy loading.

Both operations are idempotent so they can run on every boot without
duplicating nodes or edges.
"""

from app.db.neo4j_client import session
from app.taxonomy.loader import TaxonomyIndex

CONSTRAINTS = [
    "CREATE CONSTRAINT skill_name IF NOT EXISTS "
    "FOR (s:Skill) REQUIRE s.canonical_name IS UNIQUE",
    "CREATE CONSTRAINT course_code IF NOT EXISTS "
    "FOR (c:Course) REQUIRE c.code IS UNIQUE",
    "CREATE CONSTRAINT job_id IF NOT EXISTS "
    "FOR (j:JobPosting) REQUIRE j.doc_id IS UNIQUE",
    "CREATE CONSTRAINT outcome_id IF NOT EXISTS "
    "FOR (o:Outcome) REQUIRE o.outcome_id IS UNIQUE",
]


def apply_constraints() -> None:
    with session() as s:
        for statement in CONSTRAINTS:
            s.run(statement)


def load_taxonomy(index: TaxonomyIndex) -> dict[str, int]:
    """Write canonical skills and their prerequisite edges.

    Returns counts so callers can verify the load rather than assume it.
    """
    skills = [
        {
            "name": skill["canonical_name"],
            "category": skill.get("category", "general"),
            "aliases": skill.get("aliases", []),
        }
        for skill in index.skills
    ]
    prerequisites = [
        {"prereq": prereq, "name": skill["canonical_name"]}
        for skill in index.skills
        for prereq in skill.get("prerequisites", [])
    ]

    with session() as s:
        s.run(
            "UNWIND $rows AS row "
            "MERGE (sk:Skill {canonical_name: row.name}) "
            "SET sk.category = row.category, sk.aliases = row.aliases",
            rows=skills,
        )
        s.run(
            "UNWIND $rows AS row "
            "MATCH (a:Skill {canonical_name: row.prereq}) "
            "MATCH (b:Skill {canonical_name: row.name}) "
            "MERGE (a)-[:PREREQUISITE_OF]->(b)",
            rows=prerequisites,
        )

    return {"skills": len(skills), "prerequisite_edges": len(prerequisites)}


def graph_counts() -> dict[str, int]:
    """Node and edge counts, for verifying a load actually landed."""
    with session() as s:
        record = s.run(
            "MATCH (s:Skill) WITH count(s) AS skills "
            "MATCH ()-[r:PREREQUISITE_OF]->() "
            "RETURN skills, count(r) AS prerequisite_edges"
        ).single()
        return dict(record) if record else {"skills": 0, "prerequisite_edges": 0}
