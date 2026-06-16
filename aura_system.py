"""aura_system.py — player aura tier calculation."""
from enum import Enum
from typing import Dict, Any


class AuraTier(Enum):
    S_TIER = "S-Tier"
    A_TIER = "A-Tier"
    B_TIER = "B-Tier"
    CARRY = "Carry"
    FRAUD = "Fraud"
    GHOST = "Ghost"


class AuraSystem:
    """Calculates player aura, overall, and fraud scores."""

    def calculate_overall(self, stats: Dict[str, Any]) -> float:
        """Calculate overall rating from stats."""
        games = max(stats.get("games", 1), 1)
        rating = stats.get("rating", 7.0)
        goals = stats.get("goals", 0)
        assists = stats.get("assists", 0)
        impact = stats.get("impact", 5.0)
        win_rate = stats.get("win_rate", 0)
        overall = (
            rating * 8 +
            (goals / games) * 15 +
            (assists / games) * 10 +
            impact * 3 +
            win_rate * 0.2
        )
        return min(99, max(60, round(overall, 1)))

    def determine_tier(self, stats: Dict[str, Any]) -> AuraTier:
        """Determine aura tier from stats."""
        games = stats.get("games", 0)
        if games == 0:
            return AuraTier.GHOST
        if games < 3:
            return AuraTier.GHOST

        fraud = self.calculate_fraud_score(stats)
        if fraud > 60:
            return AuraTier.FRAUD

        overall = self.calculate_overall(stats)
        impact = stats.get("impact", 5.0)
        win_rate = stats.get("win_rate", 0)

        if overall >= 90 and impact >= 8 and win_rate >= 70:
            return AuraTier.S_TIER
        if overall >= 85 and impact >= 7 and win_rate >= 60:
            return AuraTier.A_TIER
        if impact >= 7 and win_rate >= 65:
            return AuraTier.CARRY
        if overall >= 75:
            return AuraTier.A_TIER
        return AuraTier.B_TIER

    def calculate_fraud_score(self, stats: Dict[str, Any]) -> float:
        """Calculate fraud score: high rating but low contribution."""
        games = max(stats.get("games", 1), 1)
        rating = stats.get("rating", 7.0)
        goals = stats.get("goals", 0)
        assists = stats.get("assists", 0)
        impact = stats.get("impact", 5.0)
        possession_lost = stats.get("possession_lost", 0)

        expected_goals = (rating - 5) * games * 0.3
        expected_assists = (rating - 5) * games * 0.2
        expected_impact = (rating - 5) * 1.5

        goal_deficit = max(0, expected_goals - goals)
        assist_deficit = max(0, expected_assists - assists)
        impact_deficit = max(0, expected_impact - impact)

        fraud = (
            goal_deficit * 3 +
            assist_deficit * 2 +
            impact_deficit * 5 +
            possession_lost * 0.5
        ) / max(games, 1)

        return min(100, round(fraud, 1))

    def get_tier_color(self, tier: AuraTier) -> int:
        colors = {
            AuraTier.S_TIER: 0x9b59b6,
            AuraTier.A_TIER: 0xf1c40f,
            AuraTier.B_TIER: 0x2ecc71,
            AuraTier.CARRY: 0x3498db,
            AuraTier.FRAUD: 0xe74c3c,
            AuraTier.GHOST: 0x95a5a6,
        }
        return colors.get(tier, 0x95a5a6)


def get_aura_system() -> AuraSystem:
    return AuraSystem()
