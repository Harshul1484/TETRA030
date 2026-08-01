"""Graph data for the explorer view."""

from fastapi import APIRouter

from app.db.queries import fetch_subgraph

router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/graph")
def graph(limit: int = 60) -> dict:
    """Skills ranked by market demand, flagged by whether they are taught.

    Returns skill nodes and their prerequisite edges rather than every node
    in the database: a force-directed layout of the full graph is visually
    unreadable, and the demand ranking is what carries meaning.
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
