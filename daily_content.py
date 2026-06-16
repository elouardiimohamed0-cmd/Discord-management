"""Daily content system - Stat of the Day and automated posting."""
import random
import asyncio
from datetime import datetime, time
from typing import Dict, Optional, List
from dataclasses import dataclass

import config
from aura_system import get_aura_system, AuraTier
from roast_engine import get_roast_engine
from card_generator import get_card_generator
from player_mapper import get_mapper

@dataclass
class DailyContent:
    type: str  # "roast" or "mvp"
    player_ea_name: str
    stat_name: str
    stat_value: float
    message: str
    card_path: Optional[str] = None

class DailyContentSystem:
    """Manages daily stat of the day and automated posting."""

    def __init__(self):
        self.aura = get_aura_system()
        self.roast = get_roast_engine()
        self.cards = get_card_generator()
        self.mapper = get_mapper()
        self.roast_prob = config.STAT_OF_DAY_ROAST_PROB
        self.mvp_prob = config.STAT_OF_DAY_MVP_PROB

    def select_stat_of_day(self, all_players: Dict[str, Dict]) -> DailyContent:
        """Select a stat of the day."""
        is_roast = random.random() < self.roast_prob

        if is_roast:
            return self._select_roast(all_players)
        return self._select_mvp(all_players)

    def _select_roast(self, all_players: Dict[str, Dict]) -> DailyContent:
        """Select a terrible stat to roast."""
        candidates = []

        for ea_name, stats in all_players.items():
            games = stats.get("games", 0)
            if games < 2:
                continue

            # Find worst stats
            rating = stats.get("rating", 10)
            goals = stats.get("goals", 0)
            assists = stats.get("assists", 0)
            poss_lost = stats.get("possession_lost", 0)
            pass_acc = stats.get("pass_accuracy", 100)
            impact = stats.get("impact", 10)

            if rating < 6.0:
                candidates.append((ea_name, "rating", rating, rating))
            if goals == 0 and games > 5:
                candidates.append((ea_name, "goals", goals, 100))
            if assists == 0 and games > 5:
                candidates.append((ea_name, "assists", assists, 100))
            if poss_lost > games * 5:
                candidates.append((ea_name, "possession_lost", poss_lost, poss_lost))
            if pass_acc < 60 and games > 5:
                candidates.append((ea_name, "pass_accuracy", pass_acc, 100 - pass_acc))
            if impact < 4.0 and games > 5:
                candidates.append((ea_name, "impact", impact, 10 - impact))

        if not candidates:
            # Fallback: pick random player with low games
            for ea_name, stats in all_players.items():
                games = stats.get("games", 0)
                if games > 0:
                    candidates.append((ea_name, "games", games, 100 - games))
                    break

        if not candidates:
            # Ultimate fallback
            first = list(all_players.keys())[0]
            candidates.append((first, "rating", all_players[first].get("rating", 5), 5))

        # Weight by badness (higher score = worse)
        total_weight = sum(c[3] for c in candidates)
        pick = random.uniform(0, total_weight)
        current = 0
        for c in candidates:
            current += c[3]
            if current >= pick:
                selected = c
                break
        else:
            selected = candidates[0]

        ea_name, stat_name, value, _ = selected
        nickname = self.mapper.get_nickname(ea_name)

        message = self.roast.stat_of_day(ea_name, stat_name, value, is_roast=True)

        # Generate card
        card = self.cards.generate_fraud_card(ea_name, all_players[ea_name])
        card_path = f"/tmp/daily_roast_{ea_name}.png"
        card.save(card_path, "PNG")

        return DailyContent(
            type="roast",
            player_ea_name=ea_name,
            stat_name=stat_name,
            stat_value=value,
            message=message,
            card_path=card_path,
        )

    def _select_mvp(self, all_players: Dict[str, Dict]) -> DailyContent:
        """Select an MVP stat to praise."""
        candidates = []

        for ea_name, stats in all_players.items():
            games = stats.get("games", 0)
            if games < 3:
                continue

            rating = stats.get("rating", 0)
            goals = stats.get("goals", 0)
            assists = stats.get("assists", 0)
            impact = stats.get("impact", 0)
            wins = stats.get("wins", 0)
            wr = (wins / games) * 100 if games > 0 else 0

            overall = self.aura.calculate_overall(stats)

            if overall >= 85:
                candidates.append((ea_name, "overall", overall, overall))
            if rating >= 8.5:
                candidates.append((ea_name, "rating", rating, rating * 10))
            if goals > games * 1.5:
                candidates.append((ea_name, "goals", goals, goals * 2))
            if assists > games * 1.2:
                candidates.append((ea_name, "assists", assists, assists * 2))
            if impact >= 8.0:
                candidates.append((ea_name, "impact", impact, impact * 10))
            if wr >= 70:
                candidates.append((ea_name, "win_rate", wr, wr))

        if not candidates:
            # Fallback: best overall
            best = None
            best_score = -1
            for ea_name, stats in all_players.items():
                games = stats.get("games", 0)
                if games >= 3:
                    overall = self.aura.calculate_overall(stats)
                    if overall > best_score:
                        best_score = overall
                        best = (ea_name, "overall", overall, overall)
            if best:
                candidates.append(best)

        if not candidates:
            first = list(all_players.keys())[0]
            candidates.append((first, "rating", all_players[first].get("rating", 7), 7))

        # Weight by goodness
        total_weight = sum(c[3] for c in candidates)
        pick = random.uniform(0, total_weight)
        current = 0
        for c in candidates:
            current += c[3]
            if current >= pick:
                selected = c
                break
        else:
            selected = candidates[0]

        ea_name, stat_name, value, _ = selected
        nickname = self.mapper.get_nickname(ea_name)

        message = self.roast.stat_of_day(ea_name, stat_name, value, is_roast=False)

        # Generate MVP card
        card = self.cards.generate_mvp_card(ea_name, all_players[ea_name])
        card_path = f"/tmp/daily_mvp_{ea_name}.png"
        card.save(card_path, "PNG")

        return DailyContent(
            type="mvp",
            player_ea_name=ea_name,
            stat_name=stat_name,
            stat_value=value,
            message=message,
            card_path=card_path,
        )

    def format_discord_message(self, content: DailyContent) -> Dict:
        """Format content for Discord message."""
        nickname = self.mapper.get_nickname(content.player_ea_name)

        if content.type == "roast":
            title = f"📉 STAT OF THE DAY - {nickname}"
            color = 0xFF0000
        else:
            title = f"📈 STAT OF THE DAY - {nickname}"
            color = 0x00FF00

        return {
            "title": title,
            "description": content.message,
            "color": color,
            "image": content.card_path,
            "timestamp": datetime.utcnow().isoformat(),
        }

# Global instance
_daily = None

def get_daily_system() -> DailyContentSystem:
    global _daily
    if _daily is None:
        _daily = DailyContentSystem()
    return _daily
