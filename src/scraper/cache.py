from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional


class FileCache:
    def __init__(self, cache_dir: Path, ttl_seconds: int = 300):
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    def get(self, url: str) -> Optional[dict[str, Any]]:
        path = self.cache_dir / f"{self._key(url)}.json"
        if not path.exists():
            return None
        import time
        if time.time() - path.stat().st_mtime > self.ttl_seconds:
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def set(self, url: str, data: dict[str, Any]) -> None:
        path = self.cache_dir / f"{self._key(url)}.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
