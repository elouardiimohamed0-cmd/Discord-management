"""
Rachad L3ERGONI Bot — ProClubsTracker Scraper v9
Defensive: tries Next.js JSON, then HTTP API, then Playwright.
Logs everything. Stores whatever data is available.
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

    # ── Method 1: Next.js __NEXT_DATA__ extraction ─────────────────────────

    async def _extract_nextjs(self, url: str) -> Optional[dict]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        try:
            async with httpx.AsyncClient(headers=headers, timeout=30, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return None

                match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', resp.text, re.DOTALL)
                if not match:
                    return None

                return json.loads(match.group(1))
        except Exception as e:
            logger.error("Next.js extract error: %s", e)
            return None

    def _parse_matches_from_nextjs(self, next_data: dict) -> List[dict]:
        """Extract matches from any possible location in Next.js data."""
        matches = []
        page_props = next_data.get("props", {}).get("pageProps", {})

        # Try multiple possible locations for matches
        possible_keys = [
            "matches", "matchData", "games", "matchHistory",
            "clubData", "club", "data", "initialData", "pageData"
        ]

        raw_matches = None
        for key in possible_keys:
            if key in page_props:
                val = page_props[key]
                if isinstance(val, list):
                    raw_matches = val
                    logger.info("Found matches in pageProps['%s'] — %d items", key, len(val))
                    break
                elif isinstance(val, dict):
                    # Could be nested
                    for subkey in ["matches", "games", "history", "data"]:
                        if subkey in val and isinstance(val[subkey], list):
                            raw_matches = val[subkey]
                            logger.info("Found matches in pageProps['%s']['%s'] — %d items", key, subkey, len(val[subkey]))
                            break
                    if raw_matches:
                        break

        if not raw_matches:
            logger.warning("No matches found in any known Next.js location")
            # Log all keys for debugging
            logger.info("Available pageProps keys: %s", list(page_props.keys()))
            return []

        for raw in raw_matches[:50]:
            if not isinstance(raw, dict):
                continue
            try:
                match = self._parse_single_match(raw)
                if match:
                    matches.append(match)
            except Exception as e:
                logger.error("Parse single match error: %s", e)
                continue

        return matches

    def _parse_single_match(self, raw: dict) -> Optional[dict]:
        """Parse a single match dict from any format."""
        try:
            # Score
            our_goals = int(raw.get("goals", 0) or raw.get("teamGoals", 0) or 0)
            opp_goals = int(raw.get("goalsAgainst", 0) or raw.get("opponentGoals", 0) or 0)

            # Opponent name — try every possible location
            opponent = "Unknown"
            for key in ["opponent", "opponentClub", "enemy", "awayClub", "homeClub"]:
                val = raw.get(key)
                if isinstance(val, dict):
                    opponent = val.get("name") or val.get("clubName") or "Unknown"
                elif isinstance(val, str):
                    opponent = val
                if opponent != "Unknown":
                    break

            # Try clubs dict
            if opponent == "Unknown":
                clubs = raw.get("clubs", {})
                if isinstance(clubs, dict):
                    for cid, cdata in clubs.items():
                        if str(cid) != str(self.club_id) and isinstance(cdata, dict):
                            opp_name = cdata.get("details", {}).get("name")
                            if opp_name:
                                opponent = opp_name
                                break

            # Match type
            mtype = raw.get("matchType", "")
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

            match_id = str(raw.get("matchId") or raw.get("id") or f"pct_{ts}")

            # Player stats — CRITICAL: try every possible location
            player_stats = {}
            players_sources = [
                raw.get("players"),
                raw.get("playerStats"),
                raw.get("memberStats"),
                raw.get("matchPlayers"),
            ]

            for players_raw in players_sources:
                if not isinstance(players_raw, dict):
                    continue
                # Could be keyed by club ID
                our_players = players_raw.get(str(self.club_id))
                if not isinstance(our_players, dict):
                    our_players = players_raw  # maybe flat dict

                if isinstance(our_players, dict):
                    for pid, p in our_players.items():
                        if not isinstance(p, dict):
                            continue
                        ea_name = p.get("playername") or p.get("name") or p.get("playerName") or f"Player_{pid}"
                        squad = self._load_squad()
                        squad_key = self._find_squad_key(ea_name, squad)
                        display_name = squad_key if squad_key else ea_name

                        seconds = int(p.get("secondsPlayed", 0) or p.get("minutes", 0) * 60 or 0)
                        minutes = seconds // 60 if seconds else (int(p.get("minutes", 0)) or 90)
                        passes_att = int(p.get("passattempts", 0) or p.get("passesAttempted", 0) or 0)
                        passes_comp = int(p.get("passesmade", 0) or p.get("passesCompleted", 0) or 0)

                        pos = (p.get("pos") or p.get("position") or "midfielder").upper()
                        pos_map = {
                            "GOALKEEPER": "GK", "DEFENDER": "CB", "MIDFIELDER": "CM",
                            "FORWARD": "ST", "STRIKER": "ST", "WING": "LW",
                        }
                        position = pos_map.get(pos, pos)

                        player_stats[display_name] = {
                            "name": display_name,
                            "position": position,
                            "goals": int(p.get("goals", 0) or p.get("goalsScored", 0) or 0),
                            "assists": int(p.get("assists", 0) or p.get("assistsMade", 0) or 0),
                            "shots": int(p.get("shots", 0) or 0),
                            "shots_on_target": int(p.get("shots", 0) or 0),
                            "passes_attempted": passes_att,
                            "passes_completed": passes_comp,
                            "pass_accuracy": round(passes_comp / max(passes_att, 1) * 100, 1) if passes_att else 0,
                            "key_passes": int(p.get("assists", 0) or 0) * 2,
                            "tackles": int(p.get("tacklesmade", 0) or p.get("tackles", 0) or 0),
                            "interceptions": int(p.get("interceptions", 0) or 0),
                            "possession_losses": passes_att - passes_comp,
                            "dribbles_attempted": 0,
                            "dribbles_completed": 0,
                            "fouls": int(p.get("fouls", 0) or 0),
                            "yellow_cards": int(p.get("yellowcards", 0) or p.get("yellowCards", 0) or 0),
                            "red_cards": int(p.get("redcards", 0) or p.get("redCards", 0) or 0),
                            "rating": float(p.get("rating", 0) or p.get("matchRating", 0) or 6.0),
                            "motm": str(p.get("man_of_the_match", 0) or p.get("motm", 0) or "0") == "1",
                            "minutes_played": minutes,
                            "saves": int(p.get("saves", 0) or 0),
                            "clean_sheets_gk": int(p.get("cleansheetsgk", 0) or p.get("cleanSheets", 0) or 0),
                            "own_goals": int(p.get("owngoals", 0) or p.get("ownGoals", 0) or 0),
                            "longshots": int(p.get("longshots", 0) or p.get("longShots", 0) or 0),
                            "chances_created": int(p.get("chancescreated", 0) or p.get("chancesCreated", 0) or 0),
                        }

            # If no player stats found, log the raw keys for debugging
            if not player_stats:
                logger.warning("No player stats for match %s. Raw keys: %s", match_id, list(raw.keys()))

            return {
                "match_id": match_id,
                "date": date_iso,
                "opponent": opponent,
                "team_goals": our_goals,
                "opponent_goals": opp_goals,
                "match_type": match_type,
                "player_stats": player_stats,
                "raw": raw,
            }

        except Exception as e:
            logger.error("Parse single match error: %s", e)
            return None

    # ── Method 2: Playwright DOM extraction ────────────────────────────────

    async def _playwright_scrape(self, max_matches: int = 20) -> dict:
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright not installed")

        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--disable-setuid-sandbox"],
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()

            try:
                await page.goto(self.pct_url, wait_until="networkidle", timeout=60_000)
                await asyncio.sleep(3)

                # Try to find __NEXT_DATA__ in rendered DOM
                next_script = await page.query_selector('script[id="__NEXT_DATA__"]')
                if next_script:
                    text = await next_script.text_content()
                    data = json.loads(text)
                    await browser.close()
                    return {
                        "matches": self._parse_matches_from_nextjs(data),
                        "club_info": {},
                        "members": [],
                        "club_stats": {},
                        "source": "playwright_nextjs",
                    }

                # Fallback: try to read match cards from DOM
                matches = []
                cards = await page.query_selector_all("[class*='match']")
                for i, card in enumerate(cards[:max_matches]):
                    text = await card.text_content() or ""
                    score_m = re.search(r'(\d+)\s*[-–]\s*(\d+)', text)
                    if score_m:
                        g1, g2 = int(score_m.group(1)), int(score_m.group(2))
                        matches.append({
                            "match_id": f"dom_{g1}_{g2}_{i}",
                            "date": "—",
                            "opponent": "Unknown",
                            "team_goals": g1,
                            "opponent_goals": g2,
                            "match_type": "friendlyMatch",
                            "player_stats": {},
                        })

                await browser.close()
                return {
                    "matches": matches,
                    "club_info": {},
                    "members": [],
                    "club_stats": {},
                    "source": "playwright_dom",
                }

            except Exception as e:
                await browser.close()
                raise

    # ── Public API ───────────────────────────────────────────────────────────

    async def scrape_all(self, max_matches: int = 20, force: bool = False) -> dict:
        """Try all methods, return best result."""
        logger.info("Starting scrape for club %s", self.club_id)

        # Method 1: Next.js from main page
        try:
            data = await self._extract_nextjs(self.pct_url)
            if data:
                matches = self._parse_matches_from_nextjs(data)
                if matches:
                    logger.info("✅ Method 1 (Next.js main): %d matches", len(matches))
                    return {
                        "matches": matches,
                        "members": [],
                        "club_info": {},
                        "club_stats": {},
                        "source": "nextjs_main",
                    }
        except Exception as e:
            logger.warning("Method 1 failed: %s", e)

        # Method 2: Next.js from matches page
        try:
            data = await self._extract_nextjs(self.matches_url)
            if data:
                matches = self._parse_matches_from_nextjs(data)
                if matches:
                    logger.info("✅ Method 2 (Next.js matches): %d matches", len(matches))
                    return {
                        "matches": matches,
                        "members": [],
                        "club_info": {},
                        "club_stats": {},
                        "source": "nextjs_matches",
                    }
        except Exception as e:
            logger.warning("Method 2 failed: %s", e)

        # Method 3: Playwright
        if PLAYWRIGHT_AVAILABLE:
            try:
                result = await self._playwright_scrape(max_matches)
                if result.get("matches"):
                    logger.info("✅ Method 3 (Playwright): %d matches", len(result["matches"]))
                    return result
            except Exception as e:
                logger.warning("Method 3 failed: %s", e)

        logger.error("All methods failed")
        return {"matches": [], "members": [], "club_info": {}, "club_stats": {}, "source": "failed"}

    async def sync_to_stats_engine(self, stats_engine, count: int = 20) -> int:
        """Sync matches to stats engine with full player data."""
        from ea_api import EAMatch, EAPlayerMatch

        data = await self.scrape_all(max_matches=count, force=True)
        matches = data.get("matches", [])
        added = 0

        for match in matches:
            if not match or stats_engine.match_exists(match["match_id"]):
                continue

            em = EAMatch(
                match_id=match["match_id"],
                date_iso=match.get("date", "—"),
                opponent_name=match.get("opponent", "Unknown"),
                team_goals=match.get("team_goals", 0),
                opponent_goals=match.get("opponent_goals", 0),
                match_type=match.get("match_type", "friendlyMatch"),
            )

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

        logger.info("[Sync] Added %d matches (source: %s)", added, data.get("source", "unknown"))
        return added

    async def check_new_match(self) -> Optional[dict]:
        data = await self.scrape_all(max_matches=1, force=True)
        matches = data.get("matches", [])
        return matches[0] if matches else None

    async def get_club_info(self) -> Optional[dict]:
        data = await self.scrape_all(max_matches=1, force=True)
        return data.get("club_info")

    def _invalidate_cache(self):
        pass


def get_scraper(club_id: str, platform: str = "common-gen5", division: str = "6"):
    return ProClubsTrackerScraper(club_id, platform, division)
