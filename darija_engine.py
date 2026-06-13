"""
Rachad L3ERGONI Bot - Darija Engine v2
Native Moroccan Darija with 95% roast mode
"""

import random
import json
from typing import List, Dict, Optional, Tuple

DARIJA_EXPRESSIONS = {
    "disappointment": [
        "lla... c'est fini.", "bon courage.", "trash. garbage.", "delete game.",
        "walo. safi.", "chi m3a9ed.", "b7al chi hwayej.", "khawya l3ba.",
        "m3a9ed l3ba.", "l3ba khawya.", "safi walo.", "z3ma... walo.",
        "hakda. b7al hakda.", "daba daba. walo.", "yallah. walo.", "wa 3ziz. chi m3a9ed."
    ],
    "laughter": [
        "hahahaha", "hahahaha chi m3a9ed", "hahahaha walo", "hahahaha z3ma",
        "hahahaha safi", "hahahaha l3ba", "hahahaha l7wayej", "hahahaha khawya",
        "hahahaha m3a9ed", "hahahaha delete game", "hahahaha trash", "hahahaha garbage"
    ],
    "thinking": [
        "z3ma...", "z3ma... walo", "z3ma... chi m3a9ed", "z3ma... b7al chi",
        "z3ma... hakda", "z3ma... l3ba", "z3ma... l7wayej", "z3ma... khawya",
        "z3ma... safi", "z3ma... yallah", "z3ma... daba", "z3ma... 3ziz"
    ],
    "anger": [
        "wallah!", "wallah chi m3a9ed!", "wallah l3ba khawya!", "wallah walo!",
        "wallah delete game!", "wallah trash!", "wallah garbage!", "wallah lla...!"
    ]
}

ROAST_TEMPLATES = {
    "goals": [
        "{name}: {goals} goals f {matches} matchs. b7al chi taxi khawya.",
        "{name}: {goals} goals. z3ma... striker? hahahaha.",
        "{name}: {goals} goals. walo. safi. delete game.",
        "{name}: {goals} goals. chi m3a9ed l3ba.",
        "{name}: {goals} goals. b7al chi 7wayej. khawya."
    ],
    "assists": [
        "{name}: {assists} assist. walo. playmaker? z3ma...",
        "{name}: {assists} assist. b7al chi passer khawya.",
        "{name}: {assists} assist. chi m3a9ed. safi walo."
    ],
    "rating": [
        "{name}: {rating}/10. pathetique. find a job.",
        "{name}: {rating}/10. z3ma... pro player? hahahaha.",
        "{name}: {rating}/10. walo. safi. chi m3a9ed.",
        "{name}: {rating}/10. b7al chi player khawya. trash."
    ],
    "defense": [
        "{name}: {tackles} tackles. b7al chi mur dial chi dar khawya.",
        "{name}: {tackles} tackles. z3ma... defender? walo.",
        "{name}: {tackles} tackles. chi m3a9ed. safi."
    ],
    "shots": [
        "{name}: {shots} shots. b7al chi sniper khawya.",
        "{name}: {shots} shots. z3ma... shooter? walo.",
        "{name}: {shots} shots. chi m3a9ed. safi."
    ],
    "passes": [
        "{name}: {passes}% passing. z3ma... xavi? hahahaha.",
        "{name}: {passes}% passing. walo. chi m3a9ed.",
        "{name}: {passes}% passing. b7al chi passer khawya."
    ],
    "general": [
        "{name}. walo. safi.", "{name}. clown. 🤡", "{name}. npc behavior.",
        "{name}. chi m3a9ed.", "{name}. b7al chi hwayej.", "{name}. l3ba khawya.",
        "{name}. delete game.", "{name}. trash. garbage.", "{name}. z3ma... player? walo.",
        "{name}. bon courage. c'est fini.", "{name}. chi 7wayej. safi.",
        "{name}. walo z3ma. hakda.", "{name}. b7al chi m3a9ed l3ba."
    ]
}

MATCH_RESULT_ROASTS = {
    "win_big": [
        "wallah! adversaire chi m3a9ed l3cha. 🤡",
        "wallah! chi m3a9ed l3ba. hahahaha.",
        "wallah! b7al chi hwayej. delete game."
    ],
    "win_small": [
        "b7al chi match dial chi m3a9ed. walo.",
        "b7al chi match khawya. safi.",
        "z3ma... win? walo. chi m3a9ed."
    ],
    "draw": [
        "noss noss. walo. c'est fini.",
        "noss noss. chi m3a9ed. safi.",
        "noss noss. l3ba khawya. delete game."
    ],
    "loss": [
        "lla... c'est fini. bon courage. 😤",
        "trash. garbage. delete game. 🗑️",
        "walo. safi. chi m3a9ed l3ba."
    ]
}

MOTM_ROASTS = [
    "{name} motm. {rating}/10. z3ma... best of the worst. 🤡",
    "{name} motm. {rating}/10. c'est pas serieux. clown team.",
    "{name} motm. {rating}/10. z3ma... mvp? walo. hahahaha."
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
    "RM": ["midfielder khawya. b7al chi maestro dial l7wayej.", "z3ma... midfielder? walo. hahahaha.", "midfielder chi m3a9ed. delete game."]
}

BANTER_TEMPLATES = [
    "z3ma... pro clubs? walo. chi m3a9ed l3ba.", "b7al chi hwayej. delete game. safi.",
    "l3ba khawya. z3ma... football? hahahaha.", "chi m3a9ed. walo. bon courage.",
    "trash. garbage. l7wayej. walo.", "z3ma... team? b7al chi m3a9ed. safi."
]

DRAMA_TEMPLATES = [
    "z3ma... drama? walo. chi m3a9ed l7wayej.", "b7al chi polemique khawya. delete game.",
    "l7wayej. z3ma... drama? hahahaha walo.", "chi m3a9ed. walo. safi. bon courage."
]

MEME_TEMPLATES = [
    "hahahaha chi m3a9ed. delete game.", "hahahaha l3ba khawya. walo. safi.",
    "hahahaha z3ma... meme? walo. chi 7wayej.", "hahahaha b7al chi hwayej. trash."
]

TRANSFER_TEMPLATES = [
    "z3ma... transfer? walo. chi m3a9ed l7wayej.", "b7al chi transfer khawya. delete game.",
    "l7wayej. z3ma... move? hahahaha walo.", "chi m3a9ed. walo. safi. bon courage."
]

PREDICTION_TEMPLATES = {
    "win": ["z3ma... win? walo. chi m3a9ed l3ba.", "b7al chi prediction khawya. delete game.", "l3ba khawya. z3ma... victory? hahahaha walo."],
    "loss": ["wallah! loss. chi m3a9ed l3ba. delete game.", "b7al chi prediction khawya. walo. safi.", "l3ba khawya. z3ma... loss? hahahaha."],
    "draw": ["noss noss. z3ma... draw? walo. chi m3a9ed.", "b7al chi prediction khawya. delete game.", "l3ba khawya. z3ma... noss noss? hahahaha walo."]
}

ADVANCED_ROASTS = {
    "possession_loss": [
        "{name}: {losses} possession losses. z3ma... ballon d'or? hahahaha.",
        "{name}: {losses} marat kayt7arrak. chi m3a9ed l3ba.",
        "{name}: {losses} marat kaydrob l3adou. walo. safi."
    ],
    "key_passes": [
        "{name}: {key_passes} key passes. z3ma... playmaker? walo.",
        "{name}: {key_passes} passes decisives. chi m3a9ed. safi."
    ],
    "dribbles": [
        "{name}: {dribbles} dribbles. z3ma... messi? hahahaha walo.",
        "{name}: {dribbles} dribbles. chi m3a9ed. safi."
    ],
    "interceptions": [
        "{name}: {interceptions} interceptions. z3ma... defender? walo.",
        "{name}: {interceptions} interceptions. b7al chi mur khawya."
    ]
}

PERSONALITIES = {
    "casablanca": {"prefixes": ["wa 3ziz", "hakda", "b7al chi", "chi", "walo", "z3ma", "safi", "daba"], "suffixes": ["safi", "walo", "z3ma", "hakda", "daba", "yallah"], "intensity": 1.0},
    "analyst": {"prefixes": ["z3ma...", "b7al chi", "chi", "walo"], "suffixes": ["safi", "walo", "z3ma", "hakda"], "intensity": 0.7},
    "toxic": {"prefixes": ["wallah!", "trash", "garbage", "delete game", "chi m3a9ed"], "suffixes": ["delete game", "trash", "garbage", "walo", "safi"], "intensity": 1.2},
    "coach": {"prefixes": ["bon courage", "z3ma...", "b7al chi", "chi"], "suffixes": ["bon courage", "safi", "walo", "z3ma"], "intensity": 0.6},
    "commentator": {"prefixes": ["wallah!", "hahahaha", "z3ma...", "b7al chi"], "suffixes": ["hahahaha", "walo", "z3ma", "safi"], "intensity": 0.9},
    "cafeteria": {"prefixes": ["hahahaha", "z3ma...", "b7al chi", "chi", "walo"], "suffixes": ["hahahaha", "walo", "z3ma", "safi", "daba"], "intensity": 1.1}
}


class DarijaEngine:
    """Native Moroccan Darija engine - 95% roast, 5% neutral"""

    def __init__(self, squad_path: str = "squad.json"):
        self.squad = self._load_squad(squad_path)
        self.roast_mode = 0.95
        self.current_personality = "casablanca"
        self.memory = {"roast_counts": {}, "mvp_counts": {}, "worst_counts": {}}

    def _load_squad(self, path: str) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def set_personality(self, personality: str):
        if personality in PERSONALITIES:
            self.current_personality = personality

    def _get_prefix(self) -> str:
        p = PERSONALITIES.get(self.current_personality, PERSONALITIES["casablanca"])
        return random.choice(p["prefixes"]) if random.random() < p["intensity"] else ""

    def _get_suffix(self) -> str:
        p = PERSONALITIES.get(self.current_personality, PERSONALITIES["casablanca"])
        return random.choice(p["suffixes"]) if random.random() < p["intensity"] else ""

    def _format(self, template: str, **kwargs) -> str:
        text = template.format(**kwargs)
        prefix = self._get_prefix()
        suffix = self._get_suffix()
        if prefix and not text.startswith(prefix):
            text = f"{prefix}. {text}"
        if suffix and not text.endswith(suffix):
            text = f"{text} {suffix}."
        return text

    def roast_player(self, name: str, stats: dict, matches: int = 5) -> List[str]:
        roasts = []
        player_info = self.squad.get(name.lower(), {})
        nickname = player_info.get("nickname", name)
        position = player_info.get("position", "")

        if "goals" in stats and stats["goals"] == 0:
            roasts.append(self._format(random.choice(ROAST_TEMPLATES["goals"]), name=nickname, goals=0, matches=matches))
        elif "goals" in stats and stats["goals"] < matches * 0.5:
            roasts.append(self._format(random.choice(ROAST_TEMPLATES["goals"]), name=nickname, goals=stats["goals"], matches=matches))

        if "assists" in stats and stats["assists"] == 0:
            roasts.append(self._format(random.choice(ROAST_TEMPLATES["assists"]), name=nickname, assists=0))

        if "rating" in stats and stats["rating"] < 7.0:
            roasts.append(self._format(random.choice(ROAST_TEMPLATES["rating"]), name=nickname, rating=stats["rating"]))

        if "tackles" in stats and stats["tackles"] < 2:
            roasts.append(self._format(random.choice(ROAST_TEMPLATES["defense"]), name=nickname, tackles=stats["tackles"]))

        if "shots" in stats and stats["shots"] > 5 and stats.get("goals", 0) == 0:
            roasts.append(self._format(random.choice(ROAST_TEMPLATES["shots"]), name=nickname, shots=stats["shots"]))

        if "pass_accuracy" in stats and stats["pass_accuracy"] < 70:
            roasts.append(self._format(random.choice(ROAST_TEMPLATES["passes"]), name=nickname, passes=stats["pass_accuracy"]))

        if position in POSITION_ROASTS:
            roasts.append(self._format(random.choice(POSITION_ROASTS[position])))

        if "possession_losses" in stats and stats["possession_losses"] > 10:
            roasts.append(self._format(random.choice(ADVANCED_ROASTS["possession_loss"]), name=nickname, losses=stats["possession_losses"]))

        if not roasts:
            roasts.append(self._format(random.choice(ROAST_TEMPLATES["general"]), name=nickname))

        self.memory["roast_counts"][name.lower()] = self.memory["roast_counts"].get(name.lower(), 0) + 1
        return roasts[:2]

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
        p1_info = self.squad.get(p1_name.lower(), {})
        p2_info = self.squad.get(p2_name.lower(), {})
        p1_nick = p1_info.get("nickname", p1_name)
        p2_nick = p2_info.get("nickname", p2_name)
        p1_score = p1_stats.get("rating", 0) + p1_stats.get("goals", 0) * 2 + p1_stats.get("assists", 0)
        p2_score = p2_stats.get("rating", 0) + p2_stats.get("goals", 0) * 2 + p2_stats.get("assists", 0)
        winner, loser = (p1_nick, p2_nick) if p1_score > p2_score else (p2_nick, p1_nick)
        return self._format("{winner} vs {loser}. z3ma... comparison? walo. chi m3a9ed l3ba. {loser} delete game.", winner=winner, loser=loser)

    def get_worst_player(self, players_stats: dict) -> Tuple[str, str]:
        worst = None
        worst_score = float('inf')
        for name, stats in players_stats.items():
            score = stats.get("rating", 10) - stats.get("goals", 0) * 2 - stats.get("assists", 0)
            if score < worst_score:
                worst_score = score
                worst = name
        if worst:
            info = self.squad.get(worst.lower(), {})
            nick = info.get("nickname", worst)
            roast = self._format("{name}. worst of the week. z3ma... player? walo. delete game.", name=nick)
            self.memory["worst_counts"][worst.lower()] = self.memory["worst_counts"].get(worst.lower(), 0) + 1
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
            info = self.squad.get(best.lower(), {})
            nick = info.get("nickname", best)
            rating = players_stats[best].get("rating", 0)
            return best, self.roast_motm(nick, rating)
        return "", ""

    def roast_leaderboard(self, leaderboard: List) -> List[str]:
        roasts = []
        for i, (name, stats) in enumerate(leaderboard[:5]):
            info = self.squad.get(name.lower(), {})
            nick = info.get("nickname", name)
            if i == 0:
                roasts.append(self._format("{name}. #1. z3ma... best? walo. chi m3a9ed.", name=nick))
            elif i == len(leaderboard) - 1:
                roasts.append(self._format("{name}. last. trash. garbage. delete game.", name=nick))
            else:
                roasts.append(self._format("{name}. #{rank}. b7al chi hwayej. walo.", name=nick, rank=i+1))
        return roasts

    def save_memory(self, path: str = "bot_memory.json"):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, indent=2, ensure_ascii=False)

    def load_memory(self, path: str = "bot_memory.json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.memory = json.load(f)
        except:
            pass


_engine = None

def get_engine(squad_path: str = "squad.json") -> DarijaEngine:
    global _engine
    if _engine is None:
        _engine = DarijaEngine(squad_path)
    return _engine
