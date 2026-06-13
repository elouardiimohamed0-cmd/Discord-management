"""
Rachad L3ERGONI Bot - ProClubsTracker Scraper v6
Based on the WORKING code from yesterday.
Strategy:
  1. Direct PCT API: https://proclubstracker.com/api/clubs/{CLUB_ID}?platform={PLATFORM}
  2. Playwright DOM fallback
  3. In-memory cache with TTL
"""

import asyncio
import json
import logging
import re
import shutil
import time
from datetime import datetime
from typing import Optional, Dict, Any, List

import httpx

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 1800

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/html,*/*",
    "Referer": "https://proclubstracker.com/",
    "Accept-Language": "en-US,en;q=0.9",
}

_cache: dict = {}
_cache_ts: float = 0.0
_cache_lock = asyncio.Lock()


class ProClubsTrackerScraper:
    """
    Scraper that uses ProClubsTracker's own API endpoint.
    This was working yesterday and returns structured JSON.
    """

    def __init__(self, club_id: str, platform: str = "common-gen5", division: str = "6"):
        self.club_id = str(club_id)
        self.platform = platform
        self.division = division
        self.pct_url = f"https://proclubstracker.com/club/{club_id}?platform={platform}&div={division}"
        self.pct_api = f"https://proclubstracker.com/api/clubs/{club_id}?platform={platform}"
        self._playwright_available = None

    # ── Cache helpers ─────────────────────────────────────────────────────

    def _cache_age(self) -> float:
        return time.time() - _cache_ts if _cache_ts else float("inf")

    def _get_cached(self, max_matches: int = 5) -> Optional[dict]:
        if not _cache or self._cache_age() > CACHE_TTL_SECONDS:
            return None
        raw = _cache.get("raw", {})
        matches = (raw.get("matches") or [])[:max_matches]
        return {**raw, "matches": matches} if matches else None

    def _set_cache(self, data: dict):
        global _cache, _cache_ts
        _cache = {"raw": data}
        _cache_ts = time.time()

    def _invalidate_cache(self):
        global _cache, _cache_ts
        _cache = {}
        _cache_ts = 0.0

    # ── Squad helpers ─────────────────────────────────────────────────────────

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

    # ── Tier 1: Direct PCT API ──────────────────────────────────────────────

    async def _pct_api_fetch(self, max_matches: int = 10) -> dict:
        """Fetch from ProClubsTracker's own API endpoint."""
        try:
            async with httpx.AsyncClient(
                headers=HEADERS, follow_redirects=True, timeout=20
            ) as client:
                logger.info("📡 Fetching PCT API: %s", self.pct_api)
                resp = await client.get(self.pct_api)

            if resp.status_code != 200:
                logger.warning("PCT API returned HTTP %s", resp.status_code)
                return {}

            data = resp.json()
            logger.info("✅ PCT API OK (keys: %s)", list(data.keys()))

        except Exception as e:
            logger.error("PCT API request failed: %s", e)
            return {}

        raw_matches_dict = data.get("matches") or {}
        league   = raw_matches_dict.get("league",   []) or []
        playoff  = raw_matches_dict.get("playoff",  []) or []
        friendly = raw_matches_dict.get("friendly", []) or []
        all_matches = (league + playoff + friendly)[:max_matches]

        logger.info(
            "Matches: %d league + %d playoff + %d friendly → %d total",
            len(league), len(playoff), len(friendly), len(all_matches),
        )

        # Parse each match into stats_engine format
        parsed_matches = []
        for raw_match in all_matches:
            parsed = self._parse_pct_match(raw_match)
            if parsed:
                parsed_matches.append(parsed)

        member_stats = data.get("memberStats") or {}
        members = member_stats.get("members") or []

        club_info_raw = data.get("clubInfoData") or {}
        club_info = club_info_raw.get(str(self.club_id)) or next(iter(club_info_raw.values()), {})

        overall = data.get("overallStats") or {}
        club_stats = {
            "wins":         overall.get("wins", "?"),
            "losses":       overall.get("losses", "?"),
            "ties":         overall.get("ties", "?"),
            "goals":        overall.get("goals", "?"),
            "goalsAgainst": overall.get("goalsAgainst", "?"),
            "skillRating":  overall.get("skillRating", "?"),
            "gamesPlayed":  overall.get("gamesPlayed", "?"),
            "bestDivision": overall.get("bestDivision", "?"),
            "wstreak":      overall.get("wstreak", "?"),
            "unbeatenstreak": overall.get("unbeatenstreak", "?"),
            "leagueAppearances": overall.get("leagueAppearances", "?"),
            "reputationtier": overall.get("reputationtier", "?"),
        }

        return {
            "matches":    parsed_matches,
            "members":    members,
            "club_info":  club_info,
            "club_stats": club_stats,
        }

    def _parse_pct_match(self, raw: dict) -> Optional[dict]:
        """Parse raw PCT API match into stats_engine MatchResult format."""
        try:
            our_id = str(self.club_id)
            clubs = raw.get("clubs", {})

            our_club = None
            opp_club = None
            for cid, club in clubs.items():
                if str(cid) == our_id:
                    our_club = club
                else:
                    opp_club = club

            if not our_club:
                return None

            our_goals = int(our_club.get("goals", 0))
            opp_goals = int(our_club.get("goalsAgainst", 0))
            result = "win" if our_goals > opp_goals else "loss" if our_goals < opp_goals else "draw"

            # Parse players into stats_engine format
            player_stats = {}
            our_players_raw = raw.get("players", {}).get(our_id, {})
            squad = self._load_squad()

            for pid, p in our_players_raw.items():
                ea_name = p.get("playername", "Unknown")
                squad_key = self._find_squad_key(ea_name, squad)
                display_name = squad_key if squad_key else ea_name

                pos = p.get("pos", "midfielder").upper()
                position_map = {"goalkeeper": "GK", "defender": "CB", "midfielder": "CM", "forward": "ST", "striker": "ST", "wing": "LW"}
                position = position_map.get(pos.lower(), pos)

                passes_att = int(p.get("passattempts", 0))
                passes_comp = int(p.get("passesmade", 0))
                pass_pct = round(passes_comp / max(passes_att, 1) * 100, 1) if passes_att > 0 else 0
                shots = int(p.get("shots", 0))
                motm = str(p.get("man_of_the_match", "0")) == "1"
                rating = float(p.get("rating", "6.0"))
                seconds = int(p.get("secondsPlayed", 0))
                minutes = seconds // 60

                player_stats[display_name] = {
                    "name": display_name, "position": position,
                    "goals": int(p.get("goals", 0)), "assists": int(p.get("assists", 0)),
                    "shots": shots, "shots_on_target": shots,
                    "passes_attempted": passes_att, "passes_completed": passes_comp,
                    "pass_accuracy": pass_pct, "key_passes": int(p.get("assists", 0)) * 2,
                    "tackles": int(p.get("tacklesmade", 0)), "interceptions": int(p.get("interceptions", 0)),
                    "possession_losses": passes_att - passes_comp,
                    "dribbles_attempted": 0, "dribbles_completed": 0,
                    "fouls": 0, "yellow_cards": int(p.get("yellowcards", 0)),
                    "red_cards": int(p.get("redcards", 0)), "rating": rating,
                    "motm": motm, "minutes_played": minutes,
                    "distance_covered": 0.0, "sprint_speed": 0.0,
                    "tackles_attempted": int(p.get("tackleattempts", 0)),
                    "own_goals": int(p.get("owngoals", 0)),
                    "big_chances_missed": max(0, int(p.get("chancescreated", 0)) - int(p.get("assists", 0))),
                    "long_goals": int(p.get("longshots", 0)),
                }

            return {
                "match_id": str(raw.get("matchId", raw.get("timestamp", ""))),
                "date": str(raw.get("timestamp", "")),
                "opponent": opp_club.get("details", {}).get("name", "Unknown") if opp_club else "Unknown",
                "team_goals": our_goals, "opponent_goals": opp_goals,
                "result": result, "match_type": "gameType9",
                "player_stats": player_stats,
                "our_name": our_club.get("details", {}).get("name", "Rachad L3ERGONI"),
                "raw_players": list(player_stats.values()),
            }
        except Exception as e:
            logger.error("Parse match error: %s", e)
            return None

    # ── Tier 2: Playwright DOM fallback ───────────────────────────────────────

    async def _playwright_dom_fetch(self, max_matches: int = 10) -> dict:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("playwright not installed")
            return {}

        chrome = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
        if not chrome:
            logger.error("No Chromium binary found")
            return {}

        async with async_playwright() as pw:
            try:
                browser = await pw.chromium.launch(
                    executable_path=chrome, headless=True,
                    args=["--no-sandbox","--disable-dev-shm-usage","--disable-gpu",
                          "--disable-setuid-sandbox","--no-zygote"],
                )
            except Exception as e:
                logger.error("Chromium launch failed: %s", e)
                return {}

            ctx = await browser.new_context(user_agent=UA, viewport={"width":1280,"height":800})
            page = await ctx.new_page()
            try:
                await page.goto(self.pct_url, wait_until="domcontentloaded", timeout=45_000)
            except Exception as e:
                logger.warning("goto failed: %s", e)
                await browser.close()
                return {}

            await asyncio.sleep(5)

            for sel in ["button:has-text('Matches')","a:has-text('Matches')","text=⚽","text=Matches"]:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=2_000):
                        await el.click()
                        break
                except Exception:
                    pass

            await asyncio.sleep(4)

            cards_data = await page.evaluate(r"""
            () => {
                const cards = Array.from(document.querySelectorAll(
                    '[class*="bg-gray-800"][class*="rounded-xl"], [class*="match-card"]'
                ));
                return cards.slice(0, 15).map(card => {
                    const text = (card.innerText || '').trim();
                    const scoreEl = card.querySelector('[class*="bg-gray-900"][class*="rounded"]');
                    const score = scoreEl ? scoreEl.innerText.trim() : '';
                    const result = /WIN/i.test(text) ? 'WIN' : /LOSS/i.test(text) ? 'LOSS' : /DRAW/i.test(text) ? 'DRAW' : '';
                    const matchType = /League/i.test(text) ? 'league' : /Friendly/i.test(text) ? 'friendly' : 'league';
                    return {text: text.slice(0, 300), score, result, matchType};
                });
            }
            """)
            await browser.close()

        matches = []
        for card in cards_data[:max_matches]:
            score_m = re.search(r'(\d+)\s*[-–]\s*(\d+)', card.get("score","") or card.get("text",""))
            if not score_m:
                continue
            our_goals, opp_goals = int(score_m.group(1)), int(score_m.group(2))
            text = card.get("text","")
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            opp_name = "Adversaire"
            idx = next((i for i,l in enumerate(lines) if 'Rachad' in l or 'L3ERGONI' in l), None)
            if idx is not None:
                for j in range(idx+1, min(idx+8, len(lines))):
                    l = lines[j]
                    if re.match(r'^\d+$',l) or 'players' in l.lower(): continue
                    if re.match(r'^\d+\s*[-–]\s*\d+$',l): continue
                    if l in ('WIN','LOSS','DRAW','League','Friendly','Today','Yesterday',''): continue
                    if any(c in l for c in ('🏆','🤝','🎖','⚽','⭐')): continue
                    opp_name = l; break
            result = "win" if card.get("result","").upper()=="WIN" else ("draw" if "DRAW" in card.get("result","").upper() else "loss")
            matches.append({
                "match_id": f"dom_{our_goals}_{opp_goals}_{len(matches)}",
                "date": "—", "opponent": opp_name,
                "team_goals": our_goals, "opponent_goals": opp_goals,
                "result": result, "match_type": "gameType9",
                "player_stats": {}, "_from_dom": True,
            })

        if matches:
            return {"matches": matches, "members": [], "club_info": {}, "club_stats": {}}
        return {}

    # ── Public API ────────────────────────────────────────────────────────────

    async def scrape_all(self, max_matches: int = 5, force: bool = False) -> dict:
        """Fetch all data from best available source."""
        async with _cache_lock:
            if not force:
                cached = self._get_cached(max_matches)
                if cached:
                    age = int(self._cache_age())
                    logger.info("📦 Cache hit (%ds old) — %d matches", age, len(cached.get("matches",[])))
                    return cached

            try:
                data = await asyncio.wait_for(self._pct_api_fetch(max_matches=10), timeout=25)
                if data.get("matches"):
                    self._set_cache(data)
                    logger.info("✅ Cache updated — %d matches stored", len(data["matches"]))
                    data["matches"] = data["matches"][:max_matches]
                    return data
                logger.info("PCT API returned no matches — trying Playwright")
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning("PCT API failed: %s", e)

            try:
                data = await asyncio.wait_for(self._playwright_dom_fetch(max_matches=10), timeout=75)
                if data.get("matches"):
                    self._set_cache(data)
                    data["matches"] = data["matches"][:max_matches]
                    return data
            except (asyncio.TimeoutError, Exception) as e:
                logger.error("Playwright DOM failed: %s", e)

            logger.error("All data sources failed")
            return {"matches": [], "members": [], "club_info": {}, "club_stats": {}}

    async def sync_to_stats_engine(self, stats_engine, count: int = 10) -> int:
        """Sync matches to stats engine."""
        data = await self.scrape_all(max_matches=count, force=True)
        matches = data.get("matches", [])
        added = 0
        for match in matches:
            if match and not stats_engine.match_exists(match["match_id"]):
                stats_engine.add_match(match)
                added += 1
        logger.info("[Sync] Added %d new matches", added)
        return added

    async def check_new_match(self) -> Optional[dict]:
        """Check for most recent match."""
        data = await self.scrape_all(max_matches=1, force=True)
        matches = data.get("matches", [])
        if matches:
            return matches[0]
        return None

    async def get_club_info(self) -> Optional[dict]:
        """Get club info from PCT API."""
        data = await self.scrape_all(max_matches=1, force=True)
        return data.get("club_info")

    def _invalidate_cache(self):
        self._invalidate_cache()


def get_scraper(club_id: str, platform: str = "common-gen5", division: str = "6"):
    return ProClubsTrackerScraper(club_id, platform, division)
