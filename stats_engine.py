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
    def compute_per_game(cls, player: PlayerStats) -> PlayerStats:
        g = max(player.games, 1)
        player.goals_pg = round(player.goals / g, 2)
        player.assists_pg = round(player.assists / g, 2)

        # PCT rating is usually already an average (1-10). If it's cumulative, divide it.
        if player.rating > 10 and player.games > 1:
            player.rating_pg = round(player.rating / g, 2)
        else:
            player.rating_pg = round(player.rating, 2)

        # Only recompute win_rate when wins/losses/draws are actually populated.
        # The scraper delivers win_rate directly from PCT in most cases and leaves
        # W/L/D at 0 — recomputing in that case would clobber a correct value to 0.
        wld_total = player.wins + player.losses + player.draws
        if wld_total > 0:
            player.win_rate = round(player.wins / wld_total * 100, 1)
        # else: keep whatever the scraper set (including 0.0 if no data at all)

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
