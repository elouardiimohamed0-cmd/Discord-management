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
        
        conn.commit()
        conn.close()
    
    def update_player(self, name: str, stats: dict):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("SELECT * FROM player_memories WHERE player_name = ?", (name,))
        row = c.fetchone()
        
        rating = stats.get('rating', 0)
        
        if not row:
            c.execute('''INSERT INTO player_memories 
                (player_name, total_games, total_goals, total_assists, total_possession_losses,
                 last_rating, best_rating, worst_rating, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (name, stats.get('games', 0), stats.get('goals', 0), stats.get('assists', 0),
                 stats.get('possession_losses', 0), rating, rating, rating, datetime.now()))
        else:
            # Replace totals (PCT returns cumulative season stats, not incremental)
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
            
            # Update best/worst historic ratings
            if rating > row[7]:
                c.execute("UPDATE player_memories SET best_rating = ? WHERE player_name = ?", (rating, name))
            if rating < row[8]:
                c.execute("UPDATE player_memories SET worst_rating = ? WHERE player_name = ?", (rating, name))
            if rating > row[13]:
                c.execute("UPDATE player_memories SET historic_high_rating = ? WHERE player_name = ?", (rating, name))
            if rating < row[14]:
                c.execute("UPDATE player_memories SET historic_low_rating = ? WHERE player_name = ?", (rating, name))
            
            # Consecutive streaks
            if rating < 5.5:
                c.execute("UPDATE player_memories SET consecutive_bad_games = consecutive_bad_games + 1, consecutive_good_games = 0 WHERE player_name = ?", (name,))
            elif rating > 7.5:
                c.execute("UPDATE player_memories SET consecutive_good_games = consecutive_good_games + 1, consecutive_bad_games = 0 WHERE player_name = ?", (name,))
            else:
                c.execute("UPDATE player_memories SET consecutive_bad_games = 0, consecutive_good_games = 0 WHERE player_name = ?", (name,))
        
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
            return f"{p1} وصل rating {m1['best_rating']}، {p2} ما وصلش لـ {m2['best_rating']}."
        else:
            return f"{p1} و {p2} بحال بحال — rivalry ماشي واضحة."
