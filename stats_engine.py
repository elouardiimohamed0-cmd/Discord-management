"""
Rachad L3ERGONI Bot - Stats Engine v2
Fixed: accepts dict from scraper, added match_exists(), proper squad name mapping
"""

import json
import math
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class PlayerMatchStats:
    """Complete stats for a single match"""
    name: str
    position: str = "unknown"
    goals: int = 0
    assists: int = 0
    shots: int = 0
    shots_on_target: int = 0
    passes_attempted: int = 0
    passes_completed: int = 0
    key_passes: int = 0
    tackles: int = 0
    interceptions: int = 0
    possession_losses: int = 0
    dribbles_attempted: int = 0
    dribbles_completed: int = 0
    fouls: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    rating: float = 6.0
    motm: bool = False
    minutes_played: int = 90
    distance_covered: float = 0.0
    sprint_speed: float = 0.0

    @property
    def pass_accuracy(self) -> float:
        if self.passes_attempted == 0:
            return 0.0
        return round((self.passes_completed / self.passes_attempted) * 100, 1)

    @property
    def shot_accuracy(self) -> float:
        if self.shots == 0:
            return 0.0
        return round((self.shots_on_target / self.shots) * 100, 1)

    @property
    def dribble_success(self) -> float:
        if self.dribbles_attempted == 0:
            return 0.0
        return round((self.dribbles_completed / self.dribbles_attempted) * 100, 1)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "position": self.position,
            "goals": self.goals,
            "assists": self.assists,
            "shots": self.shots,
            "shots_on_target": self.shots_on_target,
            "passes_attempted": self.passes_attempted,
            "passes_completed": self.passes_completed,
            "pass_accuracy": self.pass_accuracy,
            "key_passes": self.key_passes,
            "tackles": self.tackles,
            "interceptions": self.interceptions,
            "possession_losses": self.possession_losses,
            "dribbles_attempted": self.dribbles_attempted,
            "dribbles_completed": self.dribbles_completed,
            "dribble_success": self.dribble_success,
            "fouls": self.fouls,
            "yellow_cards": self.yellow_cards,
            "red_cards": self.red_cards,
            "rating": self.rating,
            "motm": self.motm,
            "minutes_played": self.minutes_played,
            "distance_covered": self.distance_covered,
            "sprint_speed": self.sprint_speed,
            "shot_accuracy": self.shot_accuracy
        }


@dataclass
class MatchResult:
    """Complete match result with all team stats"""
    match_id: str
    date: str
    opponent: str
    team_goals: int = 0
    opponent_goals: int = 0
    team_possession: float = 50.0
    opponent_possession: float = 50.0
    team_shots: int = 0
    opponent_shots: int = 0
    team_shots_on_target: int = 0
    opponent_shots_on_target: int = 0
    team_passes: int = 0
    opponent_passes: int = 0
    team_tackles: int = 0
    opponent_tackles: int = 0
    team_corners: int = 0
    opponent_corners: int = 0
    team_fouls: int = 0
    opponent_fouls: int = 0
    match_type: str = "gameType9"
    player_stats: Dict[str, PlayerMatchStats] = None

    def __post_init__(self):
        if self.player_stats is None:
            self.player_stats = {}

    @property
    def result(self) -> str:
        if self.team_goals > self.opponent_goals:
            return "win"
        elif self.team_goals < self.opponent_goals:
            return "loss"
        return "draw"

    @property
    def goal_difference(self) -> int:
        return self.team_goals - self.opponent_goals

    def to_dict(self) -> dict:
        return {
            "match_id": self.match_id,
            "date": self.date,
            "opponent": self.opponent,
            "result": self.result,
            "team_goals": self.team_goals,
            "opponent_goals": self.opponent_goals,
            "goal_difference": self.goal_difference,
            "team_possession": self.team_possession,
            "opponent_possession": self.opponent_possession,
            "team_shots": self.team_shots,
            "opponent_shots": self.opponent_shots,
            "team_shots_on_target": self.team_shots_on_target,
            "opponent_shots_on_target": self.opponent_shots_on_target,
            "team_passes": self.team_passes,
            "opponent_passes": self.opponent_passes,
            "team_tackles": self.team_tackles,
            "opponent_tackles": self.opponent_tackles,
            "team_corners": self.team_corners,
            "opponent_corners": self.opponent_corners,
            "team_fouls": self.team_fouls,
            "opponent_fouls": self.opponent_fouls,
            "match_type": self.match_type,
            "player_stats": {k: v.to_dict() for k, v in self.player_stats.items()}
        }


class StatsEngine:
    """Engine to gather, process, and analyze all Pro Clubs stats"""

    def __init__(self, data_path: str = "match_data.json"):
        self.data_path = data_path
        self.matches: List[MatchResult] = []
        self.player_career: Dict[str, List[PlayerMatchStats]] = {}
        self.load_data()

    def load_data(self):
        """Load match data from JSON"""
        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for match_data in data.get("matches", []):
                    match = self._dict_to_match(match_data)
                    self.matches.append(match)
                    for name, stats in match.player_stats.items():
                        if name not in self.player_career:
                            self.player_career[name] = []
                        self.player_career[name].append(stats)
        except Exception as e:
            print(f"[StatsEngine] Load error: {e}")
            pass

    def save_data(self):
        """Save match data to JSON"""
        data = {
            "matches": [m.to_dict() for m in self.matches],
            "last_updated": datetime.now().isoformat()
        }
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _dict_to_match(self, data: dict) -> MatchResult:
        """Convert dict to MatchResult"""
        match = MatchResult(
            match_id=data["match_id"],
            date=data["date"],
            opponent=data["opponent"],
            team_goals=data.get("team_goals", 0),
            opponent_goals=data.get("opponent_goals", 0),
            team_possession=data.get("team_possession", 50.0),
            opponent_possession=data.get("opponent_possession", 50.0),
            team_shots=data.get("team_shots", 0),
            opponent_shots=data.get("opponent_shots", 0),
            team_shots_on_target=data.get("team_shots_on_target", 0),
            opponent_shots_on_target=data.get("opponent_shots_on_target", 0),
            team_passes=data.get("team_passes", 0),
            opponent_passes=data.get("opponent_passes", 0),
            team_tackles=data.get("team_tackles", 0),
            opponent_tackles=data.get("opponent_tackles", 0),
            team_corners=data.get("team_corners", 0),
            opponent_corners=data.get("opponent_corners", 0),
            team_fouls=data.get("team_fouls", 0),
            opponent_fouls=data.get("opponent_fouls", 0),
            match_type=data.get("match_type", "gameType9")
        )
        for name, stats_data in data.get("player_stats", {}).items():
            match.player_stats[name] = PlayerMatchStats(
                name=stats_data.get("name", name),
                position=stats_data.get("position", "unknown"),
                goals=stats_data.get("goals", 0),
                assists=stats_data.get("assists", 0),
                shots=stats_data.get("shots", 0),
                shots_on_target=stats_data.get("shots_on_target", 0),
                passes_attempted=stats_data.get("passes_attempted", 0),
                passes_completed=stats_data.get("passes_completed", 0),
                key_passes=stats_data.get("key_passes", 0),
                tackles=stats_data.get("tackles", 0),
                interceptions=stats_data.get("interceptions", 0),
                possession_losses=stats_data.get("possession_losses", 0),
                dribbles_attempted=stats_data.get("dribbles_attempted", 0),
                dribbles_completed=stats_data.get("dribbles_completed", 0),
                fouls=stats_data.get("fouls", 0),
                yellow_cards=stats_data.get("yellow_cards", 0),
                red_cards=stats_data.get("red_cards", 0),
                rating=stats_data.get("rating", 6.0),
                motm=stats_data.get("motm", False),
                minutes_played=stats_data.get("minutes_played", 90),
                distance_covered=stats_data.get("distance_covered", 0.0),
                sprint_speed=stats_data.get("sprint_speed", 0.0)
            )
        return match

    # FIX #1: Accept both MatchResult objects AND plain dicts from scraper
    def add_match(self, match_data):
        """Add a new match result - accepts MatchResult or dict"""
        # Convert dict to MatchResult if needed
        if isinstance(match_data, dict):
            match = self._dict_to_match(match_data)
        elif isinstance(match_data, MatchResult):
            match = match_data
        else:
            print(f"[StatsEngine] Invalid match type: {type(match_data)}")
            return

        self.matches.append(match)
        for name, stats in match.player_stats.items():
            if name not in self.player_career:
                self.player_career[name] = []
            self.player_career[name].append(stats)
        self.save_data()
        print(f"[StatsEngine] Added match {match.match_id}: {match.opponent} ({match.result})")

    # FIX #2: match_exists method that scraper calls
    def match_exists(self, match_id: str) -> bool:
        """Check if a match is already in the database"""
        return any(str(m.match_id) == str(match_id) for m in self.matches)

    # FIX #3: Get player stats by squad name (handles name variations)
    def get_player_stats(self, name: str, last_n: int = 5) -> dict:
        """Get aggregated stats for a player over last N matches"""
        # Try exact match first, then case-insensitive
        player_key = None
        if name in self.player_career:
            player_key = name
        else:
            # Try case-insensitive search
            name_lower = name.lower()
            for key in self.player_career:
                if key.lower() == name_lower:
                    player_key = key
                    break

        if not player_key:
            return {}

        recent = self.player_career[player_key][-last_n:]
        if not recent:
            return {}

        total_matches = len(recent)
        stats = {
            "matches": total_matches,
            "goals": sum(m.goals for m in recent),
            "assists": sum(m.assists for m in recent),
            "shots": sum(m.shots for m in recent),
            "shots_on_target": sum(m.shots_on_target for m in recent),
            "passes_attempted": sum(m.passes_attempted for m in recent),
            "passes_completed": sum(m.passes_completed for m in recent),
            "pass_accuracy": round(sum(m.pass_accuracy for m in recent) / total_matches, 1),
            "key_passes": sum(m.key_passes for m in recent),
            "tackles": sum(m.tackles for m in recent),
            "interceptions": sum(m.interceptions for m in recent),
            "possession_losses": sum(m.possession_losses for m in recent),
            "dribbles_attempted": sum(m.dribbles_attempted for m in recent),
            "dribbles_completed": sum(m.dribbles_completed for m in recent),
            "dribble_success": round(sum(m.dribble_success for m in recent) / total_matches, 1),
            "fouls": sum(m.fouls for m in recent),
            "yellow_cards": sum(m.yellow_cards for m in recent),
            "red_cards": sum(m.red_cards for m in recent),
            "rating": round(sum(m.rating for m in recent) / total_matches, 1),
            "motm_count": sum(1 for m in recent if m.motm),
            "minutes_played": sum(m.minutes_played for m in recent),
            "distance_covered": round(sum(m.distance_covered for m in recent), 1),
            "sprint_speed": round(sum(m.sprint_speed for m in recent) / total_matches, 1),
            "shot_accuracy": round(sum(m.shot_accuracy for m in recent) / total_matches, 1)
        }

        # Per-match averages
        stats["goals_per_match"] = round(stats["goals"] / total_matches, 2)
        stats["assists_per_match"] = round(stats["assists"] / total_matches, 2)
        stats["shots_per_match"] = round(stats["shots"] / total_matches, 2)
        stats["tackles_per_match"] = round(stats["tackles"] / total_matches, 2)
        stats["key_passes_per_match"] = round(stats["key_passes"] / total_matches, 2)
        stats["possession_losses_per_match"] = round(stats["possession_losses"] / total_matches, 2)

        # Advanced metrics
        offensive = stats["goals"] * 3 + stats["assists"] * 2 + stats["key_passes"] * 0.5
        defensive = stats["tackles"] * 0.5 + stats["interceptions"] * 0.3
        stats["impact_score"] = round(offensive + defensive, 1)

        # Clutch score
        clutch_matches = [m for m in recent if abs(
            next((match.goal_difference for match in self.matches if player_key in match.player_stats), 0)
        ) <= 1]
        stats["clutch_score"] = round(
            sum(m.goals for m in clutch_matches) * 2 + sum(m.assists for m in clutch_matches), 1
        ) if clutch_matches else 0

        # Error score
        stats["error_score"] = stats["possession_losses"] + stats["fouls"] * 2 + stats["yellow_cards"] * 5 + stats["red_cards"] * 10
        stats["throwing_score"] = round(stats["error_score"] / max(stats["rating"], 1), 1)

        # Form index
        if total_matches >= 5:
            recent_3 = recent[-3:]
            previous_2 = recent[-5:-3]
            recent_avg = sum(m.rating for m in recent_3) / 3
            previous_avg = sum(m.rating for m in previous_2) / 2
            stats["form_index"] = round(recent_avg - previous_avg, 1)
            stats["form_trend"] = "up" if stats["form_index"] > 0.3 else "down" if stats["form_index"] < -0.3 else "stable"
        else:
            stats["form_index"] = 0
            stats["form_trend"] = "stable"

        stats["passing_influence"] = round(stats["key_passes"] * 2 + stats["pass_accuracy"] * 0.1, 1)
        stats["defensive_contribution"] = round(stats["tackles"] * 1.5 + stats["interceptions"] * 1.0, 1)
        stats["offensive_contribution"] = round(
            stats["goals"] * 3 + stats["shots_on_target"] * 0.5 + stats["key_passes"] * 0.8, 1
        )

        return stats

    def get_team_stats(self, last_n: int = 20) -> dict:
        """Get aggregated team stats over last N matches"""
        recent = self.matches[-last_n:]
        if not recent:
            return {}

        wins = sum(1 for m in recent if m.result == "win")
        losses = sum(1 for m in recent if m.result == "loss")
        draws = sum(1 for m in recent if m.result == "draw")
        total = len(recent)

        return {
            "matches": total,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "win_rate": round((wins / total) * 100, 1) if total > 0 else 0,
            "loss_rate": round((losses / total) * 100, 1) if total > 0 else 0,
            "draw_rate": round((draws / total) * 100, 1) if total > 0 else 0,
            "goals_scored": sum(m.team_goals for m in recent),
            "goals_conceded": sum(m.opponent_goals for m in recent),
            "goal_difference": sum(m.goal_difference for m in recent),
            "avg_possession": round(sum(m.team_possession for m in recent) / total, 1),
            "avg_shots": round(sum(m.team_shots for m in recent) / total, 1),
            "avg_shots_on_target": round(sum(m.team_shots_on_target for m in recent) / total, 1),
            "avg_passes": round(sum(m.team_passes for m in recent) / total, 1),
            "avg_tackles": round(sum(m.team_tackles for m in recent) / total, 1),
            "avg_corners": round(sum(m.team_corners for m in recent) / total, 1),
            "avg_fouls": round(sum(m.team_fouls for m in recent) / total, 1),
            "current_streak": self._get_streak(recent),
            "best_streak": self._get_best_streak(recent),
            "worst_streak": self._get_worst_streak(recent)
        }

    def _get_streak(self, matches: List[MatchResult]) -> str:
        if not matches:
            return "none"
        streak_type = matches[-1].result
        count = 0
        for m in reversed(matches):
            if m.result == streak_type:
                count += 1
            else:
                break
        return f"{count} {streak_type}s"

    def _get_best_streak(self, matches: List[MatchResult]) -> int:
        best = 0
        current = 0
        for m in matches:
            if m.result == "win":
                current += 1
                best = max(best, current)
            else:
                current = 0
        return best

    def _get_worst_streak(self, matches: List[MatchResult]) -> int:
        worst = 0
        current = 0
        for m in matches:
            if m.result == "loss":
                current += 1
                worst = max(worst, current)
            else:
                current = 0
        return worst

    def get_leaderboard(self, last_n: int = 20, metric: str = "rating") -> List[Tuple[str, dict]]:
        """Get leaderboard sorted by metric"""
        players = {}
        for name in self.player_career:
            stats = self.get_player_stats(name, last_n)
            if stats:
                players[name] = stats

        sorted_players = sorted(
            players.items(),
            key=lambda x: x[1].get(metric, 0),
            reverse=True
        )
        return sorted_players

    def get_mvp(self, last_n: int = 5) -> Tuple[str, dict]:
        """Get MVP of last N matches"""
        leaderboard = self.get_leaderboard(last_n, "impact_score")
        if leaderboard:
            return leaderboard[0]
        return "", {}

    def get_worst_player(self, last_n: int = 5) -> Tuple[str, dict]:
        """Get worst player of last N matches"""
        leaderboard = self.get_leaderboard(last_n, "throwing_score")
        if leaderboard:
            return leaderboard[0]
        return "", {}

    def get_head_to_head(self, p1: str, p2: str, last_n: int = 20) -> dict:
        """Compare two players head-to-head"""
        p1_stats = self.get_player_stats(p1, last_n)
        p2_stats = self.get_player_stats(p2, last_n)

        if not p1_stats or not p2_stats:
            return {}

        return {
            "p1_name": p1,
            "p2_name": p2,
            "p1_stats": p1_stats,
            "p2_stats": p2_stats,
            "p1_wins": sum(1 for k in ["goals", "assists", "rating", "impact_score", "pass_accuracy"]
                          if p1_stats.get(k, 0) > p2_stats.get(k, 0)),
            "p2_wins": sum(1 for k in ["goals", "assists", "rating", "impact_score", "pass_accuracy"]
                          if p2_stats.get(k, 0) > p1_stats.get(k, 0)),
            "draws": sum(1 for k in ["goals", "assists", "rating", "impact_score", "pass_accuracy"]
                        if p1_stats.get(k, 0) == p2_stats.get(k, 0))
        }

    def get_match_report(self, match_id: str) -> Optional[MatchResult]:
        """Get detailed match report"""
        for match in self.matches:
            if str(match.match_id) == str(match_id):
                return match
        return None

    def get_last_match(self) -> Optional[MatchResult]:
        """Get the most recent match"""
        return self.matches[-1] if self.matches else None

    def get_form_string(self, name: str, last_n: int = 5) -> str:
        """Get form string (W/L/D) for last N matches"""
        if name not in self.player_career:
            return ""
        form = []
        for match in self.matches[-last_n:]:
            if name in match.player_stats:
                form.append(match.result[0].upper())
        return "".join(form) if form else "N/A"

    def get_career_totals(self, name: str) -> dict:
        """Get career totals for a player"""
        if name not in self.player_career:
            return {}

        all_matches = self.player_career[name]
        total = len(all_matches)

        return {
            "total_matches": total,
            "total_goals": sum(m.goals for m in all_matches),
            "total_assists": sum(m.assists for m in all_matches),
            "total_motm": sum(1 for m in all_matches if m.motm),
            "avg_rating": round(sum(m.rating for m in all_matches) / total, 1) if total > 0 else 0,
            "total_yellow_cards": sum(m.yellow_cards for m in all_matches),
            "total_red_cards": sum(m.red_cards for m in all_matches),
            "total_distance": round(sum(m.distance_covered for m in all_matches), 1),
            "best_rating": max((m.rating for m in all_matches), default=0),
            "worst_rating": min((m.rating for m in all_matches), default=10)
        }


# Singleton instance
_stats_engine = None

def get_stats_engine(data_path: str = "match_data.json") -> StatsEngine:
    global _stats_engine
    if _stats_engine is None:
        _stats_engine = StatsEngine(data_path)
    return _stats_engine
