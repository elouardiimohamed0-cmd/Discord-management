from __future__ import annotations

import asyncio
import gzip
import json
import os
from datetime import datetime
from typing import Optional

import httpx

from src.core.config import Settings
from src.core.logging import get_logger
from src.data.repositories import ClubRepository
from src.domain.models import ClubSnapshot, Match, PlayerMatchStats
from src.scraper.browser import BrowserManager
from src.scraper.cache import FileCache
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


class ProClubsTrackerClient:
    """API-first scraper with browser fallback — same method as June 24 version."""

    def __init__(
        self,
        settings: Settings,
        squad: SquadRegistry,
        repository: ClubRepository,
        headless: bool = True,
    ):
        self.settings = settings
        self.squad = squad
        self.repo = repository
        self.cache = FileCache(settings.cache_dir, ttl_seconds=120)
        self.browser = BrowserManager(headless=headless)
        self._http_client: Optional[httpx.AsyncClient] = None
        self._initialized = False
        self._init_error: Optional[str] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                headers=HEADERS,
                follow_redirects=True,
                timeout=httpx.Timeout(15.0, connect=5.0),
            )
        return self._http_client

    async def prewarm(self) -> None:
        """Pre-warm browser in background (for fallback)."""
        try:
            await self.browser.start()
            self._initialized = True
            logger.info("Browser pre-warmed")
        except Exception as e:
            logger.warning("Browser prewarm failed: %s", e)

    async def refresh(self, force: bool = False, source: str = "scheduled") -> ClubSnapshot:
        """Fetch club data — API first, browser fallback."""
        url = self.settings.pct_club_url

        # Check cache
        if not force:
            cached = self.cache.get(url)
            if cached:
                logger.info("Using cached snapshot")
                return self._parse_api_response(cached)

        # Try API first (fast, no browser needed)
        api_data = await self._fetch_api()
        if api_data:
            snapshot = self._parse_api_response(api_data)
            self.cache.set(url, api_data)
            self.repo.save_snapshot(snapshot, raw=api_data)
            self.repo.log_scrape(source=source, success=True, request_count=1)
            return snapshot

        # Fallback to browser
        logger.warning("API failed, falling back to browser...")
        snapshot = await self._scrape_with_browser(url)
        self.cache.set(url, snapshot.model_dump())
        self.repo.save_snapshot(snapshot)
        self.repo.log_scrape(source=source, success=True, request_count=2)
        return snapshot

    async def _fetch_api(self) -> Optional[dict]:
        """Direct API call — same as June 24 version."""
        client = await self._get_http_client()
        for attempt in range(3):
            try:
                logger.info("[HTTP] GET %s (attempt %d)", PCT_API_URL, attempt + 1)
                resp = await client.get(PCT_API_URL)
                logger.info("[HTTP] Status: %d", resp.status_code)

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 5 * (attempt + 1)))
                    logger.warning("Rate limited, waiting %ds", retry_after)
                    await asyncio.sleep(retry_after)
                    continue

                if resp.status_code == 403:
                    logger.warning("[HTTP] 403 — possible Cloudflare")
                    return None

                if resp.status_code != 200:
                    logger.warning("[HTTP] Status %d", resp.status_code)
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
                    logger.error("[HTTP] Response not dict: %s", type(data))
                    return None

                # Validate it looks like PCT data
                if "clubInfoData" not in data and "matches" not in data:
                    logger.warning("[HTTP] Response missing expected keys")
                    return None

                logger.info("[HTTP] Success — keys: %s", list(data.keys()))
                return data

            except httpx.TimeoutException:
                logger.warning("Timeout on attempt %d", attempt + 1)
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error("[HTTP] Error: %s", e)
                await asyncio.sleep(2 ** attempt)

        return None

    def _parse_api_response(self, data: dict) -> ClubSnapshot:
        """Parse ProClubsTracker API response into ClubSnapshot."""
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

    async def _scrape_with_browser(self, url: str, max_retries: int = 3) -> ClubSnapshot:
        """Browser fallback — same as before but using parser."""
        from src.scraper.parser import ProClubsTrackerParser
        parser = ProClubsTrackerParser()

        last_error = ""
        for attempt in range(max_retries):
            page = None
            try:
                await self.browser.start()
                page = await self.browser.new_page()
                logger.info("Browser scraping %s (attempt %d/%d)", url, attempt + 1, max_retries)

                response = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(2)

                raw_json = await page.evaluate("""() => {
                    if (window.__INITIAL_STATE__) return window.__INITIAL_STATE__;
                    if (window.__DATA__) return window.__DATA__;
                    return null;
                }""")

                if raw_json:
                    html = await page.content()
                    return parser.parse_club_page(html, url, raw_json)

                html = await page.content()
                return parser.parse_club_page(html, url, None)

            except Exception as e:
                last_error = str(e)
                logger.warning("Browser attempt %d failed: %s", attempt + 1, e)
                await asyncio.sleep(2 ** attempt)
            finally:
                if page:
                    try:
                        await page.close()
                    except Exception:
                        pass

        raise Exception(f"Browser failed after {max_retries}: {last_error}")

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

    async def close(self) -> None:
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
        await self.browser.close()
        self._initialized = False
        self._init_error = None
