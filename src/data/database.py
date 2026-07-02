"""SQLite database layer with automatic schema creation."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Optional

from src.core.logging import get_logger

logger = get_logger(__name__)


class Database:
    """Lightweight SQLite wrapper with WAL mode and connection pooling."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def initialize(self) -> None:
        """Create all tables if they don't exist."""
        logger.info("[DB] Initializing schema at %s", self.path)
        with self.connect() as conn:
            # Players (squad registry)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS players (
                    ea_id TEXT PRIMARY KEY,
                    nickname TEXT NOT NULL,
                    image TEXT,
                    personality TEXT,
                    meme_tags_json TEXT DEFAULT '[]',
                    position TEXT,
                    number INTEGER,
                    raw_json TEXT DEFAULT '{}',
                    updated_at TEXT
                )
                """
            )

            # Club snapshots
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS club_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    club_name TEXT NOT NULL,
                    division INTEGER DEFAULT 0,
                    skill_rating INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    draws INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    goals_scored INTEGER DEFAULT 0,
                    goals_conceded INTEGER DEFAULT 0,
                    scraped_at TEXT NOT NULL,
                    raw_json TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Matches
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS matches (
                    match_id TEXT PRIMARY KEY,
                    date TEXT NOT NULL,
                    opponent TEXT NOT NULL,
                    score_for INTEGER DEFAULT 0,
                    score_against INTEGER DEFAULT 0,
                    result TEXT CHECK(result IN ('W', 'D', 'L')),
                    raw_json TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Player match stats — WITH match_id column
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS player_match_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT NOT NULL DEFAULT '',
                    ea_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    position TEXT,
                    rating REAL DEFAULT 0.0,
                    minutes INTEGER DEFAULT 0,
                    goals INTEGER DEFAULT 0,
                    assists INTEGER DEFAULT 0,
                    shots INTEGER DEFAULT 0,
                    shots_on_target INTEGER DEFAULT 0,
                    passes_attempted INTEGER DEFAULT 0,
                    passes_completed INTEGER DEFAULT 0,
                    key_passes INTEGER DEFAULT 0,
                    tackles INTEGER DEFAULT 0,
                    interceptions INTEGER DEFAULT 0,
                    saves INTEGER DEFAULT 0,
                    possession_losses INTEGER DEFAULT 0,
                    red_cards INTEGER DEFAULT 0,
                    yellow_cards INTEGER DEFAULT 0,
                    clean_sheets INTEGER DEFAULT 0,
                    distance_covered REAL DEFAULT 0.0,
                    sprint_speed REAL DEFAULT 0.0,
                    raw_json TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(match_id, ea_id)
                )
                """
            )

            # Player form
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS player_form (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ea_id TEXT NOT NULL,
                    match_id TEXT NOT NULL,
                    form_score REAL DEFAULT 0.0,
                    impact_score REAL DEFAULT 0.0,
                    clutch_score REAL DEFAULT 0.0,
                    error_score REAL DEFAULT 0.0,
                    throwing_score REAL DEFAULT 0.0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(ea_id, match_id)
                )
                """
            )

            # Scrape log
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scrape_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scraped_at TEXT NOT NULL,
                    source TEXT,
                    success INTEGER DEFAULT 0,
                    error TEXT,
                    request_count INTEGER DEFAULT 0
                )
                """
            )

            # Recent replies (for deduplication)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS recent_replies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    reply_hash TEXT NOT NULL,
                    reply_text TEXT NOT NULL,
                    used_at TEXT NOT NULL
                )
                """
            )

            # Records (hall of fame / achievements)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_key TEXT NOT NULL UNIQUE,
                    player_ea_id TEXT,
                    match_id TEXT,
                    title TEXT NOT NULL,
                    value REAL DEFAULT 0.0,
                    payload_json TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Auto-post log
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS auto_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_type TEXT NOT NULL,
                    match_id TEXT,
                    channel_id TEXT,
                    message_id TEXT,
                    posted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    success INTEGER DEFAULT 1,
                    error TEXT
                )
                """
            )

            # Create indexes for performance
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_player_stats_ea_id ON player_match_stats(ea_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_player_stats_match_id ON player_match_stats(match_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_player_form_ea_id ON player_form(ea_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_scrape_log_at ON scrape_log(scraped_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_records_key ON records(record_key)"
            )

            conn.commit()

        logger.info("[DB] Schema initialized successfully")

    def reset(self) -> None:
        """Drop all tables and reinitialize. DANGER."""
        logger.warning("[DB] RESET requested — dropping all tables!")
        with self.connect() as conn:
            conn.execute("DROP TABLE IF EXISTS players")
            conn.execute("DROP TABLE IF EXISTS club_snapshots")
            conn.execute("DROP TABLE IF EXISTS matches")
            conn.execute("DROP TABLE IF EXISTS player_match_stats")
            conn.execute("DROP TABLE IF EXISTS player_form")
            conn.execute("DROP TABLE IF EXISTS scrape_log")
            conn.execute("DROP TABLE IF EXISTS recent_replies")
            conn.execute("DROP TABLE IF EXISTS records")
            conn.execute("DROP TABLE IF EXISTS auto_posts")
            conn.commit()
        self.initialize()
        logger.info("[DB] Reset complete")
