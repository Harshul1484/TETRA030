"""Stage 6: propose syllabus modifications.

The third mandated component. The brief is explicit that output must be
adoptable "without requiring the professor to redesign the entire course
structure from scratch", so the prompt is built around additions that fit
an existing structure rather than a replacement curriculum.

Prerequisite distance is passed through to the model. A skill adjacent to
existing content can be added directly; one several hops away needs its
prerequisites named rather than being dropped on a professor as a demand.
"""

import logging

from app.contracts import AugmentProposal, GapReport, SkillGap
from app.db.queries import fetch_prerequisite_chain
from app.llm.claude_client import ClaudeClient

logger = logging.getLogger(__name__)

# How many gaps are handed to the model. Beyond roughly this many, proposals
# stop being a focused revision and start being the rewrite the brief
# explicitly rules out.
MAX_GAPS_CONSIDERED = 10

UNREACHABLE_DISTANCE = 99

SYSTEM = (
    "You are a curriculum design consultant advising a university professor. "
    "You propose targeted, adoptable additions to an existing course. You "
    "never propose redesigning a course from scratch. You return only JSON."
)

TEMPLATE = """Course: {course_code} - {course_title}
Current curriculum health score: {health}/100

The course already covers:
{covered}

Skills the job market demands that this course does not adequately cover,
most urgent first:

{gaps}

Propose modifications the professor can adopt WITHOUT redesigning the course.
Respect the existing structure and sequence. Assume limited contact hours, so
prefer additions that extend existing units over new units.

Return JSON with exactly these keys:

  "added_outcomes": 2 to 4 new course outcome statements, phrased the way a
      syllabus phrases outcomes, each targeting a specific gap above

  "case_studies": 2 to 3 modern industry case studies a professor could
      discuss in an existing lecture slot, each one or two sentences

  "toolsets": 3 to 5 specific tools or libraries to introduce, naming the
      tool and the existing unit it fits into

  "project_prompts": 2 to 3 assignment briefs that close several gaps at
      once, each two or three sentences

  "rationale": one paragraph justifying these changes to a curriculum
      committee, referencing the market evidence

Rules:
- Every proposal must trace to a listed gap. Do not invent new priorities.
- Where a gap has unmet prerequisites, say what must be introduced first
  rather than assuming students can absorb it directly.
- Be concrete and current. Name real tools, real companies, real practices.
- Return only the JSON object, no other text.
"""

FALLBACK = {
    "added_outcomes": [],
    "case_studies": [],
    "toolsets": [],
    "project_prompts": [],
    "rationale": (
        "Augmentation is unavailable right now. The gap analysis above still "
        "reflects live market data and can be acted on directly."
    ),
}


class SyllabusAugmenter:
    def __init__(self, claude: ClaudeClient, include_prerequisites: bool = True):
        self.claude = claude
        self.include_prerequisites = include_prerequisites

    def propose(self, report: GapReport) -> AugmentProposal:
        considered = report.gaps[:MAX_GAPS_CONSIDERED]

        prompt = TEMPLATE.format(
            course_code=report.course_code,
            course_title=report.course_title,
            health=report.health_score,
            covered=self._describe_coverage(report),
            gaps=self._describe_gaps(considered),
        )

        raw = self.claude.complete_json(prompt, system=SYSTEM, fallback=FALLBACK)
        return self._to_proposal(report.course_code, raw)

    @staticmethod
    def _describe_coverage(report: GapReport) -> str:
        covered = [
            gap.canonical_skill
            for gap in report.gaps
            if gap.curriculum_coverage > 0.0
        ]
        if not covered:
            return "  (no overlap detected with the analysed job market skills)"
        return "\n".join(f"  - {skill}" for skill in covered[:15])

    def _describe_gaps(self, gaps: list[SkillGap]) -> str:
        lines = []
        for gap in gaps:
            lines.append(
                f"- {gap.canonical_skill} [{gap.severity.value}]\n"
                f"    demand: {gap.postings_requiring} of {gap.postings_total} postings\n"
                f"    {self._describe_reachability(gap)}"
            )
        return "\n".join(lines)

    def _describe_reachability(self, gap: SkillGap) -> str:
        """Tell the model what it would cost to teach this.

        Without this the model proposes advanced topics as though a course
        could adopt them directly, which is exactly the kind of unusable
        advice the brief warns against.
        """
        if gap.prerequisite_distance <= 1:
            return "adjacent to existing content, can be added directly"

        if gap.prerequisite_distance >= UNREACHABLE_DISTANCE:
            missing = self._missing_prerequisites(gap.canonical_skill)
            if missing:
                return (
                    "not reachable from current content; requires first: "
                    + ", ".join(missing)
                )
            return "not reachable from current content"

        return (
            f"{gap.prerequisite_distance} prerequisite steps from existing content"
        )

    def _missing_prerequisites(self, skill: str) -> list[str]:
        if not self.include_prerequisites:
            return []
        try:
            chain = fetch_prerequisite_chain(skill)
        except Exception as exc:
            logger.warning("Prerequisite lookup failed for %s: %s", skill, exc)
            return []
        return [row["prerequisite"] for row in chain if row["hops"] == 1][:3]

    @staticmethod
    def _to_proposal(course_code: str, raw: object) -> AugmentProposal:
        """Coerce a model response into the contract.

        A malformed response degrades to an empty proposal rather than
        raising: the gap report is still useful on its own.
        """
        if not isinstance(raw, dict):
            logger.warning("Augmenter returned %s, not an object", type(raw).__name__)
            raw = FALLBACK

        return AugmentProposal(
            course_code=course_code,
            added_outcomes=_string_list(raw.get("added_outcomes")),
            case_studies=_string_list(raw.get("case_studies")),
            toolsets=_string_list(raw.get("toolsets")),
            project_prompts=_string_list(raw.get("project_prompts")),
            rationale=str(raw.get("rationale") or FALLBACK["rationale"]),
        )


def _string_list(value: object) -> list[str]:
    """Models sometimes return a string where a list was asked for, or wrap
    each item in an object."""
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        return []

    items = []
    for entry in value:
        if isinstance(entry, str):
            items.append(entry)
        elif isinstance(entry, dict):
            # A common shape: {"tool": "...", "unit": "..."}
            items.append(" - ".join(str(v) for v in entry.values() if v))
    return [item for item in items if item.strip()]
