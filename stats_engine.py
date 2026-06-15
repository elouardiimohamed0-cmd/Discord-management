import math
from typing import List, Dict
from models import PlayerStats, ClubStats, MatchResult

class StatsEngine:
    POSITION_WEIGHTS = {
        "GK": {"def": 1.5, "off": 0.3, "pass": 0.8},
        "CB": {"def": 1.4, "off": 0.4, "pass": 0.9},
        "LB": {"def": 1.2, "off": 0.6, "pass": 1.0},
        "RB": {"def": 1.2, "off": 0.6, "pass": 1.0},
        "CDM": {"def": 1.2, "off": 0.7, "pass": 1.3},
        "CM": {"def": 1.0, "off": 0.9, "pass": 1.4},
        "CAM": {"def": 0.6, "off": 1.3, "pass": 1.4},
        "LW": {"def": 0.5, "off": 1.4, "pass": 1.0},
        "RW": {"def": 0.5, "off": 1.4, "pass": 1.0},
        "ST": {"def": 0.3, "off": 1.5, "pass": 0.8},
        "CF": {"def": 0.5, "off": 1.4, "pass": 1.0},
    }
    
    @classmethod
    def compute_per_game(cls, player: PlayerStats) -> PlayerStats:
        g = max(player.games, 1)
        player.goals_pg = round(player.goals / g, 2)
        player.assists_pg = round(player.assists / g, 2)
        player.rating_pg = round(player.rating / g, 2) if player.rating > 10 else round(player.rating, 2)
        player.win_rate = round(player.wins / g * 100, 1) if player.wins > 0 else 0.0
        return player
    
    @classmethod
    def compute_advanced(cls, player: PlayerStats, position: str = "CM") -> PlayerStats:
        weights = cls.POSITION_WEIGHTS.get(position, cls.POSITION_WEIGHTS["CM"])
        g = max(player.games, 1)
        
        # Impact Score: weighted offensive + defensive + passing
        off_contrib = (player.goals * 3 + player.assists * 2 + player.shots_on_target * 0.5 + player.key_passes * 1.5)
        def_contrib = (player.tackles * 2 + player.interceptions * 1.5 + player.clean_sheets * 3)
        pass_contrib = (player.passes_made * 0.05 + player.pass_accuracy * 0.5 + player.key_passes * 2)
        
        player.offensive_contribution = round(off_contrib / g * weights["off"], 2)
        player.defensive_contribution = round(def_contrib / g * weights["def"], 2)
        player.passing_influence = round(pass_contrib / g * weights["pass"], 2)
        
        player.impact_score = round(
            player.offensive_contribution + 
            player.defensive_contribution + 
            player.passing_influence, 2
        )
        
        # Clutch Score: rating in close games (simulated from win rate + rating)
        clutch_base = player.rating_pg * (player.win_rate / 100) * 10
        player.clutch_score = round(clutch_base, 2)
        
        # Error Score: possession losses + fouls + cards weighted
        player.error_score = round(
            (player.possession_losses * 1.5 + player.fouls * 2 + player.cards * 5) / g, 2
        )
        
        # Throwing Score: error score relative to rating (higher = more errors per rating point)
        player.throwing_score = round(
            player.error_score / max(player.rating_pg, 1.0), 2
        )
        
        # Form Index: recent trend (simplified as rating-based momentum)
        # In real implementation, compare last 5 vs previous 5
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
        # Highest throwing score = biggest fraud
        return max(players, key=lambda p: p.throwing_score)
    
    @classmethod
    def get_carry(cls, players: List[PlayerStats]) -> PlayerStats:
        # Highest impact + clutch
        scored = [(p.impact_score + p.clutch_score, p) for p in players]
        return max(scored, key=lambda x: x[0])[1]
    
    @classmethod
    def get_ghost(cls, players: List[PlayerStats]) -> PlayerStats:
        # Lowest minutes per game (if available)
        return min(players, key=lambda p: p.minutes_played / max(p.games, 1))
    
    @classmethod
    def get_ball_hog(cls, players: List[PlayerStats]) -> PlayerStats:
        # High possession losses + low assists
        scored = [(p.possession_losses / max(p.assists, 1), p) for p in players]
        return max(scored, key=lambda x: x[0])[1]
    
    @classmethod
    def interpret_stat(cls, stat_name: str, value: float, position: str = "") -> str:
        """Return a Darija-ready interpretation of a stat"""
        interpretations = {
            "pass_accuracy": {
                (0, 60): "Pass accuracy {val}% — كتباصي الكرة بحال إلا كتدير raffle.",
                (60, 75): "Pass accuracy {val}% — 3ndak 25% ديال التخربيق فكل باصة.",
                (75, 85): "Pass accuracy {val}% — مزيان، ولكن داك 15% الباقي خاصو تحقيق.",
                (85, 92): "Pass accuracy {val}% — صاحي، كتباصي بحال Modrić.",
                (92, 100): "Pass accuracy {val}% — هادي ماشي pass accuracy، هادي precision surgical.",
            },
            "rating": {
                (0, 5): "Rating {val} — هادي ماشي note، هادي warning.",
                (5, 6): "Rating {val} — كنتي NPC رسمي اليوم.",
                (6, 7): "Rating {val} — ماشي مزيان ماشي خايب، بحالك بحال باباك.",
                (7, 8): "Rating {val} — صاحي، كتبان لي كتعرف شنو كتدير.",
                (8, 10): "Rating {val} — هادا rating ديال Ballon d'Or، ولا غير lucky game؟",
            },
            "goals_pg": {
                (0, 0.3): "Goals per game {val} — الحارس دار save أكثر منك.",
                (0.3, 0.7): "Goals per game {val} — كتسجل من فترة لفترة، بحال taxes.",
                (0.7, 1.2): "Goals per game {val} — كتسجل بانتظام، مزيان.",
                (1.2, 2): "Goals per game {val} — هادا striker حقيقي، كتضرب بحال Haaland.",
                (2, 10): "Goals per game {val} — واش كتباغي تدخل التاريخ ولا شنو؟",
            },
        }
        
        ranges = interpretations.get(stat_name, {})
        for (low, high), text in ranges.items():
            if low <= value < high:
                return text.replace("{val}", str(value))
        
        return f"{stat_name}: {value}"
