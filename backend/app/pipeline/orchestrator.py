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
from app.db.queries import fetch_course_categories, fetch_course_gaps, fetch_courses
from app.llm.claude_client import ClaudeClient
from app.pipeline.embed import SkillIndex
from app.pipeline.extract import SkillExtractor
from app.pipeline.ingest import load_job_metadata, load_job_snapshot, load_syllabi
from app.pipeline.match import VectorMatcher
from app.pipeline.score import (
    classify_severity,
    compute_alignment_score,
    compute_gap_score,
)
from app.taxonomy.loader import TaxonomyIndex

logger = logging.getLogger(__name__)

# Distance the graph reports when a skill is unreachable from anything the
# course teaches. Mapped to a finite penalty for scoring, since an infinite
# distance would zero out the reachability term entirely.
UNREACHABLE_DISTANCE = 99
UNREACHABLE_PENALTY = 6

# Gaps returned per course. The previous value of 40 was hit by every course,
# so the count shown on screen was an artifact of the cap rather than a
# finding.
GAP_LIMIT = 200

# A skill must appear in at least this share of postings to count as a
# curriculum gap. Measured on the real corpus, 43 of 170 demanded skills were
# named by exactly one posting and the median was three. One employer wanting
# Elasticsearch is not evidence that a degree programme is failing, and
# including that tail made every course report 170 identical gaps.
MIN_DEMAND_SHARE = 0.03

# Soft skills appear in nearly every job posting, so raw frequency ranks them
# above every technical gap. They are genuine market signal and stay in the
# report, but "add teamwork to your database course" is not advice a
# curriculum committee can act on, so they are down-weighted in the ranking.
PROFESSIONAL_CATEGORY = "professional"
PROFESSIONAL_RANK_WEIGHT = 0.25

# Categories that identify a course as belonging to a specific engineering
# discipline rather than to computing.
DISCIPLINE_CATEGORIES = {"civil", "mechanical", "electrical", "process"}

# Categories whose membership says nothing about discipline. `engineering`
# holds both Engineering Drawing and Release Management; `professional` and
# `foundations` sit under every course on the platform. They cannot be used
# to decide what field a course is in.
SHARED_CATEGORIES = {"engineering", "professional", "foundations", "mathematics"}

# Categories that draw on the same pool of software postings, so demand in
# one is usable evidence for a course rooted in another.
COMPUTING_CATEGORIES = {
    "ai",
    "data",
    "web",
    "cloud",
    "systems",
    "security",
    "language",
    "engineering",
}

# Postings a subject area needs before its audit is worth stating as fact.
# Below this the ranked gaps are mostly adjacent-field demand: the corpus
# holds hundreds of software postings and a handful of civil ones, so a civil
# course scored against it will surface Cloud Computing regardless of how the
# ranking is written. Twelve is not a statistical threshold, it is the point
# below which a curriculum committee should not be shown a confident number.
EVIDENCE_FLOOR = 12

# Coverage above which a skill is treated as taught rather than missing.
# Match confidences cluster high, so this sits below the typical value for a
# genuine match and above incidental partial overlap.
COVERED_THRESHOLD = 0.6


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
        rows = fetch_course_gaps(course_code, limit=GAP_LIMIT)

        if not course_title:
            course_title = next(
                (c["title"] for c in fetch_courses() if c["code"] == course_code),
                course_code,
            )

        gaps: list[SkillGap] = []
        scores: list[float] = []
        rank_weights: dict[str, float] = {}
        categories: dict[str, str] = {}
        # Demand the syllabus already meets. Held aside so it still counts
        # toward the alignment score without appearing as a finding.
        covered_demand: list[tuple[float, float]] = []

        for row in rows:
            postings_total = max(row["postings_total"], 1)
            postings_requiring = row["postings_requiring"]
            market_demand = postings_requiring / postings_total

            confidences = row.get("coverage_confidence") or []
            coverage = max(confidences) if confidences else 0.0

            # Long-tail skills are dropped unless the course already teaches
            # them, in which case they still count toward coverage.
            if market_demand < MIN_DEMAND_SHARE and coverage <= 0.0:
                continue

            # A skill the syllabus already teaches well is not a gap. It stays
            # in the scoring set below, where its coverage raises the score,
            # but reporting it as a finding told a structural analysis course
            # its gap was Hydrology, a subject it teaches.
            if coverage >= COVERED_THRESHOLD:
                scores.append(
                    compute_gap_score(
                        market_demand=market_demand,
                        curriculum_coverage=coverage,
                        prerequisite_distance=0,
                        trend_slope=None,
                    )
                )
                covered_demand.append((market_demand, coverage))
                continue

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
            categories[row["skill"]] = row.get("category") or "general"

            gaps.append(
                SkillGap(
                    canonical_skill=row["skill"],
                    category=row.get("category") or "general",
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

        # Score against the demand in this course's own subject area rather
        # than against the whole market. Measuring an artificial intelligence
        # course on Kubernetes demand produced arithmetically correct but
        # misleading numbers: every course covered three to twelve percent of
        # total tech demand, which is normal, yet reads as a failing grade.
        domain = _course_domain(course_code)

        # In-domain skills rank above out-of-domain ones, which are demoted
        # rather than dropped: without this the largest category in the corpus
        # wins every course, and demand that genuinely crosses disciplines is
        # still worth surfacing below the course's own field.
        def rank_key(gap: SkillGap) -> tuple[int, float]:
            in_domain = (
                not domain or categories.get(gap.canonical_skill) in domain
            )
            return (1 if in_domain else 0, rank_weights[gap.canonical_skill])

        gaps.sort(key=rank_key, reverse=True)

        scoring_set = [
            gap
            for gap in gaps
            if not domain or categories.get(gap.canonical_skill) in domain
        ] or gaps

        # Demand the syllabus already meets belongs in both terms. Withholding
        # it from the report is a presentation decision; dropping it from the
        # score would penalise a course for teaching the right things.
        demand_total = sum(gap.market_demand for gap in scoring_set) + sum(
            demand for demand, _ in covered_demand
        )
        demand_covered = sum(
            gap.market_demand * gap.curriculum_coverage for gap in scoring_set
        ) + sum(demand * coverage for demand, coverage in covered_demand)

        # Ranking cannot manufacture evidence it does not have. A course whose
        # subject area is barely present in the corpus will surface adjacent
        # demand however the sort is written, so the count is reported.
        domain_postings = _domain_posting_count(rows, domain)

        # The floor exists for disciplines the corpus barely covers, not for
        # narrow subfields of one it covers well. A cloud course scored
        # against 14 cloud postings sits inside hundreds of adjacent software
        # postings that share its vocabulary; a civil course scored against 2
        # does not. Only the former is a safe comparison.
        related_postings = _domain_posting_count(
            rows, _sibling_categories(domain)
        )
        evidence_thin = (
            bool(domain)
            and domain_postings < EVIDENCE_FLOOR
            and related_postings < EVIDENCE_FLOOR
        )

        # Below the floor the out-of-domain tail is the entire list, and a
        # caveat banner does not stop a leading card reading as a
        # recommendation. Only in-domain findings are reported, even when that
        # leaves the list nearly empty.
        if evidence_thin:
            in_domain_gaps = [
                gap
                for gap in gaps
                if categories.get(gap.canonical_skill) in domain
            ]
            gaps = in_domain_gaps

        evidence_note = None
        if evidence_thin:
            subject = ", ".join(sorted(domain))
            evidence_note = (
                f"Only {domain_postings} postings in the current corpus demand "
                f"{subject} skills, below the {EVIDENCE_FLOOR} this audit "
                f"requires before reporting a subject-area verdict. Findings "
                f"outside {subject} have been withheld rather than ranked, "
                f"because they reflect what the corpus contains rather than "
                f"what this course is missing. Load a corpus with more "
                f"{subject} postings to audit this course properly."
            )

        return GapReport(
            course_code=course_code,
            course_title=course_title,
            health_score=(
                None
                if evidence_thin
                else compute_alignment_score(demand_covered, demand_total, scores)
            ),
            scored_against=sorted(domain) if domain else ["all categories"],
            domain_postings=domain_postings,
            evidence_thin=evidence_thin,
            evidence_note=evidence_note,
            gaps=gaps,
        )


def _sibling_categories(domain: set[str]) -> set[str]:
    """The wider family a subject area sits in.

    Computing categories share vocabulary and job postings, so demand in one
    is meaningful evidence for another. The engineering disciplines do not
    share a corpus that way: civil postings say nothing about mechanical.
    """
    if domain & DISCIPLINE_CATEGORIES:
        return domain & DISCIPLINE_CATEGORIES
    return COMPUTING_CATEGORIES


def _domain_posting_count(rows: list[dict], domain: set[str]) -> int:
    """Postings demanding at least one skill in the course's subject area.

    Taken as the maximum rather than the sum: summing counts one posting once
    per skill it mentions, so a single job asking for four civil skills would
    read as four postings of evidence.
    """
    if not domain:
        return max((row["postings_total"] for row in rows), default=0)
    return max(
        (
            row["postings_requiring"]
            for row in rows
            if (row.get("category") or "general") in domain
        ),
        default=0,
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

    # Reachability is deliberately absent here. The frontend renders it as its
    # own colour-coded line, and stating it twice made every gap card read as
    # if it were repeating itself.
    return "; ".join(parts)


def _derive_course_code(title: str) -> str:
    """Course codes come from syllabus filenames, which are inconsistent."""
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in title)
    words = cleaned.split()
    if not words:
        return "COURSE"
    return " ".join(words)[:48].strip().upper()


def _course_domain(course_code: str) -> set[str]:
    """Which subject areas this course actually belongs to.

    Derived from the categories of the skills it already teaches, so a course
    is judged against demand in its own field. A course teaching nothing
    recognisable gets an empty domain and falls back to the whole market.
    """
    try:
        rows = fetch_course_categories(course_code)
    except Exception as exc:
        logger.warning("Domain lookup failed for %s: %s", course_code, exc)
        return set()

    counts = {
        row["category"]: row["skills"]
        for row in rows
        if row.get("category") and row.get("skills")
    }
    if not counts:
        return set()

    # Sorted so ties break deterministically; otherwise dict iteration order
    # decides a course's subject area and it can change on reseed.
    strongest = max(sorted(counts), key=lambda c: counts[c])

    # Keep any category the course touches more than once, plus its strongest
    # one. A single incidental match should not widen the domain.
    domain = {c for c, n in counts.items() if n >= 2}
    domain.add(strongest)

    # A course anchored in a specific discipline must not be widened into
    # computing by incidental overlap: a steel design paper also teaches
    # Materials Science and Engineering Drawing, which share the `engineering`
    # category with Software Testing.
    anchored = domain & DISCIPLINE_CATEGORIES
    if anchored:
        domain -= SHARED_CATEGORIES

    return domain
