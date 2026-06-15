import os
import asyncio
import json
import re
import traceback
from datetime import datetime
from typing import Optional
from models import ClubStats, PlayerStats, MatchResult

# CRITICAL: Set these BEFORE importing playwright
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/app/ms-playwright"
os.environ["PLAYWRIGHT_CHROMIUM_USE_HEADLESS_SHELL"] = "0"

print(f"🔧 PLAYWRIGHT_BROWSERS_PATH set to: {os.environ.get('PLAYWRIGHT_BROWSERS_PATH')}")
print(f"🔧 PLAYWRIGHT_CHROMIUM_USE_HEADLESS_SHELL set to: {os.environ.get('PLAYWRIGHT_CHROMIUM_USE_HEADLESS_SHELL')}")

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

try:
    from playwright_stealth import stealth_async
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False


class ProClubsTrackerScraper:
    def __init__(self, club_url: str, headless: bool = True, use_stealth: bool = True):
        self.club_url = club_url
        self.headless = headless
        self.use_stealth = use_stealth and HAS_STEALTH
        self.browser = None
        self.context = None
        self.page = None
        self._cookie_file = "pct_cookies.json"
        self._last_error = None
    
    async def _scrape_http(self) -> Optional[ClubStats]:
        if not HAS_HTTPX:
            print("🌐 HTTP fallback: httpx not installed")
            return None
        try:
            print(f"🌐 HTTP fallback: GET {self.club_url}")
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(self.club_url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                })
                print(f"🌐 HTTP status: {response.status_code}")
                if response.status_code != 200:
                    return None
                html = response.text
                print(f"🌐 HTTP response length: {len(html)} chars")
                return self._parse_html(html)
        except Exception as e:
            print(f"⚠️ HTTP fallback failed: {e}")
            traceback.print_exc()
            return None
    
    def _parse_html(self, html: str) -> Optional[ClubStats]:
        club = ClubStats(club_name="Rachad L3ERGONI", last_updated=datetime.now())
        # Try JSON in scripts
        for pattern in [r'window\.__INITIAL_STATE__\s*=\s*({.+?});', r'"players":\s*(\[.+?\])', r'"club":\s*({.+?})']:
            m = re.search(pattern, html, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(1))
                    if isinstance(data, dict) and "players" in data:
                        for p in data["players"]:
                            name = p.get("name", "")
                            if name:
                                player = PlayerStats(name=name)
                                player.games = int(p.get("games", 0))
                                player.goals = int(p.get("goals", 0))
                                player.assists = int(p.get("assists", 0))
                                player.rating = float(p.get("rating", 0))
                                player.pass_accuracy = float(p.get("passAccuracy", 0))
                                club.players.append(player)
                        if club.players:
                            print(f"✅ HTTP: parsed {len(club.players)} players from JSON")
                            return club
                except Exception:
                    continue
        # Parse HTML table
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
        for row in rows:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if len(cells) >= 3:
                clean = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
                name = clean[0]
                if name and name.lower() not in ["player", "name", "member", ""]:
                    p = PlayerStats(name=name)
                    all_text = " ".join(clean)
                    rm = re.search(r'(\d+\.\d+)', all_text)
                    if rm:
                        p.rating = float(rm.group(1))
                    pm = re.search(r'(\d+\.?\d*)%', all_text)
                    if pm:
                        p.pass_accuracy = float(pm.group(1))
                    club.players.append(p)
        if club.players:
            print(f"✅ HTTP: parsed {len(club.players)} players from HTML table")
            return club
        print("⚠️ HTTP: no players found in HTML")
        return None
    
    async def _init_browser(self):
        if not HAS_PLAYWRIGHT:
            raise RuntimeError("Playwright not installed")
        print("🎭 Initializing Playwright browser...")
        
        # Check if browser exists before launching
        browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
        print(f"🎭 Looking for browsers in: {browsers_path}")
        if browsers_path and os.path.exists(browsers_path):
            import glob
            chrome_files = glob.glob(f"{browsers_path}/**/chrome*", recursive=True)
            print(f"🎭 Found {len(chrome_files)} chrome files: {chrome_files[:3]}")
        else:
            print(f"⚠️ Browsers path does not exist: {browsers_path}")
        
        pw = await async_playwright().start()
        print("🎭 Playwright started")
        
        print("🎭 Launching Chromium...")
        self.browser = await pw.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",
                "--disable-background-networking",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-features=site-per-process",
                "--disable-features=IsolateOrigins",
                "--disable-blink-features=AutomationControlled",
            ]
        )
        print("🎭 Chromium launched")
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        try:
            with open(self._cookie_file, "r", encoding="utf-8") as f:
                await self.context.add_cookies(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        self.page = await self.context.new_page()
        if self.use_stealth:
            await stealth_async(self.page)
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            window.chrome = { runtime: {} };
        """)
        print("🎭 Browser ready")
    
    async def _save_cookies(self):
        if self.context:
            try:
                cookies = await self.context.cookies()
                with open(self._cookie_file, "w", encoding="utf-8") as f:
                    json.dump(cookies, f)
            except Exception:
                pass
    
    async def _safe_click(self, selector: str, timeout: int = 3000):
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            await self.page.click(selector)
            await asyncio.sleep(0.5)
            return True
        except Exception:
            return False
    
    async def _extract_text(self, selector: str) -> str:
        try:
            el = await self.page.query_selector(selector)
            if el:
                return (await el.text_content() or "").strip()
        except Exception:
            pass
        return ""
    
    async def _parse_player_table(self, club: ClubStats):
        headers = await self.page.query_selector_all("table thead th, [role='columnheader']")
        header_texts = [(await h.text_content() or "").strip().lower() for h in headers]
        col_map = {}
        for i, h in enumerate(header_texts):
            if any(x in h for x in ["name", "player"]): col_map["name"] = i
            elif any(x in h for x in ["rating", "avg"]): col_map["rating"] = i
            elif any(x in h for x in ["games", "gp", "played"]): col_map["games"] = i
            elif any(x in h for x in ["goals", "gls"]): col_map["goals"] = i
            elif any(x in h for x in ["assists", "ast"]): col_map["assists"] = i
            elif any(x in h for x in ["pass %", "pass accuracy"]): col_map["pass_accuracy"] = i
            elif any(x in h for x in ["tackle", "tkl"]): col_map["tackles"] = i
            elif any(x in h for x in ["interception", "int"]): col_map["interceptions"] = i
            elif any(x in h for x in ["possession", "poss lost"]): col_map["possession_losses"] = i
            elif any(x in h for x in ["motm", "man of the match"]): col_map["motm"] = i
            elif any(x in h for x in ["distance", "km"]): col_map["distance"] = i
            elif any(x in h for x in ["minutes", "min"]): col_map["minutes"] = i
        
        rows = await self.page.query_selector_all("table tbody tr, .player-row, tr[data-player]")
        print(f"🎭 Found {len(rows)} player rows")
        for row in rows:
            try:
                cells = await row.query_selector_all("td, .stat-cell")
                if len(cells) < 3:
                    continue
                texts = [(await c.text_content() or "").strip() for c in cells]
                def get_col(key, default_idx=0):
                    idx = col_map.get(key, default_idx)
                    return texts[idx] if 0 <= idx < len(texts) else ""
                name = get_col("name", 0)
                if not name or name.lower() in ["player", "name", "member"]:
                    continue
                p = PlayerStats(name=name)
                all_text = " ".join(texts)
                rm = re.search(r'(\d+\.\d+)', get_col("rating", 1)) or re.search(r'(\d+\.\d+)', all_text)
                if rm:
                    p.rating = float(rm.group(1))
                for field, pattern in [
                    ("games", r'(\d+)'), ("goals", r'(\d+)'), ("assists", r'(\d+)'),
                    ("tackles", r'(\d+)'), ("interceptions", r'(\d+)'),
                    ("possession_losses", r'(\d+)'), ("motm", r'(\d+)'), ("minutes_played", r'(\d+)'),
                ]:
                    txt = get_col(field, 0)
                    m = re.search(pattern, txt)
                    if m:
                        setattr(p, field, int(m.group(1)))
                pm = re.search(r'(\d+\.?\d*)%', get_col("pass_accuracy", 0)) or re.search(r'(\d+\.?\d*)%', all_text)
                if pm:
                    p.pass_accuracy = float(pm.group(1))
                dm = re.search(r'(\d+\.?\d*)', get_col("distance", 0))
                if dm:
                    p.distance_covered = float(dm.group(1))
                sm = re.search(r'(\d+)', get_col("shots", 0))
                if sm:
                    p.shots = int(sm.group(1))
                club.players.append(p)
            except Exception:
                continue
        print(f"🎭 Parsed {len(club.players)} players from table")
    
    async def _scrape_playwright(self) -> Optional[ClubStats]:
        if not HAS_PLAYWRIGHT:
            print("❌ Playwright not installed")
            return None
        try:
            if not self.browser:
                await self._init_browser()
        except Exception as e:
            self._last_error = f"Browser init failed: {e}"
            print(f"❌ Browser init failed: {e}")
            traceback.print_exc()
            return None
        
        for attempt in range(2):
            try:
                print(f"🎭 Navigating to {self.club_url} (attempt {attempt+1})...")
                await self.page.goto(self.club_url, wait_until="domcontentloaded", timeout=20000)
                print(f"🎭 Page loaded, waiting 2s...")
                await asyncio.sleep(2)
                
                club = ClubStats(club_name="Rachad L3ERGONI", last_updated=datetime.now())
                try:
                    title = await self._extract_text("h1, .club-name, .title")
                    if title:
                        club.club_name = title
                        print(f"🎭 Club name: {title}")
                except Exception:
                    pass
                
                try:
                    div_text = await self._extract_text(".division, [data-testid='division']")
                    skill_text = await self._extract_text(".skill-rating, [data-testid='skill-rating']")
                    record_text = await self._extract_text(".record, [data-testid='record']")
                    dm = re.search(r'(\d+)', div_text)
                    club.division = int(dm.group(1)) if dm else 6
                    sm = re.search(r'(\d+)', skill_text)
                    club.skill_rating = int(sm.group(1)) if sm else 0
                    rms = re.findall(r'(\d+)', record_text)
                    if len(rms) >= 3:
                        club.wins, club.losses, club.draws = int(rms[0]), int(rms[1]), int(rms[2])
                    print(f"🎭 Club record: {club.wins}W {club.losses}L {club.draws}D")
                except Exception as e:
                    print(f"⚠️ Could not parse club stats: {e}")
                
                print("🎭 Clicking Players tab...")
                await self._safe_click("button:has-text('Players'), [data-testid='players-tab']")
                await asyncio.sleep(1.5)
                await self._parse_player_table(club)
                
                print("🎭 Clicking Match History...")
                await self._safe_click("button:has-text('Match History'), [data-testid='matches-tab']")
                await asyncio.sleep(1.5)
                match_rows = await self.page.query_selector_all("table tbody tr, .match-row")
                matches = []
                for i, row in enumerate(match_rows[:20]):
                    try:
                        cells = await row.query_selector_all("td, .match-cell")
                        texts = [(await c.text_content() or "").strip() for c in cells]
                        all_text = " ".join(texts)
                        scm = re.search(r'(\d+)\s*-\s*(\d+)', all_text)
                        if scm:
                            sf, sa = int(scm.group(1)), int(scm.group(2))
                            res = "W" if sf > sa else "L" if sf < sa else "D"
                            om = re.search(r'vs\.?\s*([A-Za-z0-9\s_\-]+)', all_text, re.I)
                            opp = om.group(1).strip() if om else "Unknown"
                            matches.append(MatchResult(match_id=f"m{i}", date=datetime.now(), opponent=opp, score_for=sf, score_against=sa, result=res))
                    except Exception:
                        continue
                club.matches = matches
                print(f"🎭 Found {len(matches)} matches")
                
                await self._save_cookies()
                if club.players:
                    print(f"✅ Playwright: {len(club.players)} players scraped")
                    return club
                print("⚠️ Playwright: no players found")
                return None
            except Exception as e:
                print(f"🎭 Playwright attempt {attempt+1} failed: {e}")
                traceback.print_exc()
                if attempt < 1:
                    await asyncio.sleep(3)
                else:
                    self._last_error = f"Playwright failed: {e}"
                    return None
        return None
    
    async def scrape_club(self) -> Optional[ClubStats]:
        print(f"🔍 Starting scrape of {self.club_url}")
        # Try HTTP first
        club = await self._scrape_http()
        if club and club.players:
            return club
        # Try Playwright
        print("🔍 HTTP failed, trying Playwright...")
        club = await self._scrape_playwright()
        if club and club.players:
            return club
        print(f"❌ All scraping methods failed. Last error: {self._last_error}")
        return None
    
    async def close(self):
        try:
            await self._save_cookies()
            if self.browser:
                await self.browser.close()
        except Exception:
            pass
