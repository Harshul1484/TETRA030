"""Matching is the designed swap seam, so its contract is what matters:
whatever the strategy, the output is a list of ScoredPair and nothing else.

These tests use a stub index rather than a live Chroma instance so they run
anywhere. Real semantic retrieval is covered by test_embed_integration.
"""

from app.contracts import ScoredPair, SkillMention
from app.pipeline.match import MIN_SIMILARITY, ExactMatcher, VectorMatcher
from app.taxonomy.loader import TaxonomyIndex


class StubIndex:
    """Stands in for SkillIndex with scripted responses."""

    def __init__(self, responses=None, available=True):
        self.responses = responses or {}
        self.available = available
        self.queries = []

    def query(self, text, n=3):
        self.queries.append(text)
        return self.responses.get(text, [])


def _mention(surface_form, mention_id="m1"):
    return SkillMention(
        mention_id=mention_id,
        doc_id="d1",
        surface_form=surface_form,
        context="context",
        importance=0.8,
    )


def _taxonomy():
    return TaxonomyIndex.from_disk()


def test_exact_alias_resolves_without_touching_the_index():
    """An alias hit is certain, so it must never be overridden by a
    probabilistic vector result."""
    index = StubIndex()
    matcher = VectorMatcher(index, _taxonomy())

    pair = matcher.match_one(_mention("k8s"))

    assert pair.canonical_skill == "Kubernetes"
    assert pair.similarity == 1.0
    assert index.queries == [], "exact path should not query the vector index"


def test_paraphrase_falls_through_to_vector_search():
    """A phrase sharing no keywords with any skill name must still resolve.
    0.776 is the real measured similarity for this phrase against the
    438-skill taxonomy."""
    index = StubIndex(
        {"orchestrating containers at scale": [("Kubernetes", 0.776)]}
    )
    matcher = VectorMatcher(index, _taxonomy())

    pair = matcher.match_one(_mention("orchestrating containers at scale"))

    assert pair.canonical_skill == "Kubernetes"
    assert pair.similarity == 0.776


def test_weak_vector_hits_are_discarded():
    """A low-similarity hit is more likely noise than a real match, and a
    wrong skill silently corrupts the gap report."""
    index = StubIndex({"quarterly sales targets": [("Kubernetes", 0.05)]})
    matcher = VectorMatcher(index, _taxonomy())

    assert matcher.match_one(_mention("quarterly sales targets")) is None


def test_similarity_exactly_at_threshold_is_accepted():
    index = StubIndex({"borderline phrase": [("Python", MIN_SIMILARITY)]})
    matcher = VectorMatcher(index, _taxonomy())

    assert matcher.match_one(_mention("borderline phrase")) is not None


def test_empty_index_results_yield_no_pair():
    matcher = VectorMatcher(StubIndex(), _taxonomy())
    assert matcher.match_one(_mention("no such thing anywhere")) is None


def test_match_returns_only_scored_pairs():
    """The seam contract: downstream code sees ScoredPair and nothing else."""
    index = StubIndex({"container orchestration platform": [("Kubernetes", 0.71)]})
    matcher = VectorMatcher(index, _taxonomy())

    pairs = matcher.match(
        [
            _mention("Python", "m1"),
            _mention("container orchestration platform", "m2"),
            _mention("entirely unrelated nonsense", "m3"),
        ]
    )

    assert all(isinstance(p, ScoredPair) for p in pairs)
    assert [p.mention_id for p in pairs] == ["m1", "m2"]


def test_unmatched_mentions_are_dropped_not_faked():
    """Inventing a canonical skill for an unmatched mention would put a
    skill in the graph that no document actually mentions."""
    matcher = VectorMatcher(StubIndex(), _taxonomy())
    assert matcher.match([_mention("gibberish xyzzy")]) == []


def test_exact_matcher_satisfies_the_same_interface():
    """The documented fallback must be swappable at the call site."""
    matcher = ExactMatcher(_taxonomy())

    pairs = matcher.match([_mention("k8s", "m1"), _mention("paraphrase", "m2")])

    assert len(pairs) == 1
    assert pairs[0].canonical_skill == "Kubernetes"
    assert isinstance(pairs[0], ScoredPair)


def test_threshold_rejects_measured_false_positives():
    """Regression guard on the calibrated floor.

    These similarity values are real measurements against the 438-skill
    taxonomy: ordinary syllabus prose scored this highly against unrelated
    skills. Before calibration the floor was 0.35 and every one of these
    would have entered the gap report as a phantom skill with fabricated
    evidence.
    """
    measured_false_positives = [
        ("the cafeteria serves lunch at noon", "Service Mesh", 0.565),
        ("office hours are held on tuesday afternoons", "Cron Scheduling", 0.619),
        ("the quarterly marketing budget was approved", "SLOs and Error Budgets", 0.600),
        ("this module carries four credit hours", "Payment Integration", 0.594),
    ]

    for phrase, wrong_skill, similarity in measured_false_positives:
        index = StubIndex({phrase: [(wrong_skill, similarity)]})
        matcher = VectorMatcher(index, _taxonomy())
        assert matcher.match_one(_mention(phrase)) is None, (
            f"{phrase!r} matched {wrong_skill} at {similarity}"
        )


def test_threshold_accepts_measured_true_positives():
    """The counterpart guard: a floor set too high would silently discard
    every paraphrase and reduce the system to keyword matching."""
    measured_true_positives = [
        ("orchestrating containers", "Kubernetes", 0.776),
        ("training neural networks", "Deep Learning", 0.745),
        ("deploying models to production", "Model Deployment", 0.744),
        ("analysing large datasets", "Big Data", 0.643),
    ]

    for phrase, right_skill, similarity in measured_true_positives:
        index = StubIndex({phrase: [(right_skill, similarity)]})
        matcher = VectorMatcher(index, _taxonomy())
        pair = matcher.match_one(_mention(phrase))
        assert pair is not None, f"{phrase!r} was rejected at {similarity}"
        assert pair.canonical_skill == right_skill


def test_vector_matcher_degrades_to_exact_when_index_unavailable():
    """If Chroma cannot start, exact resolution must still work rather than
    the pipeline failing outright."""
    matcher = VectorMatcher(StubIndex(available=False), _taxonomy())

    pairs = matcher.match([_mention("machine-learning", "m1")])

    assert len(pairs) == 1
    assert pairs[0].canonical_skill == "Machine Learning"
