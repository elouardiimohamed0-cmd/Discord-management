import random
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from models import PlayerStats, ClubStats
from phrases import (
    ROAST_PHRASES, FRAUD_PHRASES, GHOST_PHRASES, MVP_PHRASES,
    CARRY_PHRASES, BALL_LOSER_PHRASES, COURT_CASE_PHRASES,
    PLAYMAKER_PHRASES, KEEPER_PHRASES, MATCH_SUMMARY_PHRASES,
    PLAYER_MEMES, random_phrase, random_player_meme
)


class DarijaEngine:
    """
    PHASE 3 — Roast First Bot
    =========================
    The bot is NOT a stats bot.
    The bot is NOT an analyst.
    The bot is a teammate that EXPOSES teammates using REAL DATA.

    Design: banter first, stats second.
    99% roast frequency.
    Tracks used phrases to avoid repetition.
    """

    PERSONALITIES = {
        "casablanca": {"roast_freq": 0.99},
        "analyst": {"roast_freq": 0.50},
        "toxic": {"roast_freq": 0.99},
        "coach": {"roast_freq": 0.30},
        "commentator": {"roast_freq": 0.70},
        "cafeteria": {"roast_freq": 0.85},
    }

    # Map player names to meme nicknames (case-insensitive)
    MEME_MAP = {
        "dictator": "Dictator",
        "shark": "Shark",
        "kira": "Kira",
        "le7ya": "Le7ya",
        "marrakchi": "Marrakchi",
        "modamir": "Modamir",
        "moul l7anot": "Moul_l7anot",
        "moul_l7anot": "Moul_l7anot",
        "9ahba south africa": "9ahba",
        "brave": "Brave",
        "shawarmista": "Shawarmista",
    }

    def __init__(self, personality: str = "casablanca"):
        self.personality = personality if personality in self.PERSONALITIES else "casablanca"
        self._used: Dict[str, List[str]] = {
            "roast": [], "fraud": [], "ghost": [], "mvp": [],
            "carry": [], "ball_loser": [], "court": [],
            "playmaker": [], "keeper": [], "summary": [],
        }
        self._max_history = 15

    def set_personality(self, p: str):
        if p in self.PERSONALITIES:
            self.personality = p

    # ───────────────────────── helpers ─────────────────────────

    def _pick(self, phrases: List[str], category: str) -> str:
        """Pick random phrase, avoid recent repeats."""
        used = self._used[category]
        available = [p for p in phrases if p not in used]
        if not available:
            used.clear()
            available = phrases
        chosen = random.choice(available)
        used.append(chosen)
        if len(used) > self._max_history:
            used.pop(0)
        return chosen

    def _format(self, template: str, player: PlayerStats) -> str:
        return template.format(
            name=player.name,
            rating=round(player.rating_pg, 1),
            goals=player.goals,
            assists=player.assists,
            games=player.games,
        )

    def _get_meme(self, player_name: str) -> Optional[str]:
        key = player_name.strip().lower()
        nickname = self.MEME_MAP.get(key)
        if nickname:
            return random_player_meme(nickname)
        return None

    def _roast_stats(self, player: PlayerStats) -> List[str]:
        """Build evidence lines from real stats."""
        lines = []
        if player.rating_pg < 6.0:
            lines.append(f"{round(player.rating_pg, 1)} rating.")
        if player.possession_losses > 10:
            lines.append(f"{player.possession_losses} possession losses.")
        if player.goals == 0 and player.games > 2:
            lines.append("0 goals.")
        if player.assists == 0 and player.games > 2:
            lines.append("0 assists.")
        if player.pass_accuracy < 70:
            lines.append(f"{round(player.pass_accuracy, 1)}% pass accuracy.")
        if player.tackles < 1 and player.games > 2:
            lines.append("0 tackles.")
        return lines

    def _praise_stats(self, player: PlayerStats) -> List[str]:
        """Build praise evidence lines."""
        lines = []
        if player.rating_pg >= 7.5:
            lines.append(f"{round(player.rating_pg, 1)} rating.")
        if player.goals > 0:
            lines.append(f"{player.goals} goals.")
        if player.assists > 0:
            lines.append(f"{player.assists} assists.")
        if player.pass_accuracy >= 85:
            lines.append(f"{round(player.pass_accuracy, 1)}% pass accuracy.")
        if player.tackles > 5:
            lines.append(f"{player.tackles} tackles.")
        return lines

    def _build_response(self, phrase: str, player: PlayerStats,
                        stats_fn, category: str) -> str:
        """Roast-first builder: banter → meme → stats."""
        text = self._format(phrase, player)

        # Player meme
        meme = self._get_meme(player.name)
        if meme:
            text += f"\n\n{meme}"

        # Evidence
        stats = stats_fn(player)
        if stats:
            text += "\n\n" + "\n".join(stats)

        return text

    # ───────────────────────── core methods ─────────────────────────

    def roast(self, player: PlayerStats, position: str = "CM") -> str:
        phrase = self._pick(ROAST_PHRASES, "roast")
        return self._build_response(phrase, player, self._roast_stats, "roast")

    def praise(self, player: PlayerStats, position: str = "CM") -> str:
        phrase = self._pick(CARRY_PHRASES, "carry")
        return self._build_response(phrase, player, self._praise_stats, "carry")

    def generate(self, player: PlayerStats, position: str = "CM", roast_freq: float = 0.95) -> str:
        if random.random() < roast_freq:
            return self.roast(player, position)
        return self.praise(player, position)

    # ───────────────────────── category roasts ─────────────────────────

    def fraud(self, player: PlayerStats) -> str:
        """Fraud of the match."""
        phrase = self._pick(FRAUD_PHRASES, "fraud")
        return self._build_response(phrase, player, self._roast_stats, "fraud")

    def ghost(self, player: PlayerStats) -> str:
        """Ghost performance."""
        phrase = self._pick(GHOST_PHRASES, "ghost")
        return self._build_response(phrase, player, self._roast_stats, "ghost")

    def ball_loser(self, player: PlayerStats) -> str:
        """Most possession lost."""
        phrase = self._pick(BALL_LOSER_PHRASES, "ball_loser")
        lines = [f"{player.possession_losses} possession losses."]
        if player.pass_accuracy < 70:
            lines.append(f"{round(player.pass_accuracy, 1)}% pass accuracy.")
        text = self._format(phrase, player)
        meme = self._get_meme(player.name)
        if meme:
            text += f"\n\n{meme}"
        text += "\n\n" + "\n".join(lines)
        return text

    def court_case(self, player: PlayerStats) -> str:
        """Put a player on trial."""
        phrase = self._pick(COURT_CASE_PHRASES, "court")
        text = self._format(phrase, player)
        text += "\n\n**التهم:**"
        charges = []
        if player.rating_pg < 6.0:
            charges.append(f"• Rating {round(player.rating_pg, 1)} (الحد الأدنى 6.0)")
        if player.possession_losses > 10:
            charges.append(f"• {player.possession_losses} possession losses")
        if player.goals == 0 and player.games > 2:
            charges.append("• 0 goals")
        if player.assists == 0 and player.games > 2:
            charges.append("• 0 assists")
        if player.pass_accuracy < 70:
            charges.append(f"• {round(player.pass_accuracy, 1)}% pass accuracy")
        if not charges:
            charges.append("• ما كاين حتى تهمة، الحالة براءة.")
        text += "\n" + "\n".join(charges)
        text += "\n\n**الحكم:** "
        if len(charges) >= 3:
            text += "مذنب. ⚖️"
        elif len(charges) >= 2:
            text += "مذنب بشكل جزئي. ⚠️"
        else:
            text += "بريء. ✅"
        return text

    def mvp(self, player: PlayerStats) -> str:
        """MVP announcement."""
        phrase = self._pick(MVP_PHRASES, "mvp")
        return self._build_response(phrase, player, self._praise_stats, "mvp")

    def carry(self, player: PlayerStats) -> str:
        """Carry of the match."""
        phrase = self._pick(CARRY_PHRASES, "carry")
        return self._build_response(phrase, player, self._praise_stats, "carry")

    def playmaker(self, player: PlayerStats) -> str:
        """Best playmaker."""
        phrase = self._pick(PLAYMAKER_PHRASES, "playmaker")
        return self._build_response(phrase, player, self._praise_stats, "playmaker")

    def keeper(self, player: PlayerStats) -> str:
        """Best keeper."""
        phrase = self._pick(KEEPER_PHRASES, "keeper")
        return self._build_response(phrase, player, self._praise_stats, "keeper")

    # ───────────────────────── multi-player ─────────────────────────

    def compare(self, p1: PlayerStats, p2: PlayerStats) -> str:
        """Compare two players, end with roast."""
        winner = p1 if p1.impact_score > p2.impact_score else p2
        loser = p2 if winner == p1 else p1
        diff = round(abs(p1.impact_score - p2.impact_score), 1)

        text = f"**{winner.name}** vs **{loser.name}**\n\n"
        text += f"{winner.name}: {round(winner.impact_score, 1)} impact\n"
        text += f"{loser.name}: {round(loser.impact_score, 1)} impact\n\n"

        # Winner praise
        wp = self._pick(MVP_PHRASES, "mvp")
        text += wp.format(name=winner.name) + "\n"

        # Loser roast
        rp = self._pick(ROAST_PHRASES, "roast")
        text += rp.format(name=loser.name) + "\n"

        text += f"\nالفرق: {diff} impact points."
        return text

    def serial_offender(self, player: PlayerStats, bad_games: int = 0) -> str:
        """Player with repeated bad performances."""
        phrase = self._pick(FRAUD_PHRASES, "fraud")
        text = self._format(phrase, player)
        text += f"\n\n{player.name} كيضيع الكرة فـ {bad_games} ماتشات متتالية."
        text += "\nهادشي ماشي صدفة، هادا serial offender."
        return text

    def hall_of_shame(self, players: List[PlayerStats]) -> str:
        """Worst performances ever."""
        valid = [p for p in players if p.games > 0 and p.rating_pg > 0]
        if not valid:
            return "🏛️ **Hall of Shame**

ما كاين حتى لاعبين باش نديرو Hall of Shame."

        sorted_players = sorted(valid, key=lambda p: p.rating_pg)
        worst = sorted_players[:3]
        text = "🏛️ **Hall of Shame**

"
        for i, p in enumerate(worst, 1):
            rp = self._pick(ROAST_PHRASES, "roast")
            text += f"{i}. {rp.format(name=p.name)}
"
            text += f"   Rating: {round(p.rating_pg, 1)} | Possession lost: {p.possession_losses} | Games: {p.games}

"
        return text

    # ───────────────────────── match report ─────────────────────────

    def match_report(self, result: str, players: List[PlayerStats]) -> str:
        """Full match report with all categories."""
        text = self._pick(MATCH_SUMMARY_PHRASES, "summary") + "\n\n"
        text += f"**النتيجة:** {result}\n\n"

        if not players:
            return text

        # MVP
        mvp = max(players, key=lambda p: p.impact_score)
        text += f"🔥 **MVP:** {mvp.name} ({round(mvp.impact_score, 1)} impact)\n"
        mp = self._pick(MVP_PHRASES, "mvp")
        text += mp.format(name=mvp.name) + "\n\n"

        # Fraud
        fraud = min(players, key=lambda p: p.rating_pg)
        text += f"🚨 **Fraud of the Match:** {fraud.name} ({round(fraud.rating_pg, 1)} rating)\n"
        fp = self._pick(FRAUD_PHRASES, "fraud")
        text += fp.format(name=fraud.name) + "\n\n"

        # Ghost
        ghost = min(players, key=lambda p: p.impact_score)
        if ghost != fraud:
            text += f"👻 **Ghost:** {ghost.name} ({round(ghost.impact_score, 1)} impact)\n"
            gp = self._pick(GHOST_PHRASES, "ghost")
            text += gp.format(name=ghost.name) + "\n\n"

        # Ball Loser
        bl = max(players, key=lambda p: p.possession_losses)
        text += f"⚽ **Ball Loser:** {bl.name} ({bl.possession_losses} losses)\n"
        bp = self._pick(BALL_LOSER_PHRASES, "ball_loser")
        text += bp.format(name=bl.name) + "\n\n"

        # Carry
        carry = max(players, key=lambda p: p.impact_score)
        if carry != mvp:
            text += f"🎒 **Carry:** {carry.name} ({round(carry.impact_score, 1)} impact)\n"
            cp = self._pick(CARRY_PHRASES, "carry")
            text += cp.format(name=carry.name) + "\n\n"

        # Best Passer
        passer = max(players, key=lambda p: p.pass_accuracy)
        text += f"🎯 **Best Passer:** {passer.name} ({round(passer.pass_accuracy, 1)}%)\n"
        pp = self._pick(PLAYMAKER_PHRASES, "playmaker")
        text += pp.format(name=passer.name) + "\n\n"

        # Funniest stat
        text += "**🤣 Funniest Stat:**\n"
        funniest = min(players, key=lambda p: p.rating_pg)
        text += f"{funniest.name} — {round(funniest.rating_pg, 1)} rating فـ {funniest.games} ماتشات.\n"

        return text

    # ───────────────────────── legacy / misc ─────────────────────────

    def match_summary(self, club: ClubStats, motm: PlayerStats) -> str:
        text = f"الفوز {club.wins}، الخسارة {club.losses}. MOTM: {motm.name} بـ Impact {round(motm.impact_score, 1)}."
        return text

    def banter(self) -> str:
        return self._pick(ROAST_PHRASES, "roast")

    def drama(self, players: List[str]) -> str:
        if len(players) < 2:
            players = ["Player1", "Player2"]
        p1, p2 = players[0], players[1]
        return f"الكافيتيريا كتهضر: {p1} و {p2} كيتخاصمو فالويس شات."

    def meme(self, player: str) -> str:
        return f"{player}: أنا كندافع — also {player}: 0 tackles."

    def transfer(self, player: str) -> str:
        return f"BREAKING: {player} غادي ينتقل لـ PSG ب 200M. صافي، هادشي رسمي."

    def predict(self, players: List[str]) -> str:
        if len(players) < 2:
            players = ["Player1", "Player2"]
        p1, p2 = players[0], players[1]
        return f"ال prediction ديالي: غادي نخسرو 3-1 و {p1} غادي يضيع penalty."
