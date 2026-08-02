import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import courses, graph, market, programme, syllabi
from app.config import settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Vedha",
    version="0.1.0",
    description=(
        "Audits university syllabi against live job market data. Maps course "
        "outcomes and job postings onto a shared skill ontology in Neo4j, "
        "quantifies the gap with evidence, and generates adoptable syllabus "
        "modifications."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(courses.router)
app.include_router(graph.router)
app.include_router(market.router)
app.include_router(programme.router)
app.include_router(syllabi.router)


@app.get("/api/health")
def health() -> dict:
    """Liveness plus a quick view of whether the graph is populated."""
    status: dict = {"status": "ok"}

    try:
        from app.db.schema import graph_counts

        status["graph"] = graph_counts()
    except Exception as exc:
        status["status"] = "degraded"
        status["graph_error"] = str(exc)[:200]

    return status
