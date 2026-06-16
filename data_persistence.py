"""
phase2_data_persistence.py
Caches scraped data to SQLite + JSON so commands work even if scraper is temporarily down.
DO NOT modify scraper.py — this is a WRAPPER around it.
"""
import json
import os
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = os.getenv("MATCH_DB", "matches.db")
SQUAD_PATH = os.getenv("SQUAD_FILE", "squad.json")
ASSETS_DIR = os.getenv("ASSETS_DIR", "assets")

# NICKNAME MAP — single source of truth
NICKNAME_MAP = {
    "A999ESCANOR": "Dictator",
    "A999SHARK": "Shark",
    "Hessaidi": "Shawarmista",
    "brave-Youness95": "Brave",
    "brown-base7": "Le7ya",
    "A999KIRA": "Kira",
    "Taha1direction": "Marrakchi",
    "Yasskillz88": "Modamir",
    "Amine_bambo": "Moul_l7anot",
    "haytamox2": "9ahba_south_africa",
}

# Reverse map for lookup
NAME_TO_PSN = {v: k for k, v in NICKNAME_MAP.items()}

def init_db():
    """Initialize matches database with robust schema."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            match_id TEXT PRIMARY KEY,
            date TEXT,
            opponent TEXT,
            score_for INTEGER,
            score_against INTEGER,
            result TEXT,
            player_stats TEXT,
            created_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players_cache (
            name TEXT PRIMARY KEY,
            psn TEXT,
            nickname TEXT,
            position TEXT,
            games INTEGER,
            goals INTEGER,
            assists INTEGER,
            rating REAL,
            tackles INTEGER,
            interceptions INTEGER,
            minutes INTEGER,
            motm INTEGER,
            pass_accuracy REAL,
            possession_losses INTEGER,
            impact_score REAL,
            throwing_score REAL,
            error_score REAL,
            clutch_score REAL,
            win_rate REAL,
            updated_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS club_cache (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_match(match_id, date, opponent, score_for, score_against, result, player_stats):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO matches 
        (match_id, date, opponent, score_for, score_against, result, player_stats, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (match_id, date, opponent, score_for, score_against, result, 
          json.dumps(player_stats), datetime.now().isoformat()))
    conn.commit()
    conn.close()

def save_players_cache(players):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    for p in players:
        nickname = NICKNAME_MAP.get(p.name, p.name)
        psn = NAME_TO_PSN.get(nickname, "")
        cursor.execute("""
            INSERT OR REPLACE INTO players_cache
            (name, psn, nickname, position, games, goals, assists, rating, tackles,
             interceptions, minutes, motm, pass_accuracy, possession_losses,
             impact_score, throwing_score, error_score, clutch_score, win_rate, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p.name, psn, nickname, getattr(p, "position", "CM"),
            p.games, p.goals, p.assists, p.rating_pg,
            p.tackles, p.interceptions, p.minutes_played, p.motm,
            p.pass_accuracy, p.possession_losses,
            p.impact_score, p.throwing_score, p.error_score, p.clutch_score,
            p.win_rate, now
        ))
    conn.commit()
    conn.close()

def save_club_cache(club_name, division, skill_rating, wins, losses, draws):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    data = json.dumps({
        "club_name": club_name, "division": division, "skill_rating": skill_rating,
        "wins": wins, "losses": losses, "draws": draws,
        "updated_at": datetime.now().isoformat()
    })
    cursor.execute("INSERT OR REPLACE INTO club_cache (key, value) VALUES (?, ?)", ("club_info", data))
    conn.commit()
    conn.close()

def load_players_cache():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM players_cache ORDER BY impact_score DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def load_matches_cache(limit=50):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM matches ORDER BY date DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def load_club_cache():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM club_cache WHERE key = ?", ("club_info",))
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None

def get_squad_with_photos():
    paths = [SQUAD_PATH, f"{ASSETS_DIR}/{SQUAD_PATH}", "squad.json", "assets/squad.json"]
    for p in paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f2:
                    return json.load(f2)
            except:
                continue
    return {}

def resolve_photo_path(player_key, squad_data):
    if player_key not in squad_data:
        return ""
    player = squad_data[player_key]
    explicit = player.get("image", "")
    name = player.get("name", player_key)
    psn = player.get("psn", "")
    candidates = [
        explicit,
        f"{ASSETS_DIR}/{name}.png", f"{ASSETS_DIR}/{name}.jpg", f"{ASSETS_DIR}/{name}.jpeg",
        f"{ASSETS_DIR}/{psn}.png", f"{ASSETS_DIR}/{psn}.jpg", f"{ASSETS_DIR}/{psn}.jpeg",
        f"assets/{name}.png", f"assets/{name}.jpg", f"assets/{name}.jpeg",
        f"assets/{psn}.png", f"assets/{psn}.jpg", f"assets/{psn}.jpeg",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return ""

init_db()
