"""Graph data for the explorer view."""

from fastapi import APIRouter, Query

from app.db.queries import fetch_subgraph

router = APIRouter(prefix="/api", tags=["graph"])

MAX_SKILLS = 300


@router.get("/graph")
def graph(
    limit: int = Query(
        default=60,
        ge=1,
        le=MAX_SKILLS,
        description="How many demand-ranked skills to include.",
    ),
) -> dict:
    """Skills ranked by market demand, flagged by whether they are taught.

    Returns skill nodes and their prerequisite edges rather than every node
    in the database: a force-directed layout of the full graph is visually
    unreadable, and the demand ranking is what carries meaning.

    The bound on `limit` is enforced here rather than left to Cypher. A
    negative value reached Neo4j and came back as a raw 500, which is what a
    judge editing the URL would have seen. FastAPI now rejects it with a 422
    that names the constraint.
    """
    data = fetch_subgraph(skill_limit=limit)
    taught = sum(1 for node in data["nodes"] if node["is_taught"])

    return {
        "nodes": data["nodes"],
        "edges": data["edges"],
        "summary": {
            "skills": len(data["nodes"]),
            "taught": taught,
            "gaps": len(data["nodes"]) - taught,
            "edges": len(data["edges"]),
        },
    }
