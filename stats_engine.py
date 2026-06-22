import math
from typing import List, Dict
from models import PlayerStats, ClubStats, MatchResult

class StatsEngine:
    POSITION_WEIGHTS = {
        "GK":  {"def": 1.5, "off": 0.3, "pass": 0.8},
        "CB":  {"def": 1.4, "off": 0.4, "pass": 0.9},
        "LB":  {"def": 1.2, "off": 0.6, "pass": 1.0},
        "RB":  {"def": 1.2, "off": 0.6, "pass": 1.0},
        "CDM": {"def": 1.2, "off": 0.7, "pass": 1.3},
        "CM":  {"def": 1.0, "off": 0.9, "pass": 1.4},
        "CAM": {"def": 0.6, "off": 1.3, "pass": 1.4},
        "LW":  {"def": 0.5, "off": 1.4, "pass": 1.0},
        "RW":  {"def": 0.5, "off": 1.4, "pass": 1.0},
        "ST":  {"def": 0.3, "off": 1.5, "pass": 0.8},
        "CF":  {"def": 0.5, "off": 1.4, "pass": 1.0},
    }

    @classmethod
@classmethod
def compute_advanced(cls, player: PlayerStats, position: str = "CM") -> PlayerStats:
 """
 Stable advanced stats.

 Uses reliable PCT fields:
 - rating
 - goals
 - assists
 - pass accuracy
 - passes made
 - tackles
 - clean sheets
 - possession losses
 - cards
 - win rate

 Avoids unreliable/missing fields:
 - shots_on_target
 - key_passes
 - fouls
 - interceptions
 """
 weights = cls.POSITION_WEIGHTS.get(position, cls.POSITION_WEIGHTS["CM"])
 g = max(getattr(player, "games", 0), 1)

 goals = getattr(player, "goals", 0) or 0
 assists = getattr(player, "assists", 0) or 0
 rating_pg = getattr(player, "rating_pg", 0) or 0
 tackles = getattr(player, "tackles", 0) or 0
 clean_sheets = getattr(player, "clean_sheets", 0) or 0
 passes_made = getattr(player, "passes_made", 0) or 0
 pass_accuracy = getattr(player, "pass_accuracy", 0) or 0
 possession_losses = getattr(player, "possession_losses", 0) or 0
 cards = getattr(player, "cards", 0) or 0
 win_rate = getattr(player, "win_rate", 0) or 0

 goals_pg = goals / g
 assists_pg = assists / g
 tackles_pg = tackles / g
 passes_pg = passes_made / g
 losses_pg = possession_losses / g
 cards_pg = cards / g
 clean_sheet_rate = clean_sheets / g

 # Rating is the most stable PCT value.
 rating_score = rating_pg * 10

 # Attack score: goals + assists, weighted by position.
 off_contrib = (
  goals_pg * 25 +
  assists_pg * 18 +
  rating_pg * 2
 ) * weights["off"]

 # Defense score: tackles + clean sheets, weighted by position.
 def_contrib = (
  tackles_pg * 4 +
  clean_sheet_rate * 12 +
  rating_pg
 ) * weights["def"]

 # Passing score: accuracy + volume, weighted by position.
 safe_pass_accuracy = max(0, min(pass_accuracy, 100))
 safe_passes_pg = max(0, min(passes_pg, 80))
 pass_contrib = (
  safe_pass_accuracy * 0.20 +
  safe_passes_pg * 0.20
 ) * weights["pass"]

 # Small win bonus. Do not let win rate dominate individual stats.
 win_bonus = max(0, min(win_rate, 100)) * 0.10

 # Error penalty.
 error_penalty = (
  losses_pg * 1.5 +
  cards_pg * 8
 )

 player.offensive_contribution = round(max(0, off_contrib), 2)
 player.defensive_contribution = round(max(0, def_contrib), 2)
 player.passing_influence = round(max(0, pass_contrib), 2)

 player.impact_score = round(
  max(
   0,
   rating_score +
   player.offensive_contribution +
   player.defensive_contribution +
   player.passing_influence +
   win_bonus -
   error_penalty
  ),
  2
 )

 # Carry = good impact + goals/assists + win rate.
 player.clutch_score = round(
  max(
   0,
   player.impact_score * 0.45 +
   goals_pg * 20 +
   assists_pg * 14 +
   win_bonus
  ),
  2
 )

 # Fraud/error = low rating + possession loss + cards + bad passing.
 low_rating_penalty = max(0, 6.5 - rating_pg) * 5
 bad_pass_penalty = max(0, 75 - pass_accuracy) * 0.15 if pass_accuracy > 0 else 2
 loss_penalty = losses_pg * 2
 card_penalty = cards_pg * 10

 player.error_score = round(
  max(
   0,
   low_rating_penalty +
   bad_pass_penalty +
   loss_penalty +
   card_penalty
  ),
  2
 )

 player.throwing_score = round(
  max(
   0,
   player.error_score +
   max(0, 6.0 - rating_pg) * 2
  ),
  2
 )

 # 6.5 is a better "average" than 5.0 for FC ratings.
 player.form_index = round(rating_pg - 6.5, 2)

 return player

    @classmethod
    def compute_advanced(cls, player: PlayerStats, position: str = "CM") -> PlayerStats:
        weights = cls.POSITION_WEIGHTS.get(position, cls.POSITION_WEIGHTS["CM"])
        g = max(player.games, 1)

        off_contrib = (player.goals * 3 + player.assists * 2 + player.shots_on_target * 0.5 + player.key_passes * 1.5)
        def_contrib = (player.tackles * 2 + player.interceptions * 1.5 + player.clean_sheets * 3)
        pass_contrib = (player.passes_made * 0.05 + player.pass_accuracy * 0.5 + player.key_passes * 2)

        player.offensive_contribution = round(off_contrib / g * weights["off"], 2)
        player.defensive_contribution = round(def_contrib / g * weights["def"], 2)
        player.passing_influence     = round(pass_contrib / g * weights["pass"], 2)

        player.impact_score = round(
            player.offensive_contribution +
            player.defensive_contribution +
            player.passing_influence, 2
        )

        clutch_base = player.rating_pg * (player.win_rate / 100) * 10
        player.clutch_score = round(clutch_base, 2)

        player.error_score = round(
            (player.possession_losses * 1.5 + player.fouls * 2 + player.cards * 5) / g, 2
        )

        player.throwing_score = round(
            player.error_score / max(player.rating_pg, 1.0), 2
        )

        player.form_index = round(player.rating_pg - 5.0, 2)

        return player

    @classmethod
    def compute_all(cls, players: List[PlayerStats], squad_map: Dict) -> List[PlayerStats]:
        result = []
        for p in players:
            pos = squad_map.get(p.name, {}).get("position", "CM")
            p = cls.compute_per_game(p)
            p = cls.compute_advanced(p, pos)
            result.append(p)
        return result

    @classmethod
    def get_mvp(cls, players: List[PlayerStats]) -> PlayerStats:
        return max(players, key=lambda p: p.impact_score)

    @classmethod
    def get_worst(cls, players: List[PlayerStats]) -> PlayerStats:
        return min(players, key=lambda p: p.impact_score)

    @classmethod
    def get_fraud(cls, players: List[PlayerStats]) -> PlayerStats:
        return max(players, key=lambda p: p.throwing_score)

    @classmethod
    def get_carry(cls, players: List[PlayerStats]) -> PlayerStats:
        scored = [(p.impact_score + p.clutch_score, p) for p in players]
        return max(scored, key=lambda x: x[0])[1]

    @classmethod
    def get_ghost(cls, players: List[PlayerStats]) -> PlayerStats:
        return min(players, key=lambda p: p.minutes_played / max(p.games, 1))

    @classmethod
    def get_ball_hog(cls, players: List[PlayerStats]) -> PlayerStats:
        scored = [(p.possession_losses / max(p.assists, 1), p) for p in players]
        return max(scored, key=lambda x: x[0])[1]

    @classmethod
    def interpret_stat(cls, stat_name: str, value: float, position: str = "") -> str:
        interpretations = {
            "pass_accuracy": {
                (0, 60):   "Pass accuracy {val}% — كتباصي الكرة بحال إلا كتدير raffle.",
                (60, 75):  "Pass accuracy {val}% — 3ndak 25% ديال التخربيق فكل باصة.",
                (75, 85):  "Pass accuracy {val}% — مزيان، ولكن داك 15% الباقي خاصو تحقيق.",
                (85, 92):  "Pass accuracy {val}% — صاحي، كتباصي بحال Modrić.",
                (92, 100): "Pass accuracy {val}% — هادي ماشي pass accuracy، هادي precision surgical.",
            },
            "rating": {
                (0, 5):  "Rating {val} — هادي ماشي note، هادي warning.",
                (5, 6):  "Rating {val} — كنتي NPC رسمي اليوم.",
                (6, 7):  "Rating {val} — ماشي مزيان ماشي خايب، بحالك بحال باباك.",
                (7, 8):  "Rating {val} — صاحي، كتبان لي كتعرف شنو كتدير.",
                (8, 10): "Rating {val} — هادا rating ديال Ballon d'Or، ولا غير lucky game؟",
            },
            "goals_pg": {
                (0, 0.3):   "Goals per game {val} — الحارس دار save أكثر منك.",
                (0.3, 0.7): "Goals per game {val} — كتسجل من فترة لفترة، بحال taxes.",
                (0.7, 1.2): "Goals per game {val} — كتسجل بانتظام، مزيان.",
                (1.2, 2):   "Goals per game {val} — هادا striker حقيقي، كتضرب بحال Haaland.",
                (2, 10):    "Goals per game {val} — واش كتباغي تدخل التاريخ ولا شنو؟",
            },
            "impact_score": {
                (0, 20):   "Impact {val} — واش كتجي تشوف المباراة ولا تلعب؟",
                (20, 40):  "Impact {val} — كتبان بحال substitute ديال substitute.",
                (40, 60):  "Impact {val} — ماشي مزيان ماشي خايب، average.",
                (60, 80):  "Impact {val} — صاحي، كتجبد الفريق.",
                (80, 100): "Impact {val} — هادا carry رسمي، Ballon d'Or material.",
            },
        }

        ranges = interpretations.get(stat_name, {})
        for (low, high), text in ranges.items():
            if low <= value < high:
                return text.replace("{val}", str(value))

        return f"{stat_name}: {value}"
