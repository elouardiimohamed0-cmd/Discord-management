"""roast_engine.py — 99% roast mode, wraps Phase2 Darija."""
from typing import Dict, Any

try:
    from phase2_darija_engine import Phase2DarijaEngine
    _DARIJA_AVAILABLE = True
except ImportError:
    _DARIJA_AVAILABLE = False


class RoastEngine:
    """Aggressive roast engine. 99% roast, 1% serious."""

    def __init__(self):
        if _DARIJA_AVAILABLE:
            self._darija = Phase2DarijaEngine()
        else:
            self._darija = None

    def _make_stats(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize stats dict for Phase2 engine."""
        return {
            "avg_rating": raw.get("rating", 7.0),
            "goals": raw.get("goals", 0),
            "assists": raw.get("assists", 0),
            "matches": raw.get("games", 0),
            "possession_losses": raw.get("possession_lost", 0),
            "fraud_score": raw.get("fraud_score", 0),
            "impact_score": raw.get("impact", 0),
            "win_rate": raw.get("win_rate", 0),
            "minutes": raw.get("games", 0) * 15,
            "throwing_score": raw.get("fraud_score", 0) / 10,
        }

    def mvp_praise(self, ea_name: str, stats: Dict[str, Any]) -> str:
        if self._darija:
            return self._darija.generate_mvp_praise(ea_name, self._make_stats(stats))
        return f"👑 {ea_name} is the MVP! Monster performance."

    def fraud_accusation(self, ea_name: str, stats: Dict[str, Any]) -> str:
        if self._darija:
            return self._darija.generate_fraud_message(ea_name, self._make_stats(stats))
        return f"🤡 {ea_name} — FRAUD DETECTED. High rating, zero contribution."

    def who_sold(self, ea_name: str, stats: Dict[str, Any]) -> str:
        if self._darija:
            return self._darija.generate_who_sold(ea_name, self._make_stats(stats))
        return f"🛒 {ea_name} sold the match. Guilty of treason."

    def roast(self, ea_name: str, stats: Dict[str, Any]) -> str:
        if self._darija:
            return self._darija.generate_roast(ea_name, self._make_stats(stats), intensity=0.99)
        return f"🔥 {ea_name} — your stats are a disaster."

    def ghost_accusation(self, ea_name: str, stats: Dict[str, Any]) -> str:
        if self._darija:
            return self._darija.generate_ghost_message(ea_name)
        return f"👻 {ea_name} — GHOST. Invisible on the pitch."

    def carry_praise(self, ea_name: str, stats: Dict[str, Any]) -> str:
        if self._darija:
            return self._darija.generate_carry_message(ea_name, self._make_stats(stats))
        return f"🎒 {ea_name} — CARRY CONFIRMED. This team dies without you."


def get_roast_engine() -> RoastEngine:
    return RoastEngine()
