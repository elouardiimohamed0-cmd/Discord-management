"""
phase2_daily_engine.py
Stat of the Day system. 80% terrible stat, 20% MVP.
"""
import random
from typing import Dict, Any, List, Optional

class Phase2DailyEngine:
    """Daily content engine with 80/20 probability split."""

    @staticmethod
    def pick_stat_of_the_day(players: List[Dict]) -> Optional[Dict]:
        """Pick a stat for daily post. 80% bad, 20% MVP."""
        if not players:
            return None
        is_bad = random.random() < 0.80
        if is_bad:
            return Phase2DailyEngine._pick_bad_stat(players)
        else:
            return Phase2DailyEngine._pick_mvp_stat(players)

    @staticmethod
    def _pick_bad_stat(players: List[Dict]) -> Dict:
        """Pick the worst stat from a random player."""
        candidates = [p for p in players if p.get("games", 0) > 0]
        if not candidates:
            return {}
        player = random.choice(candidates)
        terrible_stats = [
            ("Possession Lost", player.get("possession_losses", 0)),
            ("Fraud Score", round(player.get("throwing_score", 0) * 10, 1)),
            ("Goals", player.get("goals", 0)),
            ("Rating", player.get("rating", 0)),
            ("Assists", player.get("assists", 0)),
        ]
        stat_name, stat_value = random.choice(terrible_stats)
        return {
            "type": "bad",
            "player": player,
            "stat_name": stat_name,
            "stat_value": stat_value,
            "title": "📉 STAT OF THE DAY",
        }

    @staticmethod
    def _pick_mvp_stat(players: List[Dict]) -> Dict:
        """Pick the best player for MVP edition."""
        if not players:
            return {}
        mvp = max(players, key=lambda p: p.get("impact_score", 0))
        return {
            "type": "mvp",
            "player": mvp,
            "stat_name": "Impact Score",
            "stat_value": mvp.get("impact_score", 0),
            "title": "🔥 MONSTER OF THE DAY",
        }
