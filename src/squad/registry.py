from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from src.domain.models import PlayerIdentity


class SquadRegistry:
    """Identity-only registry backed by squad.json.

    This class must never decide who played. It only enriches a player that
    already came from match.players / Pro Clubs Tracker.
    """

    def __init__(self, players: Iterable[PlayerIdentity]):
        self._by_ea_id: Dict[str, PlayerIdentity] = {}
        self._by_nickname: Dict[str, PlayerIdentity] = {}
        for player in players:
            self._by_ea_id[player.ea_id.lower()] = player
            self._by_nickname[player.nickname.lower()] = player

    @classmethod
    def from_file(cls, path: Path) -> "SquadRegistry":
        if not path.exists():
            return cls([])
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return cls(cls._parse(data))

    @staticmethod
    def _parse(data: Any) -> list[PlayerIdentity]:
        if isinstance(data, dict) and "players" in data and isinstance(data["players"], list):
            rows = data["players"]
        elif isinstance(data, dict):
            rows = list(data.values())
        elif isinstance(data, list):
            rows = data
        else:
            rows = []

        identities: list[PlayerIdentity] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            ea_id = str(row.get("ea_id") or row.get("psn") or row.get("PSN") or row.get("name") or "").strip()
            nickname = str(row.get("nickname") or row.get("name") or ea_id).strip()
            if not ea_id or not nickname:
                continue
            meme_tags = row.get("meme_tags") or row.get("tags") or []
            if isinstance(meme_tags, str):
                meme_tags = [meme_tags]
            identities.append(
                PlayerIdentity(
                    ea_id=ea_id,
                    nickname=nickname,
                    image=row.get("image"),
                    personality=row.get("personality") or row.get("style"),
                    meme_tags=list(meme_tags),
                    position=row.get("position"),
                    number=row.get("number"),
                    raw=row,
                )
            )
        return identities

    def find(self, query: str) -> Optional[PlayerIdentity]:
        key = query.lower().strip()
        if key in self._by_ea_id:
            return self._by_ea_id[key]
        if key in self._by_nickname:
            return self._by_nickname[key]
        for player in self._by_ea_id.values():
            if key in player.ea_id.lower() or key in player.nickname.lower():
                return player
        return None

    def enrich_name(self, ea_id: str, fallback: str) -> str:
        player = self._by_ea_id.get(ea_id.lower())
        return player.nickname if player else fallback

    def all(self) -> list[PlayerIdentity]:
        return list(self._by_ea_id.values())

    def __len__(self) -> int:
        return len(self._by_ea_id)
