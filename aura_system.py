"""
phase2_aura_system.py
Player Aura Tier calculation based on real stats.
"""
from typing import Dict, Any

class AuraSystem:
    """Determine player aura tier based on performance metrics."""

    TIERS = ["S-Tier", "A-Tier", "B-Tier", "Carry", "Fraud", "Ghost"]

    DESCRIPTIONS = {
        "S-Tier": "👾 MONSTER - Unstoppable force",
        "A-Tier": "🥇 ELITE - Top tier performer",
        "B-Tier": "🍀 SOLID - Reliable but not spectacular",
        "Carry": "🎒 CARRY - Carries the team on their back",
        "Fraud": "🤡 FRAUD - High rating, zero contribution",
        "Ghost": "👻 GHOST - Invisible on the pitch",
    }

    @classmethod
    def calculate_aura(cls, stats: Dict[str, Any]) -> str:
        """Calculate aura based on performance metrics."""
        matches = stats.get("matches", 0) or stats.get("games", 0)
        if matches == 0:
            return "Ghost"
        impact = stats.get("impact_score", 0)
        fraud = stats.get("fraud_score", stats.get("throwing_score", 0) * 10)
        win_rate = stats.get("win_rate", 0)
        avg_rating = stats.get("avg_rating", stats.get("rating", 0))
        if matches < 3 or stats.get("minutes", 999) < 60:
            return "Ghost"
        if fraud > 60 and avg_rating > 7.0:
            return "Fraud"
        if impact > 8 and win_rate > 70 and avg_rating > 8.0:
            return "S-Tier"
        if impact > 6 and win_rate > 65:
            return "Carry"
        if impact > 5 and win_rate > 55 and avg_rating > 7.0:
            return "A-Tier"
        return "B-Tier"

    @classmethod
    def get_description(cls, aura: str) -> str:
        return cls.DESCRIPTIONS.get(aura, "Unknown")
