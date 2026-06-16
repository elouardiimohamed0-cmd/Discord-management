"""Aura tier system - calculates player aura based on stats."""
from enum import Enum
from typing import Dict, Tuple
from dataclasses import dataclass

class AuraTier(Enum):
    S_TIER = "S-Tier"
    A_TIER = "A-Tier"
    B_TIER = "B-Tier"
    FRAUD = "Fraud"
    GHOST = "Ghost"
    CARRY = "Carry"

@dataclass
class AuraConfig:
    name: str
    color_primary: Tuple[int, int, int]
    color_secondary: Tuple[int, int, int]
    glow_color: Tuple[int, int, int, int]
    description: str
    emoji: str
    card_bg: str  # gradient key

AURA_CONFIGS = {
    AuraTier.S_TIER: AuraConfig(
        name="S-Tier",
        color_primary=(138, 43, 226),   # Purple
        color_secondary=(0, 191, 255),   # Deep Sky Blue
        glow_color=(138, 43, 226, 180),
        description="Monster aura - unstoppable force",
        emoji="👑",
        card_bg="purple_blue_energy",
    ),
    AuraTier.A_TIER: AuraConfig(
        name="A-Tier",
        color_primary=(255, 215, 0),    # Gold
        color_secondary=(255, 165, 0),   # Orange
        glow_color=(255, 215, 0, 160),
        description="Golden aura - elite performer",
        emoji="⚡",
        card_bg="gold_metal",
    ),
    AuraTier.B_TIER: AuraConfig(
        name="B-Tier",
        color_primary=(50, 205, 50),    # Lime Green
        color_secondary=(0, 255, 127),   # Spring Green
        glow_color=(50, 205, 50, 140),
        description="Green aura - solid player",
        emoji="🍀",
        card_bg="green_neon",
    ),
    AuraTier.CARRY: AuraConfig(
        name="Carry",
        color_primary=(0, 0, 139),      # Dark Blue
        color_secondary=(65, 105, 225),  # Royal Blue
        glow_color=(0, 191, 255, 200),
        description="Blue Lock style king aura",
        emoji="🎯",
        card_bg="blue_lock_king",
    ),
    AuraTier.FRAUD: AuraConfig(
        name="Fraud",
        color_primary=(255, 0, 0),      # Red
        color_secondary=(139, 0, 0),     # Dark Red
        glow_color=(255, 0, 0, 150),
        description="Clown aura - certified fraud",
        emoji="🤡",
        card_bg="clown_circus",
    ),
    AuraTier.GHOST: AuraConfig(
        name="Ghost",
        color_primary=(192, 192, 192),   # Silver
        color_secondary=(220, 220, 220), # Light Grey
        glow_color=(255, 255, 255, 100),
        description="Transparent aura - invisible player",
        emoji="👻",
        card_bg="ghost_transparent",
    ),
}

class AuraSystem:
    """Calculates aura tier from player statistics."""

    def __init__(self):
        self.weights = {
            "rating": 0.30,
            "goals_per_game": 0.15,
            "assists_per_game": 0.15,
            "win_rate": 0.15,
            "pass_accuracy": 0.10,
            "tackles_per_game": 0.05,
            "impact": 0.10,
        }

    def calculate_overall(self, stats: Dict) -> float:
        """Calculate overall rating from stats (0-100 scale)."""
        rating = stats.get("rating", 7.0)
        games = max(stats.get("games", 1), 1)
        goals = stats.get("goals", 0)
        assists = stats.get("assists", 0)
        wins = stats.get("wins", 0)
        pass_acc = stats.get("pass_accuracy", 0)
        tackles = stats.get("tackles", 0)
        impact = stats.get("impact", 5.0)

        # Normalize to 0-100
        rating_norm = min((rating / 10.0) * 100, 100)
        gpg = min((goals / games) * 20, 100)  # 5 goals/game = 100
        apg = min((assists / games) * 20, 100)
        wr = (wins / games) * 100 if games > 0 else 0
        pa = pass_acc
        tpg = min((tackles / games) * 10, 100)
        imp = min(impact * 10, 100)

        overall = (
            rating_norm * self.weights["rating"] +
            gpg * self.weights["goals_per_game"] +
            apg * self.weights["assists_per_game"] +
            wr * self.weights["win_rate"] +
            pa * self.weights["pass_accuracy"] +
            tpg * self.weights["tackles_per_game"] +
            imp * self.weights["impact"]
        )
        return round(overall, 1)

    def calculate_fraud_score(self, stats: Dict) -> float:
        """Calculate fraud score (0-100, higher = more fraud)."""
        games = max(stats.get("games", 1), 1)
        rating = stats.get("rating", 7.0)
        goals = stats.get("goals", 0)
        assists = stats.get("assists", 0)
        poss_lost = stats.get("possession_lost", 0)
        wins = stats.get("wins", 0)

        fraud = 0.0
        # Low rating with many games
        if rating < 6.0 and games > 10:
            fraud += 30
        # Low goals for attacker
        if goals < games * 0.3 and games > 10:
            fraud += 20
        # High possession lost
        if poss_lost > games * 5:
            fraud += 25
        # Low win rate
        wr = (wins / games) * 100 if games > 0 else 0
        if wr < 30 and games > 10:
            fraud += 25

        return min(fraud, 100)

    def determine_tier(self, stats: Dict) -> AuraTier:
        """Determine aura tier from stats."""
        games = stats.get("games", 0)
        overall = self.calculate_overall(stats)
        fraud_score = self.calculate_fraud_score(stats)

        # Ghost check: very few games
        if games < 3 and games > 0:
            return AuraTier.GHOST
        if games == 0:
            return AuraTier.GHOST

        # Fraud check
        if fraud_score >= 60:
            return AuraTier.FRAUD

        # Carry check: high impact, high win rate, carries team
        impact = stats.get("impact", 5.0)
        wins = stats.get("wins", 0)
        wr = (wins / games) * 100 if games > 0 else 0
        if impact >= 8.0 and wr >= 70 and overall >= 85:
            return AuraTier.CARRY

        # Standard tiers
        if overall >= 90:
            return AuraTier.S_TIER
        elif overall >= 80:
            return AuraTier.A_TIER
        elif overall >= 70:
            return AuraTier.B_TIER
        elif fraud_score >= 40:
            return AuraTier.FRAUD
        else:
            return AuraTier.B_TIER

    def get_aura_config(self, tier: AuraTier) -> AuraConfig:
        return AURA_CONFIGS.get(tier, AURA_CONFIGS[AuraTier.B_TIER])

    def get_tier_from_overall(self, overall: float, games: int = 100) -> AuraTier:
        """Quick tier from overall score."""
        if games < 3:
            return AuraTier.GHOST
        if overall >= 90:
            return AuraTier.S_TIER
        elif overall >= 80:
            return AuraTier.A_TIER
        elif overall >= 70:
            return AuraTier.B_TIER
        else:
            return AuraTier.FRAUD

# Global instance
_aura = None

def get_aura_system() -> AuraSystem:
    global _aura
    if _aura is None:
        _aura = AuraSystem()
    return _aura
