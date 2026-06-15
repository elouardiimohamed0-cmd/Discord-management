import asyncio
import json
import re
import time
from datetime import datetime
from typing import Optional, Dict, List
from playwright.async_api import async_playwright, Page, BrowserContext
from playwright_stealth import stealth_async
from models import ClubStats, PlayerStats, MatchResult

class ProClubsTrackerScraper:
    def __init__(self, club_url: str, headless: bool = True, use_stealth: bool = True):
        self.club_url = club_url
        self.headless = headless
        self.use_stealth = use_stealth
        self.browser = None
        self.context = None
        self.page = None
        self._cookie_file = "pct_cookies.json"
    
    async def _init_browser(self):
        pw = await async_playwright().start()
        self.browser = await pw.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ]
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0"
        )
        
        # Load cookies if exist
        try:
            with open(self._cookie_file, "r") as f:
                cookies = json.load(f)
                await self.context.add_cookies(cookies)
        except FileNotFoundError:
            pass
        
        self.page = await self.context.new_page()
        
        if self.use_stealth:
            await stealth_async(self.page)
        
        # Override navigator.webdriver
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            window.chrome = { runtime: {} };
        """)
    
    async def _save_cookies(self):
        if self.context:
            cookies = await self.context.cookies()
            with open(self._cookie_file, "w") as f:
                json.dump(cookies, f)
    
    async def _safe_click(self, selector: str, timeout: int = 5000):
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
                return await el.text_content() or ""
        except Exception:
            pass
        return ""
    
    async def _extract_number(self, selector: str) -> int:
        text = await self._extract_text(selector)
        nums = re.findall(r'\d+', text.replace(',', ''))
        return int(nums[0]) if nums else 0
    
    async def _extract_float(self, selector: str) -> float:
        text = await self._extract_text(selector)
        nums = re.findall(r'\d+\.?\d*', text.replace(',', ''))
        return float(nums[0]) if nums else 0.0
    
    async def scrape_club(self) -> Optional[ClubStats]:
        if not self.browser:
            await self._init_browser()
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await self.page.goto(self.club_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(2)  # Let React/Vue hydrate
                
                # Wait for club name
                await self.page.wait_for_selector("h1, .club-name, [data-testid='club-name']", timeout=10000)
                
                club = ClubStats(
                    club_name=await self._extract_text("h1, .club-name, [data-testid='club-name']") or "Rachad L3ERGONI",
                    last_updated=datetime.now()
                )
                
                # --- OVERVIEW SECTION ---
                # Try multiple selectors for division, skill rating, record
                div_text = await self._extract_text(".division, [data-testid='division'], .club-division")
                skill_text = await self._extract_text(".skill-rating, [data-testid='skill-rating']")
                record_text = await self._extract_text(".record, [data-testid='record'], .club-record")
                
                # Parse division
                div_match = re.search(r'(\d+)', div_text)
                club.division = int(div_match.group(1)) if div_match else 6
                
                # Parse skill rating
                skill_match = re.search(r'(\d+)', skill_text)
                club.skill_rating = int(skill_match.group(1)) if skill_match else 0
                
                # Parse record (W-L-D)
                record_nums = re.findall(r'(\d+)', record_text)
                if len(record_nums) >= 3:
                    club.wins = int(record_nums[0])
                    club.losses = int(record_nums[1])
                    club.draws = int(record_nums[2])
                
                # --- PLAYERS TAB ---
                # Click players tab if exists
                await self._safe_click("button:has-text('Players'), [data-testid='players-tab'], a:has-text('Players')")
                await asyncio.sleep(1.5)
                
                # Extract player table rows
                player_rows = await self.page.query_selector_all(
                    "table tbody tr, .player-row, [data-testid='player-row'], .player-card"
                )
                
                for row in player_rows:
                    try:
                        cells = await row.query_selector_all("td, .stat-cell, [data-testid*='stat']")
                        if len(cells) < 3:
                            continue
                        
                        texts = []
                        for cell in cells:
                            t = await cell.text_content()
                            texts.append(t.strip() if t else "")
                        
                        # Try to map columns - PCT usually has: Name, Rating, Games, Goals, Assists, Shots, Pass%, etc.
                        p = PlayerStats(name=texts[0] if texts else "Unknown")
                        
                        # Extract numbers from text using regex
                        all_text = " ".join(texts)
                        
                        # Rating
                        rating_match = re.search(r'(\d+\.\d+)', all_text)
                        if rating_match:
                            p.rating = float(rating_match.group(1))
                        
                        # Games
                        games_matches = re.findall(r'(\d+)\s*(?:games|matches|played|GP)', all_text, re.I)
                        if games_matches:
                            p.games = int(games_matches[0])
                        
                        # Goals
                        goals_matches = re.findall(r'(\d+)\s*(?:goals|G)', all_text, re.I)
                        if goals_matches:
                            p.goals = int(goals_matches[0])
                        
                        # Assists  
                        ast_matches = re.findall(r'(\d+)\s*(?:assists|A)', all_text, re.I)
                        if ast_matches:
                            p.assists = int(ast_matches[0])
                        
                        # Pass accuracy
                        pass_match = re.search(r'(\d+\.?\d*)%', all_text)
                        if pass_match:
                            p.pass_accuracy = float(pass_match.group(1))
                        
                        # Shots
                        shots_match = re.search(r'(\d+)\s*(?:shots|S)', all_text, re.I)
                        if shots_match:
                            p.shots = int(shots_match.group(1))
                        
                        # Tackles
                        tack_match = re.search(r'(\d+)\s*(?:tackles|T)', all_text, re.I)
                        if tack_match:
                            p.tackles = int(tack_match.group(1))
                        
                        # Interceptions
                        int_match = re.search(r'(\d+)\s*(?:interceptions|INT)', all_text, re.I)
                        if int_match:
                            p.interceptions = int(int_match.group(1))
                        
                        # Possession losses
                        pl_match = re.search(r'(\d+)\s*(?:possession|Possession Losses)', all_text, re.I)
                        if pl_match:
                            p.possession_losses = int(pl_match.group(1))
                        
                        # MOTM
                        motm_match = re.search(r'(\d+)\s*(?:MOTM|motm|Man of the Match)', all_text, re.I)
                        if motm_match:
                            p.motm = int(motm_match.group(1))
                        
                        # Distance
                        dist_match = re.search(r'(\d+\.?\d*)\s*(?:km|miles|distance)', all_text, re.I)
                        if dist_match:
                            p.distance_covered = float(dist_match.group(1))
                        
                        # Minutes
                        min_match = re.search(r'(\d+)\s*(?:minutes|min)', all_text, re.I)
                        if min_match:
                            p.minutes_played = int(min_match.group(1))
                        
                        # Try to get position from squad mapping later
                        club.players.append(p)
                        
                    except Exception as e:
                        print(f"Error parsing player row: {e}")
                        continue
                
                # --- MATCH HISTORY TAB ---
                await self._safe_click("button:has-text('Match History'), [data-testid='matches-tab'], a:has-text('Matches')")
                await asyncio.sleep(1.5)
                
                match_rows = await self.page.query_selector_all(
                    "table tbody tr, .match-row, [data-testid='match-row']"
                )
                
                matches = []
                for i, row in enumerate(match_rows[:20]):  # Last 20 matches
                    try:
                        cells = await row.query_selector_all("td, .match-cell")
                        texts = [await c.text_content() or "" for c in cells]
                        all_text = " ".join(texts)
                        
                        # Parse score (e.g., "3 - 1")
                        score_match = re.search(r'(\d+)\s*-\s*(\d+)', all_text)
                        if score_match:
                            score_for = int(score_match.group(1))
                            score_against = int(score_match.group(2))
                            
                            # Determine result
                            if score_for > score_against:
                                result = "W"
                                club.current_streak = club.current_streak + 1 if getattr(club, '_last_result', '') == 'W' else 1
                            elif score_for < score_against:
                                result = "L"
                                club.current_streak = 0
                            else:
                                result = "D"
                                club.current_streak = 0 if getattr(club, '_last_result', '') != 'D' else club.current_streak + 1
                            
                            club._last_result = result
                            
                            # Extract opponent
                            opp_match = re.search(r'vs\.?\s*([A-Za-z0-9\s]+)', all_text, re.I)
                            opponent = opp_match.group(1).strip() if opp_match else "Unknown"
                            
                            # Extract date
                            date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', all_text)
                            date_str = date_match.group(1) if date_match else datetime.now().strftime("%d/%m/%Y")
                            
                            matches.append(MatchResult(
                                match_id=f"match_{i}",
                                date=datetime.strptime(date_str, "%d/%m/%Y") if date_match else datetime.now(),
                                opponent=opponent,
                                score_for=score_for,
                                score_against=score_against,
                                result=result
                            ))
                    except Exception as e:
                        continue
                
                # --- DETAILED PLAYER STATS (click individual players if needed) ---
                # Some stats are hidden behind player detail modals
                for player in club.players:
                    try:
                        # Find and click player name
                        player_link = await self.page.query_selector(f"text='{player.name}'")
                        if player_link:
                            await player_link.click()
                            await asyncio.sleep(1)
                            
                            # Extract additional stats from modal
                            modal_text = await self._extract_text(".modal, .player-detail, [role='dialog']")
                            
                            # Possession losses
                            pl = re.search(r'(\d+)\s*(?:possession|Possession Losses)', modal_text, re.I)
                            if pl:
                                player.possession_losses = int(pl.group(1))
                            
                            # Dribbles
                            dr = re.search(r'(\d+)\s*(?:dribbles|Dribbles)', modal_text, re.I)
                            if dr:
                                player.dribbles = int(dr.group(1))
                            
                            # Fouls
                            fl = re.search(r'(\d+)\s*(?:fouls|Fouls)', modal_text, re.I)
                            if fl:
                                player.fouls = int(fl.group(1))
                            
                            # Cards
                            cr = re.search(r'(\d+)\s*(?:cards|Cards|YC|RC)', modal_text, re.I)
                            if cr:
                                player.cards = int(cr.group(1))
                            
                            # Key passes
                            kp = re.search(r'(\d+)\s*(?:key passes|Key Passes)', modal_text, re.I)
                            if kp:
                                player.key_passes = int(kp.group(1))
                            
                            # Close modal
                            await self._safe_click(".close, [aria-label='Close'], button:has-text('Close')")
                            await asyncio.sleep(0.5)
                    except Exception:
                        pass
                
                # --- HEAD TO HEAD / COMPARISON DATA ---
                await self._safe_click("button:has-text('Head to Head'), [data-testid='h2h-tab']")
                await asyncio.sleep(1)
                
                # --- CHEMISTRY / DUO STATS ---
                await self._safe_click("button:has-text('Chemistry'), [data-testid='chemistry-tab']")
                await asyncio.sleep(1)
                
                # --- FORM GRAPHS DATA ---
                # Try to extract SVG path data or text labels
                form_text = await self._extract_text(".form-graph, [data-testid='form-graph']")
                
                # --- AWARDS / SEASON WRAPPED ---
                await self._safe_click("button:has-text('Awards'), [data-testid='awards-tab']")
                await asyncio.sleep(1)
                
                await self._save_cookies()
                return club
                
            except Exception as e:
                print(f"Scrape attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(5)
                else:
                    raise
        
        return None
    
    async def close(self):
        if self.browser:
            await self._save_cookies()
            await self.browser.close()
