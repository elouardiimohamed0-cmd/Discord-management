"""Simple file-based cache for API responses."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

from src.core.logging import get_logger

logger = get_logger(__name__)


class FileCache:
    """File-based cache with TTL support."""

    def __init__(self, cache_dir: Path, ttl_seconds: int = 120):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds

    def _cache_path(self, key: str) -> Path:
        """Get the cache file path for a key."""
        safe_key = key.replace("/", "_").replace(":", "_")
        return self.cache_dir / f"{safe_key}.json"

    def get(self, key: str) -> Optional[dict]:
        """Get cached data if not expired."""
        path = self._cache_path(key)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text())
            if time.time() - data.get("_cached_at", 0) > self.ttl_seconds:
                path.unlink(missing_ok=True)
                return None
            return data.get("payload")
        except Exception as e:
            logger.warning("[Cache] Read error for %s: %s", key, e)
            path.unlink(missing_ok=True)
            return None

    def set(self, key: str, payload: Any) -> None:
        """Store data in cache."""
        path = self._cache_path(key)
        try:
            data = {
                "_cached_at": time.time(),
                "payload": payload,
            }
            path.write_text(json.dumps(data, default=str))
        except Exception as e:
            logger.warning("[Cache] Write error for %s: %s", key, e)

    def clear(self) -> None:
        """Clear all cached files."""
        for f in self.cache_dir.glob("*.json"):
            f.unlink(missing_ok=True)
        logger.info("[Cache] Cleared all entries")
