import os
import asyncio
import json
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

import httpx
from models import ClubStats, PlayerStats, MatchResult

logger = logging.getLogger("rachad_bot.scraper")

CLUB_ID = os.environ.get("CLUB_ID", "1427607")
PLATFORM = os.environ.get("PCT_PLATFORM", "common-gen5")
PCT_API = f"https://proclubstracker.com/api/clubs/{CLUB_ID}?platform={PLATFORM}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html,*/*",
    "Referer": "https://proclubstracker.com/",
    "Accept-Language": "en-US,en;q=0.9",
}

CACHE_DIR = Path(os.getenv("CACHE_DIR", "/tmp/rachad_cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
COOKIE_FILE = CACHE_DIR / "pct_cookies.json"
API_CACHE_TTL = int(os.getenv("API_CACHE_TTL", "300"))  # 5 minutes default
API_CACHE_FILE = CACHE_DIR / "api_cache.json"

class ProClubsTrackerScraper:
    """
    Hybrid scraper:
    1. Primary: httpx API call (fast, no browser)
    2. Fallback: Playwright with stealth (if API fails or blocked)
    3. Cache layer: file-based JSON cache with TTL
    """

    def __init__(self, club_url: str, headless: bool = True, use_stealth: bool = True):
        self.club_url = club_url
        self.club_id = CLUB_ID
        self.platform = PLATFORM
        self._last_error = None
        self._cache_time = 0
        self._cached_data: Optional[dict] = None
        self._headless = headless
        self._use_stealth = use_stealth
        self._playwright_available = False
        self._browser = None
        self._context = None
        self._page = None
        self._init_playwright()

    def _init_playwright(self):
        """Lazy-load Playwright only if needed."""
        try:
            from playwright.async_api import async_playwright
            self._playwright_cls = async_playwright
            self._playwright_available = True
            logger.info("Playwright available for fallback scraping.")
        except ImportError:
            self._playwright_available = False
            logger.warning("Playwright not installed. API-only mode.")

    def _to_int(self, val, default=0) -> int:
        try:
            return int(float(str(val))) if val is not None else default
        except (ValueError, TypeError):
            return default

    def _to_float(self, val, default=0.0) -> float:
        try:
            return float(str(val)) if val is not None else default
        except (ValueError, TypeError):
            return default

    def _parse_rating(self, val) -> float:
        r = self._to_float(val, 0.0)
        if r > 10:
            return round(r / 10.0, 2)
        return r

    # ── Cache helpers ──
    def _load_cache(self) -> Optional[dict]:
        try:
            if not API_CACHE_FILE.exists():
                return None
            mtime = API_CACHE_FILE.stat().st_mtime
            if time.time() - mtime > API_CACHE_TTL:
                return None
            with open(API_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Cache load error: %s", e)
            return None

    def _save_cache(self, data: dict):
        try:
            with open(API_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning("Cache save error: %s", e)

    def _load_cookies(self) -> list:
        if COOKIE_FILE.exists():
            try:
                with open(COOKIE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_cookies(self, cookies: list):
        try:
            with open(COOKIE_FILE, "w", encoding="utf-8") as f:
                json.dump(cookies, f, ensure_ascii=False)
        except Exception as e:
            logger.warning("Cookie save error: %s", e)

    # ── Primary: httpx API ──
    async def _fetch_pct_api(self) -> Optional[dict]:
        # Check memory cache first
        if self._cached_data and (time.time() - self._cache_time) < API_CACHE_TTL:
            logger.info("Using memory cache (age %ds)", int(time.time() - self._cache_time))
            return self._cached_data

        # Check file cache
        cached = self._load_cache()
        if cached:
            self._cached_data = cached
            self._cache_time = time.time()
            logger.info("Using file cache")
            return cached

        logger.info("Fetching PCT API: %s", PCT_API)
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20) as client:
                    resp = await client.get(PCT_API)
                    logger.info("PCT API status: %d", resp.status_code)
                    if resp.status_code == 429:
                        retry_after = int(resp.headers.get("Retry-After", 5 * (attempt + 1)))
                        logger.warning("PCT API 429 (attempt %d). Sleeping %ds...", attempt + 1, retry_after)
                        await asyncio.sleep(retry_after)
                        continue
                    if resp.status_code != 200:
                        logger.warning("PCT API HTTP %d: %s", resp.status_code, resp.text[:200])
                        return None
                    data = resp.json()
                    logger.info("PCT API OK (keys: %s)", list(data.keys()))
                    self._cached_data = data
                    self._cache_time = time.time()
                    self._save_cache(data)
                    return data
            except httpx.TimeoutException:
                logger.warning("PCT API timeout (attempt %d)", attempt + 1)
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error("PCT API error (attempt %d): %s", attempt + 1, e)
                self._last_error = str(e)
                await asyncio.sleep(2 ** attempt)
        logger.error("PCT API failed after 3 attempts")
        return None

    # ── Fallback: Playwright with stealth ──
    async def _fetch_pct_playwright(self) -> Optional[dict]:
        if not self._playwright_available:
            logger.error("Playwright not available for fallback")
            return None

        logger.info("Playwright fallback: scraping %s", self.club_url)
        try:
            async with self._playwright_cls() as p:
                browser_type = p.chromium
                launch_args = {
                    "headless": self._headless,
                    "args": [
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                    ]
                }
                browser = await browser_type.launch(**launch_args)
                context = await browser.new_context(
                    user_agent=HEADERS["User-Agent"],
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US",
                )

                # Load cookies
                cookies = self._load_cookies()
                if cookies:
                    await context.add_cookies(cookies)

                page = await context.new_page()

                if self._use_stealth:
                    try:
                        await page.add_init_script("""
                            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                            window.chrome = { runtime: {} };
                        """)
                    except Exception as e:
                        logger.warning("Stealth script error: %s", e)

                # Navigate with retries
                for attempt in range(3):
                    try:
                        await page.goto(self.club_url, wait_until="networkidle", timeout=30000)
                        break
                    except Exception as e:
                        logger.warning("Playwright navigate error (attempt %d): %s", attempt + 1, e)
                        if attempt == 2:
                            await browser.close()
                            return None
                        await asyncio.sleep(2 ** attempt)

                # Wait for data to load
                try:
                    await page.wait_for_selector("text=Club Stats", timeout=10000)
                except Exception:
                    pass

                # Try to extract JSON from page or API call interception
                # First, try to find API response in page resources
                data = None
                try:
                    # Check if window has data
                    data = await page.evaluate("""
                        () => {
                            if (window.__INITIAL_STATE__) return window.__INITIAL_STATE__;
                            if (window.__DATA__) return window.__DATA__;
                            return null;
                        }
                    """)
                except Exception as e:
                    logger.warning("Page evaluate error: %s", e)

                if not data:
                    # Fallback: intercept API call
                    try:
                        api_url = PCT_API
                        resp = await page.evaluate(f"""
                            async () => {{
                                const r = await fetch("{api_url}", {{
                                    headers: {{
                                        "Accept": "application/json",
                                        "Referer": "https://proclubstracker.com/"
                                    }}
                                }});
                                return await r.json();
                            }}
                        """)
                        if resp and isinstance(resp, dict):
                            data = resp
                    except Exception as e:
                        logger.warning("Fetch intercept error: %s", e)

                # Save cookies
                try:
                    cookies = await context.cookies()
                    self._save_cookies(cookies)
                except Exception as e:
                    logger.warning("Cookie save error: %s", e)

                await browser.close()

                if data:
                    logger.info("Playwright fallback succeeded")
                    self._cached_data = data
                    self._cache_time = time.time()
                    self._save_cache(data)
                    return data
                else:
                    logger.error("Playwright fallback: no data extracted")
                    return None
        except Exception as e:
            logger.error("Playwright fallback failed: %s", e)
            traceback.print_exc()
            return None

    def _extract_match_players(self, raw: dict) -> list:
        our_id = str(self.club_id)
        clubs = raw.get("clubs", {})
        our_players_raw = raw.get("players", {}).get(our_id, {})
        players = []
        for pid, p in our_players_raw.items():
            if not isinstance(p, dict):
                continue
            passes_att = self._to_int(p.get("passattempts"), 0)
            passes_comp = self._to_int(p.get("passesmade"), 0)
            seconds = self._to_int(p.get("secondsPlayed"), 0)
            rating = self._to_float(p.get("rating"), 0.0)
            if rating > 10:
                rating = round(rating / 10.0, 2)
            players.append({
                "name": p.get("playername", "Unknown"),
                "position": p.get("pos", ""),
                "goals": self._to_int(p.get("goals"), 0),
                "assists": self._to_int(p.get("assists"), 0),
                "shots": self._to_int(p.get("shots"), 0),
                "tackles": self._to_int(p.get("tacklesmade"), 0),
                "interceptions": self._to_int(p.get("interceptions"), 0),
                "passes_attempted": passes_att,
                "passes_completed": passes_comp,
                "minutes": seconds // 60,
                "motm": str(p.get("man_of_the_match", "0")) == "1",
                "rating": rating,
            })
        return players

    def _parse_pct_match(self, raw: dict) -> Optional[MatchResult]:
        try:
            our_id = str(self.club_id)
            clubs = raw.get("clubs", {})
            our_club, opp_club = None, None
            for cid, cdata in clubs.items():
                if str(cid) == our_id:
                    our_club = cdata
                else:
                    opp_club = cdata
            if not our_club:
                return None

            our_goals = self._to_int(our_club.get("goals"), 0)
            opp_goals = self._to_int(our_club.get("goalsAgainst"), 0)
            result = "W" if our_goals > opp_goals else "L" if our_goals < opp_goals else "D"

            ts = raw.get("timestamp")
            date = datetime.now()
            if ts:
                try:
                    date = datetime.fromtimestamp(int(ts))
                except Exception:
                    pass

            match_id = str(raw.get("matchId", raw.get("timestamp", "")))
            opp_name = opp_club.get("details", {}).get("name", "Unknown") if opp_club else "Unknown"

            return MatchResult(
                match_id=match_id,
                date=date,
                opponent=opp_name,
                score_for=our_goals,
                score_against=opp_goals,
                result=result,
            )
        except Exception as e:
            logger.warning("Parse match error: %s", e)
            return None

    async def scrape_club(self) -> Optional[ClubStats]:
        logger.info("Scraping club %s (platform=%s)", self.club_id, self.platform)

        # Try API first
        data = await self._fetch_pct_api()

        # Fallback to Playwright if API fails
        if not data:
            logger.warning("API failed, trying Playwright fallback...")
            data = await self._fetch_pct_playwright()

        if not data:
            logger.error("All scraping methods failed. Last error: %s", self._last_error)
            return None

        club = ClubStats(club_name="Rachad L3ERGONI", last_updated=datetime.now())

        # ── Club Info & Stats ──
        club_info_raw = data.get("clubInfoData") or {}
        club_info = club_info_raw.get(str(self.club_id)) or next(iter(club_info_raw.values()), {})
        overall = data.get("overallStats") or {}

        club.club_name = club_info.get("name") or club_info.get("clubName") or "Rachad L3ERGONI"
        club.division = self._to_int(overall.get("bestDivision") or club_info.get("divisionId"), 6)
        club.skill_rating = self._to_int(overall.get("skillRating") or club_info.get("skillRating"), 0)
        club.wins = self._to_int(overall.get("wins"), 0)
        club.losses = self._to_int(overall.get("losses"), 0)
        club.draws = self._to_int(overall.get("ties"), 0)
        club.goals_scored = self._to_int(overall.get("goals"), 0)
        club.goals_conceded = self._to_int(overall.get("goalsAgainst"), 0)

        games_played = self._to_int(overall.get("gamesPlayed"), 0)
        if games_played > 0:
            club.win_rate = round((club.wins / games_played) * 100, 1)

        logger.info("Club: %s | Div %d | SR %d | %dW %dL %dD",
                    club.club_name, club.division, club.skill_rating,
                    club.wins, club.losses, club.draws)

        # ── Players ──
        member_stats = data.get("memberStats") or {}
        members = member_stats.get("members") or []

        raw_matches_dict = data.get("matches") or {}
        all_matches_raw = (raw_matches_dict.get("league", []) or []) + \
                          (raw_matches_dict.get("playoff", []) or []) + \
                          (raw_matches_dict.get("friendly", []) or [])

        # Build from memberStats (season totals)
        player_map = {}
        for m in members:
            name = m.get("proName") or m.get("name") or "Unknown"
            p = PlayerStats(name=str(name))
            p.games = self._to_int(m.get("gamesPlayed"), 0)
            p.goals = self._to_int(m.get("goals"), 0)
            p.assists = self._to_int(m.get("assists"), 0)
            p.shots = self._to_int(m.get("shots"), 0)
            p.rating = self._parse_rating(m.get("ratingAve"))
            p.tackles = self._to_int(m.get("tacklesmade"), 0)
            p.interceptions = self._to_int(m.get("interceptions"), 0)
            p.minutes_played = self._to_int(m.get("secondsPlayed"), 0) // 60
            p.motm = self._to_int(m.get("manOfTheMatch"), 0)
            p.pass_accuracy = self._to_float(m.get("passAccuracy"), 0.0)
            p.possession_losses = self._to_int(m.get("possessionLost"), 0)
            p.distance_covered = self._to_float(m.get("distanceCovered"), 0.0)
            player_map[p.name] = p

        # Supplement from match aggregation
        match_agg = {}
        for raw_match in all_matches_raw[:30]:
            for mp in self._extract_match_players(raw_match):
                name = mp["name"]
                if name not in match_agg:
                    match_agg[name] = {
                        "games": 0, "goals": 0, "assists": 0, "shots": 0,
                        "tackles": 0, "interceptions": 0, "passes_attempted": 0,
                        "passes_completed": 0, "minutes": 0, "motm": 0,
                        "possession_losses": 0, "ratings": [],
                    }
                a = match_agg[name]
                a["games"] += 1
                a["goals"] += mp["goals"]
                a["assists"] += mp["assists"]
                a["shots"] += mp["shots"]
                a["tackles"] += mp["tackles"]
                a["interceptions"] += mp["interceptions"]
                a["passes_attempted"] += mp["passes_attempted"]
                a["passes_completed"] += mp["passes_completed"]
                a["minutes"] += mp["minutes"]
                a["motm"] += 1 if mp["motm"] else 0
                a["possession_losses"] += mp["passes_attempted"] - mp["passes_completed"]
                a["ratings"].append(mp["rating"])

        for name, agg in match_agg.items():
            if name in player_map:
                p = player_map[name]
                if p.games == 0 and agg["games"] > 0:
                    p.games = agg["games"]
                    p.goals = agg["goals"]
                    p.assists = agg["assists"]
                    p.shots = agg["shots"]
                    p.tackles = agg["tackles"]
                    p.interceptions = agg["interceptions"]
                    p.minutes_played = agg["minutes"]
                    p.motm = agg["motm"]
                    if agg["ratings"]:
                        p.rating = round(sum(agg["ratings"]) / len(agg["ratings"]), 2)
                    if agg["passes_attempted"] > 0:
                        p.pass_accuracy = round((agg["passes_completed"] / agg["passes_attempted"]) * 100, 1)
                    p.possession_losses = agg["possession_losses"]
            else:
                p = PlayerStats(name=name)
                p.games = agg["games"]
                p.goals = agg["goals"]
                p.assists = agg["assists"]
                p.shots = agg["shots"]
                p.tackles = agg["tackles"]
                p.interceptions = agg["interceptions"]
                p.minutes_played = agg["minutes"]
                p.motm = agg["motm"]
                if agg["ratings"]:
                    p.rating = round(sum(agg["ratings"]) / len(agg["ratings"]), 2)
                if agg["passes_attempted"] > 0:
                    p.pass_accuracy = round((agg["passes_completed"] / agg["passes_attempted"]) * 100, 1)
                p.possession_losses = agg["possession_losses"]
                player_map[name] = p

        club.players = list(player_map.values())
        logger.info("Parsed %d players from API/Playwright", len(club.players))

        # ── Matches ──
        for raw_match in all_matches_raw[:30]:
            parsed = self._parse_pct_match(raw_match)
            if parsed:
                club.matches.append(parsed)

        logger.info("Parsed %d matches", len(club.matches))

        if club.players or club.matches:
            return club

        logger.warning("No players or matches found")
        return None

    async def close(self):
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
