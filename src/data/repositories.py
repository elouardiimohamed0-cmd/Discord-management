from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Iterable, Optional

from src.data.database import Database
from src.domain.models import ClubSnapshot, Match, PlayerIdentity, PlayerMatchStats


def _now() -> str:
    return datetime.now().isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


class ClubRepository:
    def __init__(self, db: Database):
        self.db = db

    def upsert_identities(self, identities: Iterable[PlayerIdentity]) -> None:
        now = _now()
        with self.db.connect() as conn:
            for player in identities:
                conn.execute(
                    """
                    INSERT INTO players
                    (ea_id, nickname, image, personality, meme_tags_json, position, number, raw_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ea_id) DO UPDATE SET
                        nickname=excluded.nickname,
                        image=excluded.image,
                        personality=excluded.personality,
                        meme_tags_json=excluded.meme_tags_json,
                        position=excluded.position,
                        number=excluded.number,
                        raw_json=excluded.raw_json,
                        updated_at=excluded.updated_at
                    """,
                    (
                        player.ea_id,
                        player.nickname,
                        player.image,
                        player.personality,
                        _json(player.meme_tags),
                        player.position,
                        player.number,
                        _json(player.raw),
                        now,
                    ),
                )

    def save_snapshot(self, snapshot: ClubSnapshot, raw: dict[str, Any] | None = None) -> None:
        now = _now()
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO club_snapshots
                (club_name, division, skill_rating, wins, draws, losses, goals_scored, goals_conceded, scraped_at, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.club_name,
                    snapshot.division,
                    snapshot.skill_rating,
                    snapshot.wins,
                    snapshot.draws,
                    snapshot.losses,
                    snapshot.goals_scored,
                    snapshot.goals_conceded,
                    snapshot.scraped_at.isoformat(),
                    _json(raw or snapshot.model_dump()),
                ),
            )
            for match in snapshot.matches:
                self._save_match_with_connection(conn, match, now)

    def _save_match_with_connection(self, conn: Any, match: Match, now: str) -> None:
        conn.execute(
            """
            INSERT INTO matches
            (match_id, date, opponent, score_for, score_against, result, raw_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(match_id) DO UPDATE SET
                date=excluded.date,
                opponent=excluded.opponent,
                score_for=excluded.score_for,
                score_against=excluded.score_against,
                result=excluded.result,
                raw_json=excluded.raw_json,
                updated_at=excluded.updated_at
            """,
            (
                match.match_id,
                match.date.isoformat(),
                match.opponent,
                match.score_for,
                match.score_against,
                match.result,
                _json(match.raw),
                now,
                now,
            ),
        )
        for player in match.players:
            conn.execute(
                """
                INSERT INTO player_match_stats
                (match_id, ea_id, display_name, position, rating, minutes, goals, assists, shots,
                 passes_attempted, passes_completed, tackles, interceptions, saves, possession_losses,
                 red_cards, yellow_cards, clean_sheets, raw_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(match_id, ea_id) DO UPDATE SET
                    display_name=excluded.display_name,
                    position=excluded.position,
                    rating=excluded.rating,
                    minutes=excluded.minutes,
                    goals=excluded.goals,
                    assists=excluded.assists,
                    shots=excluded.shots,
                    passes_attempted=excluded.passes_attempted,
                    passes_completed=excluded.passes_completed,
                    tackles=excluded.tackles,
                    interceptions=excluded.interceptions,
                    saves=excluded.saves,
                    possession_losses=excluded.possession_losses,
                    red_cards=excluded.red_cards,
                    yellow_cards=excluded.yellow_cards,
                    clean_sheets=excluded.clean_sheets,
                    raw_json=excluded.raw_json,
                    updated_at=excluded.updated_at
                """,
                (
                    match.match_id,
                    player.ea_id,
                    player.display_name,
                    player.position,
                    player.rating,
                    player.minutes,
                    player.goals,
                    player.assists,
                    player.shots,
                    player.passes_attempted,
                    player.passes_completed,
                    player.tackles,
                    player.interceptions,
                    player.saves,
                    player.possession_losses,
                    player.red_cards,
                    player.yellow_cards,
                    player.clean_sheets,
                    _json(player.raw),
                    now,
                    now,
                ),
            )

    def log_scrape(self, source: str, success: bool, error: str = "", request_count: int = 0) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO scrape_log (scraped_at, source, success, error, request_count) VALUES (?, ?, ?, ?, ?)",
                (_now(), source, 1 if success else 0, error, request_count),
            )

    def latest_match(self) -> Optional[Match]:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM matches ORDER BY date DESC LIMIT 1").fetchone()
            if not row:
                return None
            player_rows = conn.execute(
                "SELECT * FROM player_match_stats WHERE match_id = ? ORDER BY rating DESC, goals DESC, assists DESC",
                (row["match_id"],),
            ).fetchall()
        return self._row_to_match(row, player_rows)

    def aggregate_leaderboard(self, metric: str = "goals", limit: int = 10) -> list[dict[str, Any]]:
        allowed = {
            "goals": "SUM(goals)",
            "assists": "SUM(assists)",
            "rating": "AVG(rating)",
            "minutes": "SUM(minutes)",
            "losses": "SUM(possession_losses)",
            "saves": "SUM(saves)",
            "matches": "COUNT(DISTINCT match_id)",
        }
        expression = allowed.get(metric, allowed["goals"])
        with self.db.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT ea_id, display_name, {expression} AS value, COUNT(DISTINCT match_id) AS matches
                FROM player_match_stats
                GROUP BY ea_id, display_name
                ORDER BY value DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _row_to_match(self, row: Any, player_rows: Iterable[Any]) -> Match:
        players = [
            PlayerMatchStats(
                ea_id=p["ea_id"],
                display_name=p["display_name"],
                position=p["position"],
                rating=p["rating"],
                minutes=p["minutes"],
                goals=p["goals"],
                assists=p["assists"],
                shots=p["shots"],
                passes_attempted=p["passes_attempted"],
                passes_completed=p["passes_completed"],
                tackles=p["tackles"],
                interceptions=p["interceptions"],
                saves=p["saves"],
                possession_losses=p["possession_losses"],
                red_cards=p["red_cards"],
                yellow_cards=p["yellow_cards"],
                clean_sheets=p["clean_sheets"],
                raw=json.loads(p["raw_json"] or "{}"),
            )
            for p in player_rows
        ]
        return Match(
            match_id=row["match_id"],
            date=datetime.fromisoformat(row["date"]),
            opponent=row["opponent"],
            score_for=row["score_for"],
            score_against=row["score_against"],
            result=row["result"],
            players=players,
            raw=json.loads(row["raw_json"] or "{}"),
        )
