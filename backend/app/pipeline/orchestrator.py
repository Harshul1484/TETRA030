"""Runs the six stages end to end.

Ingest -> Extract -> Embed -> Match -> Score -> (Augment, separately)

Components are constructed once and reused: the embedding model takes
seconds to load, so building a Pipeline per request would make the API
unusable.
"""

import logging
from pathlib import Path

from app.contracts import Document, GapReport, SkillGap
from app.db import writer
from app.db.queries import fetch_course_gaps, fetch_courses
from app.llm.claude_client import ClaudeClient
from app.pipeline.embed import SkillIndex
from app.pipeline.extract import SkillExtractor
from app.pipeline.ingest import load_job_metadata, load_job_snapshot, load_syllabi
from app.pipeline.match import VectorMatcher
from app.pipeline.score import classify_severity, compute_gap_score, compute_health_score
from app.taxonomy.loader import TaxonomyIndex

logger = logging.getLogger(__name__)

# Distance the graph reports when a skill is unreachable from anything the
# course teaches. Mapped to a finite penalty for scoring, since an infinite
# distance would zero out the reachability term entirely.
UNREACHABLE_DISTANCE = 99
UNREACHABLE_PENALTY = 6

# Soft skills appear in nearly every job posting, so raw frequency ranks them
# above every technical gap. They are genuine market signal and stay in the
# report, but "add teamwork to your database course" is not advice a
# curriculum committee can act on, so they are down-weighted in the ranking.
PROFESSIONAL_CATEGORY = "professional"
PROFESSIONAL_RANK_WEIGHT = 0.25


class Pipeline:
    def __init__(self) -> None:
        self.taxonomy = TaxonomyIndex.from_disk()
        self.claude = ClaudeClient()
        self.index = SkillIndex()
        self.extractor = SkillExtractor(self.taxonomy, self.claude, self.index)
        self.matcher = VectorMatcher(self.index, self.taxonomy)

    def index_taxonomy(self) -> int:
        return self.index.index_taxonomy(self.taxonomy)

    def ingest_document(self, document: Document) -> tuple[list, list]:
        mentions = self.extractor.extract(document)
        pairs = self.matcher.match(mentions)
        return mentions, pairs

    def ingest_jobs(self, limit: int | None = None, snapshot: Path | None = None) -> int:
        documents = load_job_snapshot(snapshot)
        metadata = load_job_metadata(snapshot)
        if limit:
            documents = documents[:limit]

        written = 0
        for index, document in enumerate(documents, start=1):
            try:
                mentions, pairs = self.ingest_document(document)
                writer.write_job_skills(
                    document, mentions, pairs, metadata.get(document.doc_id)
                )
                written += 1
            except Exception as exc:
                logger.warning("Failed on %s: %s", document.doc_id, exc)

            if index % 25 == 0:
                logger.info("Processed %d/%d postings", index, len(documents))

        return written

    def ingest_syllabus(self, document: Document, course_code: str | None = None) -> str:
        code = course_code or _derive_course_code(document.title)
        writer.write_course(code=code, title=document.title)
        mentions, pairs = self.ingest_document(document)
        writer.write_course_skills(code, mentions, pairs)
        return code

    def ingest_syllabi(self, directory: Path) -> list[str]:
        codes = []
        for document in load_syllabi(directory):
            try:
                codes.append(self.ingest_syllabus(document))
            except Exception as exc:
                logger.warning("Failed on %s: %s", document.doc_id, exc)
        return codes

    def build_report(self, course_code: str, course_title: str = "") -> GapReport:
        """Turn graph state into a ranked, evidence-backed gap report."""
        rows = fetch_course_gaps(course_code)

        if not course_title:
            course_title = next(
                (c["title"] for c in fetch_courses() if c["code"] == course_code),
                course_code,
            )

        gaps: list[SkillGap] = []
        scores: list[float] = []
        rank_weights: dict[str, float] = {}

        for row in rows:
            postings_total = max(row["postings_total"], 1)
            postings_requiring = row["postings_requiring"]
            market_demand = postings_requiring / postings_total

            confidences = row.get("coverage_confidence") or []
            coverage = max(confidences) if confidences else 0.0

            raw_distance = row["prerequisite_distance"]
            distance = (
                UNREACHABLE_PENALTY
                if raw_distance >= UNREACHABLE_DISTANCE
                else raw_distance
            )

            score = compute_gap_score(
                market_demand=market_demand,
                curriculum_coverage=coverage,
                prerequisite_distance=distance,
                trend_slope=None,
            )
            scores.append(score)

            rank_weight = market_demand * (1.0 - coverage)
            if row.get("category") == PROFESSIONAL_CATEGORY:
                rank_weight *= PROFESSIONAL_RANK_WEIGHT
            rank_weights[row["skill"]] = rank_weight

            gaps.append(
                SkillGap(
                    canonical_skill=row["skill"],
                    severity=classify_severity(score),
                    market_demand=round(market_demand, 4),
                    curriculum_coverage=round(coverage, 4),
                    prerequisite_distance=raw_distance,
                    trend_slope=None,
                    postings_requiring=postings_requiring,
                    postings_total=postings_total,
                    evidence=_build_evidence(
                        postings_requiring, postings_total, coverage, raw_distance
                    ),
                )
            )

        gaps.sort(key=lambda g: rank_weights[g.canonical_skill], reverse=True)

        return GapReport(
            course_code=course_code,
            course_title=course_title,
            health_score=compute_health_score(scores),
            gaps=gaps,
        )


def _build_evidence(
    requiring: int, total: int, coverage: float, distance: int
) -> str:
    """A gap without evidence is an assertion. Every number here is real."""
    parts = [f"{requiring} of {total} postings require this"]

    if coverage <= 0.0:
        parts.append("no outcome in this course covers it")
    else:
        parts.append(f"current coverage is only {coverage:.0%}")

    if distance >= UNREACHABLE_DISTANCE:
        parts.append("no prerequisite path from what this course already teaches")
    elif distance <= 1:
        parts.append("adjacent to existing content, so a low-cost addition")
    else:
        parts.append(f"{distance} prerequisite hops from existing content")

    return "; ".join(parts)


def _derive_course_code(title: str) -> str:
    """Course codes come from syllabus filenames, which are inconsistent."""
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in title)
    words = cleaned.split()
    if not words:
        return "COURSE"
    return " ".join(words)[:48].strip().upper()
