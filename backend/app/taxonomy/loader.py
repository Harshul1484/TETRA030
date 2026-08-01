import json
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).parent / "data" / "skills.json"


class TaxonomyIndex:
    """Resolves free-text skill mentions to canonical taxonomy names.

    Extraction links to this taxonomy rather than inventing nodes. Without
    that constraint, "ML", "Machine Learning", and "machine-learning" become
    three separate Skill nodes and every gap number downstream is garbage.

    Ambiguous aliases raise at construction time rather than silently
    resolving to whichever skill happened to load last.
    """

    def __init__(self, skills: list[dict[str, Any]]):
        self.skills = skills
        self._lookup: dict[str, str] = {}
        for skill in skills:
            canonical = skill["canonical_name"]
            for form in [canonical, *skill.get("aliases", [])]:
                normalized = self._normalize(form)
                existing = self._lookup.get(normalized)
                if existing and existing != canonical:
                    raise ValueError(
                        f"Ambiguous alias {form!r}: maps to both "
                        f"{existing!r} and {canonical!r}"
                    )
                self._lookup[normalized] = canonical

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.strip().lower().replace("-", " ").replace("_", " ").split())

    def resolve(self, surface_form: str) -> str | None:
        return self._lookup.get(self._normalize(surface_form))

    def canonical_names(self) -> list[str]:
        return [s["canonical_name"] for s in self.skills]

    @classmethod
    def from_disk(cls) -> "TaxonomyIndex":
        return cls(json.loads(DATA_PATH.read_text(encoding="utf-8")))
