import hashlib
import json
from pathlib import Path
from typing import Any


class DiskCache:
    """Content-addressed cache. Same input always yields the same output.

    This is what keeps the demo alive when the API key expires or rate
    limits hit during judging: a warm cache serves complete results with
    no network call at all.
    """

    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.root / f"{digest}.json"

    def get(self, key: str) -> Any | None:
        path = self._path(key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def set(self, key: str, value: Any) -> None:
        self._path(key).write_text(
            json.dumps(value, ensure_ascii=False), encoding="utf-8"
        )
