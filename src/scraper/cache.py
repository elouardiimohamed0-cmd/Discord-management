from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional


class JsonCache:
    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def get(self, key: str, ttl_seconds: int) -> Optional[dict[str, Any]]:
        path = self.directory / f"{key}.json"
        if not path.exists():
            return None
        if time.time() - path.stat().st_mtime > ttl_seconds:
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def set(self, key: str, value: dict[str, Any]) -> None:
        path = self.directory / f"{key}.json"
        path.write_text(json.dumps(value, ensure_ascii=False, default=str), encoding="utf-8")
