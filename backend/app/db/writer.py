"""Write extracted skills into the graph.

Courses and their outcomes on one side, job postings on the other, joined
through the shared Skill nodes the taxonomy already created. Every write is
batched with UNWIND and idempotent, so re-running an ingest updates rather
than duplicates.
"""

from app.contracts import Document, ScoredPair, SkillMention
from app.db.neo4j_client import session


def write_course(code: str, title: str, institution: str = "", department: str = "") -> None:
    with session() as s:
        s.run(
            "MERGE (c:Course {code: $code}) "
            "SET c.title = $title, "
            "    c.institution = $institution, "
            "    c.department = $department",
            code=code,
            title=title,
            institution=institution,
            department=department,
        )


def write_course_skills(
    course_code: str,
    mentions: list[SkillMention],
    pairs: list[ScoredPair],
) -> int:
    """Attach taught skills to a course through Outcome nodes.

    Confidence combines match certainty with how central the skill was to
    the document: a skill mentioned in passing should not count as fully
    taught just because the string matched exactly.
    """
    by_mention = {m.mention_id: m for m in mentions}
    rows = []
    for pair in pairs:
        mention = by_mention.get(pair.mention_id)
        if mention is None:
            continue
        rows.append(
            {
                "outcome_id": pair.mention_id,
                "text": mention.context,
                "skill": pair.canonical_skill,
                "confidence": round(pair.similarity * mention.importance, 4),
            }
        )

    if not rows:
        return 0

    with session() as s:
        s.run(
            "MATCH (c:Course {code: $code}) "
            "UNWIND $rows AS row "
            "MERGE (o:Outcome {outcome_id: row.outcome_id}) "
            "SET o.text = row.text "
            "MERGE (c)-[:HAS_OUTCOME]->(o) "
            "WITH o, row "
            "MATCH (sk:Skill {canonical_name: row.skill}) "
            "MERGE (o)-[t:TEACHES]->(sk) "
            "SET t.confidence = row.confidence",
            code=course_code,
            rows=rows,
        )
    return len(rows)


def write_job_skills(
    document: Document,
    mentions: list[SkillMention],
    pairs: list[ScoredPair],
    metadata: dict | None = None,
) -> int:
    """Create the JobPosting node and its skill demands."""
    meta = metadata or {}
    by_mention = {m.mention_id: m for m in mentions}

    rows = []
    for pair in pairs:
        mention = by_mention.get(pair.mention_id)
        if mention is None:
            continue
        rows.append(
            {
                "skill": pair.canonical_skill,
                "importance": round(mention.importance, 4),
                "evidence": mention.context,
            }
        )

    with session() as s:
        s.run(
            "MERGE (j:JobPosting {doc_id: $doc_id}) "
            "SET j.title = $title, "
            "    j.source = $source, "
            "    j.source_url = $source_url, "
            "    j.posted_date = $posted_date, "
            "    j.seniority = $seniority",
            doc_id=document.doc_id,
            title=document.title,
            source=document.source,
            source_url=meta.get("source_url", ""),
            posted_date=str(document.posted_date) if document.posted_date else None,
            seniority=meta.get("seniority", "mid"),
        )

        company = meta.get("company", "")
        if company:
            s.run(
                "MATCH (j:JobPosting {doc_id: $doc_id}) "
                "MERGE (e:Employer {name: $company}) "
                "MERGE (j)-[:POSTED_BY]->(e)",
                doc_id=document.doc_id,
                company=company,
            )

        if rows:
            s.run(
                "MATCH (j:JobPosting {doc_id: $doc_id}) "
                "UNWIND $rows AS row "
                "MATCH (sk:Skill {canonical_name: row.skill}) "
                "MERGE (j)-[r:REQUIRES]->(sk) "
                "SET r.importance = row.importance, r.evidence = row.evidence",
                doc_id=document.doc_id,
                rows=rows,
            )

    return len(rows)


def clear_ingested_data() -> dict[str, int]:
    """Remove courses and postings, leaving the taxonomy intact.

    Useful when re-seeding: the Skill nodes and their prerequisite edges are
    expensive to rebuild and never change between ingests.
    """
    with session() as s:
        record = s.run(
            "MATCH (n) WHERE n:Course OR n:Outcome OR n:JobPosting OR n:Employer "
            "WITH count(n) AS removed "
            "MATCH (m) WHERE m:Course OR m:Outcome OR m:JobPosting OR m:Employer "
            "DETACH DELETE m "
            "RETURN removed"
        ).single()
    return {"removed": record["removed"] if record else 0}
