"""
Rachad L3ERGONI Bot - EA FC26 API Scraper v4
Based on fc-clubs-api by carlos-menezes
Direct EA API calls with browser headers + Playwright fallback
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
import httpx


class FC26Scraper:
    """
    EA FC26 Pro Clubs API Scraper
    Uses the same endpoints as fc-clubs-api with proper browser headers
    """

    BASE_URL = "https://proclubs.ea.com/fc26/api"

    # Match types from EA API
    MATCH_TYPES = {
        "gameType9": "league",
        "gameType13": "playoff", 
        "gameType5": "friendly"
    }

    def __init__(self, club_id: str, platform: str = "common-gen5"):
        self.club_id = str(club_id)
        self.platform = platform

        # Browser headers that bypass EA's blocking
        self.headers = {
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
            "Cache-Control": "no-cache",
        }

        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers=self.headers,
            http2=True,  # HTTP/2 helps bypass some detection
        )

        self.playwright_available = False
        try:
            from playwright.async_api import async_playwright
            self.playwright_available = True
        except ImportError:
            pass

    async def _get(self, endpoint: str, params: Dict = None) -> Optional[Any]:
        """Make API request with retry logic"""
        url = f"{self.BASE_URL}/{endpoint}"
        params = params or {}
        params["platform"] = self.platform

        # Add clubId only if not already in params (some endpoints use different param names)
        if "clubId" not in params and "clubIds" not in params:
            params["clubId"] = self.club_id

        try:
            response = await self.client.get(url, params=params)

            if response.status_code == 200:
                return response.json()
            elif response.status_code in [403, 429, 503]:
                print(f"[API] Blocked ({response.status_code}), trying Playwright fallback...")
                return await self._get_playwright(endpoint, params)
            else:
                print(f"[API] HTTP {response.status_code} from {endpoint}")
                return None

        except httpx.TimeoutException:
            print(f"[API] Timeout on {endpoint}, trying Playwright fallback...")
            return await self._get_playwright(endpoint, params)
        except Exception as e:
            print(f"[API] Error on {endpoint}: {e}")
            return None

    async def _get_playwright(self, endpoint: str, params: Dict) -> Optional[Any]:
        """Playwright fallback for blocked requests"""
        if not self.playwright_available:
            return None

        url = f"{self.BASE_URL}/{endpoint}"
        query = "&".join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{url}?{query}"

        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent=self.headers["User-Agent"],
                    extra_http_headers={
                        "Accept": self.headers["Accept"],
                        "Accept-Language": self.headers["Accept-Language"],
                        "Origin": self.headers["Origin"],
                        "Referer": self.headers["Referer"],
                    }
                )
                page = await context.new_page()

                response = await page.goto(full_url, wait_until="networkidle", timeout=30000)

                if response and response.status == 200:
                    text = await page.inner_text("body")
                    try:
                        data = json.loads(text)
                        await browser.close()
                        return data
                    except:
                        pre = await page.query_selector("pre")
                        if pre:
                            text = await pre.inner_text()
                            data = json.loads(text)
                            await browser.close()
                            return data
                        await browser.close()
                        return None
                else:
                    await browser.close()
                    return None
        except Exception as e:
            print(f"[Playwright] Error: {e}")
            return None

    # === EA API ENDPOINTS (from fc-clubs-api) ===

    async def search_club(self, club_name: str) -> Optional[List[Dict]]:
        """Search for club by name - returns list of matching clubs"""
        data = await self._get("clubs/search", {"clubName": club_name})
        if data and isinstance(data, list):
            return data
        return None

    async def get_club_info(self) -> Optional[Dict]:
        """Get club basic info"""
        return await self._get("club/info")

    async def get_overall_stats(self) -> Optional[List[Dict]]:
        """Get club overall stats (wins, losses, draws, etc.)"""
        return await self._get("clubs/overallStats", {"clubIds": self.club_id})

    async def get_member_career_stats(self) -> Optional[List[Dict]]:
        """Get all members' career stats (all-time)"""
        return await self._get("clubs/memberCareerStats", {"clubId": self.club_id})

    async def get_member_stats(self) -> Optional[List[Dict]]:
        """Get all members' current season stats"""
        return await self._get("clubs/memberStats", {"clubId": self.club_id})

    async def get_match_history(self, match_type: str = "gameType9") -> List[Dict]:
        """Get match history for a specific match type"""
        data = await self._get("club/matchHistory", {"matchType": match_type})
        if not data:
            return []
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return data.get("raw", []) or data.get("matches", []) or []
        return []

    async def get_matches_stats(self) -> Optional[List[Dict]]:
        """Get detailed match stats (from fc-clubs-api matchesStats endpoint)"""
        return await self._get("clubs/matches", {"clubId": self.club_id})

    async def get_all_matches(self, count: int = 10) -> List[Dict]:
        """Get matches from all types combined"""
        all_matches = []

        for match_type in self.MATCH_TYPES.keys():
            matches = await self.get_match_history(match_type)
            for match in matches:
                match["_matchType"] = match_type
                match["_matchTypeName"] = self.MATCH_TYPES[match_type]
                all_matches.append(match)

        # Sort by timestamp (newest first)
        all_matches.sort(key=lambda x: int(x.get("timestamp", x.get("match_timestamp", 0))), reverse=True)
        return all_matches[:count]

    def _parse_match(self, raw_match: Dict) -> Optional[Dict]:
        """Convert raw EA match to bot format"""
        try:
            # Handle both old and new API formats
            match_id = raw_match.get("matchId", raw_match.get("match_id", f"ea_{datetime.now().timestamp()}"))
            timestamp = int(raw_match.get("timestamp", raw_match.get("match_timestamp", 0)))
            match_time = datetime.fromtimestamp(timestamp).isoformat() if timestamp else datetime.now().isoformat()

            # Clubs data
            clubs = raw_match.get("clubs", {})
            teams = raw_match.get("teams", {})

            # Use whichever format is present
            club_data = clubs if clubs else teams

            our_club_id = str(self.club_id)
            opponent_club_id = None
            opponent_name = "Unknown"

            for cid, cdata in club_data.items():
                if str(cid) != our_club_id:
                    opponent_club_id = cid
                    opponent_name = cdata.get("name", "Unknown")
                    break

            our_data = club_data.get(our_club_id, {})
            opp_data = club_data.get(str(opponent_club_id), {}) if opponent_club_id else {}

            team_goals = int(our_data.get("goals", 0))
            opponent_goals = int(opp_data.get("goals", 0)) if opponent_club_id else 0

            result = "win" if team_goals > opponent_goals else "loss" if team_goals < opponent_goals else "draw"

            # Player stats
            player_stats = {}
            players = raw_match.get("players", {})
            our_players = players.get(our_club_id, {})

            for player_id, p_data in our_players.items():
                player_name = p_data.get("playername", "Unknown")
                clean_name = player_name.lower().strip()

                passes_attempted = int(p_data.get("passattempts", 0))
                passes_made = int(p_data.get("passesmade", 0))

                player_stats[clean_name] = {
                    "goals": int(p_data.get("goals", 0)),
                    "assists": int(p_data.get("assists", 0)),
                    "shots": int(p_data.get("shots", 0)),
                    "passes_attempted": passes_attempted,
                    "passes_made": passes_made,
                    "pass_accuracy": round((passes_made / max(passes_attempted, 1)) * 100, 1),
                    "key_passes": int(p_data.get("key_passes", 0)),
                    "tackles": int(p_data.get("tacklesmade", p_data.get("tackles", 0))),
                    "tackle_attempts": int(p_data.get("tackleattempts", 0)),
                    "interceptions": int(p_data.get("interceptions", 0)),
                    "possession_losses": int(p_data.get("possession_losses", passes_attempted - passes_made)),
                    "dribbles_attempted": int(p_data.get("dribbleattempts", p_data.get("dribbles_attempted", 0))),
                    "dribbles_completed": int(p_data.get("dribbles_completed", 0)),
                    "fouls": int(p_data.get("fouls", 0)),
                    "yellow_cards": int(p_data.get("yellowcards", p_data.get("yellow_cards", 0))),
                    "red_cards": int(p_data.get("redcards", p_data.get("red_cards", 0))),
                    "rating": float(p_data.get("rating", 6.0)),
                    "motm": str(p_data.get("man_of_the_match", "0")).lower() in ["1", "true", "yes"],
                    "position": p_data.get("pos", "unknown"),
                    "minutes_played": int(int(p_data.get("secondsPlayed", 7200)) / 60),
                    "saves": int(p_data.get("saves", 0)),
                    "goals_conceded": int(p_data.get("goalsconceded", 0)),
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
                "match_type_name": raw_match.get("_matchTypeName", "league"),
                "player_stats": player_stats,
            }

        except Exception as e:
            print(f"[Parse Error] {e}")
            import traceback
            traceback.print_exc()
            return None

    async def check_new_match(self) -> Optional[Dict]:
        """Check for most recent match"""
        matches = await self.get_all_matches(count=1)
        if matches:
            return self._parse_match(matches[0])
        return None

    async def sync_recent_matches(self, stats_engine, count: int = 10) -> int:
        """Sync matches to stats engine"""
        raw_matches = await self.get_all_matches(count=count)
        added = 0

        for raw in raw_matches:
            parsed = self._parse_match(raw)
            if parsed:
                if not stats_engine.match_exists(parsed["match_id"]):
                    stats_engine.add_match(parsed)
                    added += 1
                    print(f"[Sync] Added: {parsed['match_time']} vs {parsed['opponent']} ({parsed['result']})")

        if added == 0:
            print(f"[Sync] No new matches (checked {len(raw_matches)})")

        return added

    async def close(self):
        """Close client"""
        await self.client.aclose()


def get_scraper(club_id: str, platform: str = "common-gen5") -> FC26Scraper:
    return FC26Scraper(club_id, platform)


# === TEST ===
if __name__ == "__main__":
    async def test():
        scraper = FC26Scraper(club_id="1427607", platform="common-gen5")

        print("Testing EA API with fc-clubs-api approach...")

        # Test 1: Club info
        print("\n1. Club Info:")
        info = await scraper.get_club_info()
        print(json.dumps(info, indent=2) if info else "Failed")

        # Test 2: Overall stats
        print("\n2. Overall Stats:")
        stats = await scraper.get_overall_stats()
        print(json.dumps(stats, indent=2) if stats else "Failed")

        # Test 3: Member stats
        print("\n3. Member Stats:")
        members = await scraper.get_member_stats()
        print(f"Found {len(members) if members else 0} members")
        if members:
            print(json.dumps(members[0], indent=2))

        # Test 4: Match history
        print("\n4. Match History:")
        matches = await scraper.get_all_matches(count=5)
        print(f"Found {len(matches)} matches")
        for m in matches[:3]:
            parsed = scraper._parse_match(m)
            if parsed:
                print(f"  {parsed['match_time']}: {parsed['team_goals']}-{parsed['opponent_goals']} vs {parsed['opponent']}")

        await scraper.close()

    asyncio.run(test())
