from __future__ import annotations

from pathlib import Path

base = Path('/data/discord-rebuild-phase2')


def w(path: str, content: str) -> None:
    p = base / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding='utf-8')


# ---- new packages ----
w('src/data/__init__.py', '"""Database and repository layer."""\n')
w('src/scraper/__init__.py', '"""Pro Clubs Tracker scraping layer."""\n')

# ---- schema ----
w('src/data/schema.sql', r'''PRAGMA foreign_keys = ON;

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
''')

# ---- db + repo ----
w('src/data/database.py', r'''from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from src.core.logging import get_logger

logger = get_logger(__name__)


class Database:
    def __init__(self, path: Path, schema_path: Path | None = None):
        self.path = path
        self.schema_path = schema_path or Path(__file__).with_name("schema.sql")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        schema = self.schema_path.read_text(encoding="utf-8")
        with self.connect() as conn:
            conn.executescript(schema)
        logger.info("SQLite database initialized at %s", self.path)
''')

w('src/data/repositories.py', r'''from __future__ import annotations

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
''')

# ---- scraper ----
w('src/scraper/cache.py', r'''from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional


class JsonCache:
    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def get(self, key: str, ttl_seconds: int) -> Optional[dict[str, Any]]:
        path = self.directory / f"{key}.json"
        if not path.exists():
            return None
        if time.time() - path.stat().st_mtime > ttl_seconds:
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def set(self, key: str, value: dict[str, Any]) -> None:
        path = self.directory / f"{key}.json"
        path.write_text(json.dumps(value, ensure_ascii=False, default=str), encoding="utf-8")
''')

w('src/scraper/browser.py', r'''from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from src.core.logging import get_logger

logger = get_logger(__name__)


class BrowserFetcher:
    def __init__(self, cache_dir: Path, headless: bool = True):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cookie_path = self.cache_dir / "pct_cookies.json"
        self.headless = headless

    async def fetch_json_from_page(self, page_url: str, api_url: str) -> Optional[dict[str, Any]]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("Playwright is not installed; browser fallback disabled")
            return None

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
            )
            await self._load_cookies(context)
            page = await context.new_page()
            try:
                await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
                await page.goto(page_url, wait_until="networkidle", timeout=30000)
                data = await page.evaluate("() => window.__INITIAL_STATE__ || window.__DATA__ || window.clubData || null")
                if not data:
                    data = await page.evaluate(
                        """async (url) => {
                            const response = await fetch(url, {headers: {Accept: 'application/json'}});
                            return await response.json();
                        }""",
                        api_url,
                    )
                await self._save_cookies(context)
                return data if isinstance(data, dict) else None
            except Exception as exc:
                logger.warning("Browser fetch failed: %s", exc)
                return None
            finally:
                await browser.close()

    async def _load_cookies(self, context: Any) -> None:
        if not self.cookie_path.exists():
            return
        try:
            cookies = json.loads(self.cookie_path.read_text(encoding="utf-8"))
            if cookies:
                await context.add_cookies(cookies)
        except Exception:
            return

    async def _save_cookies(self, context: Any) -> None:
        try:
            cookies = await context.cookies()
            self.cookie_path.write_text(json.dumps(cookies, ensure_ascii=False), encoding="utf-8")
        except Exception:
            return
''')

w('src/scraper/parser.py', r'''from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from src.domain.models import ClubSnapshot, Match, PlayerMatchStats
from src.squad.registry import SquadRegistry


class ProClubsTrackerParser:
    def __init__(self, club_id: str, squad: SquadRegistry):
        self.club_id = str(club_id)
        self.squad = squad

    def parse(self, raw: dict[str, Any]) -> ClubSnapshot:
        club_info = raw.get("clubInfoData") or {}
        club_row = club_info.get(self.club_id) or (next(iter(club_info.values()), {}) if club_info else {})
        overall = raw.get("overallStats") or {}
        matches = self._parse_matches(raw)
        return ClubSnapshot(
            club_name=club_row.get("name") or club_row.get("clubName") or "Unknown Club",
            division=self._int(overall.get("bestDivision") or club_row.get("divisionId"), 0),
            skill_rating=self._int(overall.get("skillRating") or club_row.get("skillRating"), 0),
            wins=self._int(overall.get("wins"), 0),
            draws=self._int(overall.get("ties"), 0),
            losses=self._int(overall.get("losses"), 0),
            goals_scored=self._int(overall.get("goals"), 0),
            goals_conceded=self._int(overall.get("goalsAgainst"), 0),
            scraped_at=datetime.now(),
            matches=matches,
        )

    def _parse_matches(self, raw: dict[str, Any]) -> list[Match]:
        raw_matches = raw.get("matches") or {}
        all_matches: list[dict[str, Any]] = []
        if isinstance(raw_matches, dict):
            for key in ("league", "playoff", "friendly"):
                rows = raw_matches.get(key) or []
                if isinstance(rows, list):
                    all_matches.extend(rows)
        elif isinstance(raw_matches, list):
            all_matches = raw_matches

        parsed: list[Match] = []
        for row in all_matches:
            if not isinstance(row, dict):
                continue
            match = self._parse_match(row)
            if match and match.players:
                parsed.append(match)
        parsed.sort(key=lambda m: m.date, reverse=True)
        return parsed

    def _parse_match(self, row: dict[str, Any]) -> Optional[Match]:
        clubs = row.get("clubs") or {}
        if not isinstance(clubs, dict):
            return None
        ours = clubs.get(self.club_id)
        opponent = None
        for club_key, club_value in clubs.items():
            if str(club_key) != self.club_id:
                opponent = club_value
                break
        if not isinstance(ours, dict):
            return None

        score_for = self._int(ours.get("goals"), 0)
        score_against = self._int(ours.get("goalsAgainst"), 0)
        result = "W" if score_for > score_against else "L" if score_for < score_against else "D"
        timestamp = row.get("timestamp") or row.get("time")
        date = datetime.now()
        if timestamp:
            try:
                date = datetime.fromtimestamp(int(timestamp))
            except Exception:
                pass
        match_id = str(row.get("matchId") or row.get("matchid") or timestamp or f"{date.isoformat()}-{score_for}-{score_against}")
        players = self._parse_match_players(row)
        return Match(
            match_id=match_id,
            date=date,
            opponent=self._opponent_name(opponent),
            score_for=score_for,
            score_against=score_against,
            result=result,  # type: ignore[arg-type]
            players=players,
            raw=row,
        )

    def _parse_match_players(self, row: dict[str, Any]) -> list[PlayerMatchStats]:
        raw_players = ((row.get("players") or {}).get(self.club_id) or {})
        players: list[PlayerMatchStats] = []
        if not isinstance(raw_players, dict):
            return players
        for _pid, raw_player in raw_players.items():
            if not isinstance(raw_player, dict):
                continue
            ea_id = str(
                raw_player.get("playername")
                or raw_player.get("name")
                or raw_player.get("personaName")
                or "Unknown"
            ).strip()
            identity = self.squad.find(ea_id)
            display = identity.nickname if identity else ea_id
            passes_attempted = self._int(raw_player.get("passattempts"), 0)
            passes_completed = self._int(raw_player.get("passesmade"), 0)
            rating = self._rating(raw_player.get("rating"))
            minutes = self._int(raw_player.get("secondsPlayed"), 0) // 60
            players.append(
                PlayerMatchStats(
                    ea_id=ea_id,
                    display_name=display,
                    position=(identity.position if identity else (raw_player.get("pos") or None)),
                    rating=rating,
                    minutes=minutes,
                    goals=self._int(raw_player.get("goals"), 0),
                    assists=self._int(raw_player.get("assists"), 0),
                    shots=self._int(raw_player.get("shots"), 0),
                    passes_attempted=passes_attempted,
                    passes_completed=passes_completed,
                    tackles=self._int(raw_player.get("tacklesmade"), 0),
                    interceptions=self._int(raw_player.get("interceptions"), 0),
                    saves=self._int(raw_player.get("saves"), 0),
                    possession_losses=max(0, passes_attempted - passes_completed),
                    red_cards=self._int(raw_player.get("redcards"), 0),
                    yellow_cards=self._int(raw_player.get("yellowcards"), 0),
                    clean_sheets=self._int(raw_player.get("cleansheetsany"), 0),
                    raw=raw_player,
                )
            )
        return players

    @staticmethod
    def _opponent_name(opponent: Any) -> str:
        if not isinstance(opponent, dict):
            return "Unknown"
        details = opponent.get("details") if isinstance(opponent.get("details"), dict) else {}
        return details.get("name") or opponent.get("name") or opponent.get("clubName") or "Unknown"

    @staticmethod
    def _int(value: Any, default: int = 0) -> int:
        try:
            return int(float(str(value))) if value is not None else default
        except Exception:
            return default

    @staticmethod
    def _float(value: Any, default: float = 0.0) -> float:
        try:
            return float(str(value)) if value is not None else default
        except Exception:
            return default

    def _rating(self, value: Any) -> float:
        rating = self._float(value, 0.0)
        return round(rating / 10.0, 2) if rating > 10 else round(rating, 2)
''')

w('src/scraper/proclubs_tracker.py', r'''from __future__ import annotations

import gzip
from typing import Any, Optional

import httpx

from src.core.config import Settings
from src.core.logging import get_logger
from src.data.repositories import ClubRepository
from src.domain.models import ClubSnapshot
from src.scraper.browser import BrowserFetcher
from src.scraper.cache import JsonCache
from src.scraper.parser import ProClubsTrackerParser
from src.squad.registry import SquadRegistry

logger = get_logger(__name__)


class ProClubsTrackerClient:
    def __init__(self, settings: Settings, squad: SquadRegistry, repository: ClubRepository):
        self.settings = settings
        self.squad = squad
        self.repository = repository
        self.parser = ProClubsTrackerParser(settings.club_id, squad)
        self.cache = JsonCache(settings.cache_dir / "pct")
        self.browser = BrowserFetcher(settings.cache_dir / "browser")
        self.api_url = f"{{https://proclubstracker.com/api/clubs/{settings.club_id}}}?platform={settings.pct_platform}"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
            "Accept": "application/json, text/html,*/*",
            "Referer": "https://proclubstracker.com/",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def refresh(self, force: bool = False, source: str = "manual") -> ClubSnapshot:
        raw: Optional[dict[str, Any]] = None
        request_count = 0

        if not force:
            raw = self.cache.get("club", ttl_seconds=max(60, self.settings.scrape_interval_minutes * 60))
            if raw:
                logger.info("Using cached Pro Clubs Tracker payload")

        try:
            if raw is None:
                request_count += 1
                raw = await self._fetch_api()

            if raw is None:
                request_count += 1
                raw = await self.browser.fetch_json_from_page(self.settings.pct_club_url, self.api_url)

            if raw is None:
                raise RuntimeError("Pro Clubs Tracker returned no usable data")

            self.cache.set("club", raw)
            snapshot = self.parser.parse(raw)
            self.repository.save_snapshot(snapshot, raw=raw)
            self.repository.log_scrape(source=source, success=True, request_count=request_count)
            logger.info("Saved snapshot: %s matches", len(snapshot.matches))
            return snapshot
        except Exception as exc:
            self.repository.log_scrape(source=source, success=False, error=str(exc), request_count=request_count)
            logger.exception("Refresh failed")
            raise

    async def _fetch_api(self) -> Optional[dict[str, Any]]:
        async with httpx.AsyncClient(headers=self.headers, follow_redirects=True, timeout=20) as client:
            response = await client.get(self.api_url)
            if response.status_code in {403, 429}:
                logger.warning("PCT API blocked/limited: %s", response.status_code)
                return None
            if response.status_code != 200:
                logger.warning("PCT API status %s", response.status_code)
                return None

            raw = response.content
            if raw[:2] == b"\x1f\x8b" or "gzip" in response.headers.get("content-encoding", "").lower():
                raw = gzip.decompress(raw)
            if raw[:100].strip().startswith(b"<"):
                logger.warning("PCT API returned HTML instead of JSON")
                return None

            data = response.json()
            return data if isinstance(data, dict) else None
''')

# ---- services ----
w('src/services/match_service.py', r'''from __future__ import annotations

from typing import Any, Optional

from src.data.repositories import ClubRepository
from src.domain.models import ClubSnapshot, Match
from src.scraper.proclubs_tracker import ProClubsTrackerClient


class MatchService:
    def __init__(self, client: ProClubsTrackerClient, repository: ClubRepository):
        self.client = client
        self.repository = repository
        self.current_snapshot: Optional[ClubSnapshot] = None

    async def refresh(self, force: bool = False, source: str = "manual") -> ClubSnapshot:
        self.current_snapshot = await self.client.refresh(force=force, source=source)
        return self.current_snapshot

    def latest_match(self) -> Optional[Match]:
        if self.current_snapshot and self.current_snapshot.latest_match:
            return self.current_snapshot.latest_match
        return self.repository.latest_match()

    def status(self) -> dict[str, Any]:
        latest = self.latest_match()
        return {
            "has_latest_match": latest is not None,
            "latest_match_id": latest.match_id if latest else None,
            "latest_players": len(latest.players) if latest else 0,
            "latest_score": f"{latest.score_for}-{latest.score_against}" if latest else None,
            "opponent": latest.opponent if latest else None,
        }
''')

# ---- wire into app ----
w('src/core/app.py', r'''from __future__ import annotations

from dataclasses import dataclass

from src.core.config import Settings, load_settings
from src.data.database import Database
from src.data.repositories import ClubRepository
from src.discord_layer.bot import build_bot
from src.scraper.proclubs_tracker import ProClubsTrackerClient
from src.services.match_service import MatchService
from src.squad.registry import SquadRegistry


@dataclass
class AppContext:
    settings: Settings
    squad: SquadRegistry
    db: Database
    repo: ClubRepository
    pct: ProClubsTrackerClient
    matches: MatchService
    bot: object


def create_app() -> AppContext:
    settings = load_settings()
    squad = SquadRegistry.from_file(settings.squad_file)

    db = Database(settings.database_path)
    db.initialize()
    repo = ClubRepository(db)

    # store squad identities for enrichment (identity only)
    repo.upsert_identities(squad.all())

    pct = ProClubsTrackerClient(settings=settings, squad=squad, repository=repo)
    matches = MatchService(client=pct, repository=repo)

    bot = build_bot(settings=settings, squad=squad, match_service=matches)

    return AppContext(
        settings=settings,
        squad=squad,
        db=db,
        repo=repo,
        pct=pct,
        matches=matches,
        bot=bot,
    )
''')

# ---- update bot wiring to accept match_service + add /sync + /status ----
w('src/discord_layer/bot.py', r'''from __future__ import annotations

import discord
from discord.ext import commands

from src.core.config import Settings
from src.core.logging import get_logger
from src.discord_layer.commands import register_commands
from src.services.match_service import MatchService
from src.squad.registry import SquadRegistry

logger = get_logger(__name__)


def build_bot(settings: Settings, squad: SquadRegistry, match_service: MatchService) -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix=settings.command_prefix, intents=intents, help_command=None)

    bot.settings = settings  # type: ignore[attr-defined]
    bot.squad = squad  # type: ignore[attr-defined]
    bot.matches = match_service  # type: ignore[attr-defined]

    @bot.event
    async def on_ready() -> None:
        logger.info("Logged in as %s", bot.user)
        if settings.discord_guild_id:
            guild = discord.Object(id=settings.discord_guild_id)
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            logger.info("Synced commands to guild %s", settings.discord_guild_id)
        else:
            await bot.tree.sync()
            logger.info("Synced global commands")

    register_commands(bot)
    return bot
''')

w('src/discord_layer/commands.py', r'''from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from src.core.logging import get_logger

logger = get_logger(__name__)

REQUIRED_COMMANDS = [
    "player",
    "mvp",
    "fraud",
    "ghost",
    "carry",
    "who_sold",
    "ball_loser",
    "playmaker",
    "sniper",
    "compare",
    "court_case",
    "club",
    "records",
    "form",
    "awards",
    "legend",
    "hall_of_shame",
    "hall_of_fame",
    "match_report",
    "leaderboard",
]


def _phase_message(command: str) -> str:
    return (
        f"✅ `/{command}` is registered.\n"
        "Phase 2 is now wiring Pro Clubs Tracker + match.players truth. "
        "Phase 3 will add the full roast/stat/card behavior."
    )


def _get_match_service(bot: commands.Bot):
    return getattr(bot, "matches", None)


def register_commands(bot: commands.Bot) -> None:
    @bot.tree.command(name="sync", description="Fetch latest club data from Pro Clubs Tracker")
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: i.user.id)
    async def sync(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        svc = _get_match_service(bot)
        if not svc:
            await interaction.followup.send("Match service not wired.")
            return
        snapshot = await svc.refresh(force=True, source="discord:/sync")
        latest = snapshot.latest_match
        if not latest:
            await interaction.followup.send(f"Sync ok. Matches: {len(snapshot.matches)} (no latest match).")
            return
        await interaction.followup.send(
            f"✅ Sync ok. Latest: {latest.score_for}-{latest.score_against} vs {latest.opponent} | "
            f"match.players: {len(latest.players)}"
        )

    @bot.tree.command(name="status", description="Show current data status")
    async def status(interaction: discord.Interaction) -> None:
        svc = _get_match_service(bot)
        if not svc:
            await interaction.response.send_message("Match service not wired.")
            return
        st = svc.status()
        await interaction.response.send_message(
            "\n".join(
                [
                    "📊 Data status",
                    f"Latest match: {st.get('latest_match_id')}",
                    f"Score: {st.get('latest_score')} vs {st.get('opponent')}",
                    f"match.players: {st.get('latest_players')}",
                ]
            )
        )

    # ---- required command shells (still phase-3 logic later) ----
    @bot.tree.command(name="player", description="Player profile, stats, lore, and card")
    @app_commands.describe(player="Nickname, EA ID, or PSN")
    async def player(interaction: discord.Interaction, player: str) -> None:
        await interaction.response.send_message(_phase_message("player"))

    @bot.tree.command(name="mvp", description="Best performer from eligible match players")
    async def mvp(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("mvp"))

    @bot.tree.command(name="fraud", description="Fraud verdict for a player")
    @app_commands.describe(player="Nickname, EA ID, or PSN")
    async def fraud(interaction: discord.Interaction, player: Optional[str] = None) -> None:
        await interaction.response.send_message(_phase_message("fraud"))

    @bot.tree.command(name="ghost", description="Ghost verdict from match activity")
    async def ghost(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("ghost"))

    @bot.tree.command(name="carry", description="Who carried the squad")
    async def carry(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("carry"))

    @bot.tree.command(name="who_sold", description="Who sold the match")
    async def who_sold(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("who_sold"))

    @bot.tree.command(name="ball_loser", description="Most dangerous ball loss merchant")
    async def ball_loser(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("ball_loser"))

    @bot.tree.command(name="playmaker", description="Chance creator and pass dictator")
    async def playmaker(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("playmaker"))

    @bot.tree.command(name="sniper", description="Finishing and shot efficiency king")
    async def sniper(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("sniper"))

    @bot.tree.command(name="compare", description="Compare two players")
    @app_commands.describe(player_one="First player", player_two="Second player")
    async def compare(interaction: discord.Interaction, player_one: str, player_two: str) -> None:
        await interaction.response.send_message(_phase_message("compare"))

    @bot.tree.command(name="court_case", description="Open the tribunal case file")
    @app_commands.describe(player="Accused player")
    async def court_case(interaction: discord.Interaction, player: str) -> None:
        await interaction.response.send_message(_phase_message("court_case"))

    @bot.tree.command(name="club", description="Club summary and squad state")
    async def club(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("club"))

    @bot.tree.command(name="records", description="Club records and broken records")
    async def records(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("records"))

    @bot.tree.command(name="form", description="Recent form for a player")
    @app_commands.describe(player="Player", matches="Number of recent matches")
    async def form(interaction: discord.Interaction, player: str, matches: int = 5) -> None:
        await interaction.response.send_message(_phase_message("form"))

    @bot.tree.command(name="awards", description="Awards and weekly winners")
    async def awards(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("awards"))

    @bot.tree.command(name="legend", description="Legend card and lore")
    @app_commands.describe(player="Optional player")
    async def legend(interaction: discord.Interaction, player: Optional[str] = None) -> None:
        await interaction.response.send_message(_phase_message("legend"))

    @bot.tree.command(name="hall_of_shame", description="Historic fraud museum")
    async def hall_of_shame(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("hall_of_shame"))

    @bot.tree.command(name="hall_of_fame", description="Historic elite performances")
    async def hall_of_fame(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("hall_of_fame"))

    @bot.tree.command(name="match_report", description="Latest match report with banter")
    async def match_report(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("match_report"))

    @bot.tree.command(name="leaderboard", description="Leaderboard by metric")
    @app_commands.describe(metric="goals, assists, rating, minutes, losses, saves, matches")
    async def leaderboard(interaction: discord.Interaction, metric: str = "goals") -> None:
        await interaction.response.send_message(_phase_message("leaderboard"))

    logger.info("Registered required shells + /sync + /status")
''')

# ---- update requirements (Phase2 needs sqlite only, already stdlib, but uses httpx/playwright) ----
w('requirements.txt', '''discord.py>=2.3.0
python-dotenv>=1.0.0
pydantic>=2.0
httpx>=0.27.0
Pillow>=10.0.0
playwright>=1.44.0
''')

# ---- phase readme ----
w('README_PHASE2.md', '''# Phase 2 — Data Engine (Pro Clubs Tracker + Playwright fallback)

This phase adds:
- SQLite normalized database schema
- ProClubsTracker client (httpx API + Playwright fallback)
- parser that builds Match objects where `match.players` is the source of truth
- persistence into `matches` and `player_match_stats`
- Discord commands: `/sync` and `/status`

Notes:
- `squad.json` is identity only (nickname/image/personality/tags). It never decides who played.
- Only players present in match payload are inserted for match-level stats.
''')

print('Phase 2 files written')
