import asyncio
import json
import re
import traceback
from datetime import datetime
from typing import Optional, List
from models import ClubStats, PlayerStats, MatchResult

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
    
    async def _init_browser(self):
        if not HAS_PLAYWRIGHT:
            raise RuntimeError("Playwright not installed")
        
        pw = await async_playwright().start()
        self.browser = await pw.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",
            ]
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        try:
            with open(self._cookie_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)
                await self.context.add_cookies(cookies)
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
        headers = await self.page.query_selector_all("table thead th, .table-header-cell, [role='columnheader']")
        header_texts = []
        for h in headers:
            t = await h.text_content()
            header_texts.append((t or "").strip().lower())
        
        col_map = {}
        for i, h in enumerate(header_texts):
            if any(x in h for x in ["name", "player", "member"]):
                col_map["name"] = i
            elif any(x in h for x in ["rating", "avg", "match rating"]):
                col_map["rating"] = i
            elif any(x in h for x in ["games", "gp", "played", "matches", "apps"]):
                col_map["games"] = i
            elif any(x in h for x in ["goals", "gls", "g"]):
                col_map["goals"] = i
            elif any(x in h for x in ["assists", "ast", "a"]):
                col_map["assists"] = i
            elif any(x in h for x in ["shot", "sh", "sho"]):
                col_map["shots"] = i
            elif any(x in h for x in ["pass %", "pass accuracy", "passacc", "pass%"]):
                col_map["pass_accuracy"] = i
            elif any(x in h for x in ["tackle", "tkl", "tackles"]):
                col_map["tackles"] = i
            elif any(x in h for x in ["interception", "int", "interceptions"]):
                col_map["interceptions"] = i
            elif any(x in h for x in ["possession", "poss lost", "dispossessed", "losses"]):
                col_map["possession_losses"] = i
            elif any(x in h for x in ["motm", "man of the match", "mom"]):
                col_map["motm"] = i
            elif any(x in h for x in ["distance", "km", "dist", "dis"]):
                col_map["distance"] = i
            elif any(x in h for x in ["minutes", "min", "mins", "time"]):
                col_map["minutes"] = i
        
        rows = await self.page.query_selector_all("table tbody tr, .player-row, [data-testid='player-row'], tr[data-player]")
        for row in rows:
            try:
                cells = await row.query_selector_all("td, .stat-cell, [data-testid*='stat']")
                if len(cells) < 3:
                    continue
                
                texts = []
                for cell in cells:
                    t = await cell.text_content()
                    texts.append((t or "").strip())
                
                def get_col(key, default_idx=0):
                    idx = col_map.get(key, default_idx)
                    if 0 <= idx < len(texts):
                        return texts[idx]
                    return ""
                
                name = get_col("name", 0)
                if not name or name.lower() in ["player", "name", "member"]:
                    continue
                
                p = PlayerStats(name=name)
                all_text = " ".join(texts)
                
                # Extract numbers safely
                rating_match = re.search(r'(\d+\.\d+)', get_col("rating", 1)) or re.search(r'(\d+\.\d+)', all_text)
                if rating_match:
                    p.rating = float(rating_match.group(1))
                
                for field, pattern in [
                    ("games", r'(\d+)'),
                    ("goals", r'(\d+)'),
                    ("assists", r'(\d+)'),
                    ("tackles", r'(\d+)'),
                    ("interceptions", r'(\d+)'),
                    ("possession_losses", r'(\d+)'),
                    ("motm", r'(\d+)'),
                    ("minutes_played", r'(\d+)'),
                ]:
                    txt = get_col(field, 0)
                    m = re.search(pattern, txt)
                    if m:
                        setattr(p, field, int(m.group(1)))
                
                # Pass accuracy
                pass_txt = get_col("pass_accuracy", 0)
                pa = re.search(r'(\d+\.?\d*)%', pass_txt) or re.search(r'(\d+\.?\d*)%', all_text)
                if pa:
                    p.pass_accuracy = float(pa.group(1))
                
                # Distance
                dist_txt = get_col("distance", 0)
                dt = re.search(r'(\d+\.?\d*)', dist_txt)
                if dt:
                    p.distance_covered = float(dt.group(1))
                
                # Shots
                shots_txt = get_col("shots", 0)
                sh = re.search(r'(\d+)', shots_txt)
                if sh:
                    p.shots = int(sh.group(1))
                
                club.players.append(p)
            except Exception:
                continue
    
    async def scrape_club(self) -> Optional[ClubStats]:
        """Scrape ProClubsTracker. NEVER raises. Returns None on total failure."""
        if not HAS_PLAYWRIGHT:
            print("❌ Playwright not installed. Cannot scrape.")
            return None
        
        try:
            if not self.browser:
                await self._init_browser()
        except Exception as e:
            print(f"❌ Browser init failed: {e}")
            traceback.print_exc()
            return None
        
        max_retries = 2
        for attempt in range(max_retries):
            try:
                await self.page.goto(self.club_url, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(2)
                
                # Wait for any content
                try:
                    await self.page.wait_for_selector("body", timeout=5000)
                except Exception:
                    pass
                
                club = ClubStats(
                    club_name="Rachad L3ERGONI",
                    last_updated=datetime.now()
                )
                
                # Try to get club name from page
                try:
                    title = await self._extract_text("h1, .club-name, [data-testid='club-name'], .title")
                    if title:
                        club.club_name = title
                except Exception:
                    pass
                
                # Overview stats
                try:
                    div_text = await self._extract_text(".division, [data-testid='division'], .club-division")
                    skill_text = await self._extract_text(".skill-rating, [data-testid='skill-rating']")
                    record_text = await self._extract_text(".record, [data-testid='record'], .club-record")
                    
                    div_match = re.search(r'(\d+)', div_text)
                    club.division = int(div_match.group(1)) if div_match else 6
                    
                    skill_match = re.search(r'(\d+)', skill_text)
                    club.skill_rating = int(skill_match.group(1)) if skill_match else 0
                    
                    record_nums = re.findall(r'(\d+)', record_text)
                    if len(record_nums) >= 3:
                        club.wins = int(record_nums[0])
                        club.losses = int(record_nums[1])
                        club.draws = int(record_nums[2])
                except Exception:
                    pass
                
                # Players tab
                await self._safe_click("button:has-text('Players'), [data-testid='players-tab'], a:has-text('Players'), #players-tab")
                await asyncio.sleep(1.5)
                await self._parse_player_table(club)
                
                # Match History
                await self._safe_click("button:has-text('Match History'), [data-testid='matches-tab'], a:has-text('Matches'), #matches-tab")
                await asyncio.sleep(1.5)
                
                match_rows = await self.page.query_selector_all("table tbody tr, .match-row, [data-testid='match-row']")
                matches = []
                for i, row in enumerate(match_rows[:20]):
                    try:
                        cells = await row.query_selector_all("td, .match-cell")
                        texts = [(await c.text_content() or "").strip() for c in cells]
                        all_text = " ".join(texts)
                        
                        score_match = re.search(r'(\d+)\s*-\s*(\d+)', all_text)
                        if score_match:
                            score_for = int(score_match.group(1))
                            score_against = int(score_match.group(2))
                            
                            if score_for > score_against:
                                result = "W"
                            elif score_for < score_against:
                                result = "L"
                            else:
                                result = "D"
                            
                            opp_match = re.search(r'vs\.?\s*([A-Za-z0-9\s_\-]+)', all_text, re.I)
                            opponent = opp_match.group(1).strip() if opp_match else "Unknown"
                            
                            date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', all_text)
                            date_parsed = datetime.now()
                            if date_match:
                                try:
                                    date_parsed = datetime.strptime(date_match.group(1), "%d/%m/%Y")
                                except ValueError:
                                    try:
                                        date_parsed = datetime.strptime(date_match.group(1), "%m/%d/%Y")
                                    except ValueError:
                                        pass
                            
                            matches.append(MatchResult(
                                match_id=f"match_{i}",
                                date=date_parsed,
                                opponent=opponent,
                                score_for=score_for,
                                score_against=score_against,
                                result=result
                            ))
                    except Exception:
                        continue
                
                club.matches = matches
                
                # Detailed stats via modals
                for player in club.players:
                    try:
                        safe_name = player.name.replace("'", "\\'").replace('"', '\\"')
                        player_link = await self.page.query_selector(f"text='{safe_name}'")
                        if player_link:
                            await player_link.click()
                            await asyncio.sleep(0.8)
                            
                            modal_text = await self._extract_text(".modal, .player-detail, [role='dialog'], .overlay")
                            
                            for pattern, field in [
                                (r'(\d+)\s*(?:possession|Possession Losses|dispossessed)', "possession_losses"),
                                (r'(\d+)\s*(?:dribbles|Dribbles)', "dribbles"),
                                (r'(\d+)\s*(?:fouls|Fouls)', "fouls"),
                                (r'(\d+)\s*(?:cards|Cards|YC|RC|yellow|red)', "cards"),
                                (r'(\d+)\s*(?:key passes|Key Passes|key_passes)', "key_passes"),
                            ]:
                                m = re.search(pattern, modal_text, re.I)
                                if m:
                                    setattr(player, field, int(m.group(1)))
                            
                            await self._safe_click(".close, [aria-label='Close'], button:has-text('Close'), .overlay")
                            await asyncio.sleep(0.3)
                    except Exception:
                        pass
                
                await self._save_cookies()
                
                if club.players:
                    print(f"✅ Scraped {len(club.players)} players from PCT")
                    return club
                else:
                    print("⚠️ No players found in scrape")
                    return None
                    
            except Exception as e:
                print(f"Scrape attempt {attempt + 1} failed: {e}")
                traceback.print_exc()
                if attempt < max_retries - 1:
                    await asyncio.sleep(3)
                else:
                    return None
        
        return None
    
    async def close(self):
        try:
            await self._save_cookies()
            if self.browser:
                await self.browser.close()
        except Exception:
            pass
