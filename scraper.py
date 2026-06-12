"""
Pro Clubs Tracker scraper — two-tier strategy + in-memory cache.
Returns data in the format bot.py expects: {matches, members, club_info, club_stats}
Each match has: match_id, our_name, opp_name, our_goals, opp_goals, result, date, players[]
"""
import asyncio
import json
import logging
import re
import shutil
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

CLUB_ID  = "1427607"
PLATFORM = "common-gen5"
PCT_URL  = f"https://proclubstracker.com/club/{CLUB_ID}?platform={PLATFORM}&div=6"
PCT_API  = f"https://proclubstracker.com/api/clubs/{CLUB_ID}?platform={PLATFORM}"

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


def cache_age_seconds() -> float:
    return time.time() - _cache_ts if _cache_ts else float("inf")


def invalidate_cache():
    global _cache, _cache_ts
    _cache = {}
    _cache_ts = 0.0
    logger.info("Cache invalidated")


def get_cached(max_matches: int = 5) -> Optional[dict]:
    if not _cache or cache_age_seconds() > CACHE_TTL_SECONDS:
        return None
    raw = _cache.get("raw", {})
    matches = (raw.get("matches") or [])[:max_matches]
    return {**raw, "matches": matches} if matches else None


# ── Tier 1: Direct PCT API ─────────────────────────────────────────────────────

async def _pct_api_fetch(max_matches: int = 10) -> dict:
    try:
        async with httpx.AsyncClient(
            headers=HEADERS, follow_redirects=True, timeout=20
        ) as client:
            logger.info("📡 Fetching PCT API: %s", PCT_API)
            resp = await client.get(PCT_API)

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

    # Parse each match into the format bot.py expects
    parsed_matches = []
    for raw_match in all_matches:
        parsed = _parse_pct_match(raw_match)
        if parsed:
            parsed_matches.append(parsed)

    member_stats = data.get("memberStats") or {}
    members = member_stats.get("members") or []

    club_info_raw = data.get("clubInfoData") or {}
    club_info = club_info_raw.get(str(CLUB_ID)) or next(iter(club_info_raw.values()), {})

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


def _parse_pct_match(raw: dict) -> dict:
    """Parse raw PCT API match into bot-friendly format."""
    try:
        our_id = str(CLUB_ID)
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
        result = "W" if our_goals > opp_goals else "L" if our_goals < opp_goals else "D"

        # Parse players
        players = []
        our_players_raw = raw.get("players", {}).get(our_id, {})

        for pid, p in our_players_raw.items():
            passes_att = int(p.get("passattempts", 0))
            passes_comp = int(p.get("passesmade", 0))
            pass_pct = round(passes_comp / max(passes_att, 1) * 100, 1) if passes_att > 0 else 0

            players.append({
                "name": p.get("playername", "Unknown"),
                "position": p.get("pos", ""),
                "rating": float(p.get("rating", 0)) / 10.0 if float(p.get("rating", 0)) > 10 else float(p.get("rating", 0)),
                "goals": int(p.get("goals", 0)),
                "assists": int(p.get("assists", 0)),
                "shots": int(p.get("shots", 0)),
                "tackles": int(p.get("tacklesmade", 0)),
                "tackles_attempted": int(p.get("tackleattempts", 0)),
                "interceptions": int(p.get("interceptions", 0)),
                "passes_attempted": passes_att,
                "passes_completed": passes_comp,
                "pass_pct": pass_pct,
                "own_goals": int(p.get("owngoals", 0)),
                "big_chances_missed": max(0, int(p.get("chancescreated", 0)) - int(p.get("assists", 0))),
                "long_goals": int(p.get("longshots", 0)),
            })

        players.sort(key=lambda x: x["rating"], reverse=True)

        return {
            "match_id": str(raw.get("matchId", raw.get("timestamp", ""))),
            "our_name": our_club.get("details", {}).get("name", "Rachad L3ERGONI"),
            "opp_name": opp_club.get("details", {}).get("name", "Unknown") if opp_club else "Unknown",
            "our_goals": our_goals,
            "opp_goals": opp_goals,
            "result": result,
            "date": str(raw.get("timestamp", "")),
            "players": players,
        }
    except Exception as e:
        logger.error("Parse match error: %s", e)
        return None


# ── Tier 2: Playwright DOM fallback ───────────────────────────────────────────

async def _playwright_dom_fetch(max_matches: int = 10) -> dict:
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
            await page.goto(PCT_URL, wait_until="domcontentloaded", timeout=45_000)
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
        result = "W" if card.get("result","").upper()=="WIN" else ("D" if "DRAW" in card.get("result","").upper() else "L")
        matches.append({
            "match_id": f"dom_{our_goals}_{opp_goals}_{len(matches)}",
            "timestamp": 0, "date": "—",
            "our_name": "Rachad L3ERGONI", "opp_name": opp_name,
            "our_goals": our_goals, "opp_goals": opp_goals,
            "result": result, "players": [], "raw": card, "_from_dom": True,
        })

    if matches:
        return {"matches": matches, "members": [], "club_info": {}, "club_stats": {}}
    return {}


# ── Public API ─────────────────────────────────────────────────────────────────

async def fetch_all(max_matches: int = 5, force: bool = False) -> dict:
    global _cache, _cache_ts

    async with _cache_lock:
        if not force:
            cached = get_cached(max_matches)
            if cached:
                age = int(cache_age_seconds())
                logger.info("📦 Cache hit (%ds old) — %d matches", age, len(cached.get("matches",[])))
                return cached

        try:
            data = await asyncio.wait_for(_pct_api_fetch(max_matches=10), timeout=25)
            if data.get("matches"):
                _cache = {"raw": data}
                _cache_ts = time.time()
                logger.info("✅ Cache updated — %d matches stored", len(data["matches"]))
                data["matches"] = data["matches"][:max_matches]
                return data
            logger.info("PCT API returned no matches — trying Playwright")
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning("PCT API failed: %s", e)

        try:
            data = await asyncio.wait_for(_playwright_dom_fetch(max_matches=10), timeout=75)
            if data.get("matches"):
                _cache = {"raw": data}
                _cache_ts = time.time()
                data["matches"] = data["matches"][:max_matches]
                return data
        except (asyncio.TimeoutError, Exception) as e:
            logger.error("Playwright DOM failed: %s", e)

        logger.error("All data sources failed")
        return {"matches": [], "members": [], "club_info": {}, "club_stats": {}}
