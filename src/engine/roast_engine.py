from __future__ import annotations

import random
import importlib.util
from pathlib import Path
from typing import Optional

from src.core.logging import get_logger
from src.data.repositories import ClubRepository
from src.domain.models import PlayerIdentity, PlayerMatchStats
from src.squad.registry import SquadRegistry

logger = get_logger(__name__)

# Load phrases from project root
_phrases_path = Path(__file__).resolve().parents[2] / "phrases.py"
if _phrases_path.exists():
    spec = importlib.util.spec_from_file_location("phrases", _phrases_path)
    phrases_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(phrases_module)
    ROAST_PHRASES = getattr(phrases_module, "ROAST_PHRASES", [])
    FRAUD_PHRASES = getattr(phrases_module, "FRAUD_PHRASES", [])
    GHOST_PHRASES = getattr(phrases_module, "GHOST_PHRASES", [])
    MVP_PHRASES = getattr(phrases_module, "MVP_PHRASES", [])
    CARRY_PHRASES = getattr(phrases_module, "CARRY_PHRASES", [])
    BALL_LOSER_PHRASES = getattr(phrases_module, "BALL_LOSER_PHRASES", [])
    COURT_CASE_PHRASES = getattr(phrases_module, "COURT_CASE_PHRASES", [])
    PLAYMAKER_PHRASES = getattr(phrases_module, "PLAYMAKER_PHRASES", [])
    KEEPER_PHRASES = getattr(phrases_module, "KEEPER_PHRASES", [])
    MATCH_SUMMARY_PHRASES = getattr(phrases_module, "MATCH_SUMMARY_PHRASES", [])
    PLAYER_MEMES = getattr(phrases_module, "PLAYER_MEMES", {})
else:
    ROAST_PHRASES = FRAUD_PHRASES = GHOST_PHRASES = MVP_PHRASES = CARRY_PHRASES = []
    BALL_LOSER_PHRASES = COURT_CASE_PHRASES = PLAYMAKER_PHRASES = KEEPER_PHRASES = []
    MATCH_SUMMARY_PHRASES = []
    PLAYER_MEMES = {}


class RoastEngine:
    def __init__(self, repository: ClubRepository, squad: SquadRegistry):
        self.repo = repository
        self.squad = squad

    def _pick(self, category: str, pool: list[str]) -> str:
        recent = self.repo.get_recent_replies(category, limit=20)
        available = [p for p in pool if p not in recent]
        if not available:
            available = pool
        if not available:
            return "..."
        choice = random.choice(available)
        self.repo.record_reply(category, choice)
        return choice

    def _player_meme(self, identity: PlayerIdentity) -> str:
        memes = PLAYER_MEMES.get(identity.nickname, ["اليوم عندنا ملف خاص بهاد اللاعب."])
        return random.choice(memes)

    def mvp_roast(self, player: PlayerMatchStats, identity: PlayerIdentity) -> str:
        return "\n".join([
            self._pick("mvp", MVP_PHRASES),
            f"**{identity.nickname}** | Rating: {player.rating} | G+A: {player.goals}+{player.assists}",
            self._player_meme(identity),
        ])

    def fraud_roast(self, player: PlayerMatchStats, identity: PlayerIdentity) -> str:
        return "\n".join([
            self._pick("fraud", FRAUD_PHRASES),
            f"**{identity.nickname}** | Rating: {player.rating} | Losses: {player.possession_losses}",
            self._player_meme(identity),
        ])

    def ghost_roast(self, player: PlayerMatchStats, identity: PlayerIdentity) -> str:
        return "\n".join([
            self._pick("ghost", GHOST_PHRASES),
            f"**{identity.nickname}** | Minutes: {player.minutes} | Rating: {player.rating}",
            self._player_meme(identity),
        ])

    def carry_roast(self, player: PlayerMatchStats, identity: PlayerIdentity) -> str:
        return "\n".join([
            self._pick("carry", CARRY_PHRASES),
            f"**{identity.nickname}** | G+A: {player.goals}+{player.assists} | Impact: {player.goals + player.assists + player.key_passes}",
            self._player_meme(identity),
        ])

    def ball_loser_roast(self, player: PlayerMatchStats, identity: PlayerIdentity) -> str:
        return "\n".join([
            self._pick("ball_loser", BALL_LOSER_PHRASES),
            f"**{identity.nickname}** | Possession Losses: {player.possession_losses} | Pass%: {player.pass_accuracy}%",
            self._player_meme(identity),
        ])

    def playmaker_roast(self, player: PlayerMatchStats, identity: PlayerIdentity) -> str:
        return "\n".join([
            self._pick("playmaker", PLAYMAKER_PHRASES),
            f"**{identity.nickname}** | Assists: {player.assists} | Key Passes: {player.key_passes} | Pass%: {player.pass_accuracy}%",
            self._player_meme(identity),
        ])

    def sniper_roast(self, player: PlayerMatchStats, identity: PlayerIdentity) -> str:
        efficiency = (player.goals / max(player.shots, 1)) * 100
        return "\n".join([
            f"🎯 **Sniper**",
            f"**{identity.nickname}** | Goals: {player.goals} | Shots: {player.shots} | Efficiency: {efficiency:.1f}%",
            self._player_meme(identity),
        ])

    def who_sold_roast(self, player: PlayerMatchStats, identity: PlayerIdentity) -> str:
        return "\n".join([
            self._pick("fraud", FRAUD_PHRASES),
            f"**{identity.nickname}** | Rating: {player.rating} | Errors: {player.possession_losses + player.yellow_cards + player.red_cards}",
            "هادشي ماشي غلطة، هادا مشروع.",
            self._player_meme(identity),
        ])

    def court_case_roast(self, player: PlayerMatchStats, identity: PlayerIdentity) -> str:
        return "\n".join([
            "⚖️ **المحكمة العسكرية للكرة القدم**",
            f"**المتهم**: {identity.nickname}",
            f"**التُهم**: Rating {player.rating} | Losses {player.possession_losses} | Cards {player.yellow_cards + player.red_cards}",
            self._pick("court", COURT_CASE_PHRASES),
            self._player_meme(identity),
            "الحكم: **مذنب بجميع التهم**",
        ])

    def general_roast(self, player: PlayerMatchStats, identity: PlayerIdentity) -> str:
        return "\n".join([
            self._pick("roast", ROAST_PHRASES),
            f"**{identity.nickname}** | Rating: {player.rating}",
            self._player_meme(identity),
        ])

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

    def match_summary(self, match) -> str:
        base = self._pick("summary", MATCH_SUMMARY_PHRASES)
        result_emoji = "✅" if match.result == "W" else "❌" if match.result == "L" else "➖"
        return f"{result_emoji} {match.score_for}-{match.score_against} vs {match.opponent}\n{base}"
