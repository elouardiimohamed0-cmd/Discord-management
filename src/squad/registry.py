from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from src.domain.models import PlayerIdentity


class SquadRegistry:
    def __init__(self, players: Dict[str, PlayerIdentity]):
        self._by_ea_id: Dict[str, PlayerIdentity] = {}
        self._by_nickname: Dict[str, PlayerIdentity] = {}
        self._by_psn: Dict[str, PlayerIdentity] = {}
        for key, p in players.items():
            self._by_ea_id[p.ea_id.lower()] = p
            self._by_nickname[p.nickname.lower()] = p
            if p.raw.get("psn"):
                self._by_psn[p.raw["psn"].lower()] = p

    @classmethod
    def from_file(cls, path: Path) -> "SquadRegistry":
        data = json.loads(path.read_text(encoding="utf-8"))
        players = {}
        for key, raw in data.items():
            players[key] = PlayerIdentity(
                ea_id=raw.get("psn", key),  # PSN is often the EA ID
                nickname=raw.get("nickname", raw.get("name", key)),
                image=raw.get("image"),
                personality=raw.get("style") or raw.get("personality"),
                meme_tags=raw.get("meme_tags", []),
                position=raw.get("position"),
                number=raw.get("number"),
                raw=raw,
            )
        return cls(players)

    def find(self, query: str) -> Optional[PlayerIdentity]:
        q = query.lower().strip()
        return (
            self._by_ea_id.get(q)
            or self._by_nickname.get(q)
            or self._by_psn.get(q)
            or self._fuzzy_find(q)
        )

    def find_by_ea_id(self, ea_id: str) -> Optional[PlayerIdentity]:
        return self._by_ea_id.get(ea_id.lower())

    def _fuzzy_find(self, query: str) -> Optional[PlayerIdentity]:
        for p in self._by_ea_id.values():
            if query in p.nickname.lower() or query in p.ea_id.lower():
                return p
        return None

    def all(self) -> List[PlayerIdentity]:
        return list(self._by_ea_id.values())
