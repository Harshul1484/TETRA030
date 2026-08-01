"""The extractor is the bridge between free text and the taxonomy.

Its one hard rule is that it cannot introduce a skill the taxonomy does not
know. Constraining the model in the prompt reduces invention but does not
guarantee it, so these tests exercise what happens when the model
misbehaves anyway.

A stub Claude client is used throughout: no API calls, no cost, and the
malformed responses can be reproduced exactly.
"""

from app.contracts import Document, DocumentKind
from app.pipeline.extract import SkillExtractor
from app.taxonomy.loader import TaxonomyIndex


class StubClaude:
    def __init__(self, response):
        self.response = response
        self.prompts = []

    def complete_json(self, prompt, system="", fallback=None):
        self.prompts.append(prompt)
        return self.response


class StubIndex:
    def __init__(self, candidates=None, available=True):
        self.available = available
        self.candidates = candidates or []

    def query(self, text, n=3):
        return [(skill, 0.8) for skill in self.candidates[:n]]


def _document(text="Course covers Python and Kubernetes.", kind=DocumentKind.SYLLABUS):
    return Document(
        doc_id="d1", kind=kind, title="Test", raw_text=text, source="test"
    )


def _taxonomy():
    return TaxonomyIndex.from_disk()


def test_extracts_valid_skills():
    claude = StubClaude(
        [
            {"skill": "Python", "evidence": "students learn Python", "importance": 0.9},
            {"skill": "Kubernetes", "evidence": "deploy with k8s", "importance": 0.6},
        ]
    )
    extractor = SkillExtractor(_taxonomy(), claude)

    mentions = extractor.extract(_document())

    assert [m.surface_form for m in mentions] == ["Python", "Kubernetes"]
    assert mentions[0].importance == 0.9


def test_invented_skills_are_rejected():
    """The core guarantee. A model that ignores the allowed list must not
    be able to put a skill in the graph that the taxonomy does not know."""
    claude = StubClaude(
        [
            {"skill": "Python", "evidence": "uses Python", "importance": 0.8},
            {"skill": "Quantum Blockchain Synergy", "evidence": "made up", "importance": 0.9},
        ]
    )
    extractor = SkillExtractor(_taxonomy(), claude)

    mentions = extractor.extract(_document())

    assert [m.surface_form for m in mentions] == ["Python"]


def test_aliases_are_normalized_to_canonical_names():
    """If the model answers with an alias, it still resolves to one node."""
    claude = StubClaude(
        [{"skill": "k8s", "evidence": "kubernetes clusters", "importance": 0.7}]
    )
    extractor = SkillExtractor(_taxonomy(), claude)

    mentions = extractor.extract(_document())

    assert [m.surface_form for m in mentions] == ["Kubernetes"]


def test_duplicate_skills_are_collapsed():
    """One document mentioning a skill twice is still one edge in the graph."""
    claude = StubClaude(
        [
            {"skill": "Python", "evidence": "Python basics", "importance": 0.8},
            {"skill": "python3", "evidence": "Python advanced", "importance": 0.6},
        ]
    )
    extractor = SkillExtractor(_taxonomy(), claude)

    assert len(extractor.extract(_document())) == 1


def test_empty_response_yields_no_mentions():
    extractor = SkillExtractor(_taxonomy(), StubClaude([]))
    assert extractor.extract(_document()) == []


def test_non_list_response_is_handled():
    """The fallback path returns whatever the caller supplied, and a
    malformed model response must not crash the pipeline."""
    extractor = SkillExtractor(_taxonomy(), StubClaude({"error": "rate limited"}))
    assert extractor.extract(_document()) == []


def test_malformed_elements_are_skipped():
    claude = StubClaude(
        [
            "not a dict",
            {"no_skill_key": True},
            {"skill": "Python", "evidence": "ok", "importance": 0.5},
            None,
        ]
    )
    extractor = SkillExtractor(_taxonomy(), claude)

    mentions = extractor.extract(_document())

    assert [m.surface_form for m in mentions] == ["Python"]


def test_importance_as_string_is_coerced():
    """Models sometimes return numbers as strings."""
    claude = StubClaude(
        [{"skill": "Python", "evidence": "ok", "importance": "0.75"}]
    )
    extractor = SkillExtractor(_taxonomy(), claude)

    assert extractor.extract(_document())[0].importance == 0.75


def test_out_of_range_importance_is_clamped():
    claude = StubClaude(
        [
            {"skill": "Python", "evidence": "a", "importance": 5.0},
            {"skill": "Java", "evidence": "b", "importance": -3.0},
        ]
    )
    extractor = SkillExtractor(_taxonomy(), claude)

    mentions = extractor.extract(_document())

    assert all(0.0 <= m.importance <= 1.0 for m in mentions)


def test_missing_importance_defaults_to_midpoint():
    claude = StubClaude([{"skill": "Python", "evidence": "ok"}])
    extractor = SkillExtractor(_taxonomy(), claude)

    assert extractor.extract(_document())[0].importance == 0.5


def test_vector_index_shortlists_candidates():
    """The cost optimisation: the prompt should carry the shortlist, not
    all 438 canonical names."""
    index = StubIndex(candidates=["Python", "Kubernetes", "Docker"])
    claude = StubClaude([])
    extractor = SkillExtractor(_taxonomy(), claude, index)

    extractor.extract(_document())

    prompt = claude.prompts[0]
    assert "- Python" in prompt
    assert "- Kubernetes" in prompt
    assert "- Quantum Computing" not in prompt, "full taxonomy leaked into prompt"


def test_falls_back_to_full_taxonomy_without_index():
    """Extraction must still work when Chroma is unavailable."""
    claude = StubClaude([])
    extractor = SkillExtractor(_taxonomy(), claude, StubIndex(available=False))

    extractor.extract(_document())

    assert "- Python" in claude.prompts[0]
    assert len(claude.prompts[0]) > 5000, "expected the full taxonomy in the prompt"


def test_long_documents_are_truncated():
    """Job descriptions repeat boilerplate after the requirements section,
    so the prompt must not carry the whole thing."""
    claude = StubClaude([])
    extractor = SkillExtractor(_taxonomy(), claude, StubIndex(candidates=["Python"]))

    extractor.extract(_document(text="word " * 20000))

    assert len(claude.prompts[0]) < 20000


def test_context_is_truncated_to_contract_limit():
    claude = StubClaude(
        [{"skill": "Python", "evidence": "x" * 2000, "importance": 0.5}]
    )
    extractor = SkillExtractor(_taxonomy(), claude)

    assert len(extractor.extract(_document())[0].context) <= 500
