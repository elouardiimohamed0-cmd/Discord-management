import os
import asyncio
import json
import gzip
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import httpx
from data_store import DataStore
from browser_manager import BrowserManager

logger = logging.getLogger("rachad_bot.scraper_service")

CLUB_ID = os.environ.get("CLUB_ID", "1427607")
PLATFORM = os.environ.get("PCT_PLATFORM", "common-gen5")
PCT_API_URL = f"https://proclubstracker.com/api/clubs/{CLUB_ID}?platform={PLATFORM}"
PCT_PAGE_URL = os.environ.get("PCT_CLUB_URL", f"https://proclubstracker.com/club/{CLUB_ID}?platform={PLATFORM}&div=6")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html,*/*",
    "Referer": "https://proclubstracker.com/",
    "Accept-Language": "en-US,en;q=0.9",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

class ScraperService:
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.store = DataStore()
        self.browser = BrowserManager()
        self._min_interval = 600
        self._max_per_hour = 6
        self._hourly_window = 3600
        self._cooldown_until = 0
        self._cooldown_duration = 3600
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3
        self._request_count = 0
        self._window_start = time.time()
        self._last_scrape = 0
        self._http_client = None
        self._mem_cache = None
        self._cache_time = 0
        self._cache_ttl = 600
        self._initialized = True
        logger.info("ScraperService initialized")

    async def _get_client(self):
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                headers=HEADERS, follow_redirects=True,
                timeout=httpx.Timeout(15.0, connect=5.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._http_client

    def _in_cooldown(self):
        return time.time() < self._cooldown_until

    def _rate_limited(self):
        now = time.time()
        if now - self._window_start > self._hourly_window:
            self._request_count = 0
            self._window_start = now
        return self._request_count >= self._max_per_hour

    def _interval_ok(self):
        return time.time() - self._last_scrape >= self._min_interval

    def _enter_cooldown(self, reason=""):
        self._cooldown_until = time.time() + self._cooldown_duration
        self._consecutive_failures += 1
        logger.warning("[COOLDOWN] %s | Failures: %d | Duration: %ds", reason, self._consecutive_failures, self._cooldown_duration)

    async def get_club_data(self, force=False, source="unknown"):
        now = time.time()

        # 1. Memory cache
        if self._mem_cache and (now - self._cache_time) < self._cache_ttl:
            logger.info("[CACHE] Memory hit (age %ds)", int(now - self._cache_time))
            return self._mem_cache

        # 2. Database
        db = await asyncio.to_thread(self.store.get_latest_snapshot)
        if db:
            self._mem_cache = db
            self._cache_time = now
            age = 0
            try:
                age = int(now - datetime.fromisoformat(db["scraped_at"]).timestamp())
            except Exception:
                pass
            logger.info("[CACHE] DB hit (age %ds)", age)
            if age < 900:
                return db

        # 3. Can we scrape?
        if self._in_cooldown():
            rem = int(self._cooldown_until - now)
            logger.warning("[BLOCKED] Cooldown %ds | Source: %s", rem, source)
            await asyncio.to_thread(self.store.log_scrape, source, False, f"Cooldown {rem}s", 0)
            return db

        if self._rate_limited():
            logger.warning("[BLOCKED] Hourly limit %d/%d | Source: %s", self._request_count, self._max_per_hour, source)
            await asyncio.to_thread(self.store.log_scrape, source, False, "Hourly limit", 0)
            return db

        if not force and not self._interval_ok():
            wait = int(self._min_interval - (now - self._last_scrape))
            logger.info("[BLOCKED] Interval wait %ds | Source: %s", wait, source)
            return db

        # 4. Scrape
        logger.info("[SCRAPE] Starting | Source: %s", source)
        result = await self._scrape(source)
        if result:
            self._mem_cache = result
            self._cache_time = now
            self._last_scrape = now
            self._consecutive_failures = 0
            return result
        else:
            self._enter_cooldown("Scrape failed")
            return db

    async def _scrape(self, source):
        self._request_count += 1
        reqs = 1

        # Try HTTP
        data = await self._fetch_api()
        if data:
            logger.info("[SCRAPE] API ok | reqs: %d", reqs)
            await asyncio.to_thread(self.store.log_scrape, source, True, "", reqs)
            return data

        # Too many failures?
        if self._consecutive_failures >= self._max_consecutive_failures:
            logger.error("[SCRAPE] Max failures reached")
            await asyncio.to_thread(self.store.log_scrape, source, False, "Max failures", reqs)
            return None

        # Try browser
        reqs += 1
        data = await self._fetch_browser()
        if data:
            logger.info("[SCRAPE] Browser ok | reqs: %d", reqs)
            await asyncio.to_thread(self.store.log_scrape, source, True, "browser", reqs)
            return data

        logger.error("[SCRAPE] All failed | reqs: %d", reqs)
        await asyncio.to_thread(self.store.log_scrape, source, False, "All failed", reqs)
        return None

    async def _fetch_api(self):
        try:
            c = await self._get_client()
            logger.info("[HTTP] GET %s", PCT_API_URL)
            r = await c.get(PCT_API_URL)
            if r.status_code == 429:
                self._enter_cooldown("PCT API 429")
                return None
            if r.status_code == 403:
                self._enter_cooldown("PCT API 403/CF")
                return None
            if r.status_code != 200:
                logger.warning("[HTTP] Status %d", r.status_code)
                return None

            raw = r.content

            # Check for HTML/Cloudflare challenge
            if raw[:100].strip().startswith(b"<") or b"cloudflare" in raw[:500].lower():
                logger.warning("[HTTP] HTML/CF challenge. First 200 bytes: %s", raw[:200])
                self._enter_cooldown("Cloudflare HTML response")
                return None

            # Manual decompression fallback
            ce = r.headers.get("content-encoding", "").lower()
            if raw[:2] == b'\x1f\x8b' or "gzip" in ce:
                try:
                    raw = gzip.decompress(raw)
                    logger.info("[HTTP] Decompressed gzip")
                except Exception as e:
                    logger.warning("[HTTP] gzip decompress failed: %s", e)
            elif raw[:4] == b'\x28\xb5\x2f\xfd' or "br" in ce:
                try:
                    import brotli
                    raw = brotli.decompress(raw)
                    logger.info("[HTTP] Decompressed brotli")
                except Exception:
                    logger.warning("[HTTP] brotli not available or failed")

            # Try parsing JSON
            try:
                data = json.loads(raw)
            except Exception:
                try:
                    text = raw.decode("utf-8", errors="replace")
                    data = json.loads(text)
                except Exception as e2:
                    logger.error("[HTTP] JSON parse fail. First 500 bytes (hex): %s", raw[:500].hex()[:200])
                    logger.error("[HTTP] Decode error: %s", e2)
                    return None

            if not isinstance(data, dict):
                logger.error("[HTTP] Response not dict: %s", type(data))
                return None

            logger.info("[HTTP] Success (keys: %s)", list(data.keys())[:5])
            return self._parse(data)
        except httpx.TimeoutException:
            return None
        except Exception as e:
            logger.error("[HTTP] Error: %s", e)
            return None

    async def _fetch_browser(self):
        page = await self.browser.get_page()
        if not page:
            return None
        try:
            await page.goto(PCT_PAGE_URL, wait_until="networkidle", timeout=30000)
            try:
                await page.wait_for_selector("text=Club Stats", timeout=10000)
            except Exception:
                pass

            data = await page.evaluate("""
                () => { return window.__INITIAL_STATE__ || window.__DATA__ || window.clubData || null; }
            """)
            if data and isinstance(data, dict):
                await self.browser.save_session()
                return self._parse(data)

            # Fallback API via page
            try:
                api = await page.evaluate(f"""
                    async () => {{
                        try {{
                            const r = await fetch("{PCT_API_URL}", {{headers:{{"Accept":"application/json"}}}});
                            return await r.json();
                        }} catch(e) {{ return null; }}
                    }}
                """)
                if api and isinstance(api, dict):
                    await self.browser.save_session()
                    return self._parse(api)
            except Exception:
                pass
            return None
        except Exception as e:
            logger.error("[BROWSER] Error: %s", e)
            return None

    def _parse(self, raw):
        """
        Parse PCT API response.
        Uses memberStats (season totals) for REAL website stats.
        Match data supplements missing fields like minutes_played, shots, saves.
        """
        try:
            info = raw.get("clubInfoData") or {}
            club = info.get(str(CLUB_ID)) or next(iter(info.values()), {})
            overall = raw.get("overallStats") or {}

            res = {
                "club_name": club.get("name") or club.get("clubName") or "Rachad L3ERGONI",
                "division": self._int(overall.get("bestDivision") or club.get("divisionId"), 6),
                "skill_rating": self._int(overall.get("skillRating") or club.get("skillRating"), 0),
                "wins": self._int(overall.get("wins"), 0),
                "losses": self._int(overall.get("losses"), 0),
                "draws": self._int(overall.get("ties"), 0),
                "goals_scored": self._int(overall.get("goals"), 0),
                "goals_conceded": self._int(overall.get("goalsAgainst"), 0),
                "win_rate": 0.0,
                "players": [],
                "matches": [],
                "scraped_at": datetime.now().isoformat(),
            }

            g = res["wins"] + res["losses"] + res["draws"]
            if g > 0:
                res["win_rate"] = round((res["wins"] / g) * 100, 1)

            # ─── STEP 1: Aggregate match data to supplement missing season stats ───
            raw_matches = raw.get("matches") or {}
            all_m = (
                (raw_matches.get("league", []) or [])
                + (raw_matches.get("playoff", []) or [])
                + (raw_matches.get("friendly", []) or [])
            )

            match_agg = {}
            for rm in all_m[:30]:
                our_id = str(CLUB_ID)
                players = rm.get("players", {}).get(our_id, {})
                for pid, p in players.items():
                    name = p.get("playername", "Unknown")
                    if name not in match_agg:
                        match_agg[name] = {
                            "games": 0,
                            "minutes": 0,
                            "shots": 0,
                            "pass_attempts": 0,
                            "pass_completed": 0,
                            "tackles": 0,
                            "saves": 0,
                            "goals_conceded": 0,
                            "redcards": 0,
                            "clean_sheets": 0,
                        }
                    a = match_agg[name]
                    a["games"] += 1
                    a["minutes"] += self._int(p.get("secondsPlayed"), 0) // 60
                    a["shots"] += self._int(p.get("shots"), 0)
                    a["pass_attempts"] += self._int(p.get("passattempts"), 0)
                    a["pass_completed"] += self._int(p.get("passesmade"), 0)
                    a["tackles"] += self._int(p.get("tacklesmade"), 0)
                    a["saves"] += self._int(p.get("saves"), 0)
                    a["goals_conceded"] += self._int(p.get("goalsconceded"), 0)
                    a["redcards"] += self._int(p.get("redcards"), 0)
                    a["clean_sheets"] += self._int(p.get("cleansheetsany"), 0)

            # ─── STEP 2: REAL PLAYER STATS from memberStats (season totals) ───
            member_stats = raw.get("memberStats") or {}
            members = member_stats.get("members", [])

            for m in members:
                if not isinstance(m, dict):
                    continue
                name = m.get("proName") or m.get("name")
                if not name or not isinstance(name, str) or not name.strip():
                    continue

                games = self._int(m.get("gamesPlayed"), 0)
                if games == 0:
                    logger.debug("[FILTER] Excluding %s: 0 games played this season", name)
                    continue

                rating = self._float(m.get("ratingAve"), 0.0)
                if rating > 10:
                    rating = round(rating / 10.0, 2)

                # ── Pass accuracy: API gives it directly as a percentage ──
                pass_acc = self._float(m.get("passSuccessRate"), 0.0)

                # ── Possession losses: derive from passesMade + passSuccessRate ──
                passes_made = self._int(m.get("passesMade"), 0)
                if pass_acc > 0 and passes_made > 0:
                    pass_attempts = round(passes_made / (pass_acc / 100.0))
                    possession_losses = max(0, pass_attempts - passes_made)
                else:
                    possession_losses = 0

                # ── Match data supplements (minutes, shots, saves, etc.) ──
                agg = match_agg.get(name, {})
                minutes_played = agg.get("minutes", 0)
                shots = agg.get("shots", 0)
                saves = agg.get("saves", 0)
                goals_conceded = agg.get("goals_conceded", 0)

                # Cards: prefer memberStats redCards, fallback to match aggregation
                cards = self._int(m.get("redCards"), 0)
                if cards == 0:
                    cards = agg.get("redcards", 0)

                # Clean sheets: prefer memberStats, fallback to match data
                clean_sheets = self._int(m.get("cleanSheetsDef"), 0) + self._int(m.get("cleanSheetsGK"), 0)
                if clean_sheets == 0:
                    clean_sheets = agg.get("clean_sheets", 0)

                # Tackles from API (correct camelCase)
                tackles = self._int(m.get("tacklesMade"), 0)

                res["players"].append({
                    "name": name.strip(),
                    "games": games,
                    "goals": self._int(m.get("goals"), 0),
                    "assists": self._int(m.get("assists"), 0),
                    "shots": shots,
                    "rating": rating,
                    "tackles": tackles,
                    "interceptions": 0,          # Not available in PCT API
                    "minutes_played": minutes_played,
                    "motm": self._int(m.get("manOfTheMatch"), 0),
                    "pass_accuracy": pass_acc,
                    "passes_made": passes_made,
                    "possession_losses": possession_losses,
                    "distance_covered": 0.0,     # Not available in PCT API
                    "cards": cards,
                    "clean_sheets": clean_sheets,
                    "saves": saves,
                    "goals_conceded": goals_conceded,
                    "win_rate": self._float(m.get("winRate"), 0.0),
                })

            logger.info("[PARSE] %s | Players from memberStats (season totals): %d",
                        res["club_name"], len(res["players"]))
            logger.info("[PARSE] Players: %s", [p["name"] for p in res["players"]])

            # ─── STEP 3: Parse matches (for match history only) ───
            for rm in all_m[:30]:
                try:
                    m = self._match(rm)
                    if m:
                        res["matches"].append(m)
                except Exception:
                    pass

            logger.info("[PARSE] Matches parsed: %d", len(res["matches"]))

            # Save async
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(asyncio.to_thread(self.store.save_snapshot, res))
                else:
                    asyncio.run(asyncio.to_thread(self.store.save_snapshot, res))
            except Exception as e:
                logger.warning("[SAVE] Async save failed: %s", e)

            return res
        except Exception as e:
            logger.error("[PARSE] Error: %s", e)
            return None

    def _match(self, raw):
        try:
            our_id = str(CLUB_ID)
            clubs = raw.get("clubs", {})
            ours, opp = None, None
            for cid, c in clubs.items():
                if str(cid) == our_id:
                    ours = c
                else:
                    opp = c
            if not ours:
                return None
            gf = self._int(ours.get("goals"), 0)
            ga = self._int(ours.get("goalsAgainst"), 0)
            r = "W" if gf > ga else "L" if gf < ga else "D"
            ts = raw.get("timestamp")
            ds = datetime.now().isoformat()
            if ts:
                try:
                    ds = datetime.fromtimestamp(int(ts)).isoformat()
                except Exception:
                    pass
            return {
                "match_id": str(raw.get("matchId", ts or "")),
                "date": ds,
                "opponent": (opp.get("details", {}).get("name", "Unknown") if opp else "Unknown"),
                "score_for": gf,
                "score_against": ga,
                "result": r,
            }
        except Exception:
            return None

    def _int(self, v, d=0):
        try:
            return int(float(str(v))) if v is not None else d
        except Exception:
            return d

    def _float(self, v, d=0.0):
        try:
            return float(str(v)) if v is not None else d
        except Exception:
            return d

    def metrics(self):
        now = time.time()
        return {
            "cooldown": self._in_cooldown(),
            "cooldown_remaining": max(0, int(self._cooldown_until - now)),
            "rate_limited": self._rate_limited(),
            "requests_hour": self._request_count,
            "last_scrape_age": int(now - self._last_scrape) if self._last_scrape else -1,
            "failures": self._consecutive_failures,
            "cache_age": int(now - self._cache_time) if self._cache_time else -1,
        }

    async def db_stats(self):
        return await asyncio.to_thread(self.store.get_scrape_stats, 24)

    async def close(self):
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
        await self.browser.close()
