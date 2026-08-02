"""API contract tests.

Graph-dependent endpoints are skipped when Neo4j is unreachable so the unit
suite still runs anywhere. What is always checked is the shape of the
contract, since the frontend generates its types from this schema.
"""

import io

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _neo4j_available() -> bool:
    try:
        from app.db.neo4j_client import session

        with session() as s:
            s.run("RETURN 1").single()
        return True
    except Exception:
        return False


NEEDS_GRAPH = pytest.mark.skipif(
    not _neo4j_available(), reason="Neo4j not reachable"
)


def test_health_always_responds():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] in {"ok", "degraded"}


def test_openapi_schema_is_generated():
    """The frontend generates its TypeScript types from this schema, so it
    has to exist and carry the routes."""
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]

    assert "/api/courses" in paths
    assert "/api/courses/{course_code}/gaps" in paths
    assert "/api/augment/{course_code}" in paths
    assert "/api/graph" in paths
    assert "/api/market/trends" in paths


def test_gap_report_schema_matches_the_contract():
    schema = client.get("/openapi.json").json()
    gap_report = schema["components"]["schemas"]["GapReport"]

    assert set(gap_report["required"]) >= {
        "course_code",
        "course_title",
        "health_score",
        "gaps",
    }


def test_upload_rejects_unsupported_file_types():
    response = client.post(
        "/api/syllabi",
        files={"file": ("virus.exe", io.BytesIO(b"binary"), "application/exe")},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_upload_rejects_a_file_with_no_usable_text():
    response = client.post(
        "/api/syllabi",
        files={"file": ("thin.txt", io.BytesIO(b"too short"), "text/plain")},
    )
    assert response.status_code == 422
    assert "text layer" in response.json()["detail"].lower()


@NEEDS_GRAPH
def test_courses_endpoint_returns_health_scores():
    response = client.get("/api/courses")
    assert response.status_code == 200

    courses = response.json()
    if not courses:
        pytest.skip("database not seeded")

    assert all("health_score" in course for course in courses)
    assert all("gap_count" in course for course in courses)


@NEEDS_GRAPH
def test_unknown_course_returns_404():
    response = client.get("/api/courses/NOT-A-REAL-COURSE/gaps")
    assert response.status_code == 404


@NEEDS_GRAPH
def test_gap_report_carries_evidence_for_every_gap():
    """A gap without evidence is an assertion. Every one must cite numbers."""
    courses = client.get("/api/courses").json()
    if not courses:
        pytest.skip("database not seeded")

    report = client.get(f"/api/courses/{courses[0]['code']}/gaps").json()
    if not report["gaps"]:
        pytest.skip("no gaps computed")

    for gap in report["gaps"]:
        assert gap["evidence"], f"{gap['canonical_skill']} has no evidence"
        assert "postings require this" in gap["evidence"]
        assert gap["postings_total"] > 0


@NEEDS_GRAPH
def test_health_score_is_bounded():
    courses = client.get("/api/courses").json()
    if not courses:
        pytest.skip("database not seeded")

    report = client.get(f"/api/courses/{courses[0]['code']}/gaps").json()
    assert 0.0 <= report["health_score"] <= 100.0


@NEEDS_GRAPH
def test_graph_endpoint_returns_nodes_and_summary():
    data = client.get("/api/graph?limit=25").json()

    assert "nodes" in data
    assert "edges" in data
    assert set(data["summary"]) == {"skills", "taught", "gaps", "edges"}


@NEEDS_GRAPH
def test_trends_endpoint_shape_survives_the_forecaster_being_cut():
    """Slope is null until the forecaster ships. The contract must not
    change when it lands."""
    trends = client.get("/api/market/trends?limit=5").json()
    if not trends:
        pytest.skip("database not seeded")

    for trend in trends:
        assert "canonical_skill" in trend
        assert "history" in trend
        assert "slope" in trend


@NEEDS_GRAPH
def test_prerequisite_chain_endpoint():
    data = client.get("/api/skills/Retrieval Augmented Generation/prerequisites").json()

    assert data["skill"] == "Retrieval Augmented Generation"
    assert data["total_prerequisites"] >= 0
    if data["by_hop"]:
        assert data["by_hop"][0]["hops"] == 1


@NEEDS_GRAPH
def test_market_summary_states_the_evidence_base():
    summary = client.get("/api/market/summary").json()
    assert "postings" in summary
    assert "skills_demanded" in summary


@NEEDS_GRAPH
def test_accreditation_matrix_rejects_an_unknown_course():
    """A compliance document describing a course that does not exist is
    worse than an error, because somebody could file it."""
    response = client.get("/api/accreditation/matrix?course=NOT-A-REAL-COURSE")
    assert response.status_code == 404


@NEEDS_GRAPH
def test_accreditation_findings_state_their_own_limits():
    """The tool derives mapping, not attainment. That distinction has to
    survive into the payload, not just the docstring."""
    data = client.get("/api/accreditation/findings").json()
    assert data["pos_total"] == 12
    assert 0 <= data["pos_covered"] <= 12


@NEEDS_GRAPH
def test_programme_endpoints_bound_their_limits():
    for query in ("limit=-5", "limit=0", "limit=99999"):
        assert client.get(f"/api/programme?{query}").status_code == 422
