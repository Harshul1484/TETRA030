"""The Syllabus Augmenter, the third mandated component.

The brief requires modifications adoptable "without requiring the professor
to redesign the entire course structure from scratch", so these tests check
that the prompt carries the constraints that make that possible, and that a
malformed model response degrades rather than raising.

A stub client is used throughout: no API calls, no cost.
"""

from app.contracts import GapReport, GapSeverity, SkillGap
from app.pipeline.augment import MAX_GAPS_CONSIDERED, SyllabusAugmenter

UNREACHABLE = 99


class StubClaude:
    def __init__(self, response):
        self.response = response
        self.prompts = []
        self.systems = []

    def complete_json(self, prompt, system="", fallback=None):
        self.prompts.append(prompt)
        self.systems.append(system)
        return fallback if self.response is _USE_FALLBACK else self.response


_USE_FALLBACK = object()


def _gap(skill, distance=1, coverage=0.0, requiring=40, severity=GapSeverity.HIGH):
    return SkillGap(
        canonical_skill=skill,
        severity=severity,
        market_demand=requiring / 100,
        curriculum_coverage=coverage,
        prerequisite_distance=distance,
        postings_requiring=requiring,
        postings_total=100,
        evidence=f"{requiring} of 100 postings require this",
    )


def _report(gaps=None, health=42.0):
    return GapReport(
        course_code="CS301",
        course_title="Database Systems",
        health_score=health,
        gaps=gaps if gaps is not None else [_gap("Vector Databases")],
    )


VALID_RESPONSE = {
    "added_outcomes": ["Design and query a vector database"],
    "case_studies": ["How Spotify built semantic search"],
    "toolsets": ["pgvector, in the indexing unit"],
    "project_prompts": ["Build a document search service"],
    "rationale": "These changes target the highest demand gaps.",
}


def test_valid_response_maps_to_proposal():
    augmenter = SyllabusAugmenter(StubClaude(VALID_RESPONSE), include_prerequisites=False)

    proposal = augmenter.propose(_report())

    assert proposal.course_code == "CS301"
    assert proposal.added_outcomes == ["Design and query a vector database"]
    assert proposal.rationale.startswith("These changes")


def test_prompt_forbids_a_full_redesign():
    """The constraint the brief is explicit about."""
    claude = StubClaude(VALID_RESPONSE)
    SyllabusAugmenter(claude, include_prerequisites=False).propose(_report())

    prompt = claude.prompts[0].lower()
    assert "without redesigning" in prompt
    assert "respect the existing structure" in prompt
    assert "never propose redesigning" in claude.systems[0].lower()


def test_prompt_carries_market_evidence():
    """Proposals must trace to evidence, not to the model's priors."""
    claude = StubClaude(VALID_RESPONSE)
    report = _report([_gap("Kubernetes", requiring=47)])

    SyllabusAugmenter(claude, include_prerequisites=False).propose(report)

    assert "47 of 100 postings" in claude.prompts[0]


def test_adjacent_skills_are_marked_as_directly_addable():
    claude = StubClaude(VALID_RESPONSE)
    report = _report([_gap("Vector Databases", distance=1)])

    SyllabusAugmenter(claude, include_prerequisites=False).propose(report)

    assert "can be added directly" in claude.prompts[0]


def test_distant_skills_report_their_cost():
    """Without this the model proposes advanced topics as though a course
    could adopt them directly, which is the unusable advice the brief warns
    against."""
    claude = StubClaude(VALID_RESPONSE)
    report = _report([_gap("Retrieval Augmented Generation", distance=3)])

    SyllabusAugmenter(claude, include_prerequisites=False).propose(report)

    assert "3 prerequisite steps" in claude.prompts[0]


def test_unreachable_skills_are_flagged():
    claude = StubClaude(VALID_RESPONSE)
    report = _report([_gap("Quantum Computing", distance=UNREACHABLE)])

    SyllabusAugmenter(claude, include_prerequisites=False).propose(report)

    assert "not reachable from current content" in claude.prompts[0]


def test_covered_skills_are_listed_so_proposals_do_not_duplicate_them():
    claude = StubClaude(VALID_RESPONSE)
    report = _report(
        [_gap("SQL", coverage=0.9), _gap("Vector Databases", coverage=0.0)]
    )

    SyllabusAugmenter(claude, include_prerequisites=False).propose(report)

    prompt = claude.prompts[0]
    assert "already covers" in prompt
    assert "- SQL" in prompt


def test_only_the_top_gaps_are_sent():
    """Beyond roughly ten gaps, proposals stop being a focused revision and
    become the rewrite the brief rules out."""
    claude = StubClaude(VALID_RESPONSE)
    many = [_gap(f"Skill {i}", requiring=50 - i) for i in range(25)]

    SyllabusAugmenter(claude, include_prerequisites=False).propose(_report(many))

    prompt = claude.prompts[0]
    assert "Skill 0" in prompt
    assert f"Skill {MAX_GAPS_CONSIDERED + 5}" not in prompt


def test_malformed_response_degrades_to_empty_proposal():
    """The gap report is still useful on its own, so a bad augmentation
    must not raise."""
    augmenter = SyllabusAugmenter(StubClaude("not an object"), include_prerequisites=False)

    proposal = augmenter.propose(_report())

    assert proposal.added_outcomes == []
    assert "unavailable" in proposal.rationale


def test_fallback_path_returns_a_usable_proposal():
    augmenter = SyllabusAugmenter(StubClaude(_USE_FALLBACK), include_prerequisites=False)

    proposal = augmenter.propose(_report())

    assert proposal.course_code == "CS301"
    assert "gap analysis above still" in proposal.rationale


def test_string_where_list_expected_is_coerced():
    """Models sometimes return a bare string for a list field."""
    response = dict(VALID_RESPONSE, toolsets="pgvector")
    augmenter = SyllabusAugmenter(StubClaude(response), include_prerequisites=False)

    assert augmenter.propose(_report()).toolsets == ["pgvector"]


def test_objects_in_a_list_are_flattened():
    """Another common shape: each item wrapped in an object."""
    response = dict(
        VALID_RESPONSE,
        toolsets=[{"tool": "pgvector", "unit": "Unit 5"}, {"tool": "Chroma"}],
    )
    augmenter = SyllabusAugmenter(StubClaude(response), include_prerequisites=False)

    toolsets = augmenter.propose(_report()).toolsets

    assert "pgvector" in toolsets[0]
    assert "Unit 5" in toolsets[0]
    assert toolsets[1] == "Chroma"


def test_missing_fields_default_to_empty():
    augmenter = SyllabusAugmenter(
        StubClaude({"rationale": "only this"}), include_prerequisites=False
    )

    proposal = augmenter.propose(_report())

    assert proposal.added_outcomes == []
    assert proposal.case_studies == []
    assert proposal.rationale == "only this"


def test_empty_gap_report_still_produces_a_proposal():
    augmenter = SyllabusAugmenter(StubClaude(VALID_RESPONSE), include_prerequisites=False)

    proposal = augmenter.propose(_report(gaps=[], health=100.0))

    assert proposal.course_code == "CS301"
