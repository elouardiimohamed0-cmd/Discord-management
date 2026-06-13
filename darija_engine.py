"""
Rachad L3ERGONI Bot - Darija Engine v2
Native Moroccan Darija with 95% roast mode
Uses DODa patterns + authentic Moroccan gamer slang
"""

import random
import json
from typing import List, Dict, Optional, Tuple
from pathlib import Path

# ==========================================
# NATIVE DARIJA VOCABULARY (DODa-based)
# ==========================================

DARIJA_FILLERS = [
    "safi", "walo", "z3ma", "3ziz", "3ziz 3liya", "wa 3ziz",
    "hak", "hakda", "b7al hak", "b7al chi", "chi", "wakha",
    "yallah", "wakha yallah", "safi yallah", "walo hak",
    "b7al chi hwayej", "chi m3a9ed", "chi 7wayej",
    "l3ba", "f l3ba", "f l7wayej", "f lmatch",
    "daba", "daba daba", "wa daba", "safi daba"
]

DARIJA_EXPRESSIONS = {
    "disappointment": [
        "lla... c'est fini.", "bon courage.", "trash. garbage.", "delete game.",
        "walo. safi.", "chi m3a9ed.", "b7al chi hwayej.", "khawya l3ba.",
        "m3a9ed l3ba.", "chi 7wayej dial l3ba.", "l3ba khawya.", "walo f l3ba.",
        "safi walo.", "z3ma... walo.", "hakda. b7al hakda.", "daba daba. walo.",
        "yallah. walo.", "3ziz 3liya. walo.", "wa 3ziz. chi m3a9ed.", "hak. chi khawya."
    ],
    "laughter": [
        "hahahaha", "hahahaha chi m3a9ed", "hahahaha walo", "hahahaha z3ma",
        "hahahaha safi", "hahahaha b7al chi", "hahahaha l3ba", "hahahaha l7wayej",
        "hahahaha chi 7wayej", "hahahaha khawya", "hahahaha m3a9ed",
        "hahahaha delete game", "hahahaha trash", "hahahaha garbage",
        "hahahaha bon courage", "hahahaha c'est fini", "hahahaha lla...",
        "hahahaha wallah", "hahahaha 3ziz", "hahahaha 3ziz 3liya"
    ],
    "thinking": [
        "z3ma...", "z3ma... walo", "z3ma... chi m3a9ed", "z3ma... b7al chi",
        "z3ma... hakda", "z3ma... l3ba", "z3ma... l7wayej", "z3ma... khawya",
        "z3ma... safi", "z3ma... yallah", "z3ma... daba", "z3ma... 3ziz",
        "z3ma... 3ziz 3liya", "z3ma... wa 3ziz", "z3ma... chi 7wayej",
        "z3ma... chi m3a9ed l3ba", "z3ma... b7al chi hwayej", "z3ma... walo hak",
        "z3ma... hakda hakda", "z3ma... daba daba"
    ],
    "anger": [
        "wallah!", "wallah chi m3a9ed!", "wallah l3ba khawya!", "wallah l7wayej!",
        "wallah walo!", "wallah safi!", "wallah z3ma!", "wallah delete game!",
        "wallah trash!", "wallah garbage!", "wallah bon courage!", "wallah c'est fini!",
        "wallah lla...!", "wallah chi 7wayej!", "wallah chi m3a9ed l3ba!",
        "wallah b7al chi hwayej!", "wallah hakda!", "wallah daba!", "wallah yallah!", "wallah 3ziz!"
    ]
}

# ==========================================
# ROAST TEMPLATES BY STAT CATEGORY
# ==========================================

ROAST_TEMPLATES = {
    "goals": [
        "{name}: {goals} goals f {matches} matchs. b7al chi taxi khawya.",
        "{name}: {goals} goals. z3ma... striker? hahahaha.",
        "{name}: {goals} goals. walo. safi. delete game.",
        "{name}: {goals} goals f {matches} matchs. chi m3a9ed l3ba.",
        "{name}: {goals} goals. b7al chi 7wayej. khawya.",
        "{name}: {goals} goals. z3ma... finisher? hahahaha walo.",
        "{name}: {goals} goals. l3ba khawya. safi yallah.",
        "{name}: {goals} goals f {matches} matchs. chi m3a9ed. bon courage.",
        "{name}: {goals} goals. walo. z3ma. hakda.",
        "{name}: {goals} goals. b7al chi m3a9ed l3ba. trash."
    ],
    "assists": [
        "{name}: {assists} assist. walo. playmaker? z3ma...",
        "{name}: {assists} assist. b7al chi passer khawya.",
        "{name}: {assists} assist. z3ma... maestro? hahahaha.",
        "{name}: {assists} assist. chi m3a9ed. safi walo.",
        "{name}: {assists} assist. l7wayej. delete game.",
        "{name}: {assists} assist. walo. b7al chi hwayej.",
        "{name}: {assists} assist. z3ma... creator? hahahaha walo.",
        "{name}: {assists} assist. chi m3a9ed l3ba. bon courage.",
        "{name}: {assists} assist. khawya. safi yallah.",
        "{name}: {assists} assist. walo z3ma. hakda."
    ],
    "rating": [
        "{name}: {rating}/10. pathetique. find a job.",
        "{name}: {rating}/10. z3ma... pro player? hahahaha.",
        "{name}: {rating}/10. walo. safi. chi m3a9ed.",
        "{name}: {rating}/10. b7al chi player khawya. trash.",
        "{name}: {rating}/10. l3ba khawya. delete game.",
        "{name}: {rating}/10. z3ma... good? walo. hahahaha.",
        "{name}: {rating}/10. chi 7wayej. bon courage.",
        "{name}: {rating}/10. walo. b7al chi hwayej. safi.",
        "{name}: {rating}/10. z3ma... decent? hahahaha walo.",
        "{name}: {rating}/10. chi m3a9ed l3ba. garbage."
    ],
    "defense": [
        "{name}: {tackles} tackles. b7al chi mur dial chi dar khawya.",
        "{name}: {tackles} tackles. z3ma... defender? walo.",
        "{name}: {tackles} tackles. chi m3a9ed. safi.",
        "{name}: {tackles} tackles. b7al chi 7wayej. delete game.",
        "{name}: {tackles} tackles. walo. l3ba khawya.",
        "{name}: {tackles} tackles. z3ma... wall? hahahaha.",
        "{name}: {tackles} tackles. chi m3a9ed l3ba. bon courage.",
        "{name}: {tackles} tackles. khawya. safi yallah.",
        "{name}: {tackles} tackles. walo z3ma. b7al chi.",
        "{name}: {tackles} tackles. chi 7wayej. trash."
    ],
    "shots": [
        "{name}: {shots} shots. b7al chi sniper khawya.",
        "{name}: {shots} shots. z3ma... shooter? walo.",
        "{name}: {shots} shots. chi m3a9ed. safi.",
        "{name}: {shots} shots. walo. l3ba khawya.",
        "{name}: {shots} shots. b7al chi 7wayej. delete game.",
        "{name}: {shots} shots. z3ma... finisher? hahahaha.",
        "{name}: {shots} shots. chi m3a9ed l3ba. bon courage.",
        "{name}: {shots} shots. khawya. safi yallah.",
        "{name}: {shots} shots. walo z3ma. hakda.",
        "{name}: {shots} shots. chi 7wayej. trash."
    ],
    "passes": [
        "{name}: {passes}% passing. z3ma... xavi? hahahaha.",
        "{name}: {passes}% passing. walo. chi m3a9ed.",
        "{name}: {passes}% passing. b7al chi passer khawya.",
        "{name}: {passes}% passing. safi. delete game.",
        "{name}: {passes}% passing. z3ma... accurate? walo.",
        "{name}: {passes}% passing. chi 7wayej. bon courage.",
        "{name}: {passes}% passing. l3ba khawya. safi yallah.",
        "{name}: {passes}% passing. walo z3ma. b7al chi.",
        "{name}: {passes}% passing. chi m3a9ed l3ba. trash.",
        "{name}: {passes}% passing. khawya. garbage."
    ],
    "general": [
        "{name}. walo. safi.", "{name}. clown. 🤡", "{name}. npc behavior.",
        "{name}. chi m3a9ed.", "{name}. b7al chi hwayej.", "{name}. l3ba khawya.",
        "{name}. delete game.", "{name}. trash. garbage.", "{name}. z3ma... player? walo.",
        "{name}. bon courage. c'est fini.", "{name}. chi 7wayej. safi.",
        "{name}. walo z3ma. hakda.", "{name}. b7al chi m3a9ed l3ba.",
        "{name}. khawya. safi yallah.", "{name}. chi m3a9ed. hahahaha.",
        "{name}. l7wayej. delete game.", "{name}. z3ma... pro? hahahaha walo.",
        "{name}. walo. b7al chi khawya.", "{name}. chi 7wayej dial l3ba. trash.",
        "{name}. safi daba. walo."
    ]
}

MATCH_RESULT_ROASTS = {
    "win_big": [
        "wallah! adversaire chi m3a9ed l3cha. 🤡",
        "wallah! chi m3a9ed l3ba. hahahaha.",
        "wallah! b7al chi hwayej. delete game.",
        "wallah! l3ba khawya. safi.",
        "wallah! chi 7wayej. trash. garbage.",
        "wallah! z3ma... match? walo. hahahaha.",
        "wallah! adversaire walo. safi yallah.",
        "wallah! chi m3a9ed l3ba. bon courage.",
        "wallah! b7al chi m3a9ed. delete game.",
        "wallah! l7wayej. chi m3a9ed. walo."
    ],
    "win_small": [
        "b7al chi match dial chi m3a9ed. walo.",
        "b7al chi match khawya. safi.",
        "z3ma... win? walo. chi m3a9ed.",
        "b7al chi hwayej. delete game.",
        "chi m3a9ed l3ba. walo. bon courage.",
        "l3ba khawya. safi yallah.",
        "z3ma... victory? hahahaha walo.",
        "chi 7wayej. trash. garbage.",
        "walo. b7al chi m3a9ed. safi.",
        "hakda. chi m3a9ed l3ba. walo."
    ],
    "draw": [
        "noss noss. walo. c'est fini.",
        "noss noss. chi m3a9ed. safi.",
        "noss noss. l3ba khawya. delete game.",
        "noss noss. walo. b7al chi hwayej.",
        "noss noss. z3ma... draw? hahahaha.",
        "noss noss. chi 7wayej. bon courage.",
        "noss noss. safi yallah. walo.",
        "noss noss. trash. garbage.",
        "noss noss. chi m3a9ed l3ba. walo.",
        "noss noss. b7al chi m3a9ed. safi."
    ],
    "loss": [
        "lla... c'est fini. bon courage. 😤",
        "trash. garbage. delete game. 🗑️",
        "walo. safi. chi m3a9ed l3ba.",
        "l3ba khawya. b7al chi hwayej.",
        "z3ma... team? walo. hahahaha.",
        "chi 7wayej. delete game. bon courage.",
        "safi yallah. walo. chi m3a9ed.",
        "trash. garbage. l7wayej. walo.",
        "b7al chi m3a9ed. safi. c'est fini.",
        "lla... l3ba khawya. z3ma... walo."
    ]
}

MOTM_ROASTS = [
    "{name} motm. {rating}/10. z3ma... best of the worst. 🤡",
    "{name} motm. {rating}/10. c'est pas serieux. clown team.",
    "{name} motm. {rating}/10. z3ma... mvp? walo. hahahaha.",
    "{name} motm. {rating}/10. chi m3a9ed. safi.",
    "{name} motm. {rating}/10. b7al chi hwayej. delete game.",
    "{name} motm. {rating}/10. l3ba khawya. bon courage.",
    "{name} motm. {rating}/10. walo. chi 7wayej. trash.",
    "{name} motm. {rating}/10. z3ma... star? hahahaha walo.",
    "{name} motm. {rating}/10. chi m3a9ed l3ba. safi yallah.",
    "{name} motm. {rating}/10. b7al chi m3a9ed. garbage."
]

POSITION_ROASTS = {
    "ST": ["striker khawya. b7al chi 9ahba dial l3ba.", "z3ma... 9ahba? walo. hahahaha.",
           "striker chi m3a9ed. delete game.", "9ahba dial l3ba. walo. safi.", "b7al chi striker khawya. trash."],
    "LW": ["winger khawya. b7al chi 9t3a dial lferrari khawya.", "z3ma... winger? walo. hahahaha.",
           "winger chi m3a9ed. delete game.", "9t3a khawya. walo. safi.", "b7al chi winger khawya. trash."],
    "RW": ["winger khawya. b7al chi 9t3a dial lferrari khawya.", "z3ma... winger? walo. hahahaha.",
           "winger chi m3a9ed. delete game.", "9t3a khawya. walo. safi.", "b7al chi winger khawya. trash."],
    "CM": ["midfielder khawya. b7al chi maestro dial l7wayej.", "z3ma... maestro? walo. hahahaha.",
           "midfielder chi m3a9ed. delete game.", "maestro khawya. walo. safi.", "b7al chi midfielder khawya. trash."],
    "CAM": ["playmaker khawya. b7al chi 10 dial l3ba khawya.", "z3ma... playmaker? walo. hahahaha.",
            "playmaker chi m3a9ed. delete game.", "10 khawya. walo. safi.", "b7al chi playmaker khawya. trash."],
    "CDM": ["destroyer khawya. b7al chi tank dial l3ba khawya.", "z3ma... destroyer? walo. hahahaha.",
            "destroyer chi m3a9ed. delete game.", "tank khawya. walo. safi.", "b7al chi destroyer khawya. trash."],
    "CB": ["defender khawya. b7al chi mur dial chi dar khawya.", "z3ma... defender? walo. hahahaha.",
           "defender chi m3a9ed. delete game.", "mur khawya. walo. safi.", "b7al chi defender khawya. trash."],
    "LB": ["defender khawya. b7al chi mur dial chi dar khawya.", "z3ma... defender? walo. hahahaha.",
           "defender chi m3a9ed. delete game.", "mur khawya. walo. safi.", "b7al chi defender khawya. trash."],
    "RB": ["defender khawya. b7al chi mur dial chi dar khawya.", "z3ma... defender? walo. hahahaha.",
           "defender chi m3a9ed. delete game.", "mur khawya. walo. safi.", "b7al chi defender khawya. trash."],
    "GK": ["goalkeeper khawya. b7al chi 7aris dial l3ba khawya.", "z3ma... goalkeeper? walo. hahahaha.",
           "goalkeeper chi m3a9ed. delete game.", "7aris khawya. walo. safi.", "b7al chi goalkeeper khawya. trash."],
    "LM": ["midfielder khawya. b7al chi maestro dial l7wayej.", "z3ma... midfielder? walo. hahahaha.",
           "midfielder chi m3a9ed. delete game.", "maestro khawya. walo. safi.", "b7al chi midfielder khawya. trash."],
    "RM": ["midfielder khawya. b7al chi maestro dial l7wayej.", "z3ma... midfielder? walo. hahahaha.",
           "midfielder chi m3a9ed. delete game.", "maestro khawya. walo. safi.", "b7al chi midfielder khawya. trash."]
}

BANTER_TEMPLATES = [
    "z3ma... pro clubs? walo. chi m3a9ed l3ba.", "b7al chi hwayej. delete game. safi.",
    "l3ba khawya. z3ma... football? hahahaha.", "chi m3a9ed. walo. bon courage.",
    "trash. garbage. l7wayej. walo.", "z3ma... team? b7al chi m3a9ed. safi.",
    "wallah! chi 7wayej. delete game.", "hakda. l3ba khawya. z3ma... walo.",
    "safi yallah. chi m3a9ed l3ba. trash.", "b7al chi hwayej. walo. c'est fini.",
    "z3ma... match? chi m3a9ed. hahahaha.", "walo. l7wayej. delete game. bon courage.",
    "chi m3a9ed l3ba. b7al chi hwayej. safi.", "trash. garbage. z3ma... win? walo.",
    "hakda hakda. chi m3a9ed. safi yallah."
]

DRAMA_TEMPLATES = [
    "z3ma... drama? walo. chi m3a9ed l7wayej.", "b7al chi polemique khawya. delete game.",
    "l7wayej. z3ma... drama? hahahaha walo.", "chi m3a9ed. walo. safi. bon courage.",
    "trash. garbage. chi polemique khawya.", "z3ma... tea? b7al chi hwayej. walo.",
    "wallah! chi 7wayej. delete game. safi.", "hakda. l3ba khawya. z3ma... drama? walo.",
    "safi yallah. chi m3a9ed l7wayej. trash.", "b7al chi hwayej. walo. c'est fini."
]

MEME_TEMPLATES = [
    "hahahaha chi m3a9ed. delete game.", "hahahaha l3ba khawya. walo. safi.",
    "hahahaha z3ma... meme? walo. chi 7wayej.", "hahahaha b7al chi hwayej. trash.",
    "hahahaha chi m3a9ed l3ba. bon courage.", "hahahaha walo. z3ma. hakda. safi.",
    "hahahaha l7wayej. delete game. garbage.", "hahahaha chi 7wayej. walo. c'est fini.",
    "hahahaha z3ma... funny? walo. hahahaha.", "hahahaha b7al chi m3a9ed. safi yallah."
]

TRANSFER_TEMPLATES = [
    "z3ma... transfer? walo. chi m3a9ed l7wayej.", "b7al chi transfer khawya. delete game.",
    "l7wayej. z3ma... move? hahahaha walo.", "chi m3a9ed. walo. safi. bon courage.",
    "trash. garbage. chi transfer khawya.", "z3ma... deal? b7al chi hwayej. walo.",
    "wallah! chi 7wayej. delete game. safi.", "hakda. l3ba khawya. z3ma... transfer? walo.",
    "safi yallah. chi m3a9ed l7wayej. trash.", "b7al chi hwayej. walo. c'est fini."
]

PREDICTION_TEMPLATES = {
    "win": ["z3ma... win? walo. chi m3a9ed l3ba.", "b7al chi prediction khawya. delete game.",
            "l3ba khawya. z3ma... victory? hahahaha walo.", "chi m3a9ed. walo. safi. bon courage.",
            "trash. garbage. chi prediction khawya."],
    "loss": ["wallah! loss. chi m3a9ed l3ba. delete game.", "b7al chi prediction khawya. walo. safi.",
             "l3ba khawya. z3ma... loss? hahahaha.", "chi m3a9ed. walo. bon courage. c'est fini.",
             "trash. garbage. chi prediction khawya."],
    "draw": ["noss noss. z3ma... draw? walo. chi m3a9ed.", "b7al chi prediction khawya. delete game.",
             "l3ba khawya. z3ma... noss noss? hahahaha walo.", "chi m3a9ed. walo. safi. bon courage.",
             "trash. garbage. chi prediction khawya."]
}

# ==========================================
# ADVANCED NATIVE DARIJA ROASTS (v2)
# ==========================================

ADVANCED_ROASTS = {
    "possession_loss": [
        "{name}: {losses} possession losses. z3ma... ballon d'or? hahahaha.",
        "{name}: {losses} marat kayt7arrak. chi m3a9ed l3ba.",
        "{name}: {losses} marat kaydrob l3adou. walo. safi.",
        "{name}: {losses} possession losses. b7al chi 9ahba dial l3ba.",
        "{name}: {losses} marat kaytferrej. l3ba khawya. delete game."
    ],
    "key_passes": [
        "{name}: {key_passes} key passes. z3ma... playmaker? walo.",
        "{name}: {key_passes} passes decisives. chi m3a9ed. safi.",
        "{name}: {key_passes} key passes. b7al chi passer khawya.",
        "{name}: {key_passes} passes. walo. l7wayej. delete game."
    ],
    "dribbles": [
        "{name}: {dribbles} dribbles. z3ma... messi? hahahaha walo.",
        "{name}: {dribbles} dribbles. chi m3a9ed. safi.",
        "{name}: {dribbles} dribbles. b7al chi 7wayej. trash.",
        "{name}: {dribbles} dribbles. walo. l3ba khawya. delete game."
    ],
    "interceptions": [
        "{name}: {interceptions} interceptions. z3ma... defender? walo.",
        "{name}: {interceptions} interceptions. chi m3a9ed. safi.",
        "{name}: {interceptions} interceptions. b7al chi mur khawya.",
        "{name}: {interceptions} interceptions. walo. delete game."
    ],
    "saves": [
        "{name}: {saves} saves. z3ma... neuer? hahahaha walo.",
        "{name}: {saves} saves. chi m3a9ed. safi.",
        "{name}: {saves} saves. b7al chi 7aris khawya.",
        "{name}: {saves} saves. walo. l3ba khawya. delete game."
    ],
    "clean_sheets": [
        "{name}: {clean_sheets} clean sheets. z3ma... wall? walo.",
        "{name}: {clean_sheets} clean sheets. chi m3a9ed. safi.",
        "{name}: {clean_sheets} clean sheets. b7al chi 7aris khawya.",
        "{name}: {clean_sheets} clean sheets. walo. delete game."
    ],
    "win_rate": [
        "{name}: {win_rate}% win rate. z3ma... winner? hahahaha.",
        "{name}: {win_rate}% win rate. chi m3a9ed. safi.",
        "{name}: {win_rate}% win rate. b7al chi hwayej. trash.",
        "{name}: {win_rate}% win rate. walo. l3ba khawya. delete game."
    ],
    "form": [
        "{name}: form {form}. z3ma... good form? walo.",
        "{name}: form {form}. chi m3a9ed. safi.",
        "{name}: form {form}. b7al chi hwayej. trash.",
        "{name}: form {form}. walo. delete game."
    ]
}

# ==========================================
# PERSONALITY MODES
# ==========================================

PERSONALITIES = {
    "casablanca": {
        "prefixes": ["wa 3ziz", "hakda", "b7al chi", "chi", "walo", "z3ma", "safi", "daba"],
        "suffixes": ["safi", "walo", "z3ma", "hakda", "daba", "yallah"],
        "intensity": 1.0
    },
    "analyst": {
        "prefixes": ["z3ma...", "b7al chi", "chi", "walo"],
        "suffixes": ["safi", "walo", "z3ma", "hakda"],
        "intensity": 0.7
    },
    "toxic": {
        "prefixes": ["wallah!", "trash", "garbage", "delete game", "chi m3a9ed"],
        "suffixes": ["delete game", "trash", "garbage", "walo", "safi"],
        "intensity": 1.2
    },
    "coach": {
        "prefixes": ["bon courage", "z3ma...", "b7al chi", "chi"],
        "suffixes": ["bon courage", "safi", "walo", "z3ma"],
        "intensity": 0.6
    },
    "commentator": {
        "prefixes": ["wallah!", "hahahaha", "z3ma...", "b7al chi"],
        "suffixes": ["hahahaha", "walo", "z3ma", "safi"],
        "intensity": 0.9
    },
    "cafeteria": {
        "prefixes": ["hahahaha", "z3ma...", "b7al chi", "chi", "walo"],
        "suffixes": ["hahahaha", "walo", "z3ma", "safi", "daba"],
        "intensity": 1.1
    }
}


class DarijaEngine:
    """Native Moroccan Darija engine - 95% roast, 5% neutral"""

    def __init__(self, squad_path: str = "squad.json"):
        self.squad = self._load_squad(squad_path)
        self.roast_mode = 0.95
        self.current_personality = "casablanca"
        self._positive_filter = self._build_positive_filter()
        self.memory = {"roast_counts": {}, "mvp_counts": {}, "worst_counts": {}}

    def _load_squad(self, path: str) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def _build_positive_filter(self) -> set:
        return {
            "good", "great", "amazing", "clean", "fire", "nice", "awesome",
            "excellent", "perfect", "best", "better", "wonderful", "fantastic",
            "superb", "brilliant", "outstanding", "incredible", "magnificent",
            "beautiful", "solid", "strong", "impressive", "phenomenal", "elite",
            "world class", "legendary", "goat", "clutch", "nasty", "sick",
            "dope", "lit", "smooth", "crispy", "beast", "monster", "killer",
            "dominant", "unstoppable", "unreal", "insane", "crazy", "wild",
            "mad", "ill", "pog", "poggers", "ggs", "wp", "well played",
            "gg", "good game", "nice one", "well done", "great job", "amazing job",
            "fantastic job", "incredible job", "outstanding job", "phenomenal job",
            "superb job", "brilliant job", "excellent job", "perfect job",
            "good work", "great work", "amazing work", "fantastic work",
            "incredible work", "outstanding work", "phenomenal work", "superb work",
            "brilliant work", "excellent work", "perfect work", "good effort",
            "great effort", "amazing effort", "fantastic effort", "incredible effort",
            "outstanding effort", "phenomenal effort", "superb effort", "brilliant effort",
            "excellent effort", "perfect effort", "good performance", "great performance",
            "amazing performance", "fantastic performance", "incredible performance",
            "outstanding performance", "phenomenal performance", "superb performance",
            "brilliant performance", "excellent performance", "perfect performance",
            "good show", "great show", "amazing show", "fantastic show",
            "incredible show", "outstanding show", "phenomenal show", "superb show",
            "brilliant show", "excellent show", "perfect show", "good stuff",
            "great stuff", "amazing stuff", "fantastic stuff", "incredible stuff",
            "outstanding stuff", "phenomenal stuff", "superb stuff", "brilliant stuff",
            "excellent stuff", "perfect stuff", "good play", "great play",
            "amazing play", "fantastic play", "incredible play", "outstanding play",
            "phenomenal play", "superb play", "brilliant play", "excellent play",
            "perfect play", "good move", "great move", "amazing move", "fantastic move",
            "incredible move", "outstanding move", "phenomenal move", "superb move",
            "brilliant move", "excellent move", "perfect move", "good shot",
            "great shot", "amazing shot", "fantastic shot", "incredible shot",
            "outstanding shot", "phenomenal shot", "superb shot", "brilliant shot",
            "excellent shot", "perfect shot", "good pass", "great pass", "amazing pass",
            "fantastic pass", "incredible pass", "outstanding pass", "phenomenal pass",
            "superb pass", "brilliant pass", "excellent pass", "perfect pass",
            "good save", "great save", "amazing save", "fantastic save",
            "incredible save", "outstanding save", "phenomenal save", "superb save",
            "brilliant save", "excellent save", "perfect save", "good tackle",
            "great tackle", "amazing tackle", "fantastic tackle", "incredible tackle",
            "outstanding tackle", "phenomenal tackle", "superb tackle", "brilliant tackle",
            "excellent tackle", "perfect tackle", "good goal", "great goal",
            "amazing goal", "fantastic goal", "incredible goal", "outstanding goal",
            "phenomenal goal", "superb goal", "brilliant goal", "excellent goal",
            "perfect goal", "good assist", "great assist", "amazing assist",
            "fantastic assist", "incredible assist", "outstanding assist",
            "phenomenal assist", "superb assist", "brilliant assist", "excellent assist",
            "perfect assist", "good defense", "great defense", "amazing defense",
            "fantastic defense", "incredible defense", "outstanding defense",
            "phenomenal defense", "superb defense", "brilliant defense",
            "excellent defense", "perfect defense", "good attack", "great attack",
            "amazing attack", "fantastic attack", "incredible attack", "outstanding attack",
            "phenomenal attack", "superb attack", "brilliant attack", "excellent attack",
            "perfect attack", "good game", "great game", "amazing game", "fantastic game",
            "incredible game", "outstanding game", "phenomenal game", "superb game",
            "brilliant game", "excellent game", "perfect game", "good match",
            "great match", "amazing match", "fantastic match", "incredible match",
            "outstanding match", "phenomenal match", "superb match", "brilliant match",
            "excellent match", "perfect match", "good win", "great win", "amazing win",
            "fantastic win", "incredible win", "outstanding win", "phenomenal win",
            "superb win", "brilliant win", "excellent win", "perfect win", "good victory",
            "great victory", "amazing victory", "fantastic victory", "incredible victory",
            "outstanding victory", "phenomenal victory", "superb victory", "brilliant victory",
            "excellent victory", "perfect victory", "good result", "great result",
            "amazing result", "fantastic result", "incredible result", "outstanding result",
            "phenomenal result", "superb result", "brilliant result", "excellent result",
            "perfect result", "good season", "great season", "amazing season",
            "fantastic season", "incredible season", "outstanding season",
            "phenomenal season", "superb season", "brilliant season", "excellent season",
            "perfect season", "good streak", "great streak", "amazing streak",
            "fantastic streak", "incredible streak", "outstanding streak",
            "phenomenal streak", "superb streak", "brilliant streak", "excellent streak",
            "perfect streak", "good run", "great run", "amazing run", "fantastic run",
            "incredible run", "outstanding run", "phenomenal run", "superb run",
            "brilliant run", "excellent run", "perfect run", "good form", "great form",
            "amazing form", "fantastic form", "incredible form", "outstanding form",
            "phenomenal form", "superb form", "brilliant form", "excellent form",
            "perfect form", "good rating", "great rating", "amazing rating",
            "fantastic rating", "incredible rating", "outstanding rating",
            "phenomenal rating", "superb rating", "brilliant rating", "excellent rating",
            "perfect rating", "good stats", "great stats", "amazing stats",
            "fantastic stats", "incredible stats", "outstanding stats",
            "phenomenal stats", "superb stats", "brilliant stats", "excellent stats",
            "perfect stats", "good performance", "great performance", "amazing performance",
            "fantastic performance", "incredible performance", "outstanding performance",
            "phenomenal performance", "superb performance", "brilliant performance",
            "excellent performance", "perfect performance", "good player", "great player",
            "amazing player", "fantastic player", "incredible player", "outstanding player",
            "phenomenal player", "superb player", "brilliant player", "excellent player",
            "perfect player", "good team", "great team", "amazing team", "fantastic team",
            "incredible team", "outstanding team", "phenomenal team", "superb team",
            "brilliant team", "excellent team", "perfect team", "good squad", "great squad",
            "amazing squad", "fantastic squad", "incredible squad", "outstanding squad",
            "phenomenal squad", "superb squad", "brilliant squad", "excellent squad",
            "perfect squad", "good club", "great club", "amazing club", "fantastic club",
            "incredible club", "outstanding club", "phenomenal club", "superb club",
            "brilliant club", "excellent club", "perfect club"
        }

    def set_personality(self, personality: str):
        """Switch bot personality dynamically"""
        if personality in PERSONALITIES:
            self.current_personality = personality

    def _get_personality_prefix(self) -> str:
        """Get prefix based on current personality"""
        personality = PERSONALITIES.get(self.current_personality, PERSONALITIES["casablanca"])
        return random.choice(personality["prefixes"]) if random.random() < personality["intensity"] else ""

    def _get_personality_suffix(self) -> str:
        """Get suffix based on current personality"""
        personality = PERSONALITIES.get(self.current_personality, PERSONALITIES["casablanca"])
        return random.choice(personality["suffixes"]) if random.random() < personality["intensity"] else ""

    def _filter_positive(self, text: str) -> str:
        """Remove any positive words from output"""
        words = text.lower().split()
        filtered = [w for w in words if w not in self._positive_filter]
        return " ".join(filtered) if filtered else "walo. safi."

    def _add_imperfections(self, text: str) -> str:
        """Add human-like imperfections to text"""
        # Randomly lowercase start
        if random.random() < 0.3:
            text = text[0].lower() + text[1:] if text else text
        # Randomly add extra punctuation
        if random.random() < 0.2:
            text = text.replace(".", "!!", 1)
        # Randomly drop articles
        if random.random() < 0.15:
            text = text.replace(" le ", " ", 1).replace(" la ", " ", 1)
        return text

    def _format_roast(self, template: str, **kwargs) -> str:
        """Format a roast template with imperfections"""
        text = template.format(**kwargs)
        text = self._add_imperfections(text)
        # Add personality flavor
        prefix = self._get_personality_prefix()
        suffix = self._get_personality_suffix()
        if prefix and not text.startswith(prefix):
            text = f"{prefix}. {text}"
        if suffix and not text.endswith(suffix):
            text = f"{text} {suffix}."
        return text

    def roast_player(self, name: str, stats: dict, matches: int = 5) -> List[str]:
        """Generate data-driven roast for a player"""
        roasts = []
        player_info = self.squad.get(name.lower(), {})
        nickname = player_info.get("nickname", name)
        position = player_info.get("position", "")

        # Goals roast
        if "goals" in stats:
            goals = stats["goals"]
            if goals == 0:
                roasts.append(self._format_roast(
                    random.choice(ROAST_TEMPLATES["goals"]),
                    name=nickname, goals=goals, matches=matches
                ))
            elif goals < matches * 0.5:
                roasts.append(self._format_roast(
                    random.choice(ROAST_TEMPLATES["goals"]),
                    name=nickname, goals=goals, matches=matches
                ))

        # Assists roast
        if "assists" in stats:
            assists = stats["assists"]
            if assists == 0:
                roasts.append(self._format_roast(
                    random.choice(ROAST_TEMPLATES["assists"]),
                    name=nickname, assists=assists
                ))

        # Rating roast
        if "rating" in stats:
            rating = stats["rating"]
            if rating < 7.0:
                roasts.append(self._format_roast(
                    random.choice(ROAST_TEMPLATES["rating"]),
                    name=nickname, rating=rating
                ))

        # Defense roast
        if "tackles" in stats:
            tackles = stats["tackles"]
            if tackles < 2:
                roasts.append(self._format_roast(
                    random.choice(ROAST_TEMPLATES["defense"]),
                    name=nickname, tackles=tackles
                ))

        # Shots roast
        if "shots" in stats:
            shots = stats["shots"]
            if shots > 5 and stats.get("goals", 0) == 0:
                roasts.append(self._format_roast(
                    random.choice(ROAST_TEMPLATES["shots"]),
                    name=nickname, shots=shots
                ))

        # Pass accuracy roast
        if "pass_accuracy" in stats:
            passes = stats["pass_accuracy"]
            if passes < 70:
                roasts.append(self._format_roast(
                    random.choice(ROAST_TEMPLATES["passes"]),
                    name=nickname, passes=passes
                ))

        # Position roast
        if position in POSITION_ROASTS:
            roasts.append(self._format_roast(
                random.choice(POSITION_ROASTS[position]),
                name=nickname
            ))

        # Advanced stats roasts
        if "possession_losses" in stats:
            losses = stats["possession_losses"]
            if losses > 10:
                roasts.append(self._format_roast(
                    random.choice(ADVANCED_ROASTS["possession_loss"]),
                    name=nickname, losses=losses
                ))

        if "key_passes" in stats:
            key_passes = stats["key_passes"]
            if key_passes == 0:
                roasts.append(self._format_roast(
                    random.choice(ADVANCED_ROASTS["key_passes"]),
                    name=nickname, key_passes=key_passes
                ))

        if "dribbles" in stats:
            dribbles = stats["dribbles"]
            if dribbles > 5 and stats.get("goals", 0) == 0:
                roasts.append(self._format_roast(
                    random.choice(ADVANCED_ROASTS["dribbles"]),
                    name=nickname, dribbles=dribbles
                ))

        # General fallback roast
        if not roasts:
            roasts.append(self._format_roast(
                random.choice(ROAST_TEMPLATES["general"]),
                name=nickname
            ))

        # Update memory
        self.memory["roast_counts"][name.lower()] = self.memory["roast_counts"].get(name.lower(), 0) + 1

        return roasts[:2]  # Max 2 sentences

    def roast_match_result(self, team_goals: int, opponent_goals: int, opponent_name: str = "") -> str:
        """Roast match result based on score"""
        if team_goals > opponent_goals:
            if team_goals - opponent_goals >= 3:
                return self._format_roast(random.choice(MATCH_RESULT_ROASTS["win_big"]))
            else:
                return self._format_roast(random.choice(MATCH_RESULT_ROASTS["win_small"]))
        elif team_goals == opponent_goals:
            return self._format_roast(random.choice(MATCH_RESULT_ROASTS["draw"]))
        else:
            return self._format_roast(random.choice(MATCH_RESULT_ROASTS["loss"]))

    def roast_motm(self, name: str, rating: float) -> str:
        """Roast even the MOTM"""
        player_info = self.squad.get(name.lower(), {})
        nickname = player_info.get("nickname", name)
        return self._format_roast(random.choice(MOTM_ROASTS), name=nickname, rating=rating)

    def banter(self) -> str:
        """Random football banter"""
        return self._format_roast(random.choice(BANTER_TEMPLATES))

    def drama(self) -> str:
        """Random drama/polemique"""
        return self._format_roast(random.choice(DRAMA_TEMPLATES))

    def meme(self) -> str:
        """Random meme in Darija"""
        return self._format_roast(random.choice(MEME_TEMPLATES))

    def transfer(self) -> str:
        """Random transfer rumor"""
        return self._format_roast(random.choice(TRANSFER_TEMPLATES))

    def predict(self, prediction: str) -> str:
        """Roast a match prediction"""
        return self._format_roast(random.choice(PREDICTION_TEMPLATES.get(prediction, PREDICTION_TEMPLATES["loss"])))

    def get_worst_player(self, players_stats: dict) -> Tuple[str, str]:
        """Find and roast the worst player"""
        worst = None
        worst_score = float('inf')
        for name, stats in players_stats.items():
            score = stats.get("rating", 10) - stats.get("goals", 0) * 2 - stats.get("assists", 0)
            if score < worst_score:
                worst_score = score
                worst = name
        if worst:
            player_info = self.squad.get(worst.lower(), {})
            nickname = player_info.get("nickname", worst)
            roast = self._format_roast(
                "{name}. worst of the week. z3ma... player? walo. delete game.",
                name=nickname
            )
            self.memory["worst_counts"][worst.lower()] = self.memory["worst_counts"].get(worst.lower(), 0) + 1
            return worst, roast
        return "", ""

    def get_mvp(self, players_stats: dict) -> Tuple[str, str]:
        """Find and roast the MVP (even best gets roasted)"""
        best = None
        best_score = -1
        for name, stats in players_stats.items():
            score = stats.get("rating", 0) + stats.get("goals", 0) * 2 + stats.get("assists", 0)
            if score > best_score:
                best_score = score
                best = name
        if best:
            player_info = self.squad.get(best.lower(), {})
            nickname = player_info.get("nickname", best)
            rating = players_stats[best].get("rating", 0)
            roast = self.roast_motm(nickname, rating)
            self.memory["mvp_counts"][best.lower()] = self.memory["mvp_counts"].get(best.lower(), 0) + 1
            return best, roast
        return "", ""

    def compare_players(self, p1_name: str, p1_stats: dict, p2_name: str, p2_stats: dict) -> str:
        """Compare two players with roast"""
        p1_info = self.squad.get(p1_name.lower(), {})
        p2_info = self.squad.get(p2_name.lower(), {})
        p1_nick = p1_info.get("nickname", p1_name)
        p2_nick = p2_info.get("nickname", p2_name)

        p1_score = p1_stats.get("rating", 0) + p1_stats.get("goals", 0) * 2 + p1_stats.get("assists", 0)
        p2_score = p2_stats.get("rating", 0) + p2_stats.get("goals", 0) * 2 + p2_stats.get("assists", 0)

        if p1_score > p2_score:
            winner, loser = p1_nick, p2_nick
        else:
            winner, loser = p2_nick, p1_nick

        return self._format_roast(
            "{winner} vs {loser}. z3ma... comparison? walo. chi m3a9ed l3ba. {loser} delete game.",
            winner=winner, loser=loser
        )

    def roast_leaderboard(self, leaderboard: List[Tuple[str, dict]]) -> List[str]:
        """Roast leaderboard entries"""
        roasts = []
        for i, (name, stats) in enumerate(leaderboard[:5]):
            player_info = self.squad.get(name.lower(), {})
            nickname = player_info.get("nickname", name)
            if i == 0:
                roasts.append(self._format_roast(
                    "{name}. #1. z3ma... best? walo. chi m3a9ed.", name=nickname
                ))
            elif i == len(leaderboard) - 1:
                roasts.append(self._format_roast(
                    "{name}. last. trash. garbage. delete game.", name=nickname
                ))
            else:
                roasts.append(self._format_roast(
                    "{name}. #{rank}. b7al chi hwayej. walo.", name=nickname, rank=i+1
                ))
        return roasts

    def save_memory(self, path: str = "bot_memory.json"):
        """Save bot memory"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, indent=2, ensure_ascii=False)

    def load_memory(self, path: str = "bot_memory.json"):
        """Load bot memory"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.memory = json.load(f)
        except:
            pass


# Singleton instance
_engine = None

def get_engine(squad_path: str = "squad.json") -> DarijaEngine:
    global _engine
    if _engine is None:
        _engine = DarijaEngine(squad_path)
    return _engine
