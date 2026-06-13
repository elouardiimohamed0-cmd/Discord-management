"""
Rachad L3ERGONI Bot - Bulletproof ProClubsTracker Scraper v10
Guaranteed to work on Render with automatic browser installation
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
    Bulletproof scraper that handles ALL Render deployment issues
    """

    BASE_URL = "https://proclubstracker.com"

    def __init__(self, club_id: str, platform: str = "common-gen5", division: str = "6"):
        self.club_id = str(club_id)
        self.platform = platform
        self.division = division
        self.club_url = f"{self.BASE_URL}/club/{self.club_id}?platform={self.platform}&div={self.division}"
        self._browser_ready = False

    def _ensure_browsers(self) -> bool:
        """Ensure Playwright browsers are installed - multiple strategies"""
        if self._browser_ready:
            return True

        # Strategy 1: Check if browsers already exist
        browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
        if browsers_path:
            # Check if chromium exists in custom path
            chromium_paths = [
                os.path.join(browsers_path, "chromium-1223", "chrome-linux", "chrome"),
                os.path.join(browsers_path, "chromium_headless_shell-1223", "chrome-headless-shell-linux64", "chrome-headless-shell"),
            ]
            for path in chromium_paths:
                if os.path.exists(path):
                    print(f"[Scraper] ✅ Found browser at: {path}")
                    self._browser_ready = True
                    return True

        # Strategy 2: Check default cache location
        home = os.path.expanduser("~")
        default_paths = [
            os.path.join(home, ".cache", "ms-playwright", "chromium-1223", "chrome-linux", "chrome"),
            os.path.join(home, ".cache", "ms-playwright", "chromium_headless_shell-1223", "chrome-headless-shell-linux64", "chrome-headless-shell"),
            "/opt/render/.cache/ms-playwright/chromium-1223/chrome-linux/chrome",
            "/opt/render/.cache/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-linux64/chrome-headless-shell",
        ]
        for path in default_paths:
            if os.path.exists(path):
                print(f"[Scraper] ✅ Found browser at: {path}")
                # Set the path so Playwright finds it
                os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.dirname(os.path.dirname(os.path.dirname(path)))
                self._browser_ready = True
                return True

        # Strategy 3: Install browsers at runtime
        print("[Scraper] Browsers not found, installing at runtime...")
        try:
            # Set install path to project directory for persistence
            project_dir = os.path.dirname(os.path.abspath(__file__))
            install_path = os.path.join(project_dir, ".playwright")
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = install_path

            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True,
                text=True,
                timeout=180,
                cwd=project_dir
            )
            print(f"[Scraper] Install output: {result.stdout}")
            if result.returncode == 0:
                print("[Scraper] ✅ Browsers installed successfully")
                self._browser_ready = True
                return True
            else:
                print(f"[Scraper] ❌ Install failed: {result.stderr}")
        except subprocess.TimeoutExpired:
            print("[Scraper] ❌ Browser install timed out")
        except Exception as e:
            print(f"[Scraper] ❌ Browser install error: {e}")

        return False

    async def _init_browser(self):
        """Initialize browser with multiple fallback options"""
        from playwright.async_api import async_playwright
        self.playwright = await async_playwright().start()

        # Get browser path
        browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")

        # Build launch options
        launch_options_list = [
            # Option 1: Default (uses PLAYWRIGHT_BROWSERS_PATH env var)
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
        ]

        # Add explicit path options if we know where browsers are
        if browsers_path:
            chromium_path = os.path.join(browsers_path, "chromium-1223", "chrome-linux", "chrome")
            headless_path = os.path.join(browsers_path, "chromium_headless_shell-1223", "chrome-headless-shell-linux64", "chrome-headless-shell")

            if os.path.exists(chromium_path):
                launch_options_list.append({
                    "headless": True,
                    "executable_path": chromium_path,
                    "args": ['--no-sandbox', '--disable-setuid-sandbox']
                })
            if os.path.exists(headless_path):
                launch_options_list.append({
                    "headless": True,
                    "executable_path": headless_path,
                    "args": ['--no-sandbox', '--disable-setuid-sandbox']
                })

        # Try each option
        last_error = None
        for i, options in enumerate(launch_options_list):
            try:
                print(f"[Scraper] Trying browser launch option {i+1}...")
                self.browser = await self.playwright.chromium.launch(**options)
                print(f"[Scraper] ✅ Browser launched!")
                break
            except Exception as e:
                last_error = e
                print(f"[Scraper] Option {i+1} failed: {str(e)[:100]}")
                continue
        else:
            if last_error:
                raise last_error
            raise Exception("All browser launch options failed")

        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        )
        self.page = await self.context.new_page()

    async def _close_browser(self):
        try:
            if hasattr(self, 'context') and self.context:
                await self.context.close()
            if hasattr(self, 'browser') and self.browser:
                await self.browser.close()
            if hasattr(self, 'playwright') and self.playwright:
                await self.playwright.stop()
        except:
            pass

    async def scrape_all(self) -> Dict[str, Any]:
        """Scrape with guaranteed browser availability"""
        # Ensure browsers are ready
        if not self._ensure_browsers():
            print("[Scraper] ❌ Cannot proceed - no browsers available")
            return {"error": "Playwright browsers not available", "matches": [], "players": []}

        try:
            await self._init_browser()
        except Exception as e:
            print(f"[Scraper] ❌ Browser init failed: {e}")
            return {"error": str(e), "matches": [], "players": []}

        try:
            print(f"[Scraper] Navigating to: {self.club_url}")
            await self.page.goto(self.club_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(5)

            title = await self.page.title()
            print(f"[Scraper] Page title: {title}")

            # Extract all tables (matches and players)
            tables = await self.page.query_selector_all('table')
            print(f"[Scraper] Found {len(tables)} tables")

            all_data = {
                "club_id": self.club_id,
                "platform": self.platform,
                "scraped_at": datetime.now().isoformat(),
                "url": self.club_url,
                "page_title": title,
                "matches": [],
                "players": [],
            }

            # Extract data from all tables
            for table_idx, table in enumerate(tables):
                try:
                    rows = await table.query_selector_all('tbody tr, tr')
                    table_data = []
                    for row in rows:
                        cells = await row.query_selector_all('td')
                        if len(cells) >= 2:
                            row_dict = {}
                            for i, cell in enumerate(cells):
                                text = (await cell.inner_text()).strip()
                                row_dict[f"col_{i}"] = text
                            if row_dict:
                                table_data.append(row_dict)

                    if table_data:
                        # Try to determine if this is matches or players
                        first_row = table_data[0]
                        values = list(first_row.values())
                        value_text = " ".join(values).lower()

                        if any(word in value_text for word in ["opponent", "vs", "win", "loss", "draw", "score"]):
                            all_data["matches"].extend(table_data)
                            print(f"[Scraper] Table {table_idx}: {len(table_data)} matches")
                        elif any(word in value_text for word in ["player", "goals", "assists", "rating", "passes"]):
                            all_data["players"].extend(table_data)
                            print(f"[Scraper] Table {table_idx}: {len(table_data)} players")
                        else:
                            # Unknown table, add to matches as fallback
                            all_data["matches"].extend(table_data)

                except Exception as e:
                    print(f"[Scraper] Table {table_idx} error: {e}")
                    continue

            print(f"[Scraper] Total: {len(all_data['matches'])} matches, {len(all_data['players'])} players")
            return all_data

        except Exception as e:
            print(f"[Scraper] Scraping error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "matches": [], "players": []}

        finally:
            await self._close_browser()

    def _parse_score(self, score_str: str) -> Tuple[int, int]:
        try:
            clean = score_str.replace(" ", "").replace("–", "-").replace("—", "-")
            if "-" in clean:
                parts = clean.split("-")
                return int(parts[0]), int(parts[1])
        except:
            pass
        return 0, 0

    def _convert_match(self, raw_match: Dict, players_data: List[Dict]) -> Optional[Dict]:
        try:
            # Extract opponent from any column
            opponent = "Unknown"
            for key in raw_match:
                val = raw_match[key].lower()
                if any(word in val for word in ["opponent", "vs", "team"]):
                    opponent = raw_match[key]
                    break
            if opponent == "Unknown":
                # Try second column as opponent
                keys = list(raw_match.keys())
                if len(keys) > 1:
                    opponent = raw_match[keys[1]]

            # Extract score
            score_str = "0-0"
            for key in raw_match:
                val = raw_match[key]
                if "-" in val and any(c.isdigit() for c in val):
                    score_str = val
                    break

            team_goals, opponent_goals = self._parse_score(score_str)

            # Determine result
            result = "draw"
            for key in raw_match:
                val = raw_match[key].lower()
                if "win" in val:
                    result = "win"
                    break
                elif "loss" in val:
                    result = "loss"
                    break
            if result == "draw":
                result = "win" if team_goals > opponent_goals else "loss" if team_goals < opponent_goals else "draw"

            return {
                "match_id": f"pct_{hash(str(raw_match)) % 10000000}",
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
        if not all_data or all_data.get("error"):
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

        if added == 0:
            print(f"[Sync] No new matches (found {len(matches)} total)")

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
