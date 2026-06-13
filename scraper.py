"""
Rachad L3ERGONI Bot - EA FC26 Scraper v2
Dual-engine: httpx (fast) + Playwright (fallback for blocked API)
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
import httpx


class FC26Scraper:
    BASE_URL = "https://proclubs.ea.com/fc26/api"

    def __init__(self, club_id: str, platform: str = "common-gen5"):
        self.club_id = str(club_id)
        self.platform = platform
        self.client = httpx.AsyncClient(
            timeout=30.0, 
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Origin": "https://www.ea.com",
                "Referer": "https://www.ea.com/",
                "Connection": "keep-alive",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
            }
        )
        self.playwright_available = False
        try:
            from playwright.async_api import async_playwright
            self.playwright_available = True
        except ImportError:
            print("[Scraper] Playwright not installed, browser fallback unavailable")

    async def _get_httpx(self, endpoint: str, params: Dict = None) -> Optional[Any]:
        """Try httpx first (fast)"""
        url = f"{self.BASE_URL}/{endpoint}"
        params = params or {}
        params["platform"] = self.platform
        params["clubId"] = self.club_id

        try:
            response = await self.client.get(url, params=params)
            if response.status_code == 200:
                return response.json()
            elif response.status_code in [403, 429, 503]:
                print(f"[Scraper] API blocked ({response.status_code}), will try Playwright fallback")
                return None
            else:
                print(f"[Scraper] HTTP {response.status_code} from {endpoint}")
                return None
        except httpx.TimeoutException:
            print(f"[Scraper] Timeout on {endpoint}, will try Playwright fallback")
            return None
        except Exception as e:
            print(f"[Scraper] Error on {endpoint}: {e}")
            return None

    async def _get_playwright(self, endpoint: str, params: Dict = None) -> Optional[Any]:
        """Playwright fallback when httpx is blocked"""
        if not self.playwright_available:
            return None

        url = f"{self.BASE_URL}/{endpoint}"
        params = params or {}
        params["platform"] = self.platform
        params["clubId"] = self.club_id

        # Build full URL with params
        query = "&".join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{url}?{query}"

        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                    extra_http_headers={
                        "Accept": "application/json, text/plain, */*",
                        "Accept-Language": "en-US,en;q=0.9",
                        "Origin": "https://www.ea.com",
                        "Referer": "https://www.ea.com/",
                    }
                )
                page = await context.new_page()

                # Navigate to API endpoint and extract JSON
                response = await page.goto(full_url, wait_until="networkidle", timeout=30000)

                if response and response.status == 200:
                    # Try to get JSON from page
                    content = await page.content()
                    # Clean up HTML wrapper if present
                    text = await page.inner_text("body")
                    try:
                        data = json.loads(text)
                        await browser.close()
                        return data
                    except json.JSONDecodeError:
                        # Maybe it's wrapped in <pre> tags
                        pre = await page.query_selector("pre")
                        if pre:
                            text = await pre.inner_text()
                            data = json.loads(text)
                            await browser.close()
                            return data
                        await browser.close()
                        return None
                else:
                    print(f"[Scraper] Playwright got status {response.status if response else 'none'}")
                    await browser.close()
                    return None
        except Exception as e:
            print(f"[Scraper] Playwright error: {e}")
            return None

    async def _get(self, endpoint: str, params: Dict = None) -> Optional[Any]:
        """Dual-engine: try httpx first, then Playwright fallback"""
        # Try httpx first
        data = await self._get_httpx(endpoint, params)
        if data is not None:
            return data

        # Fallback to Playwright
        print(f"[Scraper] Falling back to Playwright for {endpoint}")
        return await self._get_playwright(endpoint, params)

    async def get_club_info(self) -> Optional[Dict]:
        """Get club basic info"""
        return await self._get("club/info")

    async def get_club_stats(self) -> Optional[Dict]:
        """Get club seasonal stats"""
        return await self._get("club/stats")

    async def get_match_history(self, match_type: str = "gameType9") -> List[Dict]:
        """
        Get last 5 matches
        match_type: gameType9 (league), gameType13 (playoff), gameType5 (friendly)
        """
        data = await self._get("club/matchHistory", {"matchType": match_type})
        if not data:
            return []

        # EA returns list directly or wrapped in "raw"
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return data.get("raw", []) or data.get("matches", []) or []
        return []

    async def get_all_recent_matches(self, count: int = 10) -> List[Dict]:
        """Get recent matches from all match types combined"""
        all_matches = []

        for match_type in ["gameType9", "gameType13", "gameType5"]:
            matches = await self.get_match_history(match_type)
            for match in matches:
                match["_matchType"] = match_type
                all_matches.append(match)

        # Sort by timestamp (newest first)
        all_matches.sort(key=lambda x: int(x.get("timestamp", 0)), reverse=True)
        return all_matches[:count]

    def _parse_match(self, raw_match: Dict) -> Optional[Dict]:
        """Convert raw EA match data to bot format"""
        try:
            match_id = raw_match.get("matchId", raw_match.get("matchId", "unknown"))
            timestamp = int(raw_match.get("timestamp", 0))
            match_time = datetime.fromtimestamp(timestamp).isoformat()

            clubs = raw_match.get("clubs", {})
            players = raw_match.get("players", {})

            # Find our club and opponent
            our_club_id = str(self.club_id)
            opponent_club_id = None
            opponent_name = "Unknown"

            for cid, club_data in clubs.items():
                if str(cid) != our_club_id:
                    opponent_club_id = cid
                    opponent_name = club_data.get("name", "Unknown")
                    break

            our_club_data = clubs.get(our_club_id, {})
            opponent_club_data = clubs.get(str(opponent_club_id), {}) if opponent_club_id else {}

            team_goals = int(our_club_data.get("goals", 0))
            opponent_goals = int(opponent_club_data.get("goals", 0)) if opponent_club_id else 0

            result = "win" if team_goals > opponent_goals else "loss" if team_goals < opponent_goals else "draw"

            # Parse player stats
            player_stats = {}
            our_players = players.get(our_club_id, {})

            for player_id, p_data in our_players.items():
                player_name = p_data.get("playername", "Unknown")
                clean_name = player_name.lower().strip()

                passes_attempted = int(p_data.get("passattempts", 0))
                passes_made = int(p_data.get("passesmade", 0))
                pass_accuracy = (passes_made / max(passes_attempted, 1)) * 100

                player_stats[clean_name] = {
                    "goals": int(p_data.get("goals", 0)),
                    "assists": int(p_data.get("assists", 0)),
                    "shots": int(p_data.get("shots", 0)),
                    "passes_attempted": passes_attempted,
                    "passes_made": passes_made,
                    "pass_accuracy": round(pass_accuracy, 1),
                    "tackles": int(p_data.get("tacklesmade", 0)),
                    "tackle_attempts": int(p_data.get("tackleattempts", 0)),
                    "rating": float(p_data.get("rating", 6.0)),
                    "motm": str(p_data.get("man_of_the_match", "0")) == "1",
                    "red_cards": int(p_data.get("redcards", 0)),
                    "yellow_cards": int(p_data.get("yellowcards", 0)),
                    "seconds_played": int(p_data.get("secondsPlayed", 0)),
                    "position": p_data.get("pos", "unknown"),
                    "dribbles_attempted": int(p_data.get("dribbleattempts", 0)),
                    "fouls": int(p_data.get("fouls", 0)),
                    "interceptions": int(p_data.get("interceptions", 0)),
                    "possession_losses": int(p_data.get("possession_losses", p_data.get("passattempts", 0) - p_data.get("passesmade", 0))),
                }

            return {
                "match_id": str(match_id),
                "timestamp": timestamp,
                "match_time": match_time,
                "opponent": opponent_name,
                "team_goals": team_goals,
                "opponent_goals": opponent_goals,
                "result": result,
                "match_type": raw_match.get("_matchType", "gameType9"),
                "player_stats": player_stats,
            }
        except Exception as e:
            print(f"[Parse Error] {e}")
            return None

    async def check_new_match(self) -> Optional[Dict]:
        """Check if there's a new match"""
        matches = await self.get_all_recent_matches(count=1)
        if not matches:
            return None

        parsed = self._parse_match(matches[0])
        return parsed

    async def sync_recent_matches(self, stats_engine, count: int = 10) -> int:
        """
        Sync recent matches to stats engine
        Returns number of new matches added
        """
        raw_matches = await self.get_all_recent_matches(count=count)
        added = 0

        for raw in raw_matches:
            parsed = self._parse_match(raw)
            if parsed:
                if not stats_engine.match_exists(parsed["match_id"]):
                    stats_engine.add_match(parsed)
                    added += 1
                    print(f"[Sync] Added match: {parsed['match_time']} vs {parsed['opponent']} ({parsed['result']})")

        if added == 0:
            print(f"[Sync] No new matches found (checked {len(raw_matches)} recent)")

        return added

    async def close(self):
        """Close httpx client"""
        await self.client.aclose()


def get_scraper(club_id: str, platform: str = "common-gen5") -> FC26Scraper:
    return FC26Scraper(club_id, platform)
