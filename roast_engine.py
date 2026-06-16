"""Roast engine - 99% roast, 1% serious.
Generates aggressive, context-aware roasts for Pro Clubs players.
"""
import random
from typing import Dict, List, Optional
from dataclasses import dataclass

from aura_system import AuraSystem, get_aura_system, AuraTier
from darija_engine import get_darija_engine
from player_mapper import get_mapper

@dataclass
class RoastMetrics:
    """Metrics used to determine roast severity and content."""
    rating: float
    games: int
    goals: int
    assists: int
    tackles: int
    possession_lost: int
    pass_accuracy: float
    win_rate: float
    impact: float
    fraud_score: float
    aura_tier: AuraTier

class RoastEngine:
    """Generates aggressive roasts with Darija flavor."""

    def __init__(self):
        self.aura = get_aura_system()
        self.darija = get_darija_engine()
        self.mapper = get_mapper()
        self.roast_ratio = 0.99  # 99% roast, 1% serious

    def _build_metrics(self, stats: Dict) -> RoastMetrics:
        """Build metrics from raw stats dict."""
        games = max(stats.get("games", 1), 1)
        return RoastMetrics(
            rating=stats.get("rating", 7.0),
            games=games,
            goals=stats.get("goals", 0),
            assists=stats.get("assists", 0),
            tackles=stats.get("tackles", 0),
            possession_lost=stats.get("possession_lost", 0),
            pass_accuracy=stats.get("pass_accuracy", 0.0),
            win_rate=(stats.get("wins", 0) / games) * 100 if games > 0 else 0,
            impact=stats.get("impact", 5.0),
            fraud_score=self.aura.calculate_fraud_score(stats),
            aura_tier=self.aura.determine_tier(stats),
        )

    def _generate_english_roast(self, nickname: str, metrics: RoastMetrics) -> str:
        """Generate English roast component."""
        roasts = []

        if metrics.aura_tier == AuraTier.GHOST:
            roasts.extend([
                f"{nickname} is basically a spectator with a controller.",
                f"{nickname} has {metrics.games} games played. That's not a player, that's a ghost haunting the club.",
                f"Even the bench has more presence than {nickname}.",
                f"{nickname} is so invisible, the opponent team doesn't even mark them.",
            ])

        if metrics.aura_tier == AuraTier.FRAUD:
            roasts.extend([
                f"{nickname} is a certified fraud with a fraud score of {metrics.fraud_score:.0f}.",
                f"{nickname}'s rating of {metrics.rating} is an insult to football.",
                f"The opponent sends thank you letters to {nickname} after every match.",
                f"{nickname} loses possession more times than a broken vending machine.",
                f"If mediocrity was a person, it would be {nickname}.",
            ])

        if metrics.rating < 6.0 and metrics.games > 5:
            roasts.extend([
                f"{nickname}'s rating of {metrics.rating} needs a lawyer to defend it.",
                f"{nickname} plays like their controller is upside down.",
                f"The ball sees {nickname} coming and changes direction.",
                f"{nickname} has more games played than brain cells used.",
            ])

        if metrics.possession_lost > metrics.games * 5:
            roasts.extend([
                f"{nickname} lost possession {metrics.possession_lost} times. Are you playing for us or the opponent?",
                f"{nickname} delivers the ball to the enemy like a paid courier.",
                f"With {metrics.possession_lost} possessions lost, {nickname} is the opponent's best player.",
                f"{nickname} treats the ball like a hot potato dipped in lava.",
            ])

        if metrics.goals == 0 and metrics.games > 10:
            roasts.extend([
                f"{nickname} has 0 goals in {metrics.games} games. Even the goalkeeper scores more.",
                f"{nickname} couldn't score in an empty net with a map and GPS.",
                f"{metrics.games} games, 0 goals. {nickname} is a defensive striker.",
                f"{nickname} shoots like they're allergic to the goal.",
            ])

        if metrics.assists == 0 and metrics.games > 10:
            roasts.extend([
                f"{nickname} has 0 assists in {metrics.games} games. Team play is not in their dictionary.",
                f"{nickname} passes like they're playing solo queue in a team game.",
                f"{metrics.games} games, 0 assists. {nickname} is a one-man disaster.",
            ])

        if metrics.win_rate < 30 and metrics.games > 10:
            roasts.extend([
                f"{nickname} has a {metrics.win_rate:.0f}% win rate. That's not a player, that's a curse.",
                f"When {nickname} joins, the team morale drops faster than their rating.",
                f"{nickname}'s win rate is so low, even the relegation zone is above them.",
            ])

        if metrics.impact < 4.0 and metrics.games > 5:
            roasts.extend([
                f"{nickname}'s impact score of {metrics.impact} is lower than my patience.",
                f"{nickname} impacts the game like a feather impacts a hurricane.",
                f"Impact score {metrics.impact}? {nickname} is just taking up server space.",
            ])

        if not roasts:
            # Generic roast
            roasts = [
                f"{nickname} is the reason we can't have nice things.",
                f"{nickname} plays like they learned football from a YouTube tutorial.",
                f"{nickname} is proof that EA matchmaking has a sense of humor.",
                f"{nickname} makes the team look like a charity case.",
                f"{nickname} is the human equivalent of a loading screen.",
            ]

        return random.choice(roasts)

    def _generate_english_praise(self, nickname: str, metrics: RoastMetrics) -> str:
        """Generate English praise (1% serious)."""
        praises = [
            f"{nickname} is absolutely elite. Rating {metrics.rating}, impact {metrics.impact}.",
            f"{nickname} carries harder than a delivery truck. Respect.",
            f"{nickname} is the backbone of this team. {metrics.goals} goals, {metrics.assists} assists.",
            f"{nickname} plays like a demon. That {metrics.aura_tier.value} aura is deserved.",
            f"{nickname} is the reason we win games. Pure class.",
        ]
        return random.choice(praises)

    def roast(self, ea_name: str, stats: Dict) -> str:
        """Generate a full roast (English + Darija) for a player."""
        nickname = self.mapper.get_nickname(ea_name)
        metrics = self._build_metrics(stats)

        # 99% roast, 1% praise
        if random.random() > self.roast_ratio:
            english = self._generate_english_praise(nickname, metrics)
            darija = self.darija.praise_player(nickname, stats)
        else:
            english = self._generate_english_roast(nickname, metrics)
            darija = self.darija.roast_player(nickname, stats)

        return f"**{english}**

*{darija}*"

    def roast_multiple(self, players: List[tuple]) -> str:
        """Roast multiple players."""
        results = []
        for ea_name, stats in players:
            results.append(self.roast(ea_name, stats))
        return "

---

".join(results)

    def mvp_praise(self, ea_name: str, stats: Dict) -> str:
        """Generate MVP praise (override roast ratio)."""
        nickname = self.mapper.get_nickname(ea_name)
        metrics = self._build_metrics(stats)
        english = self._generate_english_praise(nickname, metrics)
        darija = self.darija.praise_player(nickname, stats)
        return f"**{english}**

*{darija}*"

    def fraud_accusation(self, ea_name: str, stats: Dict) -> str:
        """Generate specific fraud accusation."""
        nickname = self.mapper.get_nickname(ea_name)
        metrics = self._build_metrics(stats)

        english = f"🤡 **FRAUD ALERT: {nickname}** 🤡
Fraud Score: {metrics.fraud_score:.0f}/100
Aura: {metrics.aura_tier.value}"
        darija = self.darija.generate("roast_fraud", nickname=nickname, score=f"{metrics.fraud_score:.0f}")

        return f"{english}

*{darija}*"

    def ghost_accusation(self, ea_name: str, stats: Dict) -> str:
        """Generate ghost accusation."""
        nickname = self.mapper.get_nickname(ea_name)
        games = stats.get("games", 0)

        english = f"👻 **GHOST DETECTED: {nickname}** 👻
Games Played: {games}
Status: Basically doesn't exist"
        darija = self.darija.generate("roast_ghost", nickname=nickname, games=games)

        return f"{english}

*{darija}*"

    def carry_praise(self, ea_name: str, stats: Dict) -> str:
        """Generate carry praise."""
        nickname = self.mapper.get_nickname(ea_name)
        metrics = self._build_metrics(stats)

        english = f"🎯 **CARRY CONFIRMED: {nickname}** 🎯
Impact: {metrics.impact}
Win Rate: {metrics.win_rate:.0f}%
Aura: {metrics.aura_tier.value}"
        darija = self.darija.generate("praise_carry", nickname=nickname, score=f"{metrics.impact}")

        return f"{english}

*{darija}*"

    def who_sold(self, ea_name: str, stats: Dict) -> str:
        """Generate 'who sold' accusation."""
        nickname = self.mapper.get_nickname(ea_name)

        english = f"🚨 **WHO SOLD? {nickname} SOLD.** 🚨"
        darija = self.darija.who_sold(nickname)

        return f"{english}

*{darija}*"

    def stat_of_day(self, ea_name: str, stat_name: str, value, is_roast: bool = True) -> str:
        """Generate stat of the day message."""
        nickname = self.mapper.get_nickname(ea_name)

        if is_roast:
            english = f"📉 **STAT OF THE DAY: {nickname}** 📉
{stat_name}: {value}"
        else:
            english = f"📈 **STAT OF THE DAY: {nickname}** 📈
{stat_name}: {value}"

        darija = self.darija.stat_of_day(nickname, stat_name, value, is_roast)

        return f"{english}

*{darija}*"

# Global instance
_roast = None

def get_roast_engine() -> RoastEngine:
    global _roast
    if _roast is None:
        _roast = RoastEngine()
    return _roast
