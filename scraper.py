"""
Rachad L3ERGONI Bot - ProClubsTracker Scraper
"""

import os
import json
import asyncio
import subprocess
import sys
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple


class ProClubsTrackerScraper:
    BASE_URL = "https://proclubstracker.com"
    
    def __init__(self, club_id: str, platform: str = "common-gen5", division: str = "6"):
        self.club_id = str(club_id)
        self.platform = platform
        self.division = division
        self.club_url = f"{self.BASE_URL}/club/{self.club_id}?platform={self.platform}&div={self.division}"
    
    def _ensure_browsers(self) -> bool:
        home = os.path.expanduser("~")
        paths = [
            os.path.join(home, ".cache", "ms-playwright", "chromium-1223", "chrome-linux", "chrome"),
            "/opt/render/.cache/ms-playwright/chromium-1223/chrome-linux/chrome",
        ]
        for path in paths:
            if os.path.exists(path):
                return True
        
        try:
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], 
                         capture_output=True, timeout=180)
            return True
        except:
            return False
    
    async def scrape_all(self) -> Dict[str, Any]:
        if not self._ensure_browsers():
            return {"matches": [], "players": [], "error": "No browsers"}
        
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
                context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
                page = await context.new_page()
                
                await page.goto(self.club_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(5)
                
                tables = await page.query_selector_all('table')
                all_matches = []
                all_players = []
                
                for table in tables:
                    rows = await table.query_selector_all('tr')
                    for row in rows:
                        cells = await row.query_selector_all('td')
                        if len(cells) >= 2:
                            row_dict = {f"col_{i}": (await cell.inner_text()).strip() for i, cell in enumerate(cells)}
                            # Classify
                            text = " ".join(row_dict.values()).lower()
                            if any(w in text for w in ["opponent", "vs", "win", "loss", "score"]):
                                all_matches.append(row_dict)
                            elif any(w in text for w in ["player", "goals", "assists", "rating"]):
                                all_players.append(row_dict)
                
                await browser.close()
                return {"matches": all_matches, "players": all_players}
        except Exception as e:
            return {"matches": [], "players": [], "error": str(e)}
    
    def _parse_score(self, score_str: str) -> Tuple[int, int]:
        try:
            clean = score_str.replace(" ", "").replace("–", "-")
            if "-" in clean:
                parts = clean.split("-")
                return int(parts[0]), int(parts[1])
        except:
            pass
        return 0, 0
    
    def _convert_match(self, raw: Dict, players: List[Dict]) -> Optional[Dict]:
        try:
            vals = list(raw.values())
            opponent = vals[1] if len(vals) > 1 else "Unknown"
            score_str = next((v for v in vals if "-" in v and any(c.isdigit() for c in v)), "0-0")
            team_goals, opp_goals = self._parse_score(score_str)
            result = "win" if team_goals > opp_goals else "loss" if team_goals < opp_goals else "draw"
            
            return {
                "match_id": f"pct_{hash(str(raw)) % 10000000}",
                "timestamp": int(datetime.now().timestamp()),
                "match_time": datetime.now().isoformat(),
                "opponent": opponent,
                "team_goals": team_goals,
                "opponent_goals": opp_goals,
                "result": result,
                "match_type": "gameType9",
                "player_stats": {},
            }
        except:
            return None
    
    async def sync_to_stats_engine(self, stats_engine, count: int = 10) -> int:
        data = await self.scrape_all()
        if data.get("error"):
            return 0
        
        added = 0
        for match in data.get("matches", [])[:count]:
            parsed = self._convert_match(match, data.get("players", []))
            if parsed and not stats_engine.match_exists(parsed["match_id"]):
                stats_engine.add_match(parsed)
                added += 1
        
        return added
    
    async def check_new_match(self) -> Optional[Dict]:
        data = await self.scrape_all()
        matches = data.get("matches", [])
        if matches:
            return self._convert_match(matches[0], data.get("players", []))
        return None


def get_scraper(club_id: str, platform: str = "common-gen5", division: str = "6"):
    return ProClubsTrackerScraper(club_id, platform, division)
