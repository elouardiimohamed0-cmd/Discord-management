"""
Rachad L3ERGONI Bot — Stats Engine v3
SQLite-backed. Calculates advanced metrics.
"""

import json
import math
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from ea_api import EAPlayerMatch, EAMatch


@dataclass
class PlayerMatchStats:
    """ALL fields have defaults for Python 3.14 compatibility."""
    name: str = ""
    position: str = "CM"
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
    saves: int = 0
    clean_sheets_gk: int = 0
    own_goals: int = 0
    longshots: int = 0
    chances_created: int = 0

    @property
    def pass_accuracy(self) -> float:
        if self.passes_attempted == 0:
            return 0.0
        return round((self.passes_completed / self.passes_attempted) * 100, 1)

    @property
    def shot_accuracy(self) -> float:
        if self.shots == 0:
            return 0.0
        return round((self.shots_on_target / max(self.shots, 1)) * 100, 1)

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
            "fouls": self.fouls,
            "yellow_cards": self.yellow_cards,
            "red_cards": self.red_cards,
            "rating": self.rating,
            "motm": self.motm,
            "minutes_played": self.minutes_played,
            "saves": self.saves,
            "clean_sheets_gk": self.clean_sheets_gk,
            "own_goals": self.own_goals,
            "longshots": self.longshots,
            "chances_created": self.chances_created,
            "shot_accuracy": self.shot_accuracy,
        }


@dataclass
class MatchResult:
    match_id: str = ""
    date: str = ""
    opponent: str = ""
    team_goals: int = 0
    opponent_goals: int = 0
    match_type: str = "friendlyMatch"
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
            "match_type": self.match_type,
            "player_stats": {k: v.to_dict() for k, v in self.player_stats.items()},
        }


class StatsEngine:
    def __init__(self, db_path: str = "bot_data.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS matches (
                    match_id TEXT PRIMARY KEY,
                    date TEXT,
                    opponent TEXT,
                    team_goals INTEGER,
                    opponent_goals INTEGER,
                    match_type TEXT,
                    json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS player_matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT,
                    player_name TEXT,
                    position TEXT,
                    goals INTEGER,
                    assists INTEGER,
                    shots INTEGER,
                    shots_on_target INTEGER,
                    passes_attempted INTEGER,
                    passes_completed INTEGER,
                    key_passes INTEGER,
                    tackles INTEGER,
                    interceptions INTEGER,
                    possession_losses INTEGER,
                    dribbles_attempted INTEGER,
                    dribbles_completed INTEGER,
                    fouls INTEGER,
                    yellow_cards INTEGER,
                    red_cards INTEGER,
                    rating REAL,
                    motm INTEGER,
                    minutes_played INTEGER,
                    saves INTEGER,
                    clean_sheets_gk INTEGER,
                    own_goals INTEGER,
                    longshots INTEGER,
                    chances_created INTEGER,
                    FOREIGN KEY (match_id) REFERENCES matches(match_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_player_matches_name ON player_matches(player_name)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_player_matches_match ON player_matches(match_id)
            """)
            conn.commit()

    def match_exists(self, match_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT 1 FROM matches WHERE match_id = ?", (match_id,))
            return cur.fetchone() is not None

    def add_match(self, match: EAMatch):
        if self.match_exists(match.match_id):
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO matches (match_id, date, opponent, team_goals, opponent_goals, match_type, json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match.match_id,
                    match.date_iso,
                    match.opponent_name,
                    match.team_goals,
                    match.opponent_goals,
                    match.match_type,
                    json.dumps(match.raw, ensure_ascii=False),
                ),
            )
            for name, ps in match.player_stats.items():
                conn.execute(
                    """
                    INSERT INTO player_matches (
                        match_id, player_name, position, goals, assists, shots, shots_on_target,
                        passes_attempted, passes_completed, key_passes, tackles, interceptions,
                        possession_losses, dribbles_attempted, dribbles_completed, fouls,
                        yellow_cards, red_cards, rating, motm, minutes_played, saves,
                        clean_sheets_gk, own_goals, longshots, chances_created
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        match.match_id,
                        name,
                        ps.position,
                        ps.goals,
                        ps.assists,
                        ps.shots,
                        ps.shots_on_target,
                        ps.passes_attempted,
                        ps.passes_completed,
                        ps.key_passes,
                        ps.tackles,
                        ps.interceptions,
                        ps.possession_losses,
                        ps.dribbles_attempted,
                        ps.dribbles_completed,
                        ps.fouls,
                        ps.yellow_cards,
                        ps.red_cards,
                        ps.rating,
                        int(ps.motm),
                        ps.minutes_played,
                        ps.saves,
                        ps.clean_sheets_gk,
                        ps.own_goals,
                        ps.longshots,
                        ps.chances_created,
                    ),
                )
            conn.commit()

    def get_player_stats(self, name: str, last_n: int = 5) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM player_matches
                WHERE player_name = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (name, last_n),
            ).fetchall()

        if not rows:
            return {}

        total = len(rows)
        stats = {
            "matches": total,
            "goals": sum(r["goals"] for r in rows),
            "assists": sum(r["assists"] for r in rows),
            "shots": sum(r["shots"] for r in rows),
            "shots_on_target": sum(r["shots_on_target"] for r in rows),
            "passes_attempted": sum(r["passes_attempted"] for r in rows),
            "passes_completed": sum(r["passes_completed"] for r in rows),
            "pass_accuracy": round(
                sum(r["passes_completed"] / max(r["passes_attempted"], 1) * 100 for r in rows) / total, 1
            ),
            "key_passes": sum(r["key_passes"] for r in rows),
            "tackles": sum(r["tackles"] for r in rows),
            "interceptions": sum(r["interceptions"] for r in rows),
            "possession_losses": sum(r["possession_losses"] for r in rows),
            "dribbles_attempted": sum(r["dribbles_attempted"] for r in rows),
            "dribbles_completed": sum(r["dribbles_completed"] for r in rows),
            "fouls": sum(r["fouls"] for r in rows),
            "yellow_cards": sum(r["yellow_cards"] for r in rows),
            "red_cards": sum(r["red_cards"] for r in rows),
            "rating": round(sum(r["rating"] for r in rows) / total, 1),
            "motm_count": sum(r["motm"] for r in rows),
            "minutes_played": sum(r["minutes_played"] for r in rows),
            "saves": sum(r["saves"] for r in rows),
            "clean_sheets_gk": sum(r["clean_sheets_gk"] for r in rows),
            "own_goals": sum(r["own_goals"] for r in rows),
            "longshots": sum(r["longshots"] for r in rows),
            "chances_created": sum(r["chances_created"] for r in rows),
            "shot_accuracy": round(
                sum(r["shots_on_target"] / max(r["shots"], 1) * 100 for r in rows if r["shots"] > 0) / max(
                    sum(1 for r in rows if r["shots"] > 0), 1
                ), 1
            ),
        }

        # Per-match averages
        stats["goals_per_match"] = round(stats["goals"] / total, 2)
        stats["assists_per_match"] = round(stats["assists"] / total, 2)
        stats["shots_per_match"] = round(stats["shots"] / total, 2)
        stats["tackles_per_match"] = round(stats["tackles"] / total, 2)
        stats["key_passes_per_match"] = round(stats["key_passes"] / total, 2)
        stats["possession_losses_per_match"] = round(stats["possession_losses"] / total, 2)

        # Advanced
        offensive = stats["goals"] * 3 + stats["assists"] * 2 + stats["key_passes"] * 0.5 + stats["longshots"] * 0.3
        defensive = stats["tackles"] * 0.5 + stats["interceptions"] * 0.3 + stats["saves"] * 0.2
        stats["impact_score"] = round(offensive + defensive, 1)

        # Error / throwing score
        stats["error_score"] = stats["possession_losses"] + stats["fouls"] * 2 + stats["yellow_cards"] * 5 + stats["red_cards"] * 10 + stats["own_goals"] * 15
        stats["throwing_score"] = round(stats["error_score"] / max(stats["rating"], 1), 1)

        # Form
        if total >= 5:
            recent_3 = rows[:3]
            previous_2 = rows[3:5]
            recent_avg = sum(r["rating"] for r in recent_3) / 3
            previous_avg = sum(r["rating"] for r in previous_2) / 2
            stats["form_index"] = round(recent_avg - previous_avg, 1)
            stats["form_trend"] = "up" if stats["form_index"] > 0.3 else "down" if stats["form_index"] < -0.3 else "stable"
        else:
            stats["form_index"] = 0
            stats["form_trend"] = "stable"

        stats["passing_influence"] = round(stats["key_passes"] * 2 + stats["pass_accuracy"] * 0.1, 1)
        stats["defensive_contribution"] = round(stats["tackles"] * 1.5 + stats["interceptions"] * 1.0 + stats["saves"] * 2.0, 1)
        stats["offensive_contribution"] = round(
            stats["goals"] * 3 + stats["shots_on_target"] * 0.5 + stats["key_passes"] * 0.8 + stats["longshots"] * 0.5, 1
        )

        # Clutch: close games (GD <= 1)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            match_ids = [r["match_id"] for r in rows]
            placeholders = ",".join("?" * len(match_ids))
            match_rows = conn.execute(
                f"SELECT match_id, ABS(team_goals - opponent_goals) as gd FROM matches WHERE match_id IN ({placeholders})",
                match_ids,
            ).fetchall()
            close_match_ids = {r["match_id"] for r in match_rows if r["gd"] <= 1}
            clutch_rows = [r for r in rows if r["match_id"] in close_match_ids]
            stats["clutch_score"] = round(
                sum(r["goals"] for r in clutch_rows) * 2 + sum(r["assists"] for r in clutch_rows), 1
            ) if clutch_rows else 0

        return stats

    def get_team_stats(self, last_n: int = 20) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM matches ORDER BY date DESC LIMIT ?", (last_n,)
            ).fetchall()

        if not rows:
            return {}

        total = len(rows)
        wins = sum(1 for r in rows if r["team_goals"] > r["opponent_goals"])
        losses = sum(1 for r in rows if r["team_goals"] < r["opponent_goals"])
        draws = total - wins - losses

        return {
            "matches": total,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "win_rate": round((wins / total) * 100, 1),
            "loss_rate": round((losses / total) * 100, 1),
            "draw_rate": round((draws / total) * 100, 1),
            "goals_scored": sum(r["team_goals"] for r in rows),
            "goals_conceded": sum(r["opponent_goals"] for r in rows),
            "goal_difference": sum(r["team_goals"] - r["opponent_goals"] for r in rows),
            "current_streak": self._streak(rows),
            "best_streak": self._best_streak(rows),
            "worst_streak": self._worst_streak(rows),
        }

    def _streak(self, rows: List[sqlite3.Row]) -> str:
        if not rows:
            return "none"
        r = "win" if rows[0]["team_goals"] > rows[0]["opponent_goals"] else ("draw" if rows[0]["team_goals"] == rows[0]["opponent_goals"] else "loss")
        count = 0
        for row in rows:
            cur = "win" if row["team_goals"] > row["opponent_goals"] else ("draw" if row["team_goals"] == row["opponent_goals"] else "loss")
            if cur == r:
                count += 1
            else:
                break
        return f"{count} {r}s"

    def _best_streak(self, rows: List[sqlite3.Row]) -> int:
        best = cur = 0
        for row in rows:
            if row["team_goals"] > row["opponent_goals"]:
                cur += 1
                best = max(best, cur)
            else:
                cur = 0
        return best

    def _worst_streak(self, rows: List[sqlite3.Row]) -> int:
        worst = cur = 0
        for row in rows:
            if row["team_goals"] < row["opponent_goals"]:
                cur += 1
                worst = max(worst, cur)
            else:
                cur = 0
        return worst

    def get_leaderboard(self, last_n: int = 20, metric: str = "impact_score") -> List[Tuple[str, dict]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            names = [
                r["player_name"]
                for r in conn.execute(
                    "SELECT DISTINCT player_name FROM player_matches ORDER BY player_name"
                ).fetchall()
            ]
        players = []
        for name in names:
            s = self.get_player_stats(name, last_n)
            if s:
                players.append((name, s))
        return sorted(players, key=lambda x: x[1].get(metric, 0), reverse=True)

    def get_mvp(self, last_n: int = 5) -> Tuple[str, dict]:
        board = self.get_leaderboard(last_n, "impact_score")
        return board[0] if board else ("", {})

    def get_worst_player(self, last_n: int = 5) -> Tuple[str, dict]:
        board = self.get_leaderboard(last_n, "throwing_score")
        return board[0] if board else ("", {})

    def get_head_to_head(self, p1: str, p2: str, last_n: int = 20) -> dict:
        s1 = self.get_player_stats(p1, last_n)
        s2 = self.get_player_stats(p2, last_n)
        if not s1 or not s2:
            return {}
        keys = ["goals", "assists", "rating", "impact_score", "pass_accuracy"]
        return {
            "p1_name": p1,
            "p2_name": p2,
            "p1_stats": s1,
            "p2_stats": s2,
            "p1_wins": sum(1 for k in keys if s1.get(k, 0) > s2.get(k, 0)),
            "p2_wins": sum(1 for k in keys if s2.get(k, 0) > s1.get(k, 0)),
            "draws": sum(1 for k in keys if s1.get(k, 0) == s2.get(k, 0)),
        }

    def get_last_match(self) -> Optional[MatchResult]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM matches ORDER BY date DESC LIMIT 1"
            ).fetchone()
            if not row:
                return None
            return self._hydrate_match(conn, row)

    def get_match_report(self, match_id: str) -> Optional[MatchResult]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM matches WHERE match_id = ?", (match_id,)
            ).fetchone()
            if not row:
                return None
            return self._hydrate_match(conn, row)

    def _hydrate_match(self, conn: sqlite3.Connection, row: sqlite3.Row) -> MatchResult:
        match = MatchResult(
            match_id=row["match_id"],
            date=row["date"],
            opponent=row["opponent"],
            team_goals=row["team_goals"],
            opponent_goals=row["opponent_goals"],
            match_type=row["match_type"],
        )
        p_rows = conn.execute(
            "SELECT * FROM player_matches WHERE match_id = ?", (row["match_id"],)
        ).fetchall()
        for r in p_rows:
            match.player_stats[r["player_name"]] = PlayerMatchStats(
                name=r["player_name"],
                position=r["position"],
                goals=r["goals"],
                assists=r["assists"],
                shots=r["shots"],
                shots_on_target=r["shots_on_target"],
                passes_attempted=r["passes_attempted"],
                passes_completed=r["passes_completed"],
                key_passes=r["key_passes"],
                tackles=r["tackles"],
                interceptions=r["interceptions"],
                possession_losses=r["possession_losses"],
                dribbles_attempted=r["dribbles_attempted"],
                dribbles_completed=r["dribbles_completed"],
                fouls=r["fouls"],
                yellow_cards=r["yellow_cards"],
                red_cards=r["red_cards"],
                rating=r["rating"],
                motm=bool(r["motm"]),
                minutes_played=r["minutes_played"],
                saves=r["saves"],
                clean_sheets_gk=r["clean_sheets_gk"],
                own_goals=r["own_goals"],
                longshots=r["longshots"],
                chances_created=r["chances_created"],
            )
        return match

    def get_form_string(self, name: str, last_n: int = 5) -> str:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT m.team_goals, m.opponent_goals
                FROM matches m
                JOIN player_matches pm ON m.match_id = pm.match_id
                WHERE pm.player_name = ?
                ORDER BY m.date DESC
                LIMIT ?
                """,
                (name, last_n),
            ).fetchall()
        if not rows:
            return "N/A"
        return "".join(
            "W" if r["team_goals"] > r["opponent_goals"] else (
                "D" if r["team_goals"] == r["opponent_goals"] else "L"
            )
            for r in rows
        )

    def get_career_totals(self, name: str) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM player_matches WHERE player_name = ?", (name,)
            ).fetchall()
        if not rows:
            return {}
        total = len(rows)
        return {
            "total_matches": total,
            "total_goals": sum(r["goals"] for r in rows),
            "total_assists": sum(r["assists"] for r in rows),
            "total_motm": sum(r["motm"] for r in rows),
            "avg_rating": round(sum(r["rating"] for r in rows) / total, 1) if total else 0,
            "total_yellow_cards": sum(r["yellow_cards"] for r in rows),
            "total_red_cards": sum(r["red_cards"] for r in rows),
            "best_rating": max((r["rating"] for r in rows), default=0),
            "worst_rating": min((r["rating"] for r in rows), default=10),
            "total_saves": sum(r["saves"] for r in rows),
            "total_clean_sheets_gk": sum(r["clean_sheets_gk"] for r in rows),
        }

    def get_all_match_ids(self) -> List[str]:
        with sqlite3.connect(self.db_path) as conn:
            return [r[0] for r in conn.execute("SELECT match_id FROM matches ORDER BY date DESC").fetchall()]


_stats_engine = None

def get_stats_engine(db_path: str = "bot_data.db") -> StatsEngine:
    global _stats_engine
    if _stats_engine is None:
        _stats_engine = StatsEngine(db_path)
    return _stats_engine
