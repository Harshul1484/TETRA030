"""Stage 2: pull taxonomy-linked skills out of a document.

The extractor is constrained to the canonical taxonomy and cannot invent
skills. Without that constraint "ML" and "Machine Learning" become separate
nodes and every downstream gap number is meaningless.

Cost note: sending all 438 canonical names in every prompt would be roughly
6k tokens of overhead per document, or about 1.8M tokens across the corpus.
Instead the vector index shortlists candidates for each document and Claude
chooses from the shortlist. That is the two mandated components working
together, and it cuts prompt size by roughly ninety percent.
"""

import logging
import uuid

from app.contracts import Document, SkillMention
from app.llm.claude_client import ClaudeClient
from app.pipeline.embed import SkillIndex
from app.taxonomy.loader import TaxonomyIndex

logger = logging.getLogger(__name__)

# How many candidate skills the vector index shortlists per document.
CANDIDATE_COUNT = 60

# Documents are truncated before extraction. Job descriptions repeat
# benefits and legal boilerplate after the requirements section, so the
# first few thousand characters carry nearly all the skill signal.
MAX_DOCUMENT_CHARS = 8000

SYSTEM = (
    "You extract technical skills from educational and job-market text. "
    "You return only a JSON array, never prose. You never invent skills "
    "outside the provided list."
)

TEMPLATE = """Identify which of the allowed skills below are genuinely required or taught in this text.

ALLOWED SKILLS (choose only from these exact names):
{allowed}

Return a JSON array. Each element:
  "skill": one exact name from the allowed list
  "evidence": the phrase from the text that shows it, verbatim, under 200 characters
  "importance": 0.0 to 1.0, how central it is to this document

Rules:
- Only include a skill if the text genuinely calls for it. Do not infer broadly.
- A passing mention scores low importance. A core requirement scores high.
- Return [] if none of the allowed skills appear.
- Return only the JSON array, no other text.

TEXT:
{text}"""


class SkillExtractor:
    """Vector shortlist, then a constrained Claude call.

    Every result is re-validated against the taxonomy after the model
    responds. Constraining a model in the prompt reduces invention but does
    not guarantee it, so the taxonomy has the final say.
    """

    def __init__(
        self,
        taxonomy: TaxonomyIndex,
        claude: ClaudeClient,
        index: SkillIndex | None = None,
    ):
        self.taxonomy = taxonomy
        self.claude = claude
        self.index = index

    def candidate_skills(self, document: Document) -> list[str]:
        """Shortlist plausible skills for this document.

        Falls back to the full taxonomy when the vector index is
        unavailable, so extraction still works without Chroma.
        """
        if self.index is None or not self.index.available:
            return self.taxonomy.canonical_names()

        hits = self.index.query(
            document.raw_text[:MAX_DOCUMENT_CHARS], n=CANDIDATE_COUNT
        )
        candidates = [skill for skill, _ in hits]
        return candidates or self.taxonomy.canonical_names()

    def extract(self, document: Document) -> list[SkillMention]:
        allowed = self.candidate_skills(document)
        prompt = TEMPLATE.format(
            allowed="\n".join(f"- {name}" for name in allowed),
            text=document.raw_text[:MAX_DOCUMENT_CHARS],
        )

        raw = self.claude.complete_json(prompt, system=SYSTEM, fallback=[])
        if not isinstance(raw, list):
            logger.warning(
                "Extractor returned %s rather than a list for %s",
                type(raw).__name__,
                document.doc_id,
            )
            return []

        mentions: list[SkillMention] = []
        seen: set[str] = set()

        for item in raw:
            if not isinstance(item, dict):
                continue

            canonical = self.taxonomy.resolve(str(item.get("skill", "")))
            if canonical is None or canonical in seen:
                continue

            seen.add(canonical)
            mentions.append(
                SkillMention(
                    mention_id=f"m-{uuid.uuid4().hex[:10]}",
                    doc_id=document.doc_id,
                    surface_form=canonical,
                    context=str(item.get("evidence", ""))[:500],
                    importance=_clamp_importance(item.get("importance")),
                )
            )

        return mentions


def _clamp_importance(value: object) -> float:
    """Models occasionally return importance as a string, or out of range."""
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, number))
