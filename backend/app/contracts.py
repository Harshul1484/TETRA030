from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class DocumentKind(str, Enum):
    SYLLABUS = "syllabus"
    JOB_POSTING = "job_posting"


class Document(BaseModel):
    """Stage 1 output: a normalized source document."""

    doc_id: str
    kind: DocumentKind
    title: str
    raw_text: str
    source: str
    posted_date: date | None = None


class SkillMention(BaseModel):
    """Stage 2 output: a skill referenced in a document, before canonicalization."""

    mention_id: str
    doc_id: str
    surface_form: str
    context: str
    importance: float = Field(ge=0.0, le=1.0, default=0.5)


class ScoredPair(BaseModel):
    """Stage 4 output. This is the swap seam: any matcher emitting these works."""

    mention_id: str
    canonical_skill: str
    similarity: float = Field(ge=0.0, le=1.0)


class GapSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


class SkillGap(BaseModel):
    """One missing or under-covered skill, with the evidence supporting it."""

    canonical_skill: str
    severity: GapSeverity
    market_demand: float = Field(ge=0.0, le=1.0)
    curriculum_coverage: float = Field(ge=0.0, le=1.0)
    prerequisite_distance: int
    trend_slope: float | None = None
    postings_requiring: int
    postings_total: int
    evidence: str


class GapReport(BaseModel):
    """Stage 5 output."""

    course_code: str
    course_title: str
    health_score: float = Field(ge=0.0, le=100.0)
    gaps: list[SkillGap]


class AugmentProposal(BaseModel):
    """Stage 6 output: modifications a professor can adopt without a redesign."""

    course_code: str
    added_outcomes: list[str]
    case_studies: list[str]
    toolsets: list[str]
    project_prompts: list[str]
    rationale: str


class TrendPoint(BaseModel):
    period: str
    frequency: int


class SkillTrend(BaseModel):
    """Slope is None until the forecaster ships. The contract never changes."""

    canonical_skill: str
    history: list[TrendPoint]
    slope: float | None = None
