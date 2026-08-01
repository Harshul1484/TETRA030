from app.llm.cache import DiskCache


def test_cache_roundtrip(tmp_path):
    cache = DiskCache(str(tmp_path))
    assert cache.get("prompt-a") is None
    cache.set("prompt-a", {"text": "result"})
    assert cache.get("prompt-a") == {"text": "result"}


def test_cache_key_is_content_addressed(tmp_path):
    cache = DiskCache(str(tmp_path))
    cache.set("prompt-a", {"text": "one"})
    cache.set("prompt-b", {"text": "two"})
    assert cache.get("prompt-a") == {"text": "one"}
    assert cache.get("prompt-b") == {"text": "two"}


def test_cache_survives_a_new_instance(tmp_path):
    """The demo depends on cache hits after a process restart: a judge
    hitting the app hours later must not trigger fresh API calls."""
    DiskCache(str(tmp_path)).set("prompt-a", {"text": "persisted"})
    assert DiskCache(str(tmp_path)).get("prompt-a") == {"text": "persisted"}


def test_cache_handles_unicode_without_mangling(tmp_path):
    cache = DiskCache(str(tmp_path))
    cache.set("prompt", {"text": "Ubersicht naive resume"})
    assert cache.get("prompt") == {"text": "Ubersicht naive resume"}


def test_cache_stores_lists_not_only_dicts(tmp_path):
    """The skill extractor caches a JSON array, not an object."""
    cache = DiskCache(str(tmp_path))
    cache.set("extract", [{"surface_form": "Python"}])
    assert cache.get("extract") == [{"surface_form": "Python"}]


def test_creates_cache_directory_if_absent(tmp_path):
    nested = tmp_path / "does" / "not" / "exist"
    cache = DiskCache(str(nested))
    cache.set("k", {"v": 1})
    assert cache.get("k") == {"v": 1}
