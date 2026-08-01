"""The contracts module is imported by every pipeline stage, so its
validation constraints are load-bearing. A bound that does not actually
reject bad input is worse than no bound: it creates false confidence.
"""

import pytest
from pydantic import ValidationError

from app.contracts import (
    Document,
    DocumentKind,
    GapReport,
    GapSeverity,
    ScoredPair,
    SkillGap,
    SkillMention,
    SkillTrend,
)


def test_document_accepts_optional_posted_date():
    doc = Document(
        doc_id="job-1",
        kind=DocumentKind.JOB_POSTING,
        title="ML Engineer",
        raw_text="text",
        source="remotive",
    )
    assert doc.posted_date is None


def test_similarity_above_one_is_rejected():
    with pytest.raises(ValidationError):
        ScoredPair(mention_id="m1", canonical_skill="Python", similarity=1.5)


def test_similarity_below_zero_is_rejected():
    with pytest.raises(ValidationError):
        ScoredPair(mention_id="m1", canonical_skill="Python", similarity=-0.1)


def test_importance_defaults_to_midpoint():
    mention = SkillMention(
        mention_id="m1", doc_id="d1", surface_form="Python", context="ctx"
    )
    assert mention.importance == 0.5


def test_health_score_above_hundred_is_rejected():
    with pytest.raises(ValidationError):
        GapReport(
            course_code="CS101",
            course_title="Intro",
            health_score=101.0,
            gaps=[],
        )


def test_gap_report_accepts_empty_gap_list():
    report = GapReport(
        course_code="CS101", course_title="Intro", health_score=100.0, gaps=[]
    )
    assert report.gaps == []


def test_trend_slope_is_optional_so_forecaster_can_be_cut():
    """The forecaster is off the critical path. If it never ships, this
    contract must still validate with slope absent."""
    trend = SkillTrend(canonical_skill="Kubernetes", history=[])
    assert trend.slope is None


def test_severity_serializes_as_plain_string():
    """The frontend reads these values directly, so they must serialize as
    strings rather than as enum reprs."""
    gap = SkillGap(
        canonical_skill="Vector Databases",
        severity=GapSeverity.CRITICAL,
        market_demand=0.9,
        curriculum_coverage=0.0,
        prerequisite_distance=1,
        postings_requiring=47,
        postings_total=312,
        evidence="47 of 312 postings require this",
    )
    assert gap.model_dump()["severity"] == "critical"
