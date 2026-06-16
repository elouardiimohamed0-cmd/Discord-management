import random
from typing import List, Dict, Optional
from models import PlayerStats, ClubStats
from phrases import ROASTS, FRAUDS, GHOSTS, CARRIES, MVPS

class DarijaEngine:
    """
    PHASE 2.2 — Casa Street Personality
    Simple. Short. Funny. No AI nonsense.
    """

    PERSONALITIES = {
        "casablanca": {"roast_freq": 0.99},
        "analyst": {"roast_freq": 0.50},
        "toxic": {"roast_freq": 0.99},
        "coach": {"roast_freq": 0.30},
        "commentator": {"roast_freq": 0.70},
        "cafeteria": {"roast_freq": 0.85},
    }

    def __init__(self, personality: str = "casablanca"):
        self.personality = personality if personality in self.PERSONALITIES else "casablanca"
        self._used_phrases = set()

    def set_personality(self, p: str):
        if p in self.PERSONALITIES:
            self.personality = p

    def _pick(self, phrases: List[str]) -> str:
        """Pick random phrase, avoid recent repeats."""
        available = [p for p in phrases if p not in self._used_phrases]
        if not available:
            self._used_phrases.clear()
            available = phrases
        chosen = random.choice(available)
        self._used_phrases.add(chosen)
        if len(self._used_phrases) > 20:
            self._used_phrases.pop()
        return chosen

    def _format(self, template: str, player: PlayerStats) -> str:
        return template.format(name=player.name, rating=round(player.rating_pg, 1))

    def roast(self, player: PlayerStats, position: str = "CM") -> str:
        """Generate a roast with embedded stats."""
        phrase = self._pick(ROASTS)
        text = self._format(phrase, player)
        # Add stats inline
        stats = []
        if player.rating_pg < 6.0:
            stats.append(f"{round(player.rating_pg, 1)} rating.")
        if player.possession_losses > 10:
            stats.append(f"{player.possession_losses} possession losses.")
        if player.goals == 0 and player.games > 3:
            stats.append(f"0 goals.")
        if player.assists == 0 and player.games > 3:
            stats.append(f"0 assists.")
        if player.pass_accuracy < 70:
            stats.append(f"{round(player.pass_accuracy, 1)}% pass accuracy.")
        if stats:
            text += "\n\n" + "\n".join(stats)
        return text

    def praise(self, player: PlayerStats, position: str = "CM") -> str:
        """Generate praise (rare)."""
        phrase = self._pick(CARRIES)
        return self._format(phrase, player)

    def generate(self, player: PlayerStats, position: str = "CM", roast_freq: float = 0.95) -> str:
        if random.random() < roast_freq:
            return self.roast(player, position)
        return self.praise(player, position)

    def compare(self, p1: PlayerStats, p2: PlayerStats) -> str:
        winner = p1 if p1.impact_score > p2.impact_score else p2
        loser = p2 if winner == p1 else p1
        return f"{winner.name} كيدر {loser.name} فجيبو ـ Impact {winner.impact_score} vs {loser.impact_score}."

    def match_summary(self, club, motm: PlayerStats) -> str:
        return f"الفوز {club.wins}، الخسارة {club.losses}. MOTM: {motm.name} بـ Impact {round(motm.impact_score, 1)}."

    def banter(self) -> str:
        return random.choice(ROASTS)

    def drama(self, players: List[str]) -> str:
        if len(players) < 2:
            players = ["Player1", "Player2"]
        p1, p2 = players[0], players[1]
        return f"الكافيتيريا كتهضر: {p1} و {p2} كيتخاصمو فالويس شات."

    def meme(self, player: str) -> str:
        return f"{player}: أنا كندافع ـ also {player}: 0 tackles."

    def transfer(self, player: str) -> str:
        return f"BREAKING: {player} غادي ينتقل لـ PSG ب 200M. صافي، هادشي رسمي."

    def predict(self, players: List[str]) -> str:
        if len(players) < 2:
            players = ["Player1", "Player2"]
        p1, p2 = players[0], players[1]
        return f"ال prediction ديالي: غادي نخسرو 3-1 و {p1} غادي يضيع penalty."
