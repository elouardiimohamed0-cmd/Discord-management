"""
Rachad L3ERGONI Bot - Hybrid Scraper v3
Primary: EA FC Pro Clubs API (direct, fast, official)
Fallback: ProClubsTracker.com (Playwright with proper waiting)
"""

import os
import json
import asyncio
import subprocess
import sys
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import httpx
import hashlib

EA_BASE = "https://proclubs.ea.com/api/fc"
PCT_BASE = "https://proclubstracker.com"


class EAFCAPIClient:
    """Direct client for EA's public Pro Clubs API. No browser needed."""

    def __init__(self, club_id: str, platform: str = "common-gen5"):
        self.club_id = str(club_id)
        self.platform = platform
        self._client: Optional[httpx.AsyncClient] = None
        self._club_info: Optional[dict] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                    "Accept": "application/json",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Origin": "https://www.ea.com",
                    "Referer": "https://www.ea.com/",
                }
            )
        return self._client

    async def _api_get(self, endpoint: str, params: dict) -> Optional[dict]:
        client = await self._get_client()
        url = f"{EA_BASE}/{endpoint}"
        for attempt in range(3):
            try:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 429:
                    await asyncio.sleep(2 ** attempt)
                else:
                    print(f"[EA API] {endpoint} -> HTTP {resp.status_code}")
                    return None
            except Exception as e:
                print(f"[EA API] {endpoint} attempt {attempt+1}: {e}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
        return None

    async def get_club_info(self) -> Optional[dict]:
        if self._club_info:
            return self._club_info
        data = await self._api_get("clubs/info", {"platform": self.platform, "clubIds": self.club_id})
        if data and isinstance(data, dict):
            self._club_info = data.get(self.club_id, data)
            return self._club_info
        return None

    async def get_matches(self, match_type: str = "gameType9", count: int = 20) -> List[dict]:
        data = await self._api_get("clubs/matches", {
            "matchType": match_type, "platform": self.platform,
            "clubIds": self.club_id, "maxResultCount": count
        })
        return data if isinstance(data, list) else []

    async def get_member_stats(self) -> List[dict]:
        data = await self._api_get("members/stats", {"platform": self.platform, "clubId": self.club_id})
        return data if isinstance(data, list) else []

    async def get_member_career_stats(self) -> List[dict]:
        data = await self._api_get("members/careerStats", {"platform": self.platform, "clubId": self.club_id})
        return data if isinstance(data, list) else []

    async def get_all_data(self, match_count: int = 20) -> Dict[str, Any]:
        club_info, matches, members, career = await asyncio.gather(
            self.get_club_info(), self.get_matches("gameType9", match_count),
            self.get_member_stats(), self.get_member_career_stats(),
            return_exceptions=True
        )
        return {
            "overview": club_info if isinstance(club_info, dict) else {},
            "matches": matches if isinstance(matches, list) else [],
            "players": members if isinstance(members, list) else [],
            "career": career if isinstance(career, list) else [],
            "timestamp": datetime.now().isoformat()
        }

    def _build_match_id(self, match: dict) -> str:
        ts = match.get("match_timestamp", "")
        mid = match.get("match_id", "")
        raw = f"{mid}_{ts}_{self.club_id}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _find_opponent_name(self, match: dict) -> str:
        teams = match.get("teams", {})
        for cid, team in teams.items():
            if str(cid) != str(self.club_id):
                return team.get("name", "Unknown")
        return "Unknown"

    def _load_squad(self) -> Dict[str, dict]:
        try:
            with open("squad.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def _find_squad_key(self, ea_name: str, squad_map: Dict[str, dict]) -> Optional[str]:
        ea_lower = ea_name.lower().strip()
        for key, info in squad_map.items():
            if info.get("name", "").lower().strip() == ea_lower: return key
            if info.get("psn", "").lower().strip() == ea_lower: return key
            if info.get("nickname", "").lower().strip() == ea_lower: return key
            name = info.get("name", "").lower().strip()
            nick = info.get("nickname", "").lower().strip()
            if name in ea_lower or ea_lower in name: return key
            if nick in ea_lower or ea_lower in nick: return key
        return None

    def _parse_ea_match(self, match: dict, squad_map: Dict[str, dict]) -> Optional[dict]:
        try:
            match_id = self._build_match_id(match)
            ts = match.get("match_timestamp", "")
            match_time = datetime.fromtimestamp(int(ts)).isoformat() if str(ts).isdigit() else datetime.now().isoformat()
            teams = match.get("teams", {})
            our_team = teams.get(self.club_id, {})
            opponent_name = self._find_opponent_name(match)
            team_goals = int(our_team.get("goals", 0))
            opponent_goals = int(our_team.get("goalsAgainst", 0))

            player_stats = {}
            all_players = match.get("players", {})
            our_players = all_players.get(self.club_id, {})

            for player_id, pstats in our_players.items():
                ea_name = pstats.get("playername", "Unknown")
                squad_key = self._find_squad_key(ea_name, squad_map)
                display_name = squad_key if squad_key else ea_name

                pos = pstats.get("pos", "midfielder").upper()
                position_map = {"goalkeeper": "GK", "defender": "CB", "midfielder": "CM", "forward": "ST", "striker": "ST", "wing": "LW"}
                position = position_map.get(pos.lower(), pos)

                pass_attempts = int(pstats.get("passattempts", 0))
                passes_made = int(pstats.get("passesmade", 0))
                pass_acc = round((passes_made / max(pass_attempts, 1)) * 100, 1)
                shots = int(pstats.get("shots", 0))
                motm = str(pstats.get("man_of_the_match", "0")) == "1"
                rating = float(pstats.get("rating", "6.0"))
                seconds = int(pstats.get("secondsPlayed", 0))
                minutes = seconds // 60

                player_stats[display_name] = {
                    "name": display_name, "position": position,
                    "goals": int(pstats.get("goals", 0)), "assists": int(pstats.get("assists", 0)),
                    "shots": shots, "shots_on_target": shots,
                    "passes_attempted": pass_attempts, "passes_completed": passes_made,
                    "pass_accuracy": pass_acc, "key_passes": int(pstats.get("assists", 0)) * 2,
                    "tackles": int(pstats.get("tacklesmade", 0)), "interceptions": 0,
                    "possession_losses": pass_attempts - passes_made,
                    "dribbles_attempted": 0, "dribbles_completed": 0,
                    "fouls": 0, "yellow_cards": int(pstats.get("yellowcards", 0)),
                    "red_cards": int(pstats.get("redcards", 0)), "rating": rating,
                    "motm": motm, "minutes_played": minutes,
                    "distance_covered": 0.0, "sprint_speed": 0.0
                }

            return {
                "match_id": match_id, "date": match_time, "opponent": opponent_name,
                "team_goals": team_goals, "opponent_goals": opponent_goals,
                "team_possession": 50.0, "opponent_possession": 50.0,
                "team_shots": team_goals * 3, "opponent_shots": opponent_goals * 3,
                "team_shots_on_target": team_goals * 2, "opponent_shots_on_target": opponent_goals * 2,
                "team_passes": sum(p.get("passes_attempted", 0) for p in player_stats.values()),
                "opponent_passes": 0,
                "team_tackles": sum(p.get("tackles", 0) for p in player_stats.values()),
                "opponent_tackles": 0, "team_corners": 0, "opponent_corners": 0,
                "team_fouls": 0, "opponent_fouls": 0, "match_type": "gameType9",
                "player_stats": player_stats
            }
        except Exception as e:
            print(f"[Parse Match Error] {e}")
            return None

    async def sync_to_stats_engine(self, stats_engine, count: int = 10) -> int:
        """Sync matches to stats engine. Loads squad.json internally."""
        squad = self._load_squad()
        matches = await self.get_matches("gameType9", count)
        added = 0
        for match in matches:
            parsed = self._parse_ea_match(match, squad)
            if parsed and not stats_engine.match_exists(parsed["match_id"]):
                stats_engine.add_match(parsed)
                added += 1
        print(f"[EA API] Synced {added} new matches")
        return added

    async def check_new_match(self) -> Optional[dict]:
        """Check for most recent match."""
        squad = self._load_squad()
        matches = await self.get_matches("gameType9", 1)
        if matches:
            return self._parse_ea_match(matches[0], squad)
        return None

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class ProClubsTrackerScraper(EAFCAPIClient):
    """
    Hybrid scraper: tries EA API first, falls back to ProClubsTracker Playwright scrape.
    Backward-compatible with the original bot.py calling conventions.
    """

    def __init__(self, club_id: str, platform: str = "common-gen5", division: str = "6"):
        super().__init__(club_id, platform)
        self.division = division
        self.club_url = f"{PCT_BASE}/club/{club_id}?platform={platform}&div={division}"
        self._playwright_available = None

    def _ensure_playwright(self) -> bool:
        if self._playwright_available is not None:
            return self._playwright_available
        try:
            import playwright
            self._playwright_available = True
            return True
        except ImportError:
            self._playwright_available = False
            return False

    def _install_browsers(self) -> bool:
        try:
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"],
                         capture_output=True, timeout=180)
            return True
        except:
            return False

    async def _scrape_pct_fallback(self) -> Dict[str, Any]:
        """Fallback: scrape ProClubsTracker with proper Playwright waiting."""
        if not self._ensure_playwright():
            print("[Fallback] Playwright not installed, cannot scrape ProClubsTracker")
            return {}

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return {}

        print(f"[Fallback] Scraping ProClubsTracker: {self.club_url}")
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
                )
                context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
                page = await context.new_page()

                # Navigate and wait for content to load
                await page.goto(self.club_url, wait_until="domcontentloaded", timeout=30000)

                # Wait for loading to finish - look for actual data or absence of loading text
                try:
                    await page.wait_for_selector("text=Loading club data...", state="detached", timeout=15000)
                except:
                    pass  # Loading text might not exist

                # Give extra time for JS to render
                await asyncio.sleep(3)

                # Try multiple selectors that might contain match data
                selectors = [
                    'table tbody tr',
                    '[class*="match"]',
                    '[class*="game"]',
                    'div:has-text("vs")',
                    'div:has-text("-")',
                ]

                all_matches = []
                all_players = []

                for selector in selectors:
                    try:
                        elements = await page.query_selector_all(selector)
                        for el in elements:
                            text = await el.inner_text()
                            text_lower = text.lower()
                            # Detect match rows by looking for score patterns or opponent names
                            if any(c in text for c in ["-", "vs", "win", "loss", "draw"]):
                                if any(c.isdigit() for c in text):
                                    cells = await el.query_selector_all('td, div[class*="cell"]')
                                    if cells:
                                        row_dict = {f"col_{i}": (await c.inner_text()).strip() for i, c in enumerate(cells)}
                                        all_matches.append(row_dict)
                            # Detect player rows
                            if any(w in text_lower for w in ["goals", "assists", "rating", "passes"]):
                                cells = await el.query_selector_all('td, div[class*="cell"]')
                                if cells:
                                    row_dict = {f"col_{i}": (await c.inner_text()).strip() for i, c in enumerate(cells)}
                                    all_players.append(row_dict)
                    except:
                        continue

                # Also try to extract from page text as last resort
                page_text = await page.content()

                await browser.close()

                print(f"[Fallback] Found {len(all_matches)} match rows, {len(all_players)} player rows")
                return {"matches": all_matches, "players": all_players, "source": "proclubstracker_fallback"}
        except Exception as e:
            print(f"[Fallback] ProClubsTracker scrape failed: {e}")
            return {}

    def _parse_fallback_match(self, raw: Dict, squad_map: Dict[str, dict]) -> Optional[dict]:
        """Parse a match row from ProClubsTracker fallback scrape."""
        try:
            vals = list(raw.values())
            opponent = vals[1] if len(vals) > 1 else "Unknown"
            score_str = next((v for v in vals if "-" in v and any(c.isdigit() for c in v)), "0-0")
            clean = score_str.replace(" ", "").replace("–", "-")
            parts = clean.split("-")
            team_goals = int(parts[0]) if parts[0].isdigit() else 0
            opponent_goals = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            result = "win" if team_goals > opponent_goals else "loss" if team_goals < opponent_goals else "draw"
            match_id = f"pct_{hash(str(raw)) % 10000000}"
            return {
                "match_id": match_id, "date": datetime.now().isoformat(),
                "opponent": opponent, "team_goals": team_goals,
                "opponent_goals": opponent_goals, "result": result,
                "match_type": "gameType9", "player_stats": {}
            }
        except:
            return None

    async def scrape_all(self) -> Dict[str, Any]:
        """Legacy method: try EA API first, fallback to ProClubsTracker."""
        # Try EA API first
        ea_data = await self.get_all_data(match_count=20)
        if ea_data.get("matches"):
            print(f"[scrape_all] EA API returned {len(ea_data['matches'])} matches")
            return ea_data

        # Fallback to ProClubsTracker
        print("[scrape_all] EA API empty, trying ProClubsTracker fallback...")
        fallback = await self._scrape_pct_fallback()
        if fallback.get("matches"):
            return {
                "overview": {}, "matches": fallback.get("matches", []),
                "players": fallback.get("players", []), "career": [],
                "timestamp": datetime.now().isoformat(), "source": "fallback"
            }

        return {"matches": [], "players": [], "error": "No data from any source"}

    async def sync_to_stats_engine(self, stats_engine, count: int = 10) -> int:
        """Legacy-compatible: sync matches using EA API (primary) or fallback."""
        # Try EA API first
        ea_added = await super().sync_to_stats_engine(stats_engine, count)
        if ea_added > 0:
            return ea_added

        # Fallback
        print("[sync_to_stats_engine] EA API returned 0, trying fallback...")
        fallback = await self._scrape_pct_fallback()
        squad = self._load_squad()
        matches = fallback.get("matches", [])[:count]
        added = 0
        for match in matches:
            parsed = self._parse_fallback_match(match, squad)
            if parsed and not stats_engine.match_exists(parsed["match_id"]):
                stats_engine.add_match(parsed)
                added += 1
        return added

    async def check_new_match(self) -> Optional[dict]:
        """Legacy-compatible: check for new match."""
        # Try EA API first
        result = await super().check_new_match()
        if result:
            return result

        # Fallback
        fallback = await self._scrape_pct_fallback()
        matches = fallback.get("matches", [])
        if matches:
            squad = self._load_squad()
            return self._parse_fallback_match(matches[0], squad)
        return None


def get_scraper(club_id: str, platform: str = "common-gen5", division: str = "6"):
    return ProClubsTrackerScraper(club_id, platform, division)
