"""Resolve skill mentions to canonical skills.

This module owns the designed swap seam. It emits nothing but `ScoredPair`,
so the entire matching strategy can be replaced without touching anything
downstream. Two strategies ship here: exact taxonomy resolution, which is
free and certain, and vector similarity, which handles paraphrases the
taxonomy cannot enumerate.
"""

import logging

from app.contracts import ScoredPair, SkillMention
from app.pipeline.embed import SkillIndex
from app.taxonomy.loader import TaxonomyIndex

logger = logging.getLogger(__name__)

# Below this similarity a vector hit is more likely noise than a real match.
# Tuned against the taxonomy: unrelated phrases typically score under 0.30.
MIN_SIMILARITY = 0.35


class VectorMatcher:
    """Exact taxonomy resolution first, vector similarity as a fallback.

    The exact path matters for more than speed. An alias hit is certain,
    while a vector hit is probabilistic, so resolving "k8s" through the
    taxonomy avoids ever letting embedding noise override a known-correct
    answer.
    """

    def __init__(self, index: SkillIndex, taxonomy: TaxonomyIndex):
        self.index = index
        self.taxonomy = taxonomy

    def match(self, mentions: list[SkillMention]) -> list[ScoredPair]:
        pairs: list[ScoredPair] = []
        for mention in mentions:
            pair = self.match_one(mention)
            if pair is not None:
                pairs.append(pair)
        return pairs

    def match_one(self, mention: SkillMention) -> ScoredPair | None:
        exact = self.taxonomy.resolve(mention.surface_form)
        if exact is not None:
            return ScoredPair(
                mention_id=mention.mention_id,
                canonical_skill=exact,
                similarity=1.0,
            )

        hits = self.index.query(mention.surface_form, n=1)
        if not hits:
            return None

        canonical_skill, similarity = hits[0]
        if similarity < MIN_SIMILARITY:
            return None

        return ScoredPair(
            mention_id=mention.mention_id,
            canonical_skill=canonical_skill,
            similarity=similarity,
        )


class ExactMatcher:
    """Taxonomy-only matcher, with no vector dependency.

    This is the documented fallback if semantic matching underperforms or
    Chroma cannot be installed. It satisfies the same interface, so swapping
    it in is a one-line change at the call site.
    """

    def __init__(self, taxonomy: TaxonomyIndex):
        self.taxonomy = taxonomy

    def match(self, mentions: list[SkillMention]) -> list[ScoredPair]:
        pairs = []
        for mention in mentions:
            canonical = self.taxonomy.resolve(mention.surface_form)
            if canonical is not None:
                pairs.append(
                    ScoredPair(
                        mention_id=mention.mention_id,
                        canonical_skill=canonical,
                        similarity=1.0,
                    )
                )
        return pairs
