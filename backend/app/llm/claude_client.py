import json
import logging
from typing import Any

from app.config import settings
from app.llm.cache import DiskCache

logger = logging.getLogger(__name__)


class ClaudeClient:
    """Cached Claude wrapper. Never raises to callers; degrades instead.

    The fallback chain is the point: cache, then live call, then the
    caller-supplied fallback. A dead key or a rate limit during judging
    degrades the output rather than breaking the page.
    """

    def __init__(self) -> None:
        self.cache = DiskCache(settings.llm_cache_path)
        self._client = self._build_client()

    @staticmethod
    def _build_client() -> Any | None:
        if not settings.anthropic_api_key:
            return None
        try:
            import anthropic
        except ImportError:
            logger.warning("anthropic package not installed; running cache-only")
            return None
        return anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def complete_json(
        self, prompt: str, system: str = "", fallback: Any = None
    ) -> Any:
        key = f"{settings.claude_model}|{system}|{prompt}"

        cached = self.cache.get(key)
        if cached is not None:
            return cached

        if self._client is None:
            logger.warning("No Claude client available; returning fallback")
            return fallback

        try:
            message = self._client.messages.create(
                model=settings.claude_model,
                max_tokens=4096,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            parsed = json.loads(strip_fences(message.content[0].text))
        except Exception as exc:
            logger.warning("Claude call failed (%s); returning fallback", exc)
            return fallback

        self.cache.set(key, parsed)
        return parsed


def strip_fences(text: str) -> str:
    """Claude often wraps JSON in markdown fences despite instructions."""
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned
    lines = cleaned.split("\n")
    if len(lines) < 3:
        return cleaned
    if lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines[1:]).strip()
