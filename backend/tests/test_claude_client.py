"""R3 requires that a dead API key or a rate limit during judging still
produces a working demo. These tests exercise that degradation path.
"""

from app.llm.claude_client import ClaudeClient, strip_fences


def test_strips_json_fences():
    assert strip_fences('```json\n{"a": 1}\n```') == '{"a": 1}'


def test_strips_bare_fences():
    assert strip_fences('```\n{"a": 1}\n```') == '{"a": 1}'


def test_leaves_unfenced_json_alone():
    assert strip_fences('{"a": 1}') == '{"a": 1}'


def test_multiline_fenced_content_survives():
    fenced = '```json\n{\n  "a": 1,\n  "b": 2\n}\n```'
    assert strip_fences(fenced) == '{\n  "a": 1,\n  "b": 2\n}'


def test_returns_fallback_when_no_api_key(monkeypatch, tmp_path):
    """The demo must survive a missing key rather than raising."""
    monkeypatch.setattr("app.config.settings.anthropic_api_key", "")
    monkeypatch.setattr("app.config.settings.llm_cache_path", str(tmp_path))
    client = ClaudeClient()
    assert client.complete_json("prompt", fallback={"ok": True}) == {"ok": True}


def test_cache_hit_bypasses_the_api_entirely(monkeypatch, tmp_path):
    """A warm cache must serve results with no client at all, which is what
    keeps an unattended judge's session working hours after the fact."""
    monkeypatch.setattr("app.config.settings.anthropic_api_key", "")
    monkeypatch.setattr("app.config.settings.llm_cache_path", str(tmp_path))
    monkeypatch.setattr("app.config.settings.claude_model", "test-model")

    client = ClaudeClient()
    key = "test-model||prompt"
    client.cache.set(key, {"cached": True})

    assert client.complete_json("prompt", fallback={"ok": False}) == {"cached": True}


def test_api_exception_degrades_to_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr("app.config.settings.llm_cache_path", str(tmp_path))

    class ExplodingClient:
        class messages:
            @staticmethod
            def create(**kwargs):
                raise RuntimeError("rate limited")

    client = ClaudeClient()
    client._client = ExplodingClient()
    assert client.complete_json("prompt", fallback=[]) == []


def test_malformed_json_response_is_not_cached(monkeypatch, tmp_path):
    """A parse failure must not poison the cache with garbage."""
    monkeypatch.setattr("app.config.settings.llm_cache_path", str(tmp_path))
    monkeypatch.setattr("app.config.settings.claude_model", "test-model")

    class Block:
        text = "this is not json"

    class BadClient:
        class messages:
            @staticmethod
            def create(**kwargs):
                return type("Msg", (), {"content": [Block()]})()

    client = ClaudeClient()
    client._client = BadClient()

    assert client.complete_json("prompt", fallback={"safe": True}) == {"safe": True}
    assert client.cache.get("test-model||prompt") is None
