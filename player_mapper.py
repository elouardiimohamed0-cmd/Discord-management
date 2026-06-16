"""Player nickname mapping system - reads squad.json and maps EA names to nicknames."""
import json
from pathlib import Path
from typing import Dict, Optional
import config

# Hardcoded fallback mapping (from requirements)
FALLBACK_NICKNAMES = {
    "A999ESCANOR": "Dictator",
    "A999SHARK": "Shark",
    "Hessaidi": "Shawarmista",
    "brave-Youness95": "Brave",
    "brown-base7": "Le7ya",
    "A999KIRA": "Kira",
    "Taha1direction": "Marrakchi",
    "Yasskillz88": "Modamir",
    "Amine_bambo": "Moul_l7anot",
    "haytamox2": "9ahba_south_africa",
}

class PlayerMapper:
    """Maps EA usernames to nicknames and manages player metadata."""

    def __init__(self, squad_file: Optional[Path] = None):
        self.squad_file = squad_file or config.SQUAD_FILE
        self._mapping: Dict[str, Dict] = {}
        self._ea_to_nickname: Dict[str, str] = {}
        self._nickname_to_ea: Dict[str, str] = {}
        self._load_squad()

    def _load_squad(self):
        """Load squad.json and build mapping."""
        if not self.squad_file.exists():
            # Use fallback only
            for ea_name, nick in FALLBACK_NICKNAMES.items():
                self._ea_to_nickname[ea_name.lower()] = nick
                self._nickname_to_ea[nick.lower()] = ea_name
            return

        try:
            with open(self.squad_file, "r", encoding="utf-8") as f:
                squad = json.load(f)

            # squad.json can be a list or dict depending on format
            players = squad if isinstance(squad, list) else squad.get("players", squad.get("members", []))

            for player in players:
                if isinstance(player, dict):
                    ea_name = player.get("ea_name") or player.get("name") or player.get("username") or ""
                    nickname = player.get("nickname") or player.get("alias") or ""
                    photo = player.get("photo") or player.get("image") or ""
                    position = player.get("position") or "CM"

                    if ea_name:
                        ea_key = ea_name.lower().strip()
                        if nickname:
                            self._ea_to_nickname[ea_key] = nickname
                            self._nickname_to_ea[nickname.lower().strip()] = ea_name
                        else:
                            # Try fallback
                            fallback = FALLBACK_NICKNAMES.get(ea_name, ea_name)
                            self._ea_to_nickname[ea_key] = fallback
                            self._nickname_to_ea[fallback.lower().strip()] = ea_name

                        self._mapping[ea_key] = {
                            "ea_name": ea_name,
                            "nickname": self._ea_to_nickname.get(ea_key, ea_name),
                            "photo": photo,
                            "position": position,
                            "raw": player,
                        }

            # Add any fallbacks not in squad
            for ea_name, nick in FALLBACK_NICKNAMES.items():
                key = ea_name.lower()
                if key not in self._ea_to_nickname:
                    self._ea_to_nickname[key] = nick
                    self._nickname_to_ea[nick.lower()] = ea_name
                    self._mapping[key] = {
                        "ea_name": ea_name,
                        "nickname": nick,
                        "photo": "",
                        "position": "CM",
                        "raw": {},
                    }

        except Exception as e:
            print(f"[PlayerMapper] Error loading squad: {e}")
            for ea_name, nick in FALLBACK_NICKNAMES.items():
                self._ea_to_nickname[ea_name.lower()] = nick
                self._nickname_to_ea[nick.lower()] = ea_name

    def get_nickname(self, ea_name: str) -> str:
        """Get nickname for EA username."""
        key = ea_name.lower().strip()
        return self._ea_to_nickname.get(key, ea_name)

    def get_ea_name(self, nickname: str) -> str:
        """Get EA username from nickname."""
        key = nickname.lower().strip()
        return self._nickname_to_ea.get(key, nickname)

    def get_photo_path(self, ea_name: str) -> Optional[Path]:
        """Get photo path for player."""
        key = ea_name.lower().strip()
        player = self._mapping.get(key)
        if not player:
            return None

        photo = player.get("photo", "")
        if photo:
            path = config.ASSETS_DIR / photo
            if path.exists():
                return path

        # Try common patterns
        patterns = [
            f"{ea_name}.png",
            f"{ea_name}.jpg",
            f"{ea_name}.jpeg",
            f"{player['nickname']}.png",
            f"{player['nickname']}.jpg",
            f"{player['nickname']}.jpeg",
        ]
        for p in patterns:
            path = config.ASSETS_DIR / p
            if path.exists():
                return path

        return None

    def get_position(self, ea_name: str) -> str:
        """Get player position."""
        key = ea_name.lower().strip()
        player = self._mapping.get(key)
        return player.get("position", "CM") if player else "CM"

    def all_nicknames(self) -> list:
        """Return all known nicknames."""
        return list(self._ea_to_nickname.values())

    def all_ea_names(self) -> list:
        """Return all EA names."""
        return list(self._nickname_to_ea.values())

# Global instance
_mapper = None

def get_mapper() -> PlayerMapper:
    global _mapper
    if _mapper is None:
        _mapper = PlayerMapper()
    return _mapper
