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
        self._by_display_name: Dict[str, PlayerIdentity] = {}  # FIX: Added display_name index
        for key, p in players.items():
            self._by_ea_id[p.ea_id.lower()] = p
            self._by_nickname[p.nickname.lower()] = p
            if p.raw.get("psn"):
                self._by_psn[p.raw["psn"].lower()] = p
            # Also index by display_name if different
            if p.ea_id.lower() != p.nickname.lower():
                self._by_display_name[p.nickname.lower()] = p

    @classmethod
    def from_file(cls, path: Path) -> "SquadRegistry":
        data = json.loads(path.read_text(encoding="utf-8"))
        players = {}
        for key, raw in data.items():
            psn_name = raw.get("psn", key)
            # FIX: Use actual EA ID if provided, otherwise use PSN name
            actual_ea_id = raw.get("ea_id", psn_name)
            players[key] = PlayerIdentity(
                ea_id=str(actual_ea_id).lower(),
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
            or self._by_display_name.get(q)  # FIX: Added display_name lookup
            or self._fuzzy_find(q)
        )

    def find_by_ea_id(self, ea_id: str) -> Optional[PlayerIdentity]:
        ea_id_lower = ea_id.lower().strip()
        result = self._by_ea_id.get(ea_id_lower)
        if result:
            return result
        return self._by_psn.get(ea_id_lower) or self._by_display_name.get(ea_id_lower)

    def find_by_display_name(self, display_name: str) -> Optional[PlayerIdentity]:
        q = display_name.lower().strip()
        return (
            self._by_psn.get(q)
            or self._by_ea_id.get(q)
            or self._by_nickname.get(q)
            or self._by_display_name.get(q)
            or self._fuzzy_find(q)
        )

    def _fuzzy_find(self, query: str) -> Optional[PlayerIdentity]:
        for p in self._by_ea_id.values():
            if query in p.nickname.lower() or query in p.ea_id.lower():
                return p
        return None

    def all(self) -> List[PlayerIdentity]:
        return list(self._by_ea_id.values())
