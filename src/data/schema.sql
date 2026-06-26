PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS players (
    ea_id TEXT PRIMARY KEY,
    nickname TEXT,
    image TEXT,
    personality TEXT,
    meme_tags_json TEXT NOT NULL DEFAULT '[]',
    position TEXT,
    number INTEGER,
    raw_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS matches (
    match_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    opponent TEXT NOT NULL,
    score_for INTEGER NOT NULL,
    score_against INTEGER NOT NULL,
    result TEXT NOT NULL CHECK(result IN ('W', 'D', 'L')),
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS player_match_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL,
    ea_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    position TEXT,
    rating REAL NOT NULL DEFAULT 0,
    minutes INTEGER NOT NULL DEFAULT 0,
    goals INTEGER NOT NULL DEFAULT 0,
    assists INTEGER NOT NULL DEFAULT 0,
    shots INTEGER NOT NULL DEFAULT 0,
    passes_attempted INTEGER NOT NULL DEFAULT 0,
    passes_completed INTEGER NOT NULL DEFAULT 0,
    tackles INTEGER NOT NULL DEFAULT 0,
    interceptions INTEGER NOT NULL DEFAULT 0,
    saves INTEGER NOT NULL DEFAULT 0,
    possession_losses INTEGER NOT NULL DEFAULT 0,
    red_cards INTEGER NOT NULL DEFAULT 0,
    yellow_cards INTEGER NOT NULL DEFAULT 0,
    clean_sheets INTEGER NOT NULL DEFAULT 0,
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(match_id, ea_id),
    FOREIGN KEY(match_id) REFERENCES matches(match_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_player_match_stats_ea_id ON player_match_stats(ea_id);
CREATE INDEX IF NOT EXISTS idx_player_match_stats_match_id ON player_match_stats(match_id);
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date DESC);

CREATE TABLE IF NOT EXISTS club_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    club_name TEXT NOT NULL,
    division INTEGER NOT NULL DEFAULT 0,
    skill_rating INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    draws INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    goals_scored INTEGER NOT NULL DEFAULT 0,
    goals_conceded INTEGER NOT NULL DEFAULT 0,
    scraped_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_club_snapshots_scraped_at ON club_snapshots(scraped_at DESC);

CREATE TABLE IF NOT EXISTS scrape_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scraped_at TEXT NOT NULL,
    source TEXT NOT NULL,
    success INTEGER NOT NULL,
    error TEXT,
    request_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_key TEXT NOT NULL UNIQUE,
    player_ea_id TEXT,
    match_id TEXT,
    title TEXT NOT NULL,
    value REAL NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS awards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    award_key TEXT NOT NULL,
    period_start TEXT,
    period_end TEXT,
    player_ea_id TEXT NOT NULL,
    title TEXT NOT NULL,
    score REAL NOT NULL DEFAULT 0,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE(award_key, period_start, period_end, player_ea_id)
);

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_ea_id TEXT,
    memory_type TEXT NOT NULL,
    text TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rivalries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_one_ea_id TEXT NOT NULL,
    player_two_ea_id TEXT NOT NULL,
    wins_one INTEGER NOT NULL DEFAULT 0,
    wins_two INTEGER NOT NULL DEFAULT 0,
    draws INTEGER NOT NULL DEFAULT 0,
    payload_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL,
    UNIQUE(player_one_ea_id, player_two_ea_id)
);

CREATE TABLE IF NOT EXISTS recent_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    reply_hash TEXT NOT NULL,
    reply_text TEXT NOT NULL,
    used_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_recent_replies_category ON recent_replies(category, used_at DESC);
