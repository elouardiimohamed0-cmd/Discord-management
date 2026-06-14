"""
Rachad L3ERGONI Bot — ProClubsTracker Scraper v7
Primary data source. Renders PCT with Playwright, extracts all stats.
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

import httpx

logger = logging.getLogger(__name__)

# Try to import playwright, but don't crash if not available
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. DOM scraping unavailable.")


class ProClubsTrackerScraper:
    """
    Scraper that renders ProClubsTracker pages with Playwright.
    Extracts club info, match history, and player stats from the DOM.
    """

    def __init__(self, club_id: str, platform: str = "common-gen5", division: str = "6"):
        self.club_id = str(club_id)
        self.platform = platform
        self.division = division
        self.pct_url = f"https://proclubstracker.com/club/{club_id}?platform={platform}&div={division}"
        self._playwright_available = PLAYWRIGHT_AVAILABLE

    def _load_squad(self) -> Dict[str, dict]:
        try:
            with open("squad.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _find_squad_key(self, ea_name: str, squad_map: Dict[str, dict]) -> Optional[str]:
        ea_lower = ea_name.lower().strip()
        for key, info in squad_map.items():
            if info.get("name", "").lower().strip() == ea_lower:
                return key
            if info.get("psn", "").lower().strip() == ea_lower:
                return key
            if info.get("nickname", "").lower().strip() == ea_lower:
                return key
            name = info.get("name", "").lower().strip()
            nick = info.get("nickname", "").lower().strip()
            if name in ea_lower or ea_lower in name:
                return key
            if nick in ea_lower or ea_lower in nick:
                return key
        return None

    # ── Primary: Playwright DOM scrape ───────────────────────────────────────

    async def _playwright_scrape(self, max_matches: int = 20) -> dict:
        """Render PCT page with Playwright and extract all data from DOM."""
        if not self._playwright_available:
            raise RuntimeError("Playwright not installed. Run: pip install playwright && playwright install chromium")

        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            # Launch browser with stealth args
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-setuid-sandbox",
                    "--no-zygote",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                ],
            )

            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
            )

            page = await context.new_page()

            try:
                # Navigate to club page
                logger.info("Navigating to %s", self.pct_url)
                await page.goto(self.pct_url, wait_until="networkidle", timeout=60_000)

                # Wait for data to load (PCT shows loading spinner first)
                await page.wait_for_selector("text=Matches", timeout=30_000)

                # Extract club info from the page
                club_info = await self._extract_club_info(page)

                # Click on Matches tab to load match data
                try:
                    matches_tab = await page.query_selector("text=Matches")
                    if matches_tab:
                        await matches_tab.click()
                        await asyncio.sleep(3)
                except Exception:
                    pass

                # Extract matches
                matches = await self._extract_matches(page, max_matches)

                # Extract member stats from the page
                members = await self._extract_members(page)

                await browser.close()

                return {
                    "matches": matches,
                    "members": members,
                    "club_info": club_info,
                    "club_stats": club_info,  # alias for compatibility
                }

            except Exception as e:
                logger.error("Playwright scrape failed: %s", e)
                await browser.close()
                raise

    async def _extract_club_info(self, page) -> dict:
        """Extract club info from PCT page."""
        try:
            # Try to get club name, division, stats from various selectors
            info = {}

            # Club name
            name_el = await page.query_selector("h1, [class*='club-name'], [class*='title']")
            if name_el:
                info["name"] = await name_el.text_content() or "Rachad L3ERGONI"

            # Stats from stat cards
            stat_cards = await page.query_selector_all("[class*='stat'], [class*='card']")
            for card in stat_cards:
                text = await card.text_content() or ""
                if "Wins" in text:
                    m = re.search(r'(\d+)', text)
                    if m:
                        info["wins"] = m.group(1)
                elif "Losses" in text:
                    m = re.search(r'(\d+)', text)
                    if m:
                        info["losses"] = m.group(1)
                elif "Goals" in text and "Against" not in text:
                    m = re.search(r'(\d+)', text)
                    if m:
                        info["goals"] = m.group(1)
                elif "Goals Against" in text:
                    m = re.search(r'(\d+)', text)
                    if m:
                        info["goalsAgainst"] = m.group(1)

            return info
        except Exception as e:
            logger.error("Extract club info error: %s", e)
            return {}

    async def _extract_matches(self, page, max_matches: int) -> List[dict]:
        """Extract match cards from PCT page."""
        matches = []

        try:
            # PCT uses match cards with score and opponent info
            # Try multiple selector patterns
            selectors = [
                "[class*='match-card']",
                "[class*='bg-gray-800']",
                "[class*='rounded-xl']",
                "div[class*='match']",
            ]

            cards = []
            for sel in selectors:
                cards = await page.query_selector_all(sel)
                if len(cards) > 0:
                    break

            logger.info("Found %d match cards", len(cards))

            for i, card in enumerate(cards[:max_matches]):
                try:
                    text = await card.text_content() or ""

                    # Extract score (e.g., "3 - 1")
                    score_match = re.search(r'(\d+)\s*[-–]\s*(\d+)', text)
                    if not score_match:
                        continue

                    our_goals = int(score_match.group(1))
                    opp_goals = int(score_match.group(2))

                    # Determine result
                    result = "win" if our_goals > opp_goals else "loss" if our_goals < opp_goals else "draw"

                    # Extract opponent name
                    lines = [l.strip() for l in text.split('\n') if l.strip()]
                    opponent = "Unknown"

                    # Look for opponent name (not a number, not "Rachad", not result keywords)
                    for line in lines:
                        if line in ("WIN", "LOSS", "DRAW", "League", "Friendly", "Playoff", "Today", "Yesterday"):
                            continue
                        if re.match(r'^\d+$', line) or re.match(r'^\d+\s*[-–]\s*\d+$', line):
                            continue
                        if "Rachad" in line or "L3ERGONI" in line:
                            continue
                        if any(c in line for c in ('🏆', '🤝', '🎖', '⚽', '⭐', '👑')):
                            continue
                        if len(line) > 2 and not line.startswith("http"):
                            opponent = line
                            break

                    # Extract match type
                    match_type = "friendlyMatch"
                    if "League" in text:
                        match_type = "leagueMatch"
                    elif "Playoff" in text:
                        match_type = "playoffMatch"

                    # Extract timestamp if available
                    ts = int(time.time()) - (i * 86400)  # fallback: assume daily
                    date_iso = datetime.utcfromtimestamp(ts).isoformat()

                    match_id = f"pct_{our_goals}_{opp_goals}_{ts}_{i}"

                    matches.append({
                        "match_id": match_id,
                        "date": date_iso,
                        "opponent": opponent,
                        "team_goals": our_goals,
                        "opponent_goals": opp_goals,
                        "result": result,
                        "match_type": match_type,
                        "player_stats": {},
                        "_from_dom": True,
                    })

                except Exception as e:
                    logger.error("Parse card error: %s", e)
                    continue

        except Exception as e:
            logger.error("Extract matches error: %s", e)

        return matches

    async def _extract_members(self, page) -> List[dict]:
        """Extract member list from PCT page."""
        members = []
        try:
            # Look for player name elements
            player_els = await page.query_selector_all("text=/^[A-Z][a-z]+$/")
            for el in player_els[:20]:
                name = await el.text_content()
                if name and len(name) > 2:
                    members.append({"playername": name.strip()})
        except Exception:
            pass
        return members

    # ── Fallback: HTTP scrape of PCT page source ────────────────────────────

    async def _http_fallback(self, max_matches: int = 10) -> dict:
        """Fallback: fetch PCT page with httpx and parse HTML."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
            async with httpx.AsyncClient(headers=headers, timeout=30, follow_redirects=True) as client:
                resp = await client.get(self.pct_url)
                if resp.status_code != 200:
                    return {"matches": [], "members": [], "club_info": {}, "club_stats": {}}

                html = resp.text

                # Try to find embedded JSON data
                json_match = re.search(r'window\.__[A-Z_]+__\s*=\s*({.*?});', html, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group(1))
                        return data
                    except:
                        pass

                # Parse match cards from HTML
                matches = []
                score_patterns = re.findall(r'(\d+)\s*[-–]\s*(\d+)', html)
                for i, (g1, g2) in enumerate(score_patterns[:max_matches]):
                    our_goals = int(g1)
                    opp_goals = int(g2)
                    result = "win" if our_goals > opp_goals else "loss" if our_goals < opp_goals else "draw"
                    matches.append({
                        "match_id": f"http_{our_goals}_{opp_goals}_{i}",
                        "date": "—",
                        "opponent": "Unknown",
                        "team_goals": our_goals,
                        "opponent_goals": opp_goals,
                        "result": result,
                        "match_type": "gameType9",
                        "player_stats": {},
                    })

                return {
                    "matches": matches,
                    "members": [],
                    "club_info": {},
                    "club_stats": {},
                }

        except Exception as e:
            logger.error("HTTP fallback error: %s", e)
            return {"matches": [], "members": [], "club_info": {}, "club_stats": {}}

    # ── Public API ───────────────────────────────────────────────────────────

    async def scrape_all(self, max_matches: int = 20, force: bool = False) -> dict:
        """Fetch all data from PCT using best available method."""
        try:
            if self._playwright_available:
                data = await self._playwright_scrape(max_matches)
                if data.get("matches"):
                    logger.info("✅ Playwright scrape: %d matches", len(data["matches"]))
                    return data
        except Exception as e:
            logger.warning("Playwright failed: %s", e)

        # Fallback to HTTP
        logger.info("Falling back to HTTP scrape...")
        return await self._http_fallback(max_matches)

    async def sync_to_stats_engine(self, stats_engine, count: int = 20) -> int:
        """Sync PCT matches to stats engine."""
        data = await self.scrape_all(max_matches=count, force=True)
        matches = data.get("matches", [])
        added = 0
        for match in matches:
            if match and not stats_engine.match_exists(match["match_id"]):
                # Convert to EAMatch format
                from ea_api import EAMatch, EAPlayerMatch
                em = EAMatch(
                    match_id=match["match_id"],
                    date_iso=match.get("date", "—"),
                    opponent_name=match.get("opponent", "Unknown"),
                    team_goals=match.get("team_goals", 0),
                    opponent_goals=match.get("opponent_goals", 0),
                    match_type=match.get("match_type", "friendlyMatch"),
                )
                stats_engine.add_match(em)
                added += 1
        logger.info("[Sync] Added %d new matches from PCT", added)
        return added

    async def check_new_match(self) -> Optional[dict]:
        """Check for most recent match on PCT."""
        data = await self.scrape_all(max_matches=1, force=True)
        matches = data.get("matches", [])
        if matches:
            return matches[0]
        return None

    async def get_club_info(self) -> Optional[dict]:
        """Get club info from PCT."""
        data = await self.scrape_all(max_matches=1, force=True)
        return data.get("club_info")

    def _invalidate_cache(self):
        pass


def get_scraper(club_id: str, platform: str = "common-gen5", division: str = "6"):
    return ProClubsTrackerScraper(club_id, platform, division)
