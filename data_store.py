import os
import json
import sqlite3
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import asdict

logger = logging.getLogger("rachad_bot.data_store")

class DataStore:
    """
    Persistent data store for club snapshots.
    Uses PostgreSQL if DATABASE_URL is set (Render), otherwise SQLite.
    """

    def __init__(self):
        self.db_url = os.environ.get("DATABASE_URL")
        self.use_postgres = self.db_url is not None
        self.sqlite_path = os.environ.get("SQLITE_PATH", "/tmp/rachad_data.db")
        self._init_db()

    def _init_db(self):
        if self.use_postgres:
            try:
                import psycopg2
                conn = psycopg2.connect(self.db_url)
                c = conn.cursor()
                c.execute("""
                    CREATE TABLE IF NOT EXISTS club_snapshots (
                        id SERIAL PRIMARY KEY,
                        scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        club_name TEXT,
                        division INTEGER,
                        skill_rating INTEGER,
                        wins INTEGER,
                        losses INTEGER,
                        draws INTEGER,
                        goals_scored INTEGER,
                        goals_conceded INTEGER,
                        win_rate REAL,
                        players_json JSONB,
                        matches_json JSONB
                    )
                """)
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_snapshots_time 
                    ON club_snapshots(scraped_at DESC)
                """)
                c.execute("""
                    CREATE TABLE IF NOT EXISTS scrape_log (
                        id SERIAL PRIMARY KEY,
                        scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        source TEXT,
                        success BOOLEAN,
                        error TEXT,
                        request_count INTEGER DEFAULT 0
                    )
                """)
                conn.commit()
                conn.close()
                logger.info("PostgreSQL datastore initialized")
            except Exception as e:
                logger.error("PostgreSQL init failed: %s. Falling back to SQLite.", e)
                self.use_postgres = False
                self._init_sqlite()
        else:
            self._init_sqlite()

    def _init_sqlite(self):
        conn = sqlite3.connect(self.sqlite_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS club_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scraped_at TEXT,
                club_name TEXT,
                division INTEGER,
                skill_rating INTEGER,
                wins INTEGER,
                losses INTEGER,
                draws INTEGER,
                goals_scored INTEGER,
                goals_conceded INTEGER,
                win_rate REAL,
                players_json TEXT,
                matches_json TEXT
            )
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshots_time 
            ON club_snapshots(scraped_at DESC)
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS scrape_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scraped_at TEXT,
                source TEXT,
                success INTEGER,
                error TEXT,
                request_count INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()
        logger.info("SQLite datastore initialized at %s", self.sqlite_path)

    def save_snapshot(self, club_data: dict) -> bool:
        """Save a club snapshot. Returns True on success."""
        try:
            players_json = json.dumps(club_data.get("players", []), ensure_ascii=False, default=str)
            matches_json = json.dumps(club_data.get("matches", []), ensure_ascii=False, default=str)

            if self.use_postgres:
                import psycopg2
                conn = psycopg2.connect(self.db_url)
                c = conn.cursor()
                c.execute("""
                    INSERT INTO club_snapshots 
                    (scraped_at, club_name, division, skill_rating, wins, losses, draws,
                     goals_scored, goals_conceded, win_rate, players_json, matches_json)
                    VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    club_data.get("club_name", ""),
                    club_data.get("division", 0),
                    club_data.get("skill_rating", 0),
                    club_data.get("wins", 0),
                    club_data.get("losses", 0),
                    club_data.get("draws", 0),
                    club_data.get("goals_scored", 0),
                    club_data.get("goals_conceded", 0),
                    club_data.get("win_rate", 0.0),
                    players_json,
                    matches_json
                ))
                conn.commit()
                conn.close()
            else:
                conn = sqlite3.connect(self.sqlite_path)
                c = conn.cursor()
                c.execute("""
                    INSERT INTO club_snapshots 
                    (scraped_at, club_name, division, skill_rating, wins, losses, draws,
                     goals_scored, goals_conceded, win_rate, players_json, matches_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    club_data.get("club_name", ""),
                    club_data.get("division", 0),
                    club_data.get("skill_rating", 0),
                    club_data.get("wins", 0),
                    club_data.get("losses", 0),
                    club_data.get("draws", 0),
                    club_data.get("goals_scored", 0),
                    club_data.get("goals_conceded", 0),
                    club_data.get("win_rate", 0.0),
                    players_json,
                    matches_json
                ))
                conn.commit()
                conn.close()
            return True
        except Exception as e:
            logger.error("Failed to save snapshot: %s", e)
            return False

    def get_latest_snapshot(self) -> Optional[dict]:
        """Retrieve the most recent club snapshot."""
        try:
            if self.use_postgres:
                import psycopg2
                conn = psycopg2.connect(self.db_url)
                c = conn.cursor()
                c.execute("""
                    SELECT club_name, division, skill_rating, wins, losses, draws,
                           goals_scored, goals_conceded, win_rate, players_json, matches_json, scraped_at
                    FROM club_snapshots
                    ORDER BY scraped_at DESC
                    LIMIT 1
                """)
                row = c.fetchone()
                conn.close()
            else:
                conn = sqlite3.connect(self.sqlite_path)
                c = conn.cursor()
                c.execute("""
                    SELECT club_name, division, skill_rating, wins, losses, draws,
                           goals_scored, goals_conceded, win_rate, players_json, matches_json, scraped_at
                    FROM club_snapshots
                    ORDER BY scraped_at DESC
                    LIMIT 1
                """)
                row = c.fetchone()
                conn.close()

            if not row:
                return None

            return {
                "club_name": row[0],
                "division": row[1],
                "skill_rating": row[2],
                "wins": row[3],
                "losses": row[4],
                "draws": row[5],
                "goals_scored": row[6],
                "goals_conceded": row[7],
                "win_rate": row[8],
                "players": json.loads(row[9]) if row[9] else [],
                "matches": json.loads(row[10]) if row[10] else [],
                "scraped_at": row[11]
            }
        except Exception as e:
            logger.error("Failed to get snapshot: %s", e)
            return None

    def log_scrape(self, source: str, success: bool, error: str = "", request_count: int = 0):
        """Log a scrape attempt for metrics."""
        try:
            if self.use_postgres:
                import psycopg2
                conn = psycopg2.connect(self.db_url)
                c = conn.cursor()
                c.execute("""
                    INSERT INTO scrape_log (scraped_at, source, success, error, request_count)
                    VALUES (NOW(), %s, %s, %s, %s)
                """, (source, success, error, request_count))
                conn.commit()
                conn.close()
            else:
                conn = sqlite3.connect(self.sqlite_path)
                c = conn.cursor()
                c.execute("""
                    INSERT INTO scrape_log (scraped_at, source, success, error, request_count)
                    VALUES (?, ?, ?, ?, ?)
                """, (datetime.now().isoformat(), source, 1 if success else 0, error, request_count))
                conn.commit()
                conn.close()
        except Exception as e:
            logger.warning("Failed to log scrape: %s", e)

    def get_scrape_stats(self, hours: int = 24) -> dict:
        """Get scrape statistics for the last N hours."""
        try:
            if self.use_postgres:
                import psycopg2
                conn = psycopg2.connect(self.db_url)
                c = conn.cursor()
                c.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes,
                        SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failures,
                        SUM(request_count) as total_requests
                    FROM scrape_log
                    WHERE scraped_at > NOW() - INTERVAL '%s hours'
                """, (hours,))
                row = c.fetchone()
                conn.close()
            else:
                conn = sqlite3.connect(self.sqlite_path)
                c = conn.cursor()
                c.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes,
                        SUM(CASE WHEN NOT success THEN 0 ELSE 1 END) as failures,
                        SUM(request_count) as total_requests
                    FROM scrape_log
                    WHERE scraped_at > datetime('now', '-{} hours')
                """.format(hours))
                row = c.fetchone()
                conn.close()

            return {
                "total_attempts": row[0] or 0,
                "successes": row[1] or 0,
                "failures": row[2] or 0,
                "total_requests": row[3] or 0
            }
        except Exception as e:
            logger.error("Failed to get stats: %s", e)
            return {"total_attempts": 0, "successes": 0, "failures": 0, "total_requests": 0}
