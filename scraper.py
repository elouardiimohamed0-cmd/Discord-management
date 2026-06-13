"""
Rachad L3ERGONI Bot - ProClubsTracker.com Scraper v9
Handles missing Playwright browsers by installing on first run
"""

import os
import json
import asyncio
import subprocess
import sys
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple


class ProClubsTrackerScraper:
    """
    ProClubsTracker scraper with auto-install for Playwright browsers
    """

    BASE_URL = "https://proclubstracker.com"

    def __init__(self, club_id: str, platform: str = "common-gen5", division: str = "6"):
        self.club_id = str(club_id)
        self.platform = platform
        self.division = division
        self.club_url = f"{self.BASE_URL}/club/{self.club_id}?platform={self.platform}&div={self.division}"
        self._playwright_checked = False
        self._playwright_available = False

    def _ensure_playwright(self) -> bool:
        """Check if Playwright browsers are installed, install if not"""
        if self._playwright_checked:
            return self._playwright_available

        try:
            from playwright.async_api import async_playwright
            self._playwright_available = True
            self._playwright_checked = True
            return True
        except ImportError:
            print("[Scraper] Playwright not installed, installing...")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True, capture_output=True)
                from playwright.async_api import async_playwright
                self._playwright_available = True
                self._playwright_checked = True
                return True
            except Exception as e:
                print(f"[Scraper] Failed to install Playwright: {e}")
                self._playwright_checked = True
                return False

    def _install_browsers(self):
        """Install Playwright browsers if missing"""
        try:
            print("[Scraper] Installing Chromium browser...")
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=True,
                capture_output=True,
                text=True,
                timeout=120
            )
            print(f"[Scraper] Browser install output: {result.stdout}")
            return True
        except subprocess.TimeoutExpired:
            print("[Scraper] Browser install timed out")
            return False
        except Exception as e:
            print(f"[Scraper] Browser install failed: {e}")
            # Try with deps
            try:
                print("[Scraper] Trying install with deps...")
                result = subprocess.run(
                    [sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=180
                )
                print(f"[Scraper] Browser install with deps succeeded")
                return True
            except Exception as e2:
                print(f"[Scraper] Browser install with deps failed: {e2}")
                return False

    async def _init_browser(self):
        """Initialize browser with fallback options"""
        from playwright.async_api import async_playwright
        self.playwright = await async_playwright().start()

        # Try different launch options
        launch_options = [
            # Option 1: Standard headless
            {
                "headless": True,
                "args": [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--window-size=1920,1080',
                ]
            },
            # Option 2: With executable path
            {
                "headless": True,
                "executable_path": "/opt/render/.cache/ms-playwright/chromium-1223/chrome-linux/chrome",
                "args": ['--no-sandbox', '--disable-setuid-sandbox']
            },
            # Option 3: With headless shell
            {
                "headless": True,
                "executable_path": "/opt/render/.cache/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-linux64/chrome-headless-shell",
                "args": ['--no-sandbox', '--disable-setuid-sandbox']
            }
        ]

        last_error = None
        for i, options in enumerate(launch_options):
            try:
                print(f"[Scraper] Trying browser launch option {i+1}...")
                self.browser = await self.playwright.chromium.launch(**options)
                print(f"[Scraper] ✅ Browser launched with option {i+1}")
                break
            except Exception as e:
                last_error = e
                print(f"[Scraper] Option {i+1} failed: {e}")
                continue
        else:
            raise last_error if last_error else Exception("All browser launch options failed")

        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        )

        self.page = await self.context.new_page()

    async def _close_browser(self):
        if hasattr(self, 'context'):
            await self.context.close()
        if hasattr(self, 'browser'):
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

    async def scrape_all(self) -> Dict[str, Any]:
        """Scrape all data with browser install fallback"""
        if not self._ensure_playwright():
            print("[Scraper] Playwright not available")
            return {}

        # Try to init browser, install if missing
        try:
            await self._init_browser()
        except Exception as e:
            if "Executable doesn't exist" in str(e):
                print("[Scraper] Browser not found, installing...")
                if self._install_browsers():
                    await self._init_browser()
                else:
                    return {}
            else:
                raise

        try:
            print(f"[Scraper] Navigating to: {self.club_url}")
            await self.page.goto(self.club_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(5)

            title = await self.page.title()
            print(f"[Scraper] Page title: {title}")

            body_text = await self.page.inner_text("body")
            print(f"[Scraper] Body length: {len(body_text)}")

            # Extract all tables
            tables = await self.page.query_selector_all('table')
            print(f"[Scraper] Found {len(tables)} tables")

            all_data = {
                "club_id": self.club_id,
                "platform": self.platform,
                "scraped_at": datetime.now().isoformat(),
                "url": self.club_url,
                "page_title": title,
            }

            # Extract matches from tables
            matches = []
            for table in tables:
                try:
                    rows = await table.query_selector_all('tbody tr')
                    for row in rows:
                        cells = await row.query_selector_all('td')
                        if len(cells) >= 3:
                            row_data = {}
                            for i, cell in enumerate(cells):
                                text = (await cell.inner_text()).strip()
                                row_data[f"col_{i}"] = text
                            matches.append(row_data)
                except:
                    pass

            all_data["matches"] = matches
            all_data["players"] = []

            print(f"[Scraper] Extracted {len(matches)} match rows")
            return all_data

        except Exception as e:
            print(f"[Scraper] Error: {e}")
            import traceback
            traceback.print_exc()
            return {}

        finally:
            await self._close_browser()

    def _parse_score(self, score_str: str) -> Tuple[int, int]:
        try:
            score_clean = score_str.replace(" ", "")
            if "-" in score_clean:
                parts = score_clean.split("-")
                return int(parts[0]), int(parts[1])
        except:
            pass
        return 0, 0

    def _convert_match(self, raw_match: Dict, players_data: List[Dict]) -> Optional[Dict]:
        try:
            opponent = raw_match.get("col_1", "Unknown")
            score_str = raw_match.get("col_2", "0-0")
            team_goals, opponent_goals = self._parse_score(score_str)

            result_str = raw_match.get("col_3", "").lower()
            if "w" in result_str:
                result = "win"
            elif "l" in result_str:
                result = "loss"
            else:
                result = "win" if team_goals > opponent_goals else "loss" if team_goals < opponent_goals else "draw"

            return {
                "match_id": f"pct_{datetime.now().timestamp()}",
                "timestamp": int(datetime.now().timestamp()),
                "match_time": datetime.now().isoformat(),
                "opponent": opponent,
                "team_goals": team_goals,
                "opponent_goals": opponent_goals,
                "result": result,
                "match_type": "gameType9",
                "player_stats": {},
            }
        except Exception as e:
            print(f"[Convert] Error: {e}")
            return None

    async def sync_to_stats_engine(self, stats_engine, count: int = 10) -> int:
        all_data = await self.scrape_all()
        if not all_data:
            return 0

        added = 0
        matches = all_data.get("matches", [])
        players = all_data.get("players", [])

        for match in matches[:count]:
            parsed = self._convert_match(match, players)
            if parsed:
                if not stats_engine.match_exists(parsed["match_id"]):
                    stats_engine.add_match(parsed)
                    added += 1
                    print(f"[Sync] Added: {parsed['opponent']} ({parsed['result']})")

        return added

    async def check_new_match(self) -> Optional[Dict]:
        all_data = await self.scrape_all()
        matches = all_data.get("matches", [])
        players = all_data.get("players", [])
        if matches:
            return self._convert_match(matches[0], players)
        return None


def get_scraper(club_id: str, platform: str = "common-gen5", division: str = "6") -> ProClubsTrackerScraper:
    return ProClubsTrackerScraper(club_id, platform, division)
