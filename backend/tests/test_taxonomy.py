"""The taxonomy is the highest-risk correctness item in the build.

If aliases do not collapse, "ML", "Machine Learning", and "machine-learning"
become three separate Skill nodes and every downstream gap number is
meaningless. Ambiguity must fail loudly at load time, not silently at query
time.
"""

import pytest

from app.taxonomy.loader import TaxonomyIndex


def _index(*skills):
    return TaxonomyIndex(list(skills))


ML = {
    "canonical_name": "Machine Learning",
    "category": "ai",
    "aliases": ["ML", "machine-learning"],
    "prerequisites": [],
}


def test_exact_canonical_name_resolves():
    assert _index(ML).resolve("Machine Learning") == "Machine Learning"


def test_aliases_collapse_to_one_canonical_skill():
    idx = _index(ML)
    assert idx.resolve("ML") == "Machine Learning"
    assert idx.resolve("machine-learning") == "Machine Learning"


def test_resolution_ignores_case_whitespace_and_separators():
    idx = _index(ML)
    assert idx.resolve("  MACHINE LEARNING  ") == "Machine Learning"
    assert idx.resolve("machine_learning") == "Machine Learning"


def test_unknown_surface_form_returns_none():
    assert _index(ML).resolve("Underwater Basket Weaving") is None


def test_duplicate_alias_across_skills_raises():
    """Two skills claiming the same alias is a data bug. It must fail at
    construction rather than resolving to whichever loaded last."""
    conflicting = {
        "canonical_name": "Meta Learning",
        "category": "ai",
        "aliases": ["ML"],
        "prerequisites": [],
    }
    with pytest.raises(ValueError, match="ML"):
        _index(ML, conflicting)


def test_alias_colliding_with_another_canonical_name_raises():
    shadowing = {
        "canonical_name": "Deep Learning",
        "category": "ai",
        "aliases": ["Machine Learning"],
        "prerequisites": [],
    }
    with pytest.raises(ValueError):
        _index(ML, shadowing)


def test_repeating_an_alias_within_one_skill_is_allowed():
    """Harmless redundancy in the data file should not break the load."""
    redundant = {
        "canonical_name": "Machine Learning",
        "category": "ai",
        "aliases": ["ML", "ML"],
        "prerequisites": [],
    }
    assert _index(redundant).resolve("ML") == "Machine Learning"


def test_canonical_names_lists_every_skill():
    other = {
        "canonical_name": "Python",
        "category": "language",
        "aliases": [],
        "prerequisites": [],
    }
    assert set(_index(ML, other).canonical_names()) == {
        "Machine Learning",
        "Python",
    }


def test_real_taxonomy_file_loads_without_ambiguity():
    """Guards the committed data file. A collision here fails the build
    rather than silently corrupting every gap number.

    The floor is 150 rather than the 300 estimated during planning. What
    matters is coverage of the skills that actually appear in tech job
    postings, not raw count: padding the file with rare skills would add
    alias-collision risk while contributing nothing to gap detection.
    """
    idx = TaxonomyIndex.from_disk()
    assert len(idx.canonical_names()) >= 150


def test_real_taxonomy_resolves_known_aliases():
    idx = TaxonomyIndex.from_disk()
    assert idx.resolve("RAG") == "Retrieval Augmented Generation"
    assert idx.resolve("k8s") == "Kubernetes"
    assert idx.resolve("js") == "JavaScript"


def test_real_taxonomy_prerequisites_reference_existing_skills():
    """A prerequisite naming a skill that does not exist would create a
    dangling edge in Neo4j and break multi-hop gap reasoning."""
    idx = TaxonomyIndex.from_disk()
    known = set(idx.canonical_names())
    dangling = [
        (skill["canonical_name"], prereq)
        for skill in idx.skills
        for prereq in skill.get("prerequisites", [])
        if prereq not in known
    ]
    assert dangling == []
