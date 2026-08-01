"""Semantic skill index backed by ChromaDB.

This is the mandated Semantic Gap Analyzer component. It runs Chroma in
embedded mode (PersistentClient), so there is no extra service to operate,
and embeddings come from a local sentence-transformers model rather than a
paid API.
"""

import logging

from app.config import settings
from app.taxonomy.loader import TaxonomyIndex

logger = logging.getLogger(__name__)

COLLECTION = "canonical_skills"


class SkillIndex:
    """Embeds canonical skills and answers nearest-neighbour queries.

    Construction is lazy and failure-tolerant: if Chroma or the embedding
    model is unavailable, `available` stays False and the matcher falls back
    to exact taxonomy resolution rather than crashing the pipeline.
    """

    def __init__(self) -> None:
        self.collection = None
        self.available = False
        try:
            import chromadb
            from chromadb.utils import embedding_functions
        except ImportError:
            logger.warning("chromadb not installed; semantic matching disabled")
            return

        try:
            client = chromadb.PersistentClient(path=settings.chroma_path)
            embedder = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=settings.embedding_model
            )
            self.collection = client.get_or_create_collection(
                name=COLLECTION, embedding_function=embedder
            )
            self.available = True
        except Exception as exc:
            logger.warning("Chroma unavailable (%s); semantic matching disabled", exc)

    def index_taxonomy(self, taxonomy: TaxonomyIndex) -> int:
        """Index each skill as its name plus aliases.

        Including aliases in the embedded text is what lets a phrase like
        "building chatbots over company documents" retrieve Retrieval
        Augmented Generation despite sharing no keywords with it.
        """
        if not self.available:
            return 0

        documents, ids, metadatas = [], [], []
        for skill in taxonomy.skills:
            canonical = skill["canonical_name"]
            aliases = " ".join(skill.get("aliases", []))
            documents.append(f"{canonical}. {aliases}".strip())
            ids.append(canonical)
            metadatas.append({"category": skill.get("category", "general")})

        self.collection.upsert(documents=documents, ids=ids, metadatas=metadatas)
        return len(ids)

    def count(self) -> int:
        return self.collection.count() if self.available else 0

    def query(self, text: str, n: int = 3) -> list[tuple[str, float]]:
        """Return (canonical_skill, similarity) pairs, best first.

        Chroma returns squared L2 distances for the default space. They are
        converted to a bounded similarity so downstream code never sees a
        raw distance or a value outside the unit interval.
        """
        if not self.available or not text.strip():
            return []

        result = self.collection.query(query_texts=[text], n_results=n)
        ids = result["ids"][0]
        distances = result["distances"][0]
        return [
            (skill_id, _distance_to_similarity(distance))
            for skill_id, distance in zip(ids, distances)
        ]


def _distance_to_similarity(distance: float) -> float:
    """Map a non-negative distance onto (0, 1], monotonically decreasing.

    A plain `1 - distance` produces negative similarities once the distance
    exceeds 1, which is common with L2, and those would violate the
    ScoredPair contract.
    """
    return round(1.0 / (1.0 + max(float(distance), 0.0)), 6)
