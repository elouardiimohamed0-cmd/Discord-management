# src/scraper/api_client.py
from __future__ import annotations

import asyncio
import gzip
import json
import os
import time
from datetime import datetime
from typing import Optional

import httpx

from src.core.config import Settings
from src.core.logging import get_logger
from src.data.repositories import ClubRepository
from src.domain.models import ClubSnapshot, Match, PlayerMatchStats
from src.scraper.parser import ProClubsTrackerParser
from src.squad.registry import SquadRegistry

logger = get_logger(__name__)

CLUB_ID = os.environ.get("CLUB_ID", "1427607")
PLATFORM = os.environ.get("PCT_PLATFORM", "common-gen5")
PCT_API_URL = f"https://proclubstracker.com/api/clubs/{CLUB_ID}?platform={PLATFORM}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html,*/*",
    "Referer": "https://proclubstracker.com/",
    "Accept-Language": "en-US,en;q=0.9",
    "DNT": "1",
    "Connection": "keep-alive",
}


class APIClient:
    """Direct API client for ProClubsTracker — fast, no browser needed."""

    def __init__(self, settings: Settings, squad: SquadRegistry, repository: ClubRepository):
        self.settings = settings
        self.squad = squad
        self.repo = repository
        self._http_client: Optional[httpx.AsyncClient] = None
        self._cache_time = 0
        self._cache_ttl = 300  # 5 minutes
        self._mem_cache: Optional[dict] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                headers=HEADERS,
                follow_redirects=True,
                timeout=httpx.Timeout(15.0, connect=5.0),
            )
        return self._http_client

    async def refresh(self, force: bool = False, source: str = "scheduled") -> ClubSnapshot:
        # Check memory cache
        now = time.time()
        if not force and self._mem_cache and (now - self._cache_time) < self._cache_ttl:
            logger.info("Using memory cache")
            return self._parse_api_response(self._mem_cache)

        # Fetch from API
        data = await self._fetch_api()
        if not data:
            raise Exception("API fetch failed")

        self._mem_cache = data
        self._cache_time = now

        snapshot = self._parse_api_response(data)
        self.repo.save_snapshot(snapshot)
        self.repo.log_scrape(source=source, success=True, request_count=1)
        return snapshot

    async def _fetch_api(self) -> Optional[dict]:
        client = await self._get_client()
        for attempt in range(3):
            try:
                logger.info("Fetching API: %s (attempt %d)", PCT_API_URL, attempt + 1)
                resp = await client.get(PCT_API_URL)
                logger.info("API status: %d", resp.status_code)

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 5 * (attempt + 1)))
                    logger.warning("Rate limited, waiting %ds", retry_after)
                    await asyncio.sleep(retry_after)
                    continue

                if resp.status_code != 200:
                    logger.warning("HTTP %d", resp.status_code)
                    return None

                raw = resp.content

                # Handle gzip
                if raw[:2] == b'\x1f\x8b':
                    try:
                        raw = gzip.decompress(raw)
                    except Exception:
                        pass

                # Parse JSON
                try:
                    data = json.loads(raw)
                except Exception:
                    text = raw.decode("utf-8", errors="replace")
                    data = json.loads(text)

                if not isinstance(data, dict):
                    logger.error("Response is not a dict: %s", type(data))
                    return None

                logger.info("API success, keys: %s", list(data.keys()))
                return data

            except httpx.TimeoutException:
                logger.warning("Timeout on attempt %d", attempt + 1)
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error("Fetch error: %s", e)
                await asyncio.sleep(2 ** attempt)

        return None

    def _parse_api_response(self, data: dict) -> ClubSnapshot:
        """Parse the ProClubsTracker API response into ClubSnapshot."""
        info = data.get("clubInfoData", {})
        club_info = info.get(str(CLUB_ID)) or next(iter(info.values()), {})
        overall = data.get("overallStats", {})

        # Parse matches
        raw_matches = data.get("matches", {})
        all_matches = (
            (raw_matches.get("league", []) or [])
            + (raw_matches.get("playoff", []) or [])
            + (raw_matches.get("friendly", []) or [])
        )

        matches = []
        for rm in all_matches[:30]:
            match = self._parse_match(rm)
            if match:
                matches.append(match)

        return ClubSnapshot(
            club_name=club_info.get("name") or club_info.get("clubName") or "Rachad L3ERGONI",
            division=self._int(overall.get("bestDivision") or club_info.get("divisionId"), 6),
            skill_rating=self._int(overall.get("skillRating") or club_info.get("skillRating"), 0),
            wins=self._int(overall.get("wins"), 0),
            draws=self._int(overall.get("ties"), 0),
            losses=self._int(overall.get("losses"), 0),
            goals_scored=self._int(overall.get("goals"), 0),
            goals_conceded=self._int(overall.get("goalsAgainst"), 0),
            matches=matches,
            scraped_at=datetime.now(),
        )

    def _parse_match(self, raw: dict) -> Optional[Match]:
        try:
            our_id = str(CLUB_ID)
            clubs = raw.get("clubs", {})
            ours, opp = None, None
            for cid, c in clubs.items():
                if str(cid) == our_id:
                    ours = c
                else:
                    opp = c
            if not ours:
                return None

            gf = self._int(ours.get("goals"), 0)
            ga = self._int(ours.get("goalsAgainst"), 0)
            result = "W" if gf > ga else "L" if gf < ga else "D"

            ts = raw.get("timestamp")
            date = datetime.now()
            if ts:
                try:
                    date = datetime.fromtimestamp(int(ts))
                except Exception:
                    pass

            # Parse players
            players = []
            our_players = raw.get("players", {}).get(our_id, {})
            for pid, p in our_players.items():
                seconds = self._int(p.get("secondsPlayed"), 0)
                passes_att = self._int(p.get("passattempts"), 0)
                passes_comp = self._int(p.get("passesmade"), 0)

                stats = PlayerMatchStats(
                    ea_id=str(pid),
                    display_name=p.get("playername", "Unknown"),
                    position=p.get("pos", ""),
                    rating=self._float(p.get("rating"), 0.0),
                    minutes=seconds // 60,
                    goals=self._int(p.get("goals"), 0),
                    assists=self._int(p.get("assists"), 0),
                    shots=self._int(p.get("shots"), 0),
                    passes_attempted=passes_att,
                    passes_completed=passes_comp,
                    tackles=self._int(p.get("tacklesmade"), 0),
                    saves=self._int(p.get("saves"), 0),
                    possession_losses=max(0, passes_att - passes_comp),
                    red_cards=self._int(p.get("redcards"), 0),
                    clean_sheets=self._int(p.get("cleansheetsany"), 0),
                    raw=p,
                )
                if stats.played:
                    players.append(stats)

            return Match(
                match_id=str(raw.get("matchId", "")),
                date=date,
                opponent=opp.get("details", {}).get("name", "Unknown") if opp else "Unknown",
                score_for=gf,
                score_against=ga,
                result=result,
                players=players,
                raw=raw,
            )
        except Exception as e:
            logger.warning("Parse match error: %s", e)
            return None

    def _int(self, v, d=0):
        try:
            return int(float(str(v))) if v is not None else d
        except Exception:
            return d

    def _float(self, v, d=0.0):
        try:
            return float(str(v)) if v is not None else d
        except Exception:
            return d

    async def close(self):
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
