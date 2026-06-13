"""
Rachad L3ERGONI Bot - Ultimate Hybrid Scraper v4
Strategy:
  1. ProClubsTracker window.__NEXT_DATA__ (instant, no DOM scraping)
  2. ProClubsTracker DOM scrape after React renders
  3. EA API fallback
  4. Manual match entry via Discord commands
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


class UltimateScraper:
    """
    Multi-strategy scraper:
    - Primary: ProClubsTracker Next.js internal data
    - Secondary: ProClubsTracker DOM after React render
    - Tertiary: EA API
    """

    def __init__(self, club_id: str, platform: str = "common-gen5", division: str = "6"):
        self.club_id = str(club_id)
        self.platform = platform
        self.division = division
        self.club_url = f"{PCT_BASE}/club/{club_id}?platform={platform}&div={division}"
        self._client: Optional[httpx.AsyncClient] = None
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

    # ===================== EA API =====================

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
                    return None
            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
        return None

    async def _ea_get_matches(self, count: int = 20) -> List[dict]:
        data = await self._api_get("clubs/matches", {
            "matchType": "gameType9", "platform": self.platform,
            "clubIds": self.club_id, "maxResultCount": count
        })
        return data if isinstance(data, list) else []

    async def _ea_get_all(self, match_count: int = 20) -> Dict[str, Any]:
        club_info, matches = await asyncio.gather(
            self._api_get("clubs/info", {"platform": self.platform, "clubIds": self.club_id}),
            self._ea_get_matches(match_count),
            return_exceptions=True
        )
        return {
            "overview": club_info if isinstance(club_info, dict) else {},
            "matches": matches if isinstance(matches, list) else [],
            "timestamp": datetime.now().isoformat()
        }

    # ===================== ProClubsTracker =====================

    async def _scrape_pct_nextjs(self) -> Dict[str, Any]:
        """
        PRIMARY METHOD: Extract Next.js internal data from window.__NEXT_DATA__
        This is how Next.js apps work - all data is embedded in the HTML initially
        or loaded via JS and stored in window.__NEXT_DATA__
        """
        if not self._ensure_playwright():
            return {}

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return {}

        print(f"[PCT] Scraping via Next.js internal data: {self.club_url}")
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
                )
                context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
                page = await context.new_page()

                # Navigate
                await page.goto(self.club_url, wait_until="networkidle", timeout=45000)
                await asyncio.sleep(2)  # Let React hydrate

                # METHOD 1: Try window.__NEXT_DATA__
                next_data = await page.evaluate("() => { try { return window.__NEXT_DATA__; } catch(e) { return null; } }")
                if next_data:
                    print(f"[PCT] Found window.__NEXT_DATA__!")
                    # Extract matches from Next.js data structure
                    props = next_data.get("props", {})
                    page_props = props.get("pageProps", {}) if isinstance(props, dict) else {}

                    # Try different possible data structures
                    matches = []
                    if "matches" in page_props:
                        matches = page_props["matches"]
                    elif "data" in page_props and isinstance(page_props["data"], dict):
                        matches = page_props["data"].get("matches", [])
                    elif "club" in page_props and isinstance(page_props["club"], dict):
                        matches = page_props["club"].get("matches", [])

                    players = []
                    if "players" in page_props:
                        players = page_props["players"]
                    elif "data" in page_props and isinstance(page_props["data"], dict):
                        players = page_props["data"].get("players", [])

                    await browser.close()
                    return {
                        "matches": matches,
                        "players": players,
                        "source": "nextjs_internal",
                        "timestamp": datetime.now().isoformat()
                    }

                # METHOD 2: Scrape rendered DOM
                print("[PCT] No __NEXT_DATA__, scraping rendered DOM...")

                # Wait for loading to finish
                for _ in range(10):
                    loading = await page.query_selector("text=Loading club data...")
                    if not loading:
                        break
                    await asyncio.sleep(1)

                await asyncio.sleep(2)  # Extra wait for React render

                # Extract all text content that looks like match data
                page_text = await page.evaluate("""() => {
                    const data = [];
                    // Look for any elements containing match-like patterns
                    const allElements = document.querySelectorAll('*');
                    for (const el of allElements) {
                        const text = el.innerText || el.textContent || '';
                        if (text.includes('vs') || text.includes('-')) {
                            if (/\d+\s*[-–]\s*\d+/.test(text)) {
                                data.push({
                                    text: text.trim(),
                                    tag: el.tagName,
                                    class: el.className
                                });
                            }
                        }
                    }
                    return data;
                }""")

                # Also try to find table data
                tables = await page.query_selector_all('table, [class*="table"], [class*="match"]')
                table_data = []
                for table in tables:
                    rows = await table.query_selector_all('tr, [class*="row"]')
                    for row in rows:
                        cells = await row.query_selector_all('td, th, [class*="cell"]')
                        if len(cells) >= 2:
                            row_text = " | ".join([(await c.inner_text()).strip() for c in cells])
                            if any(c.isdigit() for c in row_text):
                                table_data.append(row_text)

                await browser.close()

                return {
                    "dom_elements": page_text[:50],  # Limit
                    "table_rows": table_data[:20],
                    "source": "dom_scrape",
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            print(f"[PCT] Scraping failed: {e}")
            return {}

    # ===================== Parsing =====================

    def _parse_pct_match(self, raw_text: str, squad_map: Dict[str, dict]) -> Optional[dict]:
        """Parse a match from ProClubsTracker text format"""
        try:
            # Look for score pattern like "3 - 2" or "3-2"
            import re
            score_match = re.search(r'(\d+)\s*[-–]\s*(\d+)', raw_text)
            if not score_match:
                return None

            team_goals = int(score_match.group(1))
            opponent_goals = int(score_match.group(2))
            result = "win" if team_goals > opponent_goals else "loss" if team_goals < opponent_goals else "draw"

            # Try to extract opponent name (text before or after score)
            opponent = "Unknown"
            parts = raw_text.split(score_match.group(0))
            if parts:
                for part in parts:
                    clean = part.strip().replace("vs", "").replace("VS", "").strip()
                    if clean and len(clean) > 2 and not clean.isdigit():
                        opponent = clean
                        break

            match_id = f"pct_{hash(raw_text) % 10000000}"
            return {
                "match_id": match_id, "date": datetime.now().isoformat(),
                "opponent": opponent, "team_goals": team_goals,
                "opponent_goals": opponent_goals, "result": result,
                "match_type": "gameType9", "player_stats": {}
            }
        except Exception as e:
            return None

    def _parse_ea_match(self, match: dict, squad_map: Dict[str, dict]) -> Optional[dict]:
        """Parse EA API match format"""
        try:
            ts = match.get("match_timestamp", "")
            match_time = datetime.fromtimestamp(int(ts)).isoformat() if str(ts).isdigit() else datetime.now().isoformat()
            teams = match.get("teams", {})
            our_team = teams.get(self.club_id, {})

            opponent_name = "Unknown"
            for cid, team in teams.items():
                if str(cid) != str(self.club_id):
                    opponent_name = team.get("name", "Unknown")

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
                "match_id": hashlib.sha256(f"{match.get('match_id', '')}_{ts}_{self.club_id}".encode()).hexdigest()[:16],
                "date": match_time, "opponent": opponent_name,
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
            print(f"[Parse EA Match Error] {e}")
            return None

    # ===================== Public API =====================

    async def scrape_all(self) -> Dict[str, Any]:
        """Try all methods and return the best data"""
        # Method 1: ProClubsTracker Next.js
        pct_data = await self._scrape_pct_nextjs()
        if pct_data.get("matches") and len(pct_data["matches"]) > 0:
            print(f"[scrape_all] ProClubsTracker returned {len(pct_data['matches'])} matches")
            return pct_data

        # Method 2: EA API
        ea_data = await self._ea_get_all(20)
        if ea_data.get("matches") and len(ea_data["matches"]) > 0:
            print(f"[scrape_all] EA API returned {len(ea_data['matches'])} matches")
            return ea_data

        # Method 3: Return whatever PCT DOM scrape found
        if pct_data.get("dom_elements") or pct_data.get("table_rows"):
            print(f"[scrape_all] PCT DOM scrape found {len(pct_data.get('table_rows', []))} rows")
            return pct_data

        return {"matches": [], "players": [], "error": "No data from any source"}

    async def sync_to_stats_engine(self, stats_engine, count: int = 10) -> int:
        """Sync matches to stats engine using best available source"""
        squad = self._load_squad()
        added = 0

        # Try ProClubsTracker first
        pct_data = await self._scrape_pct_nextjs()
        if pct_data.get("matches") and len(pct_data["matches"]) > 0:
            for match in pct_data["matches"][:count]:
                if isinstance(match, dict):
                    parsed = self._parse_ea_match(match, squad) if "teams" in match else self._parse_pct_match(str(match), squad)
                else:
                    parsed = self._parse_pct_match(str(match), squad)
                if parsed and not stats_engine.match_exists(parsed["match_id"]):
                    stats_engine.add_match(parsed)
                    added += 1
            if added > 0:
                print(f"[Sync] Added {added} matches from ProClubsTracker")
                return added

        # Try EA API
        ea_matches = await self._ea_get_matches(count)
        for match in ea_matches:
            parsed = self._parse_ea_match(match, squad)
            if parsed and not stats_engine.match_exists(parsed["match_id"]):
                stats_engine.add_match(parsed)
                added += 1

        if added > 0:
            print(f"[Sync] Added {added} matches from EA API")
        else:
            print("[Sync] No new matches found from any source")
        return added

    async def check_new_match(self) -> Optional[dict]:
        """Check for most recent match"""
        squad = self._load_squad()

        # Try ProClubsTracker
        pct_data = await self._scrape_pct_nextjs()
        if pct_data.get("matches") and len(pct_data["matches"]) > 0:
            match = pct_data["matches"][0]
            if isinstance(match, dict) and "teams" in match:
                return self._parse_ea_match(match, squad)
            return self._parse_pct_match(str(match), squad)

        # Try EA API
        ea_matches = await self._ea_get_matches(1)
        if ea_matches:
            return self._parse_ea_match(ea_matches[0], squad)

        return None

    async def get_club_info(self) -> Optional[dict]:
        """Get club info from EA API"""
        data = await self._api_get("clubs/info", {"platform": self.platform, "clubIds": self.club_id})
        if data and isinstance(data, dict):
            return data.get(self.club_id, data)
        return None

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Legacy class name for backward compatibility
class ProClubsTrackerScraper(UltimateScraper):
    pass


def get_scraper(club_id: str, platform: str = "common-gen5", division: str = "6"):
    return ProClubsTrackerScraper(club_id, platform, division)
