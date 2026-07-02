"""Roast engine for generating player roasts."""
from __future__ import annotations

from src.core.logging import get_logger
from src.data.repositories import ClubRepository
from src.domain.models import PlayerMatchStats
from src.squad.registry import SquadRegistry

logger = get_logger(__name__)


class RoastEngine:
    """Generate roasts based on player performance."""

    def __init__(self, repository: ClubRepository, squad: SquadRegistry):
        self.repo = repository
        self.squad = squad

    def roast(self, player_name: str, stats: PlayerMatchStats) -> str:
        """Generate a roast for a player."""
        if stats.rating >= 8.0:
            return f"{player_name} is absolutely carrying! {stats.rating} rating? The team doesn't deserve you."
        elif stats.rating >= 6.0:
            return f"{player_name} had a solid {stats.rating} rating. Mid, just like your life choices."
        elif stats.rating >= 4.0:
            return f"{player_name} with a {stats.rating} rating... bro, were you even trying?"
        else:
            return f"{player_name} got a {stats.rating} rating. I've seen bots play better. Uninstall."
