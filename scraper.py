"""
Rachad L3ERGONI Bot - EA FC26 Pro Clubs LIVE API Scraper
Primary: Direct EA API (httpx) | Fallback: Playwright browser scraping
"""

import os
import json
import asyncio
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
import httpx
from dataclasses import asdict

from stats_engine import MatchResult, PlayerMatchStats, StatsEngine


class ProClubsScraper:
    """Live scraper for EA FC26 Pro Clubs - API + Playwright fallback"""

    BASE_URL = "https://proclubs.ea.com/ea_fc/clubs/"

    def __init__(self, club_id: str = None, platform: str = "common-gen5"):
        self.club_id = club_id or os.getenv("CLUB_ID", "")
        self.platform = platform or os.getenv("PLATFORM", "common-gen5")
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        self._last_match_id = None
        self._playwright_available = False
        self._browser = None
        self._page = None

    async def _init_playwright(self):
        """Initialize Playwright browser as fallback"""
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
            self._page = await self._browser.new_page()
            self._playwright_available = True
            print("[Scraper] Playwright fallback ready")
        except Exception as e:
            print(f"[Scraper] Playwright not available: {e}")
            self._playwright_available = False

    async def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make authenticated GET request to EA API"""
        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[EA API Error] {endpoint}: {e}")
            return {}

    async def get_club_info(self) -> dict:
        return await self._get("getClubInfo", {"platform": self.platform, "clubId": self.club_id})

    async def get_club_stats(self) -> dict:
        return await self._get("getClubStats", {"platform": self.platform, "clubId": self.club_id})

    async def get_recent_matches(self, match_type: str = "gameType9", count: int = 20) -> List[dict]:
        data = await self._get("matchHistory", {
            "platform": self.platform,
            "clubIds": self.club_id,
            "matchType": match_type
        })
        matches = data if isinstance(data, list) else data.get("matches", [])
        return matches[:count]

    async def get_match_details(self, match_id: str) -> dict:
        return await self._get("match", {"platform": self.platform, "matchId": match_id})

    async def get_member_stats(self) -> List[dict]:
        data = await self._get("members", {"platform": self.platform, "clubId": self.club_id})
        return data if isinstance(data, list) else data.get("members", [])

    async def get_member_career_stats(self, player_name: str) -> dict:
        members = await self.get_member_stats()
        for member in members:
            if member.get("name", "").lower() == player_name.lower():
                return member
        return {}

    async def get_seasonal_stats(self) -> dict:
        return await self._get("seasonalStats", {"platform": self.platform, "clubId": self.club_id})

    # ==========================================
    # PLAYWRIGHT FALLBACK METHODS
    # ==========================================

    async def _playwright_fetch(self, url: str) -> dict:
        """Fetch data using Playwright browser"""
        if not self._playwright_available:
            await self._init_playwright()

        if not self._page:
            return {}

        try:
            await self._page.goto(url, wait_until="networkidle")
            content = await self._page.evaluate("() => document.body.innerText")
            return json.loads(content)
        except Exception as e:
            print(f"[Playwright Error] {url}: {e}")
            return {}

    async def get_recent_matches_playwright(self, count: int = 20) -> List[dict]:
        """Fallback: Get matches via Playwright browser"""
        url = f"{self.BASE_URL}matchHistory?platform={self.platform}&clubIds={self.club_id}&matchType=gameType9"
        data = await self._playwright_fetch(url)
        matches = data if isinstance(data, list) else data.get("matches", [])
        return matches[:count]

    async def get_match_details_playwright(self, match_id: str) -> dict:
        """Fallback: Get match details via Playwright"""
        url = f"{self.BASE_URL}match?platform={self.platform}&matchId={match_id}"
        return await self._playwright_fetch(url)

    # ==========================================
    # UNIFIED METHODS (Auto-fallback)
    # ==========================================

    async def get_recent_matches_unified(self, count: int = 20) -> List[dict]:
        """Get matches - tries API first, falls back to Playwright"""
        matches = await self.get_recent_matches(count=count)
        if not matches and self._playwright_available:
            print("[Scraper] API failed, trying Playwright fallback...")
            matches = await self.get_recent_matches_playwright(count=count)
        return matches

    async def get_match_details_unified(self, match_id: str) -> dict:
        """Get match details - tries API first, falls back to Playwright"""
        details = await self.get_match_details(match_id)
        if not details and self._playwright_available:
            print("[Scraper] API failed, trying Playwright fallback...")
            details = await self.get_match_details_playwright(match_id)
        return details

    def parse_match_data(self, match_data: dict) -> MatchResult:
        """Parse raw EA API data into MatchResult"""
        match_id = match_data.get("matchId", match_data.get("match_id", ""))

        clubs = match_data.get("clubs", {})
        our_club = None
        opponent_club = None
        opponent_id = None

        for club_id, club_info in clubs.items():
            if str(club_id) == str(self.club_id):
                our_club = club_info
            else:
                opponent_club = club_info
                opponent_id = club_id

        if not our_club:
            club_ids = list(clubs.keys())
            if club_ids:
                our_club = clubs[club_ids[0]]
            if len(club_ids) > 1:
                opponent_club = clubs[club_ids[1]]
                opponent_id = club_ids[1]

        players_data = match_data.get("players", {})
        player_stats = {}

        for club_id, players in players_data.items():
            if str(club_id) == str(self.club_id):
                for player in players:
                    name = player.get("playername", player.get("name", "Unknown"))
                    stats = player.get("stats", {})

                    def safe_int(val, default=0):
                        if val is None: return default
                        try: return int(val)
                        except: return default

                    def safe_float(val, default=0.0):
                        if val is None: return default
                        try: return float(val)
                        except: return default

                    player_stats[name] = PlayerMatchStats(
                        name=name,
                        position=player.get("position", "ST"),
                        goals=safe_int(stats.get("goals")),
                        assists=safe_int(stats.get("assists")),
                        shots=safe_int(stats.get("shots")),
                        shots_on_target=safe_int(stats.get("shotattempts")),
                        passes_attempted=safe_int(stats.get("passattempts")),
                        passes_completed=safe_int(stats.get("passesmade")),
                        key_passes=safe_int(stats.get("keypasses")),
                        tackles=safe_int(stats.get("tacklesmade")),
                        interceptions=safe_int(stats.get("interceptions")),
                        possession_losses=safe_int(stats.get("possessionlost")),
                        dribbles_attempted=safe_int(stats.get("dribbles")),
                        dribbles_completed=safe_int(stats.get("dribbleSuccess")),
                        fouls=safe_int(stats.get("fouls")),
                        yellow_cards=safe_int(stats.get("yellowcards")),
                        red_cards=safe_int(stats.get("redcards")),
                        rating=safe_float(stats.get("rating"), 6.0),
                        motm=str(stats.get("motm", "0")) == "1",
                        minutes_played=safe_int(stats.get("minutesPlayed"), 90),
                        distance_covered=safe_float(stats.get("distance")),
                        sprint_speed=safe_float(stats.get("sprintSpeed"))
                    )

        our_stats = our_club.get("gameStats", {}) if our_club else {}
        opp_stats = opponent_club.get("gameStats", {}) if opponent_club else {}

        opp_name = "Unknown"
        if opponent_club:
            opp_details = opponent_club.get("details", {})
            opp_name = opp_details.get("name", opp_details.get("clubName", "Unknown"))

        match_result = MatchResult(
            match_id=match_id,
            date=match_data.get("timestamp", datetime.now().isoformat()),
            opponent=opp_name,
            team_goals=safe_int(our_stats.get("goals")),
            opponent_goals=safe_int(opp_stats.get("goals")),
            team_possession=safe_float(our_stats.get("possession"), 50.0),
            opponent_possession=safe_float(opp_stats.get("possession"), 50.0),
            team_shots=safe_int(our_stats.get("shots")),
            opponent_shots=safe_int(opp_stats.get("shots")),
            team_shots_on_target=safe_int(our_stats.get("shotattempts")),
            opponent_shots_on_target=safe_int(opp_stats.get("shotattempts")),
            team_passes=safe_int(our_stats.get("passesmade")),
            opponent_passes=safe_int(opp_stats.get("passesmade")),
            team_tackles=safe_int(our_stats.get("tacklesmade")),
            opponent_tackles=safe_int(opp_stats.get("tacklesmade")),
            team_corners=safe_int(our_stats.get("corners")),
            opponent_corners=safe_int(opp_stats.get("corners")),
            team_fouls=safe_int(our_stats.get("fouls")),
            opponent_fouls=safe_int(opp_stats.get("fouls")),
            player_stats=player_stats
        )

        return match_result

    async def check_new_match(self) -> Optional[MatchResult]:
        """Check if there's a new match since last check"""
        matches = await self.get_recent_matches_unified(count=1)
        if not matches:
            return None

        latest = matches[0]
        match_id = latest.get("matchId", latest.get("match_id", ""))

        if match_id and match_id != self._last_match_id:
            self._last_match_id = match_id
            details = await self.get_match_details_unified(match_id)
            if details:
                return self.parse_match_data(details)

        return None

    async def sync_recent_matches(self, stats_engine: StatsEngine, count: int = 10) -> int:
        """Sync recent matches to local stats engine"""
        matches = await self.get_recent_matches_unified(count=count)
        added = 0

        for match_summary in matches:
            match_id = match_summary.get("matchId", match_summary.get("match_id", ""))
            if not any(m.match_id == match_id for m in stats_engine.matches):
                match_data = await self.get_match_details_unified(match_id)
                if match_data:
                    try:
                        match_result = self.parse_match_data(match_data)
                        stats_engine.add_match(match_result)
                        added += 1
                    except Exception as e:
                        print(f"[Parse Error] Match {match_id}: {e}")

        if added > 0:
            print(f"[Sync] Added {added} new matches")

        return added

    async def close(self):
        """Close HTTP client and browser"""
        await self.client.aclose()
        if self._browser:
            await self._browser.close()
        if hasattr(self, '_playwright'):
            await self._playwright.stop()


_scraper = None

def get_scraper(club_id: str = None, platform: str = "common-gen5") -> ProClubsScraper:
    global _scraper
    if _scraper is None:
        _scraper = ProClubsScraper(club_id, platform)
    return _scraper
