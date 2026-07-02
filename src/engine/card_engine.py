"""Card engine for generating player cards."""
from __future__ import annotations

import io

import discord

from src.core.config import Settings
from src.core.logging import get_logger
from src.domain.models import PlayerMatchStats
from src.squad.registry import SquadRegistry

logger = get_logger(__name__)


class CardEngine:
    """Generate player card images."""

    def __init__(self, settings: Settings, squad: SquadRegistry):
        self.settings = settings
        self.squad = squad

    def generate(self, player_name: str, stats: PlayerMatchStats) -> discord.File:
        """Generate a player card image."""
        # Placeholder — implement actual image generation
        # For now, return a text-based card as a file
        card_text = f"""Player Card: {player_name}
Rating: {stats.rating}
Goals: {stats.goals}
Assists: {stats.assists}
Shots: {stats.shots}
Pass Accuracy: {stats.pass_accuracy}%
Minutes: {stats.minutes}
"""
        buffer = io.BytesIO(card_text.encode())
        buffer.seek(0)
        return discord.File(buffer, filename=f"{player_name}_card.txt")
