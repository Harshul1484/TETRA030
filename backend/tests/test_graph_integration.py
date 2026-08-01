"""Integration tests against a live Neo4j.

Skipped automatically when Neo4j is unreachable so the unit suite still
runs anywhere. Run the stack with `docker compose up -d neo4j` to exercise
these.
"""

import pytest

from app.db.neo4j_client import session
from app.db.schema import apply_constraints, graph_counts, load_taxonomy
from app.taxonomy.loader import TaxonomyIndex


def _neo4j_available() -> bool:
    try:
        with session() as s:
            s.run("RETURN 1").single()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _neo4j_available(), reason="Neo4j not reachable"
)


@pytest.fixture(scope="module")
def loaded_graph():
    apply_constraints()
    taxonomy = TaxonomyIndex.from_disk()
    load_taxonomy(taxonomy)
    return taxonomy


def test_every_taxonomy_skill_reaches_the_graph(loaded_graph):
    counts = graph_counts()
    assert counts["skills"] == len(loaded_graph.canonical_names())


def test_loading_twice_does_not_duplicate_nodes(loaded_graph):
    """The seed runs on every boot, so the load must be idempotent."""
    before = graph_counts()
    load_taxonomy(loaded_graph)
    assert graph_counts() == before


def test_prerequisite_edges_are_traversable(loaded_graph):
    """Multi-hop traversal is the reason this is a graph database rather
    than a relational one, so it needs a test."""
    with session() as s:
        record = s.run(
            "MATCH path = (p:Skill)-[:PREREQUISITE_OF*1..3]->"
            "(t:Skill {canonical_name: $name}) "
            "RETURN count(DISTINCT p) AS reachable",
            name="Retrieval Augmented Generation",
        ).single()
    assert record["reachable"] >= 4


def test_uniqueness_constraint_rejects_duplicate_skill(loaded_graph):
    from neo4j.exceptions import ConstraintError

    with pytest.raises(ConstraintError):
        with session() as s:
            s.run("CREATE (:Skill {canonical_name: 'Python'})")


def test_skill_nodes_carry_their_aliases(loaded_graph):
    with session() as s:
        record = s.run(
            "MATCH (s:Skill {canonical_name: 'Kubernetes'}) "
            "RETURN s.aliases AS aliases, s.category AS category"
        ).single()
    assert "k8s" in record["aliases"]
    assert record["category"] == "cloud"
