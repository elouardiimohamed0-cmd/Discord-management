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
            # FIX: Store by actual EA ID, PSN, AND nickname for lookup
            # The API returns player IDs as the dict key in players[club_id]
            # We store by PSN (which is the display name in the API) for matching
            self._by_ea_id[p.ea_id.lower()] = p
            self._by_nickname[p.nickname.lower()] = p
            if p.raw.get("psn"):
                self._by_psn[p.raw["psn"].lower()] = p

    @classmethod
    def from_file(cls, path: Path) -> "SquadRegistry":
        data = json.loads(path.read_text(encoding="utf-8"))
        players = {}
        for key, raw in data.items():
            # FIX: Use PSN as the primary lookup key since the API returns playername=PSN
            # The EA ID from API is numeric, but playername matches PSN
            psn_name = raw.get("psn", key)
            players[key] = PlayerIdentity(
                ea_id=psn_name.lower(),  # FIX: Use PSN as ea_id for matching
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
        # FIX: Also try to find by PSN name since that's what the API uses as playername
        # The API's playername field matches the PSN name in squad.json
        ea_id_lower = ea_id.lower()
        result = self._by_ea_id.get(ea_id_lower)
        if result:
            return result
        # Fallback: try PSN lookup
        return self._by_psn.get(ea_id_lower)

    def find_by_display_name(self, display_name: str) -> Optional[PlayerIdentity]:
        """Find player by display_name from API (which is the PSN name)."""
        q = display_name.lower().strip()
        return (
            self._by_psn.get(q)
            or self._by_ea_id.get(q)
            or self._by_nickname.get(q)
            or self._fuzzy_find(q)
        )

    def _fuzzy_find(self, query: str) -> Optional[PlayerIdentity]:
        for p in self._by_ea_id.values():
            if query in p.nickname.lower() or query in p.ea_id.lower():
                return p
        return None

    def all(self) -> List[PlayerIdentity]:
        return list(self._by_ea_id.values())
