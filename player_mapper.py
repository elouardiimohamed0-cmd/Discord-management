"""player_mapper.py — maps EA names ↔ nicknames."""

NICKNAME_MAP = {
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

# Reverse lookup
EA_MAP = {v: k for k, v in NICKNAME_MAP.items()}


class PlayerMapper:
    """Maps between EA names and nicknames."""

    def get_nickname(self, ea_name: str) -> str:
        """Return nickname for EA name, or EA name if not mapped."""
        return NICKNAME_MAP.get(ea_name, ea_name)

    def get_ea_name(self, nickname: str) -> str:
        """Return EA name for nickname, or nickname if not mapped."""
        return EA_MAP.get(nickname, nickname)


def get_mapper() -> PlayerMapper:
    return PlayerMapper()
