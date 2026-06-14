"""
Rachad L3ERGONI Bot — EA FC Pro Clubs Direct API Client (SYNC VERSION)
Hits proclubs.ea.com directly. No async threading. No aiosqlite.
"""

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://proclubs.ea.com/api/fc"
EA_HEADERS = {
    "authority": "proclubs.ea.com",
    "accept": "application/json",
    "accept-language": "en-US,en;q=0.9",
    "origin": "https://www.ea.com",
    "referer": "https://www.ea.com/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/141.0.0.0 Safari/537.36"
    ),
}


@dataclass
class EAPlayerMatch:
    """All fields have defaults for Python 3.14 compatibility."""
    name: str = ""
    position: str = "CM"
    goals: int = 0
    assists: int = 0
    shots: int = 0
    shots_on_target: int = 0
    passes_attempted: int = 0
    passes_completed: int = 0
    key_passes: int = 0
    tackles: int = 0
    tackles_attempted: int = 0
    interceptions: int = 0
    possession_losses: int = 0
    dribbles_attempted: int = 0
    dribbles_completed: int = 0
    fouls: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    rating: float = 6.0
    motm: bool = False
    minutes_played: int = 90
    saves: int = 0
    clean_sheets_gk: int = 0
    own_goals: int = 0
    longshots: int = 0
    chances_created: int = 0

    @property
    def pass_accuracy(self) -> float:
        if self.passes_attempted == 0:
            return 0.0
        return round((self.passes_completed / self.passes_attempted) * 100, 1)

    @property
    def shot_accuracy(self) -> float:
        if self.shots == 0:
            return 0.0
        return round((self.shots_on_target / max(self.shots, 1)) * 100, 1)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "position": self.position,
            "goals": self.goals,
            "assists": self.assists,
            "shots": self.shots,
            "shots_on_target": self.shots_on_target,
            "passes_attempted": self.passes_attempted,
            "passes_completed": self.passes_completed,
            "pass_accuracy": self.pass_accuracy,
            "key_passes": self.key_passes,
            "tackles": self.tackles,
            "tackles_attempted": self.tackles_attempted,
            "interceptions": self.interceptions,
            "possession_losses": self.possession_losses,
            "dribbles_attempted": self.dribbles_attempted,
            "dribbles_completed": self.dribbles_completed,
            "fouls": self.fouls,
            "yellow_cards": self.yellow_cards,
            "red_cards": self.red_cards,
            "rating": self.rating,
            "motm": self.motm,
            "minutes_played": self.minutes_played,
            "saves": self.saves,
            "clean_sheets_gk": self.clean_sheets_gk,
            "own_goals": self.own_goals,
            "longshots": self.longshots,
            "chances_created": self.chances_created,
            "shot_accuracy": self.shot_accuracy,
        }


@dataclass
class EAMatch:
    match_id: str = ""
    timestamp: int = 0
    date_iso: str = ""
    opponent_name: str = ""
    opponent_id: str = ""
    team_goals: int = 0
    opponent_goals: int = 0
    match_type: str = "friendlyMatch"
    player_stats: Dict[str, EAPlayerMatch] = field(default_factory=dict)
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def result(self) -> str:
        if self.team_goals > self.opponent_goals:
            return "win"
        elif self.team_goals < self.opponent_goals:
            return "loss"
        return "draw"

    def to_dict(self) -> dict:
        return {
            "match_id": self.match_id,
            "date": self.date_iso,
            "opponent": self.opponent_name,
            "result": self.result,
            "team_goals": self.team_goals,
            "opponent_goals": self.opponent_goals,
            "match_type": self.match_type,
            "player_stats": {k: v.to_dict() for k, v in self.player_stats.items()},
        }


class EAProClubsAPI:
    """
    Sync client for EA's public Pro Clubs API.
    Uses sqlite3 for persistent caching (sync, no threads).
    """

    def __init__(self, club_id: str, platform: str = "common-gen5", db_path: str = "bot_cache.db"):
        self.club_id = str(club_id)
        self.platform = platform
        self.db_path = db_path
        self._client = httpx.Client(headers=EA_HEADERS, timeout=20, follow_redirects=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    data TEXT,
                    ts INTEGER
                )
            """)
            conn.commit()

    def _cached_get(self, key: str, ttl_seconds: int, fetch_fn) -> Any:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT data, ts FROM cache WHERE key = ?", (key,)).fetchone()
            if row and (time.time() - row[1]) < ttl_seconds:
                return json.loads(row[0])

        data = fetch_fn()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, data, ts) VALUES (?, ?, ?)",
                (key, json.dumps(data, ensure_ascii=False), int(time.time())),
            )
            conn.commit()
        return data

    def _ea_get(self, endpoint: str, params: Optional[dict] = None) -> Any:
        url = f"{BASE_URL}{endpoint}"
        try:
            resp = self._client.get(url, params=params)
            if resp.status_code == 429:
                logger.warning("EA API rate limited. Sleeping 30s...")
                time.sleep(30)
                resp = self._client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException:
            logger.error("EA API timeout: %s", url)
            raise
        except httpx.HTTPStatusError as e:
            logger.error("EA API HTTP %s: %s", e.response.status_code, url)
            raise

    # ── Public API ─────────────────────────────────────────────────────

    def get_club_info(self) -> dict:
        try:
            key = f"club_info:{self.club_id}:{self.platform}"
            return self._cached_get(
                key, 300,
                lambda: self._ea_get("/clubs/info", {"platform": self.platform, "clubIds": self.club_id})
            )
        except Exception as e:
            logger.error("get_club_info error: %s", e)
            return {}

    def get_member_stats(self) -> List[dict]:
        try:
            key = f"member_stats:{self.club_id}:{self.platform}"
            return self._cached_get(
                key, 180,
                lambda: self._ea_get("/members/stats", {"platform": self.platform, "clubId": self.club_id})
            )
        except Exception as e:
            logger.error("get_member_stats error: %s", e)
            return []

    def get_member_career(self) -> List[dict]:
        try:
            key = f"member_career:{self.club_id}:{self.platform}"
            return self._cached_get(
                key, 600,
                lambda: self._ea_get("/members/careerStats", {"platform": self.platform, "clubId": self.club_id})
            )
        except Exception as e:
            logger.error("get_member_career error: %s", e)
            return []

    def get_matches(self, match_type: str = "friendlyMatch", max_results: int = 20) -> List[EAMatch]:
        try:
            key = f"matches:{self.club_id}:{self.platform}:{match_type}:{max_results}"
            raw = self._cached_get(
                key, 300,
                lambda: self._ea_get("/clubs/matches", {
                    "platform": self.platform,
                    "clubIds": self.club_id,
                    "matchType": match_type,
                    "maxResultCount": max_results,
                })
            )
            if not isinstance(raw, list):
                return []
            return [self._parse_match(m, match_type) for m in raw if m]
        except Exception as e:
            logger.error("get_matches error: %s", e)
            return []

    def get_all_matches(self, max_per_type: int = 15) -> List[EAMatch]:
        all_matches = []
        for mtype in ["leagueMatch", "playoffMatch", "friendlyMatch"]:
            try:
                matches = self.get_matches(mtype, max_per_type)
                all_matches.extend(matches)
            except Exception as e:
                logger.error("Failed fetching %s: %s", mtype, e)
        seen = set()
        unique = []
        for m in sorted(all_matches, key=lambda x: x.timestamp, reverse=True):
            if m.match_id not in seen:
                seen.add(m.match_id)
                unique.append(m)
        return unique

    def search_club(self, name: str) -> List[dict]:
        try:
            return self._ea_get("/allTimeLeaderboard/search", {"platform": self.platform, "clubName": name})
        except Exception as e:
            logger.error("search_club error: %s", e)
            return []

    # ── Parsers ─────────────────────────────────────────────────────────

    def _parse_match(self, raw: dict, match_type: str) -> Optional[EAMatch]:
        try:
            our_id = str(self.club_id)
            clubs = raw.get("clubs", {})
            our_club = None
            opp_club = None
            opp_id = None

            for cid, cdata in clubs.items():
                if str(cid) == our_id:
                    our_club = cdata
                else:
                    opp_club = cdata
                    opp_id = str(cid)

            if not our_club or not opp_club:
                return None

            our_goals = int(our_club.get("goals", 0))
            opp_goals = int(our_club.get("goalsAgainst", 0))

            ts = int(raw.get("timestamp", 0))
            dt = datetime.utcfromtimestamp(ts).isoformat() if ts else "—"

            match = EAMatch(
                match_id=str(raw.get("matchId", raw.get("timestamp", ""))),
                timestamp=ts,
                date_iso=dt,
                opponent_name=opp_club.get("details", {}).get("name", "Unknown"),
                opponent_id=opp_id or "",
                team_goals=our_goals,
                opponent_goals=opp_goals,
                match_type=match_type,
                raw=raw,
            )

            players_raw = raw.get("players", {}).get(our_id, {})
            for pid, p in players_raw.items():
                if not isinstance(p, dict):
                    continue
                seconds = int(p.get("secondsPlayed", 0))
                minutes = seconds // 60
                passes_att = int(p.get("passattempts", 0))
                passes_comp = int(p.get("passesmade", 0))
                motm = str(p.get("man_of_the_match", "0")) == "1"
                rating = float(p.get("rating", "6.0") or "6.0")
                pos = p.get("pos", "midfielder").upper()

                pos_map = {
                    "GOALKEEPER": "GK", "DEFENDER": "CB", "MIDFIELDER": "CM",
                    "FORWARD": "ST", "STRIKER": "ST", "WING": "LW",
                }
                position = pos_map.get(pos, pos)

                match.player_stats[p.get("playername", f"Player_{pid}")] = EAPlayerMatch(
                    name=p.get("playername", f"Player_{pid}"),
                    position=position,
                    goals=int(p.get("goals", 0)),
                    assists=int(p.get("assists", 0)),
                    shots=int(p.get("shots", 0)),
                    shots_on_target=int(p.get("shots", 0)),
                    passes_attempted=passes_att,
                    passes_completed=passes_comp,
                    key_passes=int(p.get("assists", 0)) * 2,
                    tackles=int(p.get("tacklesmade", 0)),
                    tackles_attempted=int(p.get("tackleattempts", 0)),
                    interceptions=int(p.get("interceptions", 0)),
                    possession_losses=passes_att - passes_comp,
                    dribbles_attempted=0,
                    dribbles_completed=0,
                    fouls=0,
                    yellow_cards=int(p.get("yellowcards", 0)),
                    red_cards=int(p.get("redcards", 0)),
                    rating=rating,
                    motm=motm,
                    minutes_played=minutes,
                    saves=int(p.get("saves", 0)),
                    clean_sheets_gk=int(p.get("cleansheetsgk", 0)),
                    own_goals=int(p.get("owngoals", 0)),
                    longshots=int(p.get("longshots", 0)),
                    chances_created=int(p.get("chancescreated", 0)),
                )

            return match
        except Exception as e:
            logger.error("Parse match error: %s", e)
            return None

    def close(self):
        self._client.close()


def get_ea_api(club_id: str, platform: str = "common-gen5") -> EAProClubsAPI:
    return EAProClubsAPI(club_id, platform)
