"""Shared, lazily constructed pipeline components.

The Pipeline loads a sentence-transformers model, which takes seconds.
Building one per request would make the API unusable, so it is constructed
once on first use and reused.
"""

from app.llm.claude_client import ClaudeClient
from app.pipeline.augment import SyllabusAugmenter
from app.pipeline.orchestrator import Pipeline

_pipeline: Pipeline | None = None
_augmenter: SyllabusAugmenter | None = None


def get_pipeline() -> Pipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = Pipeline()
    return _pipeline


def get_augmenter() -> SyllabusAugmenter:
    global _augmenter
    if _augmenter is None:
        _augmenter = SyllabusAugmenter(ClaudeClient())
    return _augmenter
