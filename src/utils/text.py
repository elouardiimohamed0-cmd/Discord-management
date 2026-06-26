from __future__ import annotations

import re
import unicodedata


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_")
    return value.lower() or "unknown"


def clamp_discord(value: str, limit: int = 1900) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"
