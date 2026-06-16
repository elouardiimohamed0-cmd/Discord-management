"""
aura_system.py
Bridges to phase2_aura_system.py.
Provides get_aura_system() and AuraTier for backward compatibility.
"""
from enum import Enum
from typing import Dict, Any

# Import the real system from phase2
try:
    from phase2_aura_system import AuraSystem
except ImportError:
    # Fallback if phase2 not available yet
    class AuraSystem:
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


class AuraTier(Enum):
    """Enum for aura tiers."""
    S_TIER = "S-Tier"
    A_TIER = "A-Tier"
    B_TIER = "B-Tier"
    CARRY = "Carry"
    FRAUD = "Fraud"
    GHOST = "Ghost"


class AuraSystemWrapper:
    """Wrapper that provides the interface bot.py expects."""
    
    def __init__(self):
        self._system = AuraSystem()
    
    def calculate_aura(self, stats: Dict[str, Any]) -> str:
        return self._system.calculate_aura(stats)
    
    def get_description(self, aura: str) -> str:
        return self._system.get_description(aura)
    
    def get_tier_color(self, aura: str) -> int:
        """Return Discord color hex for aura."""
        colors = {
            "S-Tier": 0x9b59b6,   # Purple
            "A-Tier": 0xf1c40f,   # Gold
            "B-Tier": 0x2ecc71,   # Green
            "Carry": 0x3498db,    # Blue
            "Fraud": 0xe74c3c,    # Red
            "Ghost": 0x95a5a6,    # Grey
        }
        return colors.get(aura, 0x95a5a6)


def get_aura_system() -> AuraSystemWrapper:
    """Factory function — returns aura system instance."""
    return AuraSystemWrapper()


# Also export the class directly for direct use
__all__ = ["get_aura_system", "AuraTier", "AuraSystemWrapper", "AuraSystem"]
