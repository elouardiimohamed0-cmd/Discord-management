from __future__ import annotations


def truncate(text: str, length: int = 2000) -> str:
    if len(text) <= length:
        return text
    return text[: length - 3] + "..."


def clean_nickname(name: str) -> str:
    return name.strip().replace("@", "")
