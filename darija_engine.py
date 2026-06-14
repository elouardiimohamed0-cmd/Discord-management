"""
Rachad L3ERGONI Bot — Darija Engine v3
Native Casablanca cyber-café gamer. Code-switches Darija/French.
Every roast cites real stats. Never generic.
"""

import json
import random
from typing import Dict, List, Optional, Tuple
from pathlib import Path


# ── Vocabulary Layers ───────────────────────────────────────────────────────

DARIJA_EXPRESSIONS = {
    "openers": [
        "wa 3ziz", "hakda", "b7al chi", "chi", "walo", "z3ma", "safi", "daba",
        "yallah", "daba daba", "wa 3ziz 3liya", "hakda rak", "b7al chi wa7ed",
    ],
    "closers": [
        "safi", "walo", "z3ma", "hakda", "daba", "yallah", "bon courage",
        "c'est fini", "delete game", "trash", "garbage", "chi m3a9ed",
    ],
    "disappointment": [
        "lla... c'est fini.", "bon courage.", "trash.", "garbage.", "delete game.",
        "walo. safi.", "chi m3a9ed.", "b7al chi hwayej.", "khawya l3ba.",
        "m3a9ed l3ba.", "l3ba khawya.", "safi walo.", "z3ma... walo.",
        "hakda. b7al hakda.", "daba daba. walo.", "yallah. walo.",
    ],
    "laughter": [
        "hahahaha", "hahahaha chi m3a9ed", "hahahaha walo", "hahahaha z3ma",
        "hahahaha safi", "hahahaha l3ba", "hahahaha l7wayej", "hahahaha khawya",
        "hahahaha m3a9ed", "hahahaha delete game", "hahahaha trash",
    ],
    "shock": [
        "wallah!", "wallah chi m3a9ed!", "wallah l3ba khawya!", "wallah walo!",
        "wallah delete game!", "wallah trash!", "wallah garbage!", "wallah lla...!",
    ],
    "thinking": [
        "z3ma...", "z3ma... walo", "z3ma... chi m3a9ed", "z3ma... b7al chi",
        "z3ma... hakda", "z3ma... l3ba", "z3ma... l7wayej", "z3ma... khawya",
        "z3ma... safi", "z3ma... yallah", "z3ma... daba", "z3ma... 3ziz",
    ],
}

# Stat-cited roast templates. {name} + stats interpolated.
ROAST_TEMPLATES = {
    "goals_zero": [
        "{name}: 0 goals f {matches} matchs. b7al chi taxi khawya.",
        "{name}: 0 goals. z3ma... striker? hahahaha.",
        "{name}: 0 goals. walo. safi. delete game.",
        "{name}: 0 goals. chi m3a9ed l3ba.",
        "{name}: 0 goals. b7al chi hwayej. khawya.",
        "{name}: 0 goals. l3ba khawya. l3adou chafek 3jbou.",
    ],
    "goals_low": [
        "{name}: {goals} goals f {matches} matchs. b7al chi taxi khawya.",
        "{name}: {goals} goals. z3ma... striker? hahahaha.",
        "{name}: {goals} goals. chi m3a9ed l3ba.",
        "{name}: {goals} goals. b7al chi 7wayej. khawya.",
        "{name}: {goals} goals. l3ba khawya. l3adou chafek 3jbou.",
    ],
    "assists_zero": [
        "{name}: 0 assists. walo. playmaker? z3ma...",
        "{name}: 0 assists. b7al chi passer khawya.",
        "{name}: 0 assists. chi m3a9ed. safi walo.",
        "{name}: 0 assists. l3ba khawya. delete game.",
    ],
    "assists_low": [
        "{name}: {assists} assists. walo. playmaker? z3ma...",
        "{name}: {assists} assists. b7al chi passer khawya.",
        "{name}: {assists} assists. chi m3a9ed. safi walo.",
    ],
    "rating_low": [
        "{name}: {rating}/10. pathetique. find a job.",
        "{name}: {rating}/10. z3ma... pro player? hahahaha.",
        "{name}: {rating}/10. walo. safi. chi m3a9ed.",
        "{name}: {rating}/10. b7al chi player khawya. trash.",
        "{name}: {rating}/10. l3ba khawya. delete game.",
        "{name}: {rating}/10. spectator walo. hahahaha.",
    ],
    "defense_low": [
        "{name}: {tackles} tackles. b7al chi mur dial chi dar khawya.",
        "{name}: {tackles} tackles. z3ma... defender? walo.",
        "{name}: {tackles} tackles. chi m3a9ed. safi.",
        "{name}: {tackles} tackles. l3adou daz mn 3ndek b7al chi tiran.",
    ],
    "passing_low": [
        "{name}: {pass_accuracy}% passing. z3ma... xavi? hahahaha.",
        "{name}: {pass_accuracy}% passing. walo. chi m3a9ed.",
        "{name}: {pass_accuracy}% passing. b7al chi passer khawya.",
        "{name}: {pass_accuracy}% passing. l3ba khawya. delete game.",
        "{name}: {pass_accuracy}% passing. l3adou chafek 3jbou.",
    ],
    "possession_loss_high": [
        "{name}: {possession_losses} possession losses. z3ma... ballon d'or? hahahaha.",
        "{name}: {possession_losses} marat kayt7arrak. chi m3a9ed l3ba.",
        "{name}: {possession_losses} marat kaydrob l3adou. walo. safi.",
        "{name}: {possession_losses} possession losses. b7al chi hwayej. khawya.",
        "{name}: {possession_losses} possession losses. l3ba khawya. delete game.",
    ],
    "general": [
        "{name}. walo. safi.", "{name}. clown. 🤡", "{name}. npc behavior.",
        "{name}. chi m3a9ed.", "{name}. b7al chi hwayej.", "{name}. l3ba khawya.",
        "{name}. delete game.", "{name}. trash. garbage.", "{name}. z3ma... player? walo.",
        "{name}. bon courage. c'est fini.", "{name}. chi 7wayej. safi.",
        "{name}. walo z3ma. hakda.", "{name}. b7al chi m3a9ed l3ba.",
    ],
    "gk_low": [
        "{name}: {saves} saves. z3ma... goalkeeper? hahahaha.",
        "{name}: {saves} saves. b7al chi 7aris dial l3ba khawya.",
        "{name}: {saves} saves. chi m3a9ed. safi.",
        "{name}: {saves} saves. l3ba khawya. delete game.",
    ],
    "striker_wasteful": [
        "{name}: {shots} shots, {goals} goals. b7al chi sniper khawya.",
        "{name}: {shots} shots, {goals} goals. z3ma... shooter? walo.",
        "{name}: {shots} shots, {goals} goals. chi m3a9ed. safi.",
        "{name}: {shots} shots b7al chi 9ahba dial l3ba.",
    ],
}

MATCH_RESULT_ROASTS = {
    "win_big": [
        "wallah! adversaire chi m3a9ed l3cha. 🤡",
        "wallah! chi m3a9ed l3ba. hahahaha.",
        "wallah! b7al chi hwayej. delete game.",
        "adversaire dial chi m3a9ed. safi walo.",
    ],
    "win_small": [
        "b7al chi match dial chi m3a9ed. walo.",
        "b7al chi match khawya. safi.",
        "z3ma... win? walo. chi m3a9ed.",
        "win b7al chi 7wayej. hakda.",
    ],
    "draw": [
        "noss noss. walo. c'est fini.",
        "noss noss. chi m3a9ed. safi.",
        "noss noss. l3ba khawya. delete game.",
        "noss noss. b7al chi hwayej.",
    ],
    "loss": [
        "lla... c'est fini. bon courage. 😤",
        "trash. garbage. delete game. 🗑️",
        "walo. safi. chi m3a9ed l3ba.",
        "l3ba khawya. l3adou chafek 3jbou.",
        "loss b7al chi 7wayej. delete game.",
    ],
}

MOTM_ROASTS = [
    "{name} motm. {rating}/10. z3ma... best of the worst. 🤡",
    "{name} motm. {rating}/10. c'est pas serieux. clown team.",
    "{name} motm. {rating}/10. z3ma... mvp? walo. hahahaha.",
    "{name} motm. {rating}/10. b7al chi motm dial chi m3a9ed.",
]

POSITION_ROASTS = {
    "ST": ["striker khawya. b7al chi 9ahba dial l3ba.", "z3ma... 9ahba? walo. hahahaha.", "striker chi m3a9ed. delete game."],
    "LW": ["winger khawya. b7al chi 9t3a dial lferrari khawya.", "z3ma... winger? walo. hahahaha.", "winger chi m3a9ed. delete game."],
    "RW": ["winger khawya. b7al chi 9t3a dial lferrari khawya.", "z3ma... winger? walo. hahahaha.", "winger chi m3a9ed. delete game."],
    "CM": ["midfielder khawya. b7al chi maestro dial l7wayej.", "z3ma... maestro? walo. hahahaha.", "midfielder chi m3a9ed. delete game."],
    "CAM": ["playmaker khawya. b7al chi 10 dial l3ba khawya.", "z3ma... playmaker? walo. hahahaha.", "playmaker chi m3a9ed. delete game."],
    "CDM": ["destroyer khawya. b7al chi tank dial l3ba khawya.", "z3ma... destroyer? walo. hahahaha.", "destroyer chi m3a9ed. delete game."],
    "CB": ["defender khawya. b7al chi mur dial chi dar khawya.", "z3ma... defender? walo. hahahaha.", "defender chi m3a9ed. delete game."],
    "LB": ["defender khawya. b7al chi mur dial chi dar khawya.", "z3ma... defender? walo. hahahaha.", "defender chi m3a9ed. delete game."],
    "RB": ["defender khawya. b7al chi mur dial chi dar khawya.", "z3ma... defender? walo. hahahaha.", "defender chi m3a9ed. delete game."],
    "GK": ["goalkeeper khawya. b7al chi 7aris dial l3ba khawya.", "z3ma... goalkeeper? walo. hahahaha.", "goalkeeper chi m3a9ed. delete game."],
    "LM": ["midfielder khawya. b7al chi maestro dial l7wayej.", "z3ma... midfielder? walo. hahahaha.", "midfielder chi m3a9ed. delete game."],
    "RM": ["midfielder khawya. b7al chi maestro dial l7wayej.", "z3ma... midfielder? walo. hahahaha.", "midfielder chi m3a9ed. delete game."],
}

BANTER_TEMPLATES = [
    "z3ma... pro clubs? walo. chi m3a9ed l3ba.",
    "b7al chi hwayej. delete game. safi.",
    "l3ba khawya. z3ma... football? hahahaha.",
    "chi m3a9ed. walo. bon courage.",
    "trash. garbage. l7wayej. walo.",
    "z3ma... team? b7al chi m3a9ed. safi.",
]

DRAMA_TEMPLATES = [
    "z3ma... drama? walo. chi m3a9ed l7wayej.",
    "b7al chi polemique khawya. delete game.",
    "l7wayej. z3ma... drama? hahahaha walo.",
    "chi m3a9ed. walo. safi. bon courage.",
]

MEME_TEMPLATES = [
    "hahahaha chi m3a9ed. delete game.",
    "hahahaha l3ba khawya. walo. safi.",
    "hahahaha z3ma... meme? walo. chi 7wayej.",
    "hahahaha b7al chi hwayej. trash.",
]

TRANSFER_TEMPLATES = [
    "z3ma... transfer? walo. chi m3a9ed l7wayej.",
    "b7al chi transfer khawya. delete game.",
    "l7wayej. z3ma... move? hahahaha walo.",
    "chi m3a9ed. walo. safi. bon courage.",
]

PREDICTION_TEMPLATES = {
    "win": [
        "z3ma... win? walo. chi m3a9ed l3ba.",
        "b7al chi prediction khawya. delete game.",
        "l3ba khawya. z3ma... victory? hahahaha walo.",
    ],
    "loss": [
        "wallah! loss. chi m3a9ed l3ba. delete game.",
        "b7al chi prediction khawya. walo. safi.",
        "l3ba khawya. z3ma... loss? hahahaha.",
    ],
    "draw": [
        "noss noss. z3ma... draw? walo. chi m3a9ed.",
        "b7al chi prediction khawya. delete game.",
        "l3ba khawya. z3ma... noss noss? hahahaha walo.",
    ],
}

PERSONALITIES = {
    "casablanca": {
        "prefixes": ["wa 3ziz", "hakda", "b7al chi", "chi", "walo", "z3ma", "safi", "daba"],
        "suffixes": ["safi", "walo", "z3ma", "hakda", "daba", "yallah"],
        "intensity": 1.0,
    },
    "analyst": {
        "prefixes": ["z3ma...", "b7al chi", "chi", "walo"],
        "suffixes": ["safi", "walo", "z3ma", "hakda"],
        "intensity": 0.7,
    },
    "toxic": {
        "prefixes": ["wallah!", "trash", "garbage", "delete game", "chi m3a9ed"],
        "suffixes": ["delete game", "trash", "garbage", "walo", "safi"],
        "intensity": 1.2,
    },
    "coach": {
        "prefixes": ["bon courage", "z3ma...", "b7al chi", "chi"],
        "suffixes": ["bon courage", "safi", "walo", "z3ma"],
        "intensity": 0.6,
    },
    "commentator": {
        "prefixes": ["wallah!", "hahahaha", "z3ma...", "b7al chi"],
        "suffixes": ["hahahaha", "walo", "z3ma", "safi"],
        "intensity": 0.9,
    },
    "cafeteria": {
        "prefixes": ["hahahaha", "z3ma...", "b7al chi", "chi", "walo"],
        "suffixes": ["hahahaha", "walo", "z3ma", "safi", "daba"],
        "intensity": 1.1,
    },
}


class DarijaEngine:
    def __init__(self, squad_path: str = "squad.json"):
        self.squad = self._load_squad(squad_path)
        self.roast_mode = 0.95
        self.current_personality = "casablanca"
        self.memory_path = Path("darija_memory.json")
        self.memory = self._load_memory()

    def _load_squad(self, path: str) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _load_memory(self) -> dict:
        if self.memory_path.exists():
            try:
                with open(self.memory_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"roast_counts": {}, "mvp_counts": {}, "worst_counts": {}, "historic_lows": {}}

    def save_memory(self):
        with open(self.memory_path, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, indent=2, ensure_ascii=False)

    def set_personality(self, personality: str):
        if personality in PERSONALITIES:
            self.current_personality = personality

    def _get_prefix(self) -> str:
        p = PERSONALITIES.get(self.current_personality, PERSONALITIES["casablanca"])
        if random.random() < p["intensity"]:
            return random.choice(p["prefixes"])
        return ""

    def _get_suffix(self) -> str:
        p = PERSONALITIES.get(self.current_personality, PERSONALITIES["casablanca"])
        if random.random() < p["intensity"]:
            return random.choice(p["suffixes"])
        return ""

    def _format(self, template: str, **kwargs) -> str:
        text = template.format(**kwargs)
        prefix = self._get_prefix()
        suffix = self._get_suffix()
        if prefix and not text.lower().startswith(prefix.lower()):
            text = f"{prefix}. {text}"
        if suffix and not text.lower().endswith(suffix.lower()):
            text = f"{text} {suffix}."
        return text

    def _get_nickname(self, name: str) -> str:
        info = self.squad.get(name.lower(), {})
        return info.get("nickname", name)

    def _get_position(self, name: str) -> str:
        info = self.squad.get(name.lower(), {})
        return info.get("position", "CM")

    def roast_player(self, name: str, stats: dict, matches: int = 5) -> List[str]:
        roasts = []
        nick = self._get_nickname(name)
        position = self._get_position(name)

        # Goals
        if stats.get("goals", 0) == 0:
            if position in ("ST", "LW", "RW", "CAM"):
                roasts.append(self._format(random.choice(ROAST_TEMPLATES["goals_zero"]), name=nick, matches=matches))
        elif stats.get("goals", 0) < matches * 0.3:
            roasts.append(self._format(random.choice(ROAST_TEMPLATES["goals_low"]), name=nick, goals=stats["goals"], matches=matches))

        # Assists
        if stats.get("assists", 0) == 0 and position in ("CAM", "CM", "LW", "RW"):
            roasts.append(self._format(random.choice(ROAST_TEMPLATES["assists_zero"]), name=nick))
        elif stats.get("assists", 0) < matches * 0.2 and position in ("CAM", "CM", "LW", "RW"):
            roasts.append(self._format(random.choice(ROAST_TEMPLATES["assists_low"]), name=nick, assists=stats["assists"]))

        # Rating
        if stats.get("rating", 10) < 6.5:
            roasts.append(self._format(random.choice(ROAST_TEMPLATES["rating_low"]), name=nick, rating=stats["rating"]))
        elif stats.get("rating", 10) < 7.0:
            roasts.append(self._format(random.choice(ROAST_TEMPLATES["rating_low"]), name=nick, rating=stats["rating"]))

        # Defense
        if position in ("CB", "LB", "RB", "CDM", "GK") and stats.get("tackles", 999) < 2:
            roasts.append(self._format(random.choice(ROAST_TEMPLATES["defense_low"]), name=nick, tackles=stats["tackles"]))

        # Passing
        if stats.get("pass_accuracy", 100) < 70:
            roasts.append(self._format(random.choice(ROAST_TEMPLATES["passing_low"]), name=nick, pass_accuracy=stats["pass_accuracy"]))

        # Possession losses
        if stats.get("possession_losses", 0) > 12:
            roasts.append(self._format(random.choice(ROAST_TEMPLATES["possession_loss_high"]), name=nick, possession_losses=stats["possession_losses"]))

        # GK specific
        if position == "GK" and stats.get("saves", 0) < 2 and matches >= 3:
            roasts.append(self._format(random.choice(ROAST_TEMPLATES["gk_low"]), name=nick, saves=stats["saves"]))

        # Wasteful striker
        if stats.get("shots", 0) > 8 and stats.get("goals", 0) == 0:
            roasts.append(self._format(random.choice(ROAST_TEMPLATES["striker_wasteful"]), name=nick, shots=stats["shots"], goals=stats["goals"]))

        # Position roast
        if position in POSITION_ROASTS:
            roasts.append(self._format(random.choice(POSITION_ROASTS[position])))

        # Memory-based: frequent ball loser
        if stats.get("possession_losses", 0) > 15:
            count = self.memory["roast_counts"].get(name.lower(), 0)
            if count >= 3:
                roasts.append(self._format(f"هاد ثالث أسبوع وانت فالترتيب ديال أكثر واحد كيضيع الكرة. {nick}. chi m3a9ed."))
            self.memory["roast_counts"][name.lower()] = count + 1

        if not roasts:
            roasts.append(self._format(random.choice(ROAST_TEMPLATES["general"]), name=nick))

        self.save_memory()
        return roasts[:3]

    def roast_match_result(self, team_goals: int, opponent_goals: int, opponent_name: str = "") -> str:
        if team_goals > opponent_goals:
            if team_goals - opponent_goals >= 3:
                return self._format(random.choice(MATCH_RESULT_ROASTS["win_big"]))
            return self._format(random.choice(MATCH_RESULT_ROASTS["win_small"]))
        elif team_goals == opponent_goals:
            return self._format(random.choice(MATCH_RESULT_ROASTS["draw"]))
        return self._format(random.choice(MATCH_RESULT_ROASTS["loss"]))

    def roast_motm(self, name: str, rating: float) -> str:
        return self._format(random.choice(MOTM_ROASTS), name=name, rating=rating)

    def banter(self) -> str:
        return self._format(random.choice(BANTER_TEMPLATES))

    def drama(self) -> str:
        return self._format(random.choice(DRAMA_TEMPLATES))

    def meme(self) -> str:
        return self._format(random.choice(MEME_TEMPLATES))

    def transfer(self) -> str:
        return self._format(random.choice(TRANSFER_TEMPLATES))

    def predict(self, prediction: str) -> str:
        return self._format(random.choice(PREDICTION_TEMPLATES.get(prediction, PREDICTION_TEMPLATES["loss"])))

    def compare_players(self, p1_name: str, p1_stats: dict, p2_name: str, p2_stats: dict) -> str:
        p1_nick = self._get_nickname(p1_name)
        p2_nick = self._get_nickname(p2_name)
        p1_score = p1_stats.get("rating", 0) + p1_stats.get("goals", 0) * 2 + p1_stats.get("assists", 0)
        p2_score = p2_stats.get("rating", 0) + p2_stats.get("goals", 0) * 2 + p2_stats.get("assists", 0)
        winner, loser = (p1_nick, p2_nick) if p1_score > p2_score else (p2_nick, p1_nick)
        return self._format(
            "{winner} vs {loser}. z3ma... comparison? walo. chi m3a9ed l3ba. {loser} delete game.",
            winner=winner, loser=loser,
        )

    def get_worst_player(self, players_stats: dict) -> Tuple[str, str]:
        worst = None
        worst_score = float("inf")
        for name, stats in players_stats.items():
            score = stats.get("rating", 10) - stats.get("goals", 0) * 2 - stats.get("assists", 0)
            if score < worst_score:
                worst_score = score
                worst = name
        if worst:
            nick = self._get_nickname(worst)
            roast = self._format(
                "{name}. worst of the week. z3ma... player? walo. delete game.", name=nick
            )
            self.memory["worst_counts"][worst.lower()] = self.memory["worst_counts"].get(worst.lower(), 0) + 1
            self.save_memory()
            return worst, roast
        return "", ""

    def get_mvp(self, players_stats: dict) -> Tuple[str, str]:
        best = None
        best_score = -1
        for name, stats in players_stats.items():
            score = stats.get("rating", 0) + stats.get("goals", 0) * 2 + stats.get("assists", 0)
            if score > best_score:
                best_score = score
                best = name
        if best:
            nick = self._get_nickname(best)
            rating = players_stats[best].get("rating", 0)
            return best, self.roast_motm(nick, rating)
        return "", ""

    def roast_leaderboard(self, leaderboard: List) -> List[str]:
        roasts = []
        for i, (name, stats) in enumerate(leaderboard[:5]):
            nick = self._get_nickname(name)
            if i == 0:
                roasts.append(self._format("{name}. #1. z3ma... best? walo. chi m3a9ed.", name=nick))
            elif i == len(leaderboard) - 1:
                roasts.append(self._format("{name}. last. trash. garbage. delete game.", name=nick))
            else:
                roasts.append(self._format("{name}. #{rank}. b7al chi hwayej. walo.", name=nick, rank=i + 1))
        return roasts

    def fraud_check(self, name: str, stats: dict) -> Tuple[bool, str]:
        nick = self._get_nickname(name)
        fraud_score = 0
        reasons = []
        if stats.get("goals", 0) == 0 and stats.get("assists", 0) == 0:
            fraud_score += 50
            reasons.append("0 goals, 0 assists")
        if stats.get("rating", 10) < 6.0:
            fraud_score += 30
            reasons.append(f"Rating {stats['rating']:.1f}")
        if stats.get("possession_losses", 0) > 15:
            fraud_score += 20
            reasons.append(f"{stats['possession_losses']} possession losses")
        is_fraud = fraud_score >= 50
        if is_fraud:
            roast = self._format(
                "{name}. FRAUD DETECTED. z3ma... player? walo. delete game. trash. garbage. 🗑️", name=nick
            )
        else:
            roast = self._format("{name}. z3ma... fraud? walo. chi m3a9ed. safi.", name=nick)
        return is_fraud, roast, fraud_score, reasons


_engine = None

def get_engine(squad_path: str = "squad.json") -> DarijaEngine:
    global _engine
    if _engine is None:
        _engine = DarijaEngine(squad_path)
    return _engine
