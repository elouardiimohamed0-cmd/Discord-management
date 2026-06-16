"""Image Generator - drop-in replacement for existing ImageGenerator.
Wraps the new CardGenerator to provide the same interface as the old module."""
import math
import random
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Dict

from PIL import Image, ImageDraw, ImageFont, ImageEnhance

from card_generator import get_card_generator
from player_mapper import get_mapper
from aura_system import get_aura_system


def _player_to_dict(player) -> Dict:
    """Convert PlayerStats object to dict for card generator."""
    games = getattr(player, 'games', 1) or 1
    wins = getattr(player, 'wins', 0) or 0
    return {
        "games": games,
        "rating": round(getattr(player, 'rating_pg', 7.0) or 7.0, 1),
        "goals": getattr(player, 'goals', 0) or 0,
        "assists": getattr(player, 'assists', 0) or 0,
        "tackles": getattr(player, 'tackles', 0) or 0,
        "interceptions": getattr(player, 'interceptions', 0) or 0,
        "possession_lost": getattr(player, 'possession_losses', 0) or 0,
        "pass_accuracy": round(getattr(player, 'pass_accuracy', 0) or 0, 1),
        "wins": wins,
        "motm": getattr(player, 'motm', 0) or 0,
        "impact": round(getattr(player, 'impact_score', 5.0) or 5.0, 1),
        "win_rate": round((wins / games) * 100, 1) if games > 0 else 0,
        "fraud_score": min((getattr(player, 'throwing_score', 0) or 0) * 20, 100),
    }


class ImageGenerator:
    """Drop-in replacement for existing ImageGenerator."""

    def __init__(self, assets_dir: str = "assets"):
        self.cards = get_card_generator()
        self.mapper = get_mapper()
        self.aura = get_aura_system()
        self.assets_dir = Path(assets_dir)

    def _to_bytesio(self, card: Image.Image) -> BytesIO:
        buf = BytesIO()
        card.save(buf, format="PNG")
        buf.seek(0)
        return buf

    def generate_motm_card(self, player, pos: str = "CM") -> BytesIO:
        """Generate MOTM/MVP card."""
        stats = _player_to_dict(player)
        ea_name = getattr(player, 'name', str(player))
        card = self.cards.generate_mvp_card(ea_name, stats)
        return self._to_bytesio(card)

    def generate_mvp_card(self, player, pos: str = "CM") -> BytesIO:
        """Generate MVP card."""
        return self.generate_motm_card(player, pos)

    def generate_anime_card(self, player, pos: str = "CM", style: str = "mvp", title: str = "PLAYER PROFILE") -> BytesIO:
        """Generate premium anime-style card."""
        stats = _player_to_dict(player)
        ea_name = getattr(player, 'name', str(player))
        if style == "beast":
            card = self.cards.generate_carry_card(ea_name, stats)
        elif style == "fraud":
            card = self.cards.generate_fraud_card(ea_name, stats)
        elif style == "ghost":
            card = self.cards.generate_ghost_card(ea_name, stats)
        else:
            card = self.cards.generate_mvp_card(ea_name, stats)
        return self._to_bytesio(card)

    def generate_beast_card(self, player, pos: str = "CM") -> BytesIO:
        """Generate beast mode (carry) card."""
        stats = _player_to_dict(player)
        ea_name = getattr(player, 'name', str(player))
        card = self.cards.generate_carry_card(ea_name, stats)
        return self._to_bytesio(card)

    def generate_court_case(self, player, pos: str = "CM", evidence: List[str] = None) -> BytesIO:
        """Generate court case (fraud) card."""
        stats = _player_to_dict(player)
        ea_name = getattr(player, 'name', str(player))
        card = self.cards.generate_fraud_card(ea_name, stats)
        return self._to_bytesio(card)

    def generate_daily_card(self, player, stat_name: str, stat_value, roast: str, is_bad: bool = True) -> BytesIO:
        """Generate daily stat card."""
        stats = _player_to_dict(player)
        ea_name = getattr(player, 'name', str(player))
        if is_bad:
            card = self.cards.generate_fraud_card(ea_name, stats)
        else:
            card = self.cards.generate_mvp_card(ea_name, stats)
        return self._to_bytesio(card)

    def generate_playmaker_card(self, player, pos: str = "CM") -> BytesIO:
        """Generate playmaker card."""
        stats = _player_to_dict(player)
        ea_name = getattr(player, 'name', str(player))
        card = self.cards.generate_player_card(ea_name, stats)
        return self._to_bytesio(card)

    def generate_sniper_card(self, player, pos: str = "CM") -> BytesIO:
        """Generate sniper (goal scorer) card."""
        stats = _player_to_dict(player)
        ea_name = getattr(player, 'name', str(player))
        card = self.cards.generate_player_card(ea_name, stats)
        return self._to_bytesio(card)

    def generate_ghost_card(self, player, pos: str = "CM") -> BytesIO:
        """Generate ghost card."""
        stats = _player_to_dict(player)
        ea_name = getattr(player, 'name', str(player))
        card = self.cards.generate_ghost_card(ea_name, stats)
        return self._to_bytesio(card)

    def generate_fraud_card(self, player, pos: str = "CM") -> BytesIO:
        """Generate fraud card."""
        stats = _player_to_dict(player)
        ea_name = getattr(player, 'name', str(player))
        card = self.cards.generate_fraud_card(ea_name, stats)
        return self._to_bytesio(card)

    def generate_carry_card(self, player, pos: str = "CM") -> BytesIO:
        """Generate carry card."""
        stats = _player_to_dict(player)
        ea_name = getattr(player, 'name', str(player))
        card = self.cards.generate_carry_card(ea_name, stats)
        return self._to_bytesio(card)

    def generate_standard_card(self, player, pos: str = "CM") -> BytesIO:
        """Generate standard player card."""
        stats = _player_to_dict(player)
        ea_name = getattr(player, 'name', str(player))
        card = self.cards.generate_player_card(ea_name, stats)
        return self._to_bytesio(card)
