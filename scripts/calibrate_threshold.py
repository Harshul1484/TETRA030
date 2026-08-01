"""Calibrate MIN_SIMILARITY against the loaded taxonomy.

The similarity floor in app/pipeline/match.py separates genuine skill
mentions from unrelated syllabus prose. Its absolute scale depends on the
embedding model, so it must be re-measured whenever the model changes
rather than carried over as a magic constant.

Usage, from the repository root:

    CHROMA_PATH=./data/chroma python scripts/calibrate_threshold.py

Requires the taxonomy to have been indexed first.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.pipeline.embed import SkillIndex  # noqa: E402
from app.taxonomy.loader import TaxonomyIndex  # noqa: E402

# Phrases that genuinely describe a technical skill. Every one should match.
TRUE_POSITIVES = [
    "deploying models to production",
    "securing web applications",
    "analysing large datasets",
    "training neural networks",
    "orchestrating containers",
    "designing database schemas",
    "writing automated tests",
    "building user interfaces",
    "processing streaming events",
    "tuning query performance",
]

# Ordinary syllabus and administrative prose. None should match any skill.
TRUE_NEGATIVES = [
    "the quarterly marketing budget was approved",
    "students must attend at least 75 percent of lectures",
    "the cafeteria serves lunch at noon",
    "please submit assignments by friday",
    "the exam is worth 40 marks",
    "office hours are held on tuesday afternoons",
    "this module carries four credit hours",
    "late submissions incur a ten percent penalty",
    "the field trip has been rescheduled",
    "consult the department handbook for policy",
]


def main() -> int:
    index = SkillIndex()
    if not index.available:
        print("Chroma unavailable; cannot calibrate.")
        return 1

    if index.count() == 0:
        print("Index is empty; loading taxonomy first.")
        index.index_taxonomy(TaxonomyIndex.from_disk())

    positives, negatives = [], []

    print("TRUE POSITIVES (should match)")
    for phrase in TRUE_POSITIVES:
        hits = index.query(phrase, n=1)
        if hits:
            skill, similarity = hits[0]
            positives.append(similarity)
            print(f"  {similarity:.3f}  {phrase[:45]:47} -> {skill}")

    print()
    print("TRUE NEGATIVES (should not match)")
    for phrase in TRUE_NEGATIVES:
        hits = index.query(phrase, n=1)
        if hits:
            skill, similarity = hits[0]
            negatives.append(similarity)
            print(f"  {similarity:.3f}  {phrase[:45]:47} -> {skill}")

    if not positives or not negatives:
        print("\nInsufficient data to calibrate.")
        return 1

    lowest_positive = min(positives)
    highest_negative = max(negatives)
    gap = lowest_positive - highest_negative

    print()
    print(f"true positive range : {lowest_positive:.3f} - {max(positives):.3f}")
    print(f"false positive range: {min(negatives):.3f} - {highest_negative:.3f}")
    print(f"separation gap      : {gap:+.3f}")
    print()

    if gap <= 0:
        print("WARNING: the bands overlap. No threshold separates them cleanly.")
        print("Consider a stronger embedding model or rely on exact matching.")
        return 1

    recommended = round(highest_negative + gap / 2, 2)
    print(f"recommended MIN_SIMILARITY: {recommended}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
