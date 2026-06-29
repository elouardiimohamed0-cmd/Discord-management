from __future__ import annotations

import random
from typing import Optional

from src.core.logging import get_logger
from src.data.repositories import ClubRepository
from src.domain.models import PlayerIdentity, PlayerMatchStats
from src.squad.registry import SquadRegistry

logger = get_logger(__name__)


class RoastEngine:
    def __init__(self, repository: ClubRepository, squad: SquadRegistry):
        self.repo = repository
        self.squad = squad

    # ---- phrase pools (imported from phrases.py) ----
    from phrases import (
        ROAST_PHRASES,
        FRAUD_PHRASES,
        GHOST_PHRASES,
        MVP_PHRASES,
        CARRY_PHRASES,
        BALL_LOSER_PHRASES,
        COURT_CASE_PHRASES,
        PLAYMAKER_PHRASES,
        KEEPER_PHRASES,
        MATCH_SUMMARY_PHRASES,
        PLAYER_MEMES,
    )

    def _pick(self, category: str, pool: list[str]) -> str:
        recent = self.repo.get_recent_replies(category, limit=20)
        available = [p for p in pool if p not in recent]
        if not available:
            available = pool
        choice = random.choice(available)
        self.repo.record_reply(category, choice)
        return choice

    def _player_meme(self, identity: PlayerIdentity) -> str:
        memes = self.PLAYER_MEMES.get(identity.nickname, ["اليوم عندنا ملف خاص بهاد اللاعب."])
        return random.choice(memes)

    # ---- roast generators ----
    def mvp_roast(self, player: PlayerMatchStats, identity: PlayerIdentity) -> str:
        lines = [
            self._pick("mvp", self.MVP_PHRASES),
            f"**{identity.nickname}** | Rating: {player.rating} | G+A: {player.goals}+{player.assists}",
            self._player_meme(identity),
        ]
        return "\n".join(lines)

    def fraud_roast(self, player: PlayerMatchStats, identity: PlayerIdentity) -> str:
        lines = [
            self._pick("fraud", self.FRAUD_PHRASES),
            f"**{identity.nickname}** | Rating: {player.rating} | Losses: {player.possession_losses}",
            self._player_meme(identity),
        ]
        return "\n".join(lines)

    def ghost_roast(self, player: PlayerMatchStats, identity: PlayerIdentity) -> str:
        lines = [
            self._pick("ghost", self.GHOST_PHRASES),
            f"**{identity.nickname}** | Minutes: {player.minutes} | Rating: {player.rating}",
            self._player_meme(identity),
        ]
        return "\n".join(lines)

    def carry_roast(self, player: PlayerMatchStats, identity: PlayerIdentity) -> str:
        lines = [
            self._pick("carry", self.CARRY_PHRASES),
            f"**{identity.nickname}** | G+A: {player.goals}+{player.assists} | Impact: {player.goals + player.assists + player.key_passes}",
            self._player_meme(identity),
        ]
        return "\n".join(lines)

    def ball_loser_roast(self, player: PlayerMatchStats, identity: PlayerIdentity) -> str:
        lines = [
            self._pick("ball_loser", self.BALL_LOSER_PHRASES),
            f"**{identity.nickname}** | Possession Losses: {player.possession_losses} | Pass%: {player.pass_accuracy}%",
            self._player_meme(identity),
        ]
        return "\n".join(lines)

    def playmaker_roast(self, player: PlayerMatchStats, identity: PlayerIdentity) -> str:
        lines = [
            self._pick("playmaker", self.PLAYMAKER_PHRASES),
            f"**{identity.nickname}** | Assists: {player.assists} | Key Passes: {player.key_passes} | Pass%: {player.pass_accuracy}%",
            self._player_meme(identity),
        ]
        return "\n".join(lines)

    def sniper_roast(self, player: PlayerMatchStats, identity: PlayerIdentity) -> str:
        efficiency = (player.goals / max(player.shots, 1)) * 100
        lines = [
            f"🎯 **Sniper**",
            f"**{identity.nickname}** | Goals: {player.goals} | Shots: {player.shots} | Efficiency: {efficiency:.1f}%",
            self._player_meme(identity),
        ]
        return "\n".join(lines)

    def who_sold_roast(self, player: PlayerMatchStats, identity: PlayerIdentity) -> str:
        lines = [
            self._pick("fraud", self.FRAUD_PHRASES),
            f"**{identity.nickname}** | Rating: {player.rating} | Errors: {player.possession_losses + player.yellow_cards + player.red_cards}",
            "هادشي ماشي غلطة، هادا مشروع.",
            self._player_meme(identity),
        ]
        return "\n".join(lines)

    def court_case_roast(self, player: PlayerMatchStats, identity: PlayerIdentity) -> str:
        lines = [
            "⚖️ **المحكمة العسكرية للكرة القدم**",
            f"**المتهم**: {identity.nickname}",
            f"**التُهم**: Rating {player.rating} | Losses {player.possession_losses} | Cards {player.yellow_cards + player.red_cards}",
            self._pick("court", self.COURT_CASE_PHRASES),
            self._player_meme(identity),
            "الحكم: **مذنب بجميع التهم**",
        ]
        return "\n".join(lines)

    def general_roast(self, player: PlayerMatchStats, identity: PlayerIdentity) -> str:
        lines = [
            self._pick("roast", self.ROAST_PHRASES),
            f"**{identity.nickname}** | Rating: {player.rating}",
            self._player_meme(identity),
        ]
        return "\n".join(lines)

    def compare_roast(self, p1: PlayerMatchStats, id1: PlayerIdentity, p2: PlayerMatchStats, id2: PlayerIdentity) -> str:
        winner = id1.nickname if p1.rating > p2.rating else id2.nickname
        loser = id2.nickname if p1.rating > p2.rating else id1.nickname
        diff = abs(p1.rating - p2.rating)
        return (
            f"⚔️ **{id1.nickname}** vs **{id2.nickname}**\n"
            f"Rating: {p1.rating} vs {p2.rating}\n"
            f"G+A: {p1.goals}+{p1.assists} vs {p2.goals}+{p2.assists}\n"
            f"**{winner}** يتفوق بـ {diff:.1f} نقطة.\n"
            f"**{loser}** خاصو يراجع حساباتو."
        )

    def match_summary(self, match: "Match") -> str:
        base = self._pick("summary", self.MATCH_SUMMARY_PHRASES)
        result_emoji = "✅" if match.result == "W" else "❌" if match.result == "L" else "➖"
        return f"{result_emoji} {match.score_for}-{match.score_against} vs {match.opponent}\n{base}"
