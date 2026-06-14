"""
Rachad L3ERGONI Bot — ProClubsTracker Scraper v8
Extracts Next.js __NEXT_DATA__ JSON from PCT pages.
This is the ACTUAL data structure the React app uses.
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

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class ProClubsTrackerScraper:
    def __init__(self, club_id: str, platform: str = "common-gen5", division: str = "6"):
        self.club_id = str(club_id)
        self.platform = platform
        self.division = division
        self.pct_url = f"https://proclubstracker.com/club/{club_id}?platform={platform}&div={division}"
        self.matches_url = f"https://proclubstracker.com/club/{club_id}/matches?platform={platform}&div={division}"

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

    # ── PRIMARY: Extract Next.js __NEXT_DATA__ from HTML ─────────────────────

    async def _extract_next_data(self, url: str) -> Optional[dict]:
        """Fetch PCT page and extract the Next.js data payload."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            async with httpx.AsyncClient(headers=headers, timeout=30, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.warning("PCT HTTP %s for %s", resp.status_code, url)
                    return None

                html = resp.text

                # Find __NEXT_DATA__ script tag
                # Pattern: <script id="__NEXT_DATA__" type="application/json">...</script>
                next_data_match = re.search(
                    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                    html,
                    re.DOTALL
                )

                if not next_data_match:
                    logger.warning("No __NEXT_DATA__ found in PCT HTML")
                    return None

                raw_json = next_data_match.group(1)
                data = json.loads(raw_json)

                logger.info("✅ Extracted Next.js data from PCT | keys: %s", list(data.keys()))
                return data

        except Exception as e:
            logger.error("Extract Next.js data error: %s", e)
            return None

    def _parse_nextjs_matches(self, next_data: dict) -> List[dict]:
        """Parse match data from Next.js payload."""
        matches = []
        try:
            # Next.js data structure: props.pageProps has all the data
            page_props = next_data.get("props", {}).get("pageProps", {})

            # Try different possible data locations
            matches_data = (
                page_props.get("matches") or
                page_props.get("clubData", {}).get("matches") or
                page_props.get("data", {}).get("matches") or
                []
            )

            if not isinstance(matches_data, list):
                matches_data = []

            logger.info("Found %d matches in Next.js data", len(matches_data))

            for raw in matches_data[:50]:  # limit to 50
                if not isinstance(raw, dict):
                    continue

                try:
                    # Extract score
                    our_goals = int(raw.get("goals", 0) or raw.get("teamGoals", 0) or 0)
                    opp_goals = int(raw.get("goalsAgainst", 0) or raw.get("opponentGoals", 0) or 0)

                    # Extract opponent
                    opponent = "Unknown"
                    opp_data = raw.get("opponent") or raw.get("opponentClub") or {}
                    if isinstance(opp_data, dict):
                        opponent = opp_data.get("name", "Unknown") or opp_data.get("clubName", "Unknown")
                    elif isinstance(opp_data, str):
                        opponent = opp_data

                    # Also try from clubs object
                    clubs = raw.get("clubs", {})
                    if isinstance(clubs, dict):
                        for cid, cdata in clubs.items():
                            if str(cid) != str(self.club_id):
                                opp_name = cdata.get("details", {}).get("name") if isinstance(cdata, dict) else None
                                if opp_name:
                                    opponent = opp_name

                    # Match type
                    mtype = raw.get("matchType", "friendlyMatch")
                    if isinstance(mtype, str):
                        if "league" in mtype.lower():
                            match_type = "leagueMatch"
                        elif "playoff" in mtype.lower():
                            match_type = "playoffMatch"
                        else:
                            match_type = "friendlyMatch"
                    else:
                        match_type = "friendlyMatch"

                    # Timestamp
                    ts = raw.get("timestamp") or raw.get("matchTimestamp") or int(time.time())
                    if isinstance(ts, (int, float)):
                        date_iso = datetime.utcfromtimestamp(int(ts)).isoformat()
                    else:
                        date_iso = str(ts)

                    # Match ID
                    match_id = str(raw.get("matchId") or raw.get("id") or f"pct_{ts}_{len(matches)}")

                    # Player stats
                    player_stats = {}
                    players_raw = raw.get("players", {})
                    if isinstance(players_raw, dict):
                        our_players = players_raw.get(str(self.club_id), {})
                        if isinstance(our_players, dict):
                            for pid, p in our_players.items():
                                if not isinstance(p, dict):
                                    continue
                                ea_name = p.get("playername", f"Player_{pid}")
                                squad = self._load_squad()
                                squad_key = self._find_squad_key(ea_name, squad)
                                display_name = squad_key if squad_key else ea_name

                                seconds = int(p.get("secondsPlayed", 0))
                                minutes = seconds // 60
                                passes_att = int(p.get("passattempts", 0))
                                passes_comp = int(p.get("passesmade", 0))

                                pos = p.get("pos", "midfielder").upper()
                                pos_map = {
                                    "GOALKEEPER": "GK", "DEFENDER": "CB", "MIDFIELDER": "CM",
                                    "FORWARD": "ST", "STRIKER": "ST", "WING": "LW",
                                }
                                position = pos_map.get(pos, pos)

                                player_stats[display_name] = {
                                    "name": display_name,
                                    "position": position,
                                    "goals": int(p.get("goals", 0)),
                                    "assists": int(p.get("assists", 0)),
                                    "shots": int(p.get("shots", 0)),
                                    "shots_on_target": int(p.get("shots", 0)),
                                    "passes_attempted": passes_att,
                                    "passes_completed": passes_comp,
                                    "pass_accuracy": round(passes_comp / max(passes_att, 1) * 100, 1) if passes_att > 0 else 0,
                                    "key_passes": int(p.get("assists", 0)) * 2,
                                    "tackles": int(p.get("tacklesmade", 0)),
                                    "interceptions": int(p.get("interceptions", 0)),
                                    "possession_losses": passes_att - passes_comp,
                                    "dribbles_attempted": 0,
                                    "dribbles_completed": 0,
                                    "fouls": 0,
                                    "yellow_cards": int(p.get("yellowcards", 0)),
                                    "red_cards": int(p.get("redcards", 0)),
                                    "rating": float(p.get("rating", "6.0") or "6.0"),
                                    "motm": str(p.get("man_of_the_match", "0")) == "1",
                                    "minutes_played": minutes,
                                    "saves": int(p.get("saves", 0)),
                                    "clean_sheets_gk": int(p.get("cleansheetsgk", 0)),
                                    "own_goals": int(p.get("owngoals", 0)),
                                    "longshots": int(p.get("longshots", 0)),
                                    "chances_created": int(p.get("chancescreated", 0)),
                                }

                    matches.append({
                        "match_id": match_id,
                        "date": date_iso,
                        "opponent": opponent,
                        "team_goals": our_goals,
                        "opponent_goals": opp_goals,
                        "match_type": match_type,
                        "player_stats": player_stats,
                        "raw": raw,
                    })

                except Exception as e:
                    logger.error("Parse individual match error: %s", e)
                    continue

        except Exception as e:
            logger.error("Parse Next.js matches error: %s", e)

        return matches

    def _parse_nextjs_club_info(self, next_data: dict) -> dict:
        """Parse club info from Next.js payload."""
        try:
            page_props = next_data.get("props", {}).get("pageProps", {})
            club_data = (
                page_props.get("club") or
                page_props.get("clubData") or
                page_props.get("data", {}).get("club") or
                {}
            )

            if not isinstance(club_data, dict):
                return {}

            return {
                "name": club_data.get("name", "Rachad L3ERGONI"),
                "division": club_data.get("division", "N/A"),
                "skillRating": club_data.get("skillRating", club_data.get("skill_rating", "?")),
                "wins": club_data.get("wins", "?"),
                "losses": club_data.get("losses", "?"),
                "ties": club_data.get("ties", club_data.get("draws", "?")),
                "goals": club_data.get("goals", "?"),
                "goalsAgainst": club_data.get("goalsAgainst", club_data.get("goals_against", "?")),
                "gamesPlayed": club_data.get("gamesPlayed", club_data.get("games_played", "?")),
                "bestDivision": club_data.get("bestDivision", club_data.get("best_division", "?")),
                "wstreak": club_data.get("wstreak", club_data.get("win_streak", "?")),
            }
        except Exception as e:
            logger.error("Parse club info error: %s", e)
            return {}

    def _parse_nextjs_members(self, next_data: dict) -> List[dict]:
        """Parse member list from Next.js payload."""
        try:
            page_props = next_data.get("props", {}).get("pageProps", {})
            members = (
                page_props.get("members") or
                page_props.get("clubData", {}).get("members") or
                page_props.get("data", {}).get("members") or
                []
            )
            if isinstance(members, list):
                return members
            return []
        except Exception as e:
            logger.error("Parse members error: %s", e)
            return []

    # ── FALLBACK: Playwright with network interception ──────────────────────

    async def _playwright_with_intercept(self, max_matches: int = 20) -> dict:
        """Use Playwright to render page and intercept API calls."""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright not installed")

        from playwright.async_api import async_playwright

        intercepted_data = {}

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                    "--disable-setuid-sandbox", "--no-zygote",
                ],
            )

            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={"width": 1920, "height": 1080},
            )

            page = await context.new_page()

            # Intercept network responses
            async def handle_route(route, request):
                url = request.url
                if "api" in url or "json" in url:
                    try:
                        response = await route.fetch()
                        body = await response.text()
                        try:
                            data = json.loads(body)
                            intercepted_data[url] = data
                            logger.info("Intercepted API: %s", url[:60])
                        except:
                            pass
                    except:
                        pass
                await route.continue_()

            await page.route("**/*", handle_route)

            try:
                await page.goto(self.pct_url, wait_until="networkidle", timeout=60_000)
                await asyncio.sleep(5)  # Wait for XHR
            except Exception as e:
                logger.warning("Page load warning: %s", e)

            # Also try to get __NEXT_DATA__ from rendered DOM
            try:
                next_data_script = await page.query_selector('script[id="__NEXT_DATA__"]')
                if next_data_script:
                    text = await next_data_script.text_content()
                    data = json.loads(text)
                    intercepted_data["__NEXT_DATA__"] = data
            except:
                pass

            await browser.close()

        # Process intercepted data
        if "__NEXT_DATA__" in intercepted_data:
            next_data = intercepted_data["__NEXT_DATA__"]
            matches = self._parse_nextjs_matches(next_data)
            club_info = self._parse_nextjs_club_info(next_data)
            members = self._parse_nextjs_members(next_data)
            return {
                "matches": matches,
                "members": members,
                "club_info": club_info,
                "club_stats": club_info,
            }

        # If we intercepted API responses directly
        for url, data in intercepted_data.items():
            if isinstance(data, dict) and "matches" in data:
                return {
                    "matches": data.get("matches", []),
                    "members": data.get("members", []),
                    "club_info": data.get("club", {}),
                    "club_stats": data.get("club", {}),
                }

        return {"matches": [], "members": [], "club_info": {}, "club_stats": {}}

    # ── Public API ───────────────────────────────────────────────────────────

    async def scrape_all(self, max_matches: int = 20, force: bool = False) -> dict:
        """Fetch all data from PCT using best available method."""
        # Method 1: Direct Next.js data extraction (fastest, no browser)
        logger.info("Trying Next.js data extraction...")
        next_data = await self._extract_next_data(self.pct_url)
        if next_data:
            matches = self._parse_nextjs_matches(next_data)
            if matches:
                club_info = self._parse_nextjs_club_info(next_data)
                members = self._parse_nextjs_members(next_data)
                logger.info("✅ Next.js extraction: %d matches, %d members", len(matches), len(members))
                return {
                    "matches": matches,
                    "members": members,
                    "club_info": club_info,
                    "club_stats": club_info,
                }

        # Method 2: Try matches page specifically
        logger.info("Trying matches page...")
        next_data_matches = await self._extract_next_data(self.matches_url)
        if next_data_matches:
            matches = self._parse_nextjs_matches(next_data_matches)
            if matches:
                club_info = self._parse_nextjs_club_info(next_data_matches)
                members = self._parse_nextjs_members(next_data_matches)
                return {
                    "matches": matches,
                    "members": members,
                    "club_info": club_info,
                    "club_stats": club_info,
                }

        # Method 3: Playwright fallback
        if PLAYWRIGHT_AVAILABLE:
            logger.info("Falling back to Playwright...")
            try:
                return await self._playwright_with_intercept(max_matches)
            except Exception as e:
                logger.error("Playwright fallback failed: %s", e)

        return {"matches": [], "members": [], "club_info": {}, "club_stats": {}}

    async def sync_to_stats_engine(self, stats_engine, count: int = 20) -> int:
        """Sync PCT matches to stats engine."""
        from ea_api import EAMatch, EAPlayerMatch

        data = await self.scrape_all(max_matches=count, force=True)
        matches = data.get("matches", [])
        added = 0

        for match in matches:
            if not match or stats_engine.match_exists(match["match_id"]):
                continue

            # Convert to EAMatch
            em = EAMatch(
                match_id=match["match_id"],
                date_iso=match.get("date", "—"),
                opponent_name=match.get("opponent", "Unknown"),
                team_goals=match.get("team_goals", 0),
                opponent_goals=match.get("opponent_goals", 0),
                match_type=match.get("match_type", "friendlyMatch"),
            )

            # Convert player stats
            for pname, ps in match.get("player_stats", {}).items():
                em.player_stats[pname] = EAPlayerMatch(
                    name=ps.get("name", pname),
                    position=ps.get("position", "CM"),
                    goals=ps.get("goals", 0),
                    assists=ps.get("assists", 0),
                    shots=ps.get("shots", 0),
                    shots_on_target=ps.get("shots_on_target", 0),
                    passes_attempted=ps.get("passes_attempted", 0),
                    passes_completed=ps.get("passes_completed", 0),
                    key_passes=ps.get("key_passes", 0),
                    tackles=ps.get("tackles", 0),
                    interceptions=ps.get("interceptions", 0),
                    possession_losses=ps.get("possession_losses", 0),
                    dribbles_attempted=ps.get("dribbles_attempted", 0),
                    dribbles_completed=ps.get("dribbles_completed", 0),
                    fouls=ps.get("fouls", 0),
                    yellow_cards=ps.get("yellow_cards", 0),
                    red_cards=ps.get("red_cards", 0),
                    rating=ps.get("rating", 6.0),
                    motm=ps.get("motm", False),
                    minutes_played=ps.get("minutes_played", 90),
                    saves=ps.get("saves", 0),
                    clean_sheets_gk=ps.get("clean_sheets_gk", 0),
                    own_goals=ps.get("own_goals", 0),
                    longshots=ps.get("longshots", 0),
                    chances_created=ps.get("chances_created", 0),
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
