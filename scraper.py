"""
Rachad L3ERGONI Bot - ProClubsTracker Scraper v5
CORRECT approach: Playwright with proper waiting + network interception
"""

import os
import json
import asyncio
import re
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import httpx
import hashlib

EA_BASE = "https://proclubs.ea.com/api/fc"
PCT_BASE = "https://proclubstracker.com"


class ProClubsTrackerScraper:
    """
    Proper scraper for ProClubsTracker.com
    Strategy:
    1. Playwright network intercept - catch the API calls ProClubsTracker makes
    2. Fallback: wait for React render, then extract from DOM
    3. Fallback: EA API direct
    """

    def __init__(self, club_id: str, platform: str = "common-gen5", division: str = "6"):
        self.club_id = str(club_id)
        self.platform = platform
        self.division = division
        self.club_url = f"{PCT_BASE}/club/{club_id}?platform={platform}&div={division}"
        self._client: Optional[httpx.AsyncClient] = None
        self._intercepted_data: Dict[str, Any] = {}

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

    # ===================== PLAYWRIGHT SCRAPER =====================

    async def _scrape_with_playwright(self) -> Dict[str, Any]:
        """
        Use Playwright to either:
        A) Intercept network requests to EA API
        B) Extract rendered DOM after React loads
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            print("[Scraper] Playwright not installed")
            return {}

        print(f"[Scraper] Launching Playwright for: {self.club_url}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process'
                ]
            )
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
            )
            page = await context.new_page()

            # Setup network interception to catch EA API calls
            intercepted_matches = []
            intercepted_players = []

            async def handle_route(route, request):
                url = request.url
                # Intercept EA API calls
                if 'proclubs.ea.com/api/fc' in url or 'ea.com/api/fc' in url:
                    try:
                        response = await route.fetch()
                        body = await response.json()
                        if 'matches' in url or 'match' in url:
                            if isinstance(body, list):
                                intercepted_matches.extend(body)
                            elif isinstance(body, dict):
                                intercepted_matches.append(body)
                        elif 'members' in url or 'player' in url or 'career' in url:
                            if isinstance(body, list):
                                intercepted_players.extend(body)
                        print(f"[Intercept] EA API: {url.split('?')[0]}")
                    except:
                        pass
                    await route.fallback()
                else:
                    await route.fallback()

            await page.route("**/*", handle_route)

            # Navigate to the page
            try:
                await page.goto(self.club_url, wait_until="networkidle", timeout=45000)
            except Exception as e:
                print(f"[Scraper] Navigation timeout: {e}")
                await browser.close()
                return {}

            # Wait for loading to finish
            print("[Scraper] Waiting for content to load...")
            for i in range(15):
                loading = await page.query_selector("text=/Loading club data|Loading...|Spinner/i")
                if not loading:
                    break
                await asyncio.sleep(1)

            # Extra wait for React to render
            await asyncio.sleep(3)

            # If we intercepted API data, use it
            if intercepted_matches or intercepted_players:
                print(f"[Scraper] Intercepted {len(intercepted_matches)} matches, {len(intercepted_players)} players")
                await browser.close()
                return {
                    "matches": intercepted_matches,
                    "players": intercepted_players,
                    "source": "network_intercept",
                    "timestamp": datetime.now().isoformat()
                }

            # Otherwise, extract from DOM
            print("[Scraper] No API interception, extracting from DOM...")

            # Strategy 1: Look for window.__NEXT_DATA__
            next_data = await page.evaluate("""() => {
                try {
                    return window.__NEXT_DATA__;
                } catch(e) { return null; }
            }""")

            if next_data:
                print("[Scraper] Found window.__NEXT_DATA__")
                props = next_data.get("props", {})
                page_props = props.get("pageProps", {}) if isinstance(props, dict) else {}

                matches = []
                players = []

                if isinstance(page_props, dict):
                    if "matches" in page_props and isinstance(page_props["matches"], list):
                        matches = page_props["matches"]
                    if "players" in page_props and isinstance(page_props["players"], list):
                        players = page_props["players"]
                    if "club" in page_props and isinstance(page_props["club"], dict):
                        club_data = page_props["club"]
                        if "matches" in club_data:
                            matches = club_data["matches"]
                        if "players" in club_data:
                            players = club_data["players"]

                if matches or players:
                    await browser.close()
                    return {
                        "matches": matches,
                        "players": players,
                        "source": "nextjs_data",
                        "timestamp": datetime.now().isoformat()
                    }

            # Strategy 2: Extract from rendered DOM by looking for structured data
            dom_data = await page.evaluate("""() => {
                const results = { matches: [], players: [], raw_texts: [] };

                // Look for match cards/rows - common patterns in React apps
                const matchSelectors = [
                    '[class*="match"]',
                    '[class*="game"]',
                    '[class*="fixture"]',
                    '[data-testid*="match"]',
                    'div:has(> div:has-text("vs"))',
                    'div:has(> div:has-text("-"))'
                ];

                for (const selector of matchSelectors) {
                    try {
                        const elements = document.querySelectorAll(selector);
                        for (const el of elements) {
                            const text = el.innerText || el.textContent || '';
                            if (text.length > 10 && text.length < 500) {
                                // Check if it looks like a match result
                                if (/\d+\s*[-–]\s*\d+/.test(text) || text.includes('vs')) {
                                    results.matches.push(text.trim());
                                }
                            }
                        }
                    } catch(e) {}
                }

                // Look for player stats tables/cards
                const playerSelectors = [
                    'table tr',
                    '[class*="player"]',
                    '[class*="stat"]',
                    '[class*="row"]'
                ];

                for (const selector of playerSelectors) {
                    try {
                        const elements = document.querySelectorAll(selector);
                        for (const el of elements) {
                            const text = el.innerText || el.textContent || '';
                            if (text.includes('Goals') || text.includes('Assists') || text.includes('Rating') || /\d+\.\d+/.test(text)) {
                                if (text.length > 5 && text.length < 300) {
                                    results.players.push(text.trim());
                                }
                            }
                        }
                    } catch(e) {}
                }

                // Get all visible text as fallback
                const allText = document.body.innerText;
                results.raw_texts = allText.split('\n').filter(t => t.trim().length > 0).slice(0, 100);

                return results;
            }""")

            await browser.close()

            print(f"[Scraper] DOM extraction: {len(dom_data.get('matches', []))} matches, {len(dom_data.get('players', []))} players")

            return {
                "matches": dom_data.get("matches", []),
                "players": dom_data.get("players", []),
                "raw_texts": dom_data.get("raw_texts", []),
                "source": "dom_extraction",
                "timestamp": datetime.now().isoformat()
            }

    # ===================== EA API =====================

    async def _ea_api_get(self, endpoint: str, params: dict) -> Optional[dict]:
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

        url = f"{EA_BASE}/{endpoint}"
        for attempt in range(3):
            try:
                resp = await self._client.get(url, params=params)
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
        data = await self._ea_api_get("clubs/matches", {
            "matchType": "gameType9", "platform": self.platform,
            "clubIds": self.club_id, "maxResultCount": count
        })
        return data if isinstance(data, list) else []

    # ===================== PARSING =====================

    def _parse_dom_match_text(self, text: str, squad_map: Dict[str, dict]) -> Optional[dict]:
        """Parse match from DOM text like 'FC Barcelona 3 - 2' or '3-2 vs Real Madrid'"""
        try:
            # Extract score
            score_match = re.search(r'(\d+)\s*[-–]\s*(\d+)', text)
            if not score_match:
                return None

            team_goals = int(score_match.group(1))
            opponent_goals = int(score_match.group(2))
            result = "win" if team_goals > opponent_goals else "loss" if team_goals < opponent_goals else "draw"

            # Extract opponent name
            opponent = "Unknown"
            text_without_score = text.replace(score_match.group(0), " ").replace("vs", " ").replace("VS", " ")
            words = [w.strip() for w in text_without_score.split() if w.strip() and not w.isdigit() and len(w) > 2]
            if words:
                opponent = " ".join(words[:3])  # Take first 3 non-numeric words

            match_id = f"dom_{hash(text) % 10000000}"
            return {
                "match_id": match_id, "date": datetime.now().isoformat(),
                "opponent": opponent, "team_goals": team_goals,
                "opponent_goals": opponent_goals, "result": result,
                "match_type": "gameType9", "player_stats": {}
            }
        except Exception as e:
            return None

    def _parse_ea_match(self, match: dict, squad_map: Dict[str, dict]) -> Optional[dict]:
        """Parse EA API match format with full player stats"""
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

    # ===================== PUBLIC API =====================

    async def scrape_all(self) -> Dict[str, Any]:
        """Try all methods to get live data"""
        # Method 1: Playwright (network intercept + DOM)
        pct_data = await self._scrape_with_playwright()
        if pct_data.get("matches") and len(pct_data["matches"]) > 0:
            print(f"[scrape_all] ProClubsTracker returned {len(pct_data['matches'])} items")
            return pct_data

        # Method 2: EA API direct
        ea_matches = await self._ea_get_matches(20)
        if ea_matches:
            print(f"[scrape_all] EA API returned {len(ea_matches)} matches")
            return {
                "matches": ea_matches,
                "players": [],
                "source": "ea_api",
                "timestamp": datetime.now().isoformat()
            }

        return {"matches": [], "players": [], "error": "No data from any source"}

    async def sync_to_stats_engine(self, stats_engine, count: int = 10) -> int:
        """Sync matches to stats engine"""
        squad = self._load_squad()
        added = 0

        # Try ProClubsTracker first
        pct_data = await self._scrape_with_playwright()
        matches = pct_data.get("matches", [])

        for match in matches[:count]:
            parsed = None
            if isinstance(match, dict):
                if "teams" in match:  # EA API format
                    parsed = self._parse_ea_match(match, squad)
                elif "team_goals" in match:  # Already parsed
                    parsed = match
            elif isinstance(match, str):  # DOM text format
                parsed = self._parse_dom_match_text(match, squad)

            if parsed and not stats_engine.match_exists(parsed["match_id"]):
                stats_engine.add_match(parsed)
                added += 1

        if added > 0:
            print(f"[Sync] Added {added} matches from ProClubsTracker")
            return added

        # Fallback to EA API
        ea_matches = await self._ea_get_matches(count)
        for match in ea_matches:
            parsed = self._parse_ea_match(match, squad)
            if parsed and not stats_engine.match_exists(parsed["match_id"]):
                stats_engine.add_match(parsed)
                added += 1

        if added > 0:
            print(f"[Sync] Added {added} matches from EA API")
        else:
            print("[Sync] No new matches found")
        return added

    async def check_new_match(self) -> Optional[dict]:
        """Check for most recent match"""
        squad = self._load_squad()

        # Try ProClubsTracker
        pct_data = await self._scrape_with_playwright()
        matches = pct_data.get("matches", [])
        if matches:
            match = matches[0]
            if isinstance(match, dict) and "teams" in match:
                return self._parse_ea_match(match, squad)
            elif isinstance(match, str):
                return self._parse_dom_match_text(match, squad)

        # Fallback to EA API
        ea_matches = await self._ea_get_matches(1)
        if ea_matches:
            return self._parse_ea_match(ea_matches[0], squad)

        return None

    async def get_club_info(self) -> Optional[dict]:
        """Get club info from EA API"""
        data = await self._ea_api_get("clubs/info", {"platform": self.platform, "clubIds": self.club_id})
        if data and isinstance(data, dict):
            return data.get(self.club_id, data)
        return None

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def get_scraper(club_id: str, platform: str = "common-gen5", division: str = "6"):
    return ProClubsTrackerScraper(club_id, platform, division)
