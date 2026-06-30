from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.logging import get_logger
from src.data.database import Database
from src.data.repositories import ClubRepository
from src.domain.models import Match, PlayerMatchStats
from src.squad.registry import SquadRegistry

logger = get_logger(__name__)


class RecordsService:
    """Track and retrieve club records, hall of fame, and hall of shame."""

    def __init__(self, repository: ClubRepository, squad: SquadRegistry):
        self.repo = repository
        self.squad = squad

    def compute_all_records(self) -> List[Dict[str, Any]]:
        """Compute current records from all match history."""
        records = []
        matches = self.repo.last_matches(limit=1000)

        # Match-level records
        biggest_win = max(matches, key=lambda m: m.score_for - m.score_against, default=None)
        biggest_loss = min(matches, key=lambda m: m.score_for - m.score_against, default=None)
        highest_scoring = max(matches, key=lambda m: m.score_for + m.score_against, default=None)

        if biggest_win and biggest_win.score_for > biggest_win.score_against:
            records.append({
                "key": "biggest_win",
                "title": "Biggest Win",
                "value": biggest_win.score_for - biggest_win.score_against,
                "text": f"{biggest_win.score_for}-{biggest_win.score_against} vs {biggest_win.opponent}",
                "match_id": biggest_win.match_id,
            })

        if biggest_loss and biggest_loss.score_for < biggest_loss.score_against:
            records.append({
                "key": "biggest_loss",
                "title": "Biggest Loss",
                "value": biggest_loss.score_against - biggest_loss.score_for,
                "text": f"{biggest_loss.score_for}-{biggest_loss.score_against} vs {biggest_loss.opponent}",
                "match_id": biggest_loss.match_id,
            })

        if highest_scoring:
            records.append({
                "key": "highest_scoring",
                "title": "Highest Scoring Match",
                "value": highest_scoring.score_for + highest_scoring.score_against,
                "text": f"{highest_scoring.score_for}-{highest_scoring.score_against} vs {highest_scoring.opponent}",
                "match_id": highest_scoring.match_id,
            })

        # Player-level records
        all_stats = []
        for match in matches:
            all_stats.extend(match.players)

        if all_stats:
            # Highest rating
            best_rating = max(all_stats, key=lambda p: p.rating)
            identity = self.squad.find_by_ea_id(best_rating.ea_id)
            records.append({
                "key": "best_rating",
                "title": "Highest Match Rating",
                "value": best_rating.rating,
                "text": f"{identity.nickname if identity else best_rating.display_name}: {best_rating.rating}",
                "player_ea_id": best_rating.ea_id,
                "match_id": best_rating.match_id,
            })

            # Most goals in a match
            best_goals = max(all_stats, key=lambda p: p.goals)
            identity = self.squad.find_by_ea_id(best_goals.ea_id)
            records.append({
                "key": "most_goals_match",
                "title": "Most Goals in One Match",
                "value": best_goals.goals,
                "text": f"{identity.nickname if identity else best_goals.display_name}: {best_goals.goals} goals",
                "player_ea_id": best_goals.ea_id,
                "match_id": best_goals.match_id,
            })

            # Most assists in a match
            best_assists = max(all_stats, key=lambda p: p.assists)
            identity = self.squad.find_by_ea_id(best_assists.ea_id)
            records.append({
                "key": "most_assists_match",
                "title": "Most Assists in One Match",
                "value": best_assists.assists,
                "text": f"{identity.nickname if identity else best_assists.display_name}: {best_assists.assists} assists",
                "player_ea_id": best_assists.ea_id,
                "match_id": best_assists.match_id,
            })

        return records

    def save_records(self, records: List[Dict[str, Any]]) -> None:
        now = datetime.now().isoformat()
        with self.repo.db.connect() as conn:
            for rec in records:
                conn.execute(
                    """
                    INSERT INTO records (record_key, player_ea_id, match_id, title, value, payload_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(record_key) DO UPDATE SET
                        player_ea_id=excluded.player_ea_id,
                        match_id=excluded.match_id,
                        title=excluded.title,
                        value=excluded.value,
                        payload_json=excluded.payload_json,
                        updated_at=excluded.updated_at
                    """,
                    (
                        rec["key"],
                        rec.get("player_ea_id"),
                        rec.get("match_id"),
                        rec["title"],
                        rec["value"],
                        json.dumps(rec, ensure_ascii=False),
                        now,
                        now,
                    ),
                )

    def get_records(self) -> List[Dict[str, Any]]:
        with self.repo.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM records ORDER BY value DESC"
            ).fetchall()
        return [json.loads(r["payload_json"]) for r in rows]

    def get_hall_of_fame(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Best performers of all time by average rating (min 5 matches)."""
        with self.repo.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT ea_id, display_name, AVG(rating) as avg_rating, COUNT(*) as matches,
                       SUM(goals) as total_goals, SUM(assists) as total_assists
                FROM player_match_stats
                GROUP BY ea_id, display_name
                HAVING COUNT(*) >= 5
                ORDER BY avg_rating DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        result = []
        for r in rows:
            identity = self.squad.find_by_ea_id(r["ea_id"])
            result.append({
                "ea_id": r["ea_id"],
                "nickname": identity.nickname if identity else r["display_name"],
                "avg_rating": round(r["avg_rating"], 2),
                "matches": r["matches"],
                "goals": r["total_goals"],
                "assists": r["total_assists"],
            })
        return result

    def get_hall_of_shame(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Worst performers by avg rating (min 5 matches) or worst single performances."""
        with self.repo.db.connect() as conn:
            # Worst average rating
            rows = conn.execute(
                """
                SELECT ea_id, display_name, AVG(rating) as avg_rating, COUNT(*) as matches,
                       SUM(possession_losses) as total_losses, SUM(yellow_cards + red_cards) as total_cards
                FROM player_match_stats
                GROUP BY ea_id, display_name
                HAVING COUNT(*) >= 5
                ORDER BY avg_rating ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        result = []
        for r in rows:
            identity = self.squad.find_by_ea_id(r["ea_id"])
            result.append({
                "ea_id": r["ea_id"],
                "nickname": identity.nickname if identity else r["display_name"],
                "avg_rating": round(r["avg_rating"], 2),
                "matches": r["matches"],
                "losses": r["total_losses"],
                "cards": r["total_cards"],
            })
        return result

    def get_rivalry(self, ea_id1: str, ea_id2: str) -> Optional[Dict[str, Any]]:
        """Get head-to-head rivalry stats between two players."""
        with self.repo.db.connect() as conn:
            # Find matches where both players appeared
            rows = conn.execute(
                """
                SELECT m.match_id, m.result, m.date, m.opponent,
                       p1.rating as p1_rating, p1.goals as p1_goals, p1.assists as p1_assists,
                       p2.rating as p2_rating, p2.goals as p2_goals, p2.assists as p2_assists
                FROM matches m
                JOIN player_match_stats p1 ON m.match_id = p1.match_id
                JOIN player_match_stats p2 ON m.match_id = p2.match_id
                WHERE p1.ea_id = ? AND p2.ea_id = ?
                ORDER BY m.date DESC
                """,
                (ea_id1, ea_id2),
            ).fetchall()

        if not rows:
            return None

        id1 = self.squad.find_by_ea_id(ea_id1)
        id2 = self.squad.find_by_ea_id(ea_id2)

        p1_wins = sum(1 for r in rows if r["p1_rating"] > r["p2_rating"])
        p2_wins = sum(1 for r in rows if r["p2_rating"] > r["p1_rating"])
        draws = len(rows) - p1_wins - p2_wins

        return {
            "player_one": id1.nickname if id1 else ea_id1,
            "player_two": id2.nickname if id2 else ea_id2,
            "matches_together": len(rows),
            "p1_wins": p1_wins,
            "p2_wins": p2_wins,
            "draws": draws,
            "p1_avg_rating": round(sum(r["p1_rating"] for r in rows) / len(rows), 2),
            "p2_avg_rating": round(sum(r["p2_rating"] for r in rows) / len(rows), 2),
            "recent_matches": [
                {
                    "date": r["date"][:10],
                    "opponent": r["opponent"],
                    "result": r["result"],
                    "p1_rating": r["p1_rating"],
                    "p2_rating": r["p2_rating"],
                }
                for r in rows[:5]
            ],
        }

    def generate_memory(self, ea_id: str) -> str:
        """Generate a lore/memory text for a player based on their history."""
        history = self.repo.player_matches(ea_id, limit=20)
        if not history:
            return "No history found."

        identity = self.squad.find_by_ea_id(ea_id)
        name = identity.nickname if identity else ea_id

        total_goals = sum(h.goals for h in history)
        total_assists = sum(h.assists for h in history)
        avg_rating = sum(h.rating for h in history) / len(history)
        best_match = max(history, key=lambda h: h.rating)
        worst_match = min(history, key=lambda h: h.rating)

        lines = [
            f"**{name}** - Squad Historian Report",
            f"Matches played: {len(history)}",
            f"Total G+A: {total_goals}+{total_assists}",
            f"Average rating: {avg_rating:.1f}",
            f"",
            f"Best performance: Rating {best_match.rating} vs {best_match.raw.get('opponent', 'Unknown')}",
            f"Worst performance: Rating {worst_match.rating} vs {worst_match.raw.get('opponent', 'Unknown')}",
        ]

        # Personality-based flavor
        if identity and identity.personality:
            lines.append(f"")
            lines.append(f"Known style: {identity.personality}")

        if avg_rating >= 7.5:
            lines.append(f"Verdict: **Club Legend** ⭐")
        elif avg_rating >= 6.0:
            lines.append(f"Verdict: **Reliable Soldier** 🎖️")
        elif avg_rating >= 4.5:
            lines.append(f"Verdict: **Work in Progress** 🔨")
        else:
            lines.append(f"Verdict: **Tribunal Regular** ⚖️")

        return "\n".join(lines)
