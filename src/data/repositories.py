from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Iterable, List, Optional

from src.core.logging import get_logger
from src.data.database import Database
from src.domain.models import ClubSnapshot, Match, PlayerForm, PlayerIdentity, PlayerMatchStats

logger = get_logger(__name__)

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
        logger.info("[DB] Upserted %d player identities", len(list(identities)))

    def save_snapshot(self, snapshot: ClubSnapshot, raw: dict[str, Any] | None = None) -> None:
        now = _now()
        logger.info("[DB] save_snapshot called: %s matches, club=%s", len(snapshot.matches), snapshot.club_name)

        with self.db.connect() as conn:
            # Save club snapshot
            try:
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
                        _json(raw or snapshot.model_dump(mode="json")),
                    ),
                )
                logger.info("[DB] Inserted club_snapshots row")
            except Exception as e:
                logger.error("[DB] Failed to insert club_snapshots: %s", e)
                raise

            # Save each match
            match_count = 0
            player_count = 0
            for match in snapshot.matches:
                try:
                    self._save_match_with_connection(conn, match, now)
                    match_count += 1
                    player_count += len(match.players)
                except Exception as e:
                    logger.error("[DB] Failed to save match %s: %s", match.match_id, e)
                    # Continue saving other matches

            logger.info("[DB] Saved %d matches with %d total players", match_count, player_count)

    def _save_match_with_connection(self, conn: Any, match: Match, now: str) -> None:
        # Save match row
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

        # Save player stats for this match
        for player in match.players:
            conn.execute(
                """
                INSERT INTO player_match_stats
                (match_id, ea_id, display_name, position, rating, minutes, goals, assists, shots,
                shots_on_target, passes_attempted, passes_completed, key_passes, tackles, interceptions,
                saves, possession_losses, red_cards, yellow_cards, clean_sheets, distance_covered,
                sprint_speed, raw_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(match_id, ea_id) DO UPDATE SET
                display_name=excluded.display_name,
                position=excluded.position,
                rating=excluded.rating,
                minutes=excluded.minutes,
                goals=excluded.goals,
                assists=excluded.assists,
                shots=excluded.shots,
                shots_on_target=excluded.shots_on_target,
                passes_attempted=excluded.passes_attempted,
                passes_completed=excluded.passes_completed,
                key_passes=excluded.key_passes,
                tackles=excluded.tackles,
                interceptions=excluded.interceptions,
                saves=excluded.saves,
                possession_losses=excluded.possession_losses,
                red_cards=excluded.red_cards,
                yellow_cards=excluded.yellow_cards,
                clean_sheets=excluded.clean_sheets,
                distance_covered=excluded.distance_covered,
                sprint_speed=excluded.sprint_speed,
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
                    player.shots_on_target,
                    player.passes_attempted,
                    player.passes_completed,
                    player.key_passes,
                    player.tackles,
                    player.interceptions,
                    player.saves,
                    player.possession_losses,
                    player.red_cards,
                    player.yellow_cards,
                    player.clean_sheets,
                    player.distance_covered,
                    player.sprint_speed,
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
        logger.info("[DB] Querying latest_match...")
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM matches ORDER BY date DESC LIMIT 1").fetchone()
            if not row:
                logger.warning("[DB] No matches found in database")
                return None
            logger.info("[DB] Found match: id=%s, opponent=%s, date=%s", row["match_id"], row["opponent"], row["date"])

            player_rows = conn.execute(
                "SELECT * FROM player_match_stats WHERE match_id = ? ORDER BY rating DESC, goals DESC, assists DESC",
                (row["match_id"],),
            ).fetchall()
            logger.info("[DB] Found %d players for match %s", len(player_rows), row["match_id"])

            return self._row_to_match(row, player_rows)

    def last_matches(self, limit: int = 10) -> List[Match]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM matches ORDER BY date DESC LIMIT ?", (limit,)).fetchall()
            matches = []
            for row in rows:
                player_rows = conn.execute(
                    "SELECT * FROM player_match_stats WHERE match_id = ?",
                    (row["match_id"],),
                ).fetchall()
                matches.append(self._row_to_match(row, player_rows))
            return matches

    def player_matches(self, ea_id: str, limit: int = 20) -> List[PlayerMatchStats]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT * FROM player_match_stats
                WHERE ea_id = ? ORDER BY created_at DESC LIMIT ?""",
                (ea_id, limit),
            ).fetchall()
            return [self._row_to_player_stats(r) for r in rows]

    def aggregate_leaderboard(self, metric: str = "goals", limit: int = 10) -> List[dict[str, Any]]:
        allowed = {
            "goals": "SUM(goals)",
            "assists": "SUM(assists)",
            "rating": "AVG(rating)",
            "minutes": "SUM(minutes)",
            "losses": "SUM(possession_losses)",
            "saves": "SUM(saves)",
            "matches": "COUNT(DISTINCT match_id)",
            "key_passes": "SUM(key_passes)",
            "tackles": "SUM(tackles)",
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

    def save_form(self, form: PlayerForm) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO player_form
                (ea_id, match_id, form_score, impact_score, clutch_score, error_score, throwing_score, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ea_id, match_id) DO UPDATE SET
                form_score=excluded.form_score,
                impact_score=excluded.impact_score,
                clutch_score=excluded.clutch_score,
                error_score=excluded.error_score,
                throwing_score=excluded.throwing_score
                """,
                (
                    form.ea_id,
                    form.match_id,
                    form.form_score,
                    form.impact_score,
                    form.clutch_score,
                    form.error_score,
                    form.throwing_score,
                    form.created_at.isoformat(),
                ),
            )

    def get_recent_form(self, ea_id: str, matches: int = 5) -> List[PlayerForm]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT * FROM player_form WHERE ea_id = ?
                ORDER BY created_at DESC LIMIT ?""",
                (ea_id, matches),
            ).fetchall()
            return [
                PlayerForm(
                    ea_id=r["ea_id"],
                    match_id=r["match_id"],
                    form_score=r["form_score"],
                    impact_score=r["impact_score"],
                    clutch_score=r["clutch_score"],
                    error_score=r["error_score"],
                    throwing_score=r["throwing_score"],
                    created_at=datetime.fromisoformat(r["created_at"]),
                )
                for r in rows
            ]

    def record_reply(self, category: str, text: str) -> None:
        import hashlib
        h = hashlib.md5(text.encode()).hexdigest()
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO recent_replies (category, reply_hash, reply_text, used_at) VALUES (?, ?, ?, ?)",
                (category, h, text, _now()),
            )
            # Keep only last 50 per category
            conn.execute(
                """DELETE FROM recent_replies WHERE id NOT IN (
                SELECT id FROM recent_replies WHERE category = ? ORDER BY used_at DESC LIMIT 50
                )""",
                (category,),
            )

    def get_recent_replies(self, category: str, limit: int = 20) -> List[str]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT reply_text FROM recent_replies WHERE category = ? ORDER BY used_at DESC LIMIT ?",
                (category, limit),
            ).fetchall()
            return [r["reply_text"] for r in rows]

    def _row_to_match(self, row: Any, player_rows: Iterable[Any]) -> Match:
        players = [self._row_to_player_stats(p) for p in player_rows]
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

    def _row_to_player_stats(self, row: Any) -> PlayerMatchStats:
        # FIX: sqlite3.Row doesn't have .get() — wrap in dict() first
        row_dict = dict(row)
        return PlayerMatchStats(
            ea_id=row["ea_id"],
            display_name=row["display_name"],
            match_id=row_dict.get("match_id", ""),  # FIX: Added match_id
            position=row["position"],
            rating=row["rating"],
            minutes=row["minutes"],
            goals=row["goals"],
            assists=row["assists"],
            shots=row["shots"],
            shots_on_target=row_dict.get("shots_on_target", 0) or 0,
            passes_attempted=row["passes_attempted"],
            passes_completed=row["passes_completed"],
            key_passes=row_dict.get("key_passes", 0) or 0,
            tackles=row["tackles"],
            interceptions=row["interceptions"],
            saves=row["saves"],
            possession_losses=row["possession_losses"],
            red_cards=row["red_cards"],
            yellow_cards=row["yellow_cards"],
            clean_sheets=row["clean_sheets"],
            distance_covered=row_dict.get("distance_covered", 0.0) or 0.0,
            sprint_speed=row_dict.get("sprint_speed", 0.0) or 0.0,
            raw=json.loads(row["raw_json"] or "{}"),
        )
