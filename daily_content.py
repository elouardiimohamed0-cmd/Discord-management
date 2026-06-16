"""daily_content.py — 80% bad stat, 20% MVP daily posts."""
import random
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

import discord

try:
    from phase2_daily_engine import Phase2DailyEngine
    _DAILY_AVAILABLE = True
except ImportError:
    _DAILY_AVAILABLE = False


@dataclass
class DailyContent:
    """Content object returned by select_stat_of_day."""
    card_path: Optional[str] = None
    title: str = ""
    description: str = ""
    color: int = 0x95a5a6


class DailySystem:
    """Daily content engine. 80% terrible stat, 20% MVP."""

    def __init__(self):
        if _DAILY_AVAILABLE:
            self._engine = Phase2DailyEngine()
        else:
            self._engine = None

    def select_stat_of_day(self, stats: Dict[str, Dict]) -> DailyContent:
        """Pick a stat for daily post. 80% bad, 20% MVP."""
        if not stats:
            return DailyContent(
                title="📉 No Data",
                description="No player stats available.",
                color=0x95a5a6
            )

        player_list = []
        for ea_name, s in stats.items():
            d = dict(s)
            d["name"] = ea_name
            player_list.append(d)

        if self._engine:
            pick = self._engine.pick_stat_of_day(player_list)
            if pick and pick.get("player"):
                is_bad = pick.get("type") == "bad"
                player = pick["player"]
                p_name = player.get("name", "Unknown")
                stat_name = pick.get("stat_name", "")
                stat_value = pick.get("stat_value", 0)
                from player_mapper import get_mapper
                from roast_engine import get_roast_engine
                nickname = get_mapper().get_nickname(p_name)
                roast = get_roast_engine()
                if is_bad:
                    title = pick.get("title", "📉 STAT OF THE DAY")
                    desc = roast.roast(p_name, player)
                    color = 0xe74c3c
                else:
                    title = pick.get("title", "🔥 MONSTER OF THE DAY")
                    desc = roast.mvp_praise(p_name, player)
                    color = 0xf1c40f
                return DailyContent(
                    card_path=None,
                    title=title,
                    description=f"**{nickname}** | {stat_name}: {stat_value}\n\n{desc}",
                    color=color
                )

        # Fallback
        is_bad = random.random() < 0.80
        ea_name, s = random.choice(list(stats.items()))
        from player_mapper import get_mapper
        nickname = get_mapper().get_nickname(ea_name)
        if is_bad:
            stat_name = random.choice(["possession_lost", "fraud_score", "goals"])
            stat_value = s.get(stat_name, 0)
            title = "📉 STAT OF THE DAY"
            desc = f"**{nickname}** | {stat_name}: {stat_value}\n\n{random.choice([
                'لعبتك بحال شي tutorial ديال كيفاش ما تلعبش.',
                'حتى IA فالcareer mode كتضحك عليك.',
                'الحقيقة كتوجع, و هادا هو الحقيقة ديالك.',
            ])}"
            color = 0xe74c3c
        else:
            title = "🔥 MONSTER OF THE DAY"
            desc = f"**{nickname}** | Impact: {s.get('impact', 0)}\n\nMonster performance! 👑"
            color = 0xf1c40f

        return DailyContent(
            card_path=None,
            title=title,
            description=desc,
            color=color
        )

    def format_discord_message(self, content: DailyContent) -> Dict[str, Any]:
        """Format content for Discord embed."""
        return {
            "title": content.title,
            "description": content.description,
            "color": content.color,
        }


def get_daily_system() -> DailySystem:
    return DailySystem()
