import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
from config import Config

class SquadMemory:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or Config.MEMORY_DB
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''CREATE TABLE IF NOT EXISTS player_memories (
            player_name TEXT PRIMARY KEY,
            total_games INTEGER DEFAULT 0,
            total_goals INTEGER DEFAULT 0,
            total_assists INTEGER DEFAULT 0,
            total_possession_losses INTEGER DEFAULT 0,
            mvps INTEGER DEFAULT 0,
            frauds INTEGER DEFAULT 0,
            last_rating REAL DEFAULT 0,
            best_rating REAL DEFAULT 0,
            worst_rating REAL DEFAULT 10,
            penalty_misses INTEGER DEFAULT 0,
            own_goals INTEGER DEFAULT 0,
            red_cards INTEGER DEFAULT 0,
            historic_low_rating REAL DEFAULT 10,
            historic_high_rating REAL DEFAULT 0,
            consecutive_bad_games INTEGER DEFAULT 0,
            consecutive_good_games INTEGER DEFAULT 0,
            rivalries TEXT DEFAULT '[]',
            nicknames TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS match_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT,
            player_name TEXT,
            event_type TEXT,
            event_data TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS session_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date TEXT,
            games_played INTEGER,
            wins INTEGER,
            losses INTEGER,
            top_scorer TEXT,
            top_fraud TEXT,
            motm TEXT,
            notes TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # ── PHASE 4 Tables ──
        c.execute('''CREATE TABLE IF NOT EXISTS hall_of_fame_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            player_name TEXT,
            value REAL,
            match_id TEXT,
            opponent TEXT,
            record_date TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS hall_of_shame_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            player_name TEXT,
            value REAL,
            match_id TEXT,
            opponent TEXT,
            record_date TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS weekly_awards_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_date TEXT,
            award_type TEXT,
            player_name TEXT,
            score REAL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS milestones_alerted (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT,
            milestone_key TEXT UNIQUE,
            stat_name TEXT,
            threshold INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS rivalry_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player1 TEXT,
            player2 TEXT,
            p1_wins INTEGER DEFAULT 0,
            p2_wins INTEGER DEFAULT 0,
            ties INTEGER DEFAULT 0,
            last_match_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(player1, player2)
        )''')

        conn.commit()
        conn.close()

    def update_player(self, name: str, stats: dict):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("SELECT * FROM player_memories WHERE player_name = ?", (name,))
        row = c.fetchone()

        rating = stats.get('rating', 0)

        if not row:
            # New player: INSERT base row, then seed historic high/low from the first rating
            # so we don't carry the schema defaults (high=0, low=10) forever.
            c.execute('''INSERT INTO player_memories
                (player_name, total_games, total_goals, total_assists, total_possession_losses,
                 last_rating, best_rating, worst_rating, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (name, stats.get('games', 0), stats.get('goals', 0), stats.get('assists', 0),
                 stats.get('possession_losses', 0), rating, rating, rating, datetime.now()))
            c.execute(
                "UPDATE player_memories SET historic_high_rating = ?, historic_low_rating = ? "
                "WHERE player_name = ?",
                (rating, rating, name),
            )
        else:
            c.execute('''UPDATE player_memories SET
                total_games = ?,
                total_goals = ?,
                total_assists = ?,
                total_possession_losses = ?,
                last_rating = ?,
                updated_at = ?
                WHERE player_name = ?''',
                (stats.get('games', 0), stats.get('goals', 0), stats.get('assists', 0),
                 stats.get('possession_losses', 0), rating, datetime.now(), name))

            # Column indices (match _init_db schema order):
            #   7 = last_rating, 8 = best_rating, 9 = worst_rating,
            #   13 = historic_low_rating, 14 = historic_high_rating
            best_rating = row[8]
            worst_rating = row[9]
            historic_low = row[13]
            historic_high = row[14]

            if rating > best_rating:
                c.execute("UPDATE player_memories SET best_rating = ? WHERE player_name = ?",
                          (rating, name))
            if rating < worst_rating:
                c.execute("UPDATE player_memories SET worst_rating = ? WHERE player_name = ?",
                          (rating, name))
            if rating > historic_high:
                c.execute("UPDATE player_memories SET historic_high_rating = ? WHERE player_name = ?",
                          (rating, name))
            if rating < historic_low:
                c.execute("UPDATE player_memories SET historic_low_rating = ? WHERE player_name = ?",
                          (rating, name))

        # Streak tracking applies to both new and existing rows.
        if rating < 5.5:
            c.execute(
                "UPDATE player_memories SET consecutive_bad_games = consecutive_bad_games + 1, "
                "consecutive_good_games = 0 WHERE player_name = ?",
                (name,),
            )
        elif rating > 7.5:
            c.execute(
                "UPDATE player_memories SET consecutive_good_games = consecutive_good_games + 1, "
                "consecutive_bad_games = 0 WHERE player_name = ?",
                (name,),
            )
        else:
            c.execute(
                "UPDATE player_memories SET consecutive_bad_games = 0, "
                "consecutive_good_games = 0 WHERE player_name = ?",
                (name,),
            )

        conn.commit()
        conn.close()

    def get_player_memory(self, name: str) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM player_memories WHERE player_name = ?", (name,))
        row = c.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "name": row[0],
            "total_games": row[1],
            "total_goals": row[2],
            "total_assists": row[3],
            "total_possession_losses": row[4],
            "mvps": row[5],
            "frauds": row[6],
            "last_rating": row[7],
            "best_rating": row[8],
            "worst_rating": row[9],
            "consecutive_bad": row[15],
            "consecutive_good": row[16],
            "rivalries": json.loads(row[17]),
            "nicknames": json.loads(row[18]),
        }

    def add_event(self, match_id: str, player_name: str, event_type: str, data: dict):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''INSERT INTO match_events (match_id, player_name, event_type, event_data)
            VALUES (?, ?, ?, ?)''',
            (match_id, player_name, event_type, json.dumps(data)))
        conn.commit()
        conn.close()

    def get_historical_roasts(self, player_name: str, limit: int = 5) -> List[str]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''SELECT event_data FROM match_events
            WHERE player_name = ? AND event_type = 'roast'
            ORDER BY timestamp DESC LIMIT ?''', (player_name, limit))
        rows = c.fetchall()
        conn.close()
        return [json.loads(r[0]).get("text", "") for r in rows]

    def record_session(self, games: int, wins: int, losses: int, top_scorer: str, top_fraud: str, motm: str, notes: str = ""):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''INSERT INTO session_stats
            (session_date, games_played, wins, losses, top_scorer, top_fraud, motm, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (datetime.now().strftime("%Y-%m-%d"), games, wins, losses, top_scorer, top_fraud, motm, notes))
        conn.commit()
        conn.close()

    def get_rivalry(self, p1: str, p2: str) -> str:
        m1 = self.get_player_memory(p1)
        m2 = self.get_player_memory(p2)

        if not m1 or not m2:
            return ""

        diff_goals = m1["total_goals"] - m2["total_goals"]
        diff_rating = m1["best_rating"] - m2["best_rating"]

        if diff_goals > 10:
            return f"{p1} كيدر {p2} فالتسجيل بـ {diff_goals} هدف."
        elif diff_goals < -10:
            return f"{p2} كيدر {p1} فالتسجيل بـ {abs(diff_goals)} هدف."
        elif diff_rating > 1:
            return f"{p1} وصل rating {m1['best_rating']}, {p2} ما وصلش لـ {m2['best_rating']}."
        else:
            return f"{p1} و {p2} بحال بحال — rivalry ماشي واضحة."

    # ────────────────────────────────────────────
    # PHASE 4 METHODS
    # ────────────────────────────────────────────

    def record_fame_record(self, category: str, player_name: str, value: float, match_id: str = None, opponent: str = None, record_date: str = None, description: str = ""):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO hall_of_fame_records
            (category, player_name, value, match_id, opponent, record_date, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (category, player_name, value, match_id, opponent, record_date, description))
        conn.commit()
        conn.close()

    def get_fame_records(self, category: str = None) -> list:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        if category:
            c.execute("SELECT * FROM hall_of_fame_records WHERE category = ? ORDER BY value DESC", (category,))
        else:
            c.execute("SELECT * FROM hall_of_fame_records ORDER BY created_at DESC")
        rows = c.fetchall()
        conn.close()
        return [{"id": r[0], "category": r[1], "player": r[2], "value": r[3], "match_id": r[4], "opponent": r[5], "date": r[6], "description": r[7]} for r in rows]

    def record_shame_record(self, category: str, player_name: str, value: float, match_id: str = None, opponent: str = None, record_date: str = None, description: str = ""):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO hall_of_shame_records
            (category, player_name, value, match_id, opponent, record_date, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (category, player_name, value, match_id, opponent, record_date, description))
        conn.commit()
        conn.close()

    def get_shame_records(self, category: str = None) -> list:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        if category:
            c.execute("SELECT * FROM hall_of_shame_records WHERE category = ? ORDER BY value DESC", (category,))
        else:
            c.execute("SELECT * FROM hall_of_shame_records ORDER BY created_at DESC")
        rows = c.fetchall()
        conn.close()
        return [{"id": r[0], "category": r[1], "player": r[2], "value": r[3], "match_id": r[4], "opponent": r[5], "date": r[6], "description": r[7]} for r in rows]

    def record_weekly_award(self, week_date: str, award_type: str, player_name: str, score: float, description: str = ""):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''INSERT INTO weekly_awards_history
            (week_date, award_type, player_name, score, description)
            VALUES (?, ?, ?, ?, ?)''',
            (week_date, award_type, player_name, score, description))
        conn.commit()
        conn.close()

    def get_weekly_awards(self, limit: int = 20) -> list:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM weekly_awards_history ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = c.fetchall()
        conn.close()
        return [{"week": r[1], "award": r[2], "player": r[3], "score": r[4], "desc": r[5]} for r in rows]

    def is_milestone_alerted(self, milestone_key: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT 1 FROM milestones_alerted WHERE milestone_key = ?", (milestone_key,))
        result = c.fetchone() is not None
        conn.close()
        return result

    def record_milestone_alerted(self, player_name: str, milestone_key: str, stat_name: str, threshold: int):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''INSERT OR IGNORE INTO milestones_alerted
            (player_name, milestone_key, stat_name, threshold)
            VALUES (?, ?, ?, ?)''',
            (player_name, milestone_key, stat_name, threshold))
        conn.commit()
        conn.close()

    def get_milestones_alerted(self, player_name: str = None) -> list:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        if player_name:
            c.execute("SELECT * FROM milestones_alerted WHERE player_name = ?", (player_name,))
        else:
            c.execute("SELECT * FROM milestones_alerted")
        rows = c.fetchall()
        conn.close()
        return [{"player": r[1], "key": r[2], "stat": r[3], "threshold": r[4]} for r in rows]

    def record_rivalry_result(self, p1: str, p2: str, winner: str):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        a, b = sorted([p1, p2])
        c.execute('''INSERT INTO rivalry_history (player1, player2, p1_wins, p2_wins, ties, last_match_date)
            VALUES (?, ?, 0, 0, 0, ?)
            ON CONFLICT(player1, player2) DO UPDATE SET
                p1_wins = p1_wins + CASE WHEN ? = player1 THEN 1 ELSE 0 END,
                p2_wins = p2_wins + CASE WHEN ? = player2 THEN 1 ELSE 0 END,
                ties = ties + CASE WHEN ? = 'Tie' THEN 1 ELSE 0 END,
                last_match_date = ?''',
            (a, b, datetime.now().strftime("%Y-%m-%d"), winner, winner, winner, datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
        conn.close()

    def get_rivalry_history(self, p1: str, p2: str) -> dict:
        a, b = sorted([p1, p2])
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM rivalry_history WHERE player1 = ? AND player2 = ?", (a, b))
        row = c.fetchone()
        conn.close()
        if not row:
            return {"p1_wins": 0, "p2_wins": 0, "ties": 0, "total": 0}
        return {"p1_wins": row[3], "p2_wins": row[4], "ties": row[5], "total": row[3] + row[4] + row[5], "last_date": row[6]}
