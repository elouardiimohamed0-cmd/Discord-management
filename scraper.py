"""
Rachad L3ERGONI Bot - ProClubsTracker.com Direct URL Scraper v7
Goes DIRECTLY to https://proclubstracker.com/club/1427607?platform=common-gen5&div=6
Drills through ALL tabs with Playwright
"""

import os
import json
import asyncio
import re
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple


class ProClubsTrackerScraper:
    """
    Direct URL scraper for proclubstracker.com
    URL: https://proclubstracker.com/club/1427607?platform=common-gen5&div=6
    """

    BASE_URL = "https://proclubstracker.com"

    def __init__(self, club_id: str, platform: str = "common-gen5", division: str = "6"):
        self.club_id = str(club_id)
        self.platform = platform
        self.division = division
        self.club_url = f"{self.BASE_URL}/club/{self.club_id}?platform={self.platform}&div={self.division}"
        self.playwright_available = False
        try:
            from playwright.async_api import async_playwright
            self.playwright_available = True
        except ImportError:
            print("[Scraper] Playwright not installed. Install: pip install playwright && playwright install chromium")

    async def _init_browser(self):
        """Initialize Playwright browser with stealth settings"""
        from playwright.async_api import async_playwright
        self.playwright = await async_playwright().start()

        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
                '--window-size=1920,1080',
                '--disable-blink-features=AutomationControlled',
            ]
        )

        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='Europe/London',
        )

        # Add stealth script to hide Playwright
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            window.chrome = { runtime: {} };
        """)

        self.page = await self.context.new_page()

        # Block unnecessary resources for speed
        await self.page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2,ico}", lambda route: route.abort())

    async def _close_browser(self):
        """Close browser"""
        if hasattr(self, 'context'):
            await self.context.close()
        if hasattr(self, 'browser'):
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

    async def _goto(self, url: str, wait_for: str = None, timeout: int = 30000):
        """Navigate to page with optional wait selector"""
        await self.page.goto(url, wait_until="networkidle", timeout=timeout)
        if wait_for:
            await self.page.wait_for_selector(wait_for, timeout=10000)
        await asyncio.sleep(2)

    async def _click_tab(self, tab_text: str) -> bool:
        """Click a tab by partial text match"""
        try:
            selectors = [
                f'button:has-text("{tab_text}")',
                f'a:has-text("{tab_text}")',
                f'[role="tab"]:has-text("{tab_text}")',
                f'.tab:has-text("{tab_text}")',
                f'[data-testid*="{tab_text.lower()}"]',
                f'nav button:has-text("{tab_text}")',
                f'nav a:has-text("{tab_text}")',
            ]

            for selector in selectors:
                try:
                    tab = await self.page.query_selector(selector)
                    if tab:
                        await tab.click()
                        await asyncio.sleep(3)
                        return True
                except:
                    continue

            # Fallback: try all buttons and links
            elements = await self.page.query_selector_all('button, a, [role="tab"]')
            for el in elements:
                try:
                    text = await el.inner_text()
                    if tab_text.lower() in text.lower():
                        await el.click()
                        await asyncio.sleep(3)
                        return True
                except:
                    continue

            print(f"[Scraper] Tab not found: {tab_text}")
            return False

        except Exception as e:
            print(f"[Scraper] Tab click error: {e}")
            return False

    async def _extract_text(self, selector: str) -> str:
        """Extract text from element"""
        try:
            el = await self.page.query_selector(selector)
            if el:
                return (await el.inner_text()).strip()
            return ""
        except:
            return ""

    async def _extract_all_text(self, selector: str) -> List[str]:
        """Extract text from all matching elements"""
        try:
            elements = await self.page.query_selector_all(selector)
            texts = []
            for el in elements:
                text = (await el.inner_text()).strip()
                if text:
                    texts.append(text)
            return texts
        except:
            return []

    async def _extract_table(self, table_selector: str = 'table') -> List[Dict[str, str]]:
        """Extract complete table data"""
        data = []
        try:
            tables = await self.page.query_selector_all(table_selector)
            for table in tables:
                headers = []
                header_cells = await table.query_selector_all('thead th, thead td, tr:first-child th, tr:first-child td')
                for cell in header_cells:
                    headers.append((await cell.inner_text()).strip())

                rows = await table.query_selector_all('tbody tr, tr:not(:first-child)')
                for row in rows:
                    cells = await row.query_selector_all('td')
                    if len(cells) > 0:
                        row_data = {}
                        for i, cell in enumerate(cells):
                            if i < len(headers):
                                row_data[headers[i]] = (await cell.inner_text()).strip()
                            else:
                                row_data[f"col_{i}"] = (await cell.inner_text()).strip()
                        if row_data:
                            data.append(row_data)
        except Exception as e:
            print(f"[Table Extract] Error: {e}")
        return data

    async def _extract_cards(self) -> Dict[str, str]:
        """Extract stat cards (label + value pairs)"""
        stats = {}
        try:
            card_selectors = [
                '[data-testid="stat-card"]',
                '.stat-card',
                '.stats-card',
                '.card',
                '.stat-box',
                '.metric-card',
            ]

            for selector in card_selectors:
                cards = await self.page.query_selector_all(selector)
                for card in cards:
                    try:
                        label = await card.query_selector('.label, .title, .name, h3, h4, .stat-name')
                        value = await card.query_selector('.value, .number, .stat, .data, .stat-value')
                        if label and value:
                            label_text = (await label.inner_text()).strip()
                            value_text = (await value.inner_text()).strip()
                            if label_text and value_text:
                                stats[label_text] = value_text
                    except:
                        continue
        except Exception as e:
            print(f"[Card Extract] Error: {e}")
        return stats

    # === NAVIGATION ===

    async def navigate_to_club(self) -> bool:
        """Navigate DIRECTLY to club URL"""
        try:
            print(f"[Scraper] Navigating DIRECTLY to: {self.club_url}")
            await self._goto(self.club_url, wait_for='body', timeout=30000)

            # Check if page loaded correctly
            page_title = await self.page.title()
            print(f"[Scraper] Page title: {page_title}")

            # Check for error messages
            error_text = await self._extract_text('.error, .not-found, .no-data')
            if error_text and ("not found" in error_text.lower() or "no data" in error_text.lower()):
                print(f"[Scraper] Error on page: {error_text}")
                return False

            # Check if club name is present
            page_text = await self.page.inner_text("body")
            if "Rachad" in page_text or "L3ERGONI" in page_text or "1427607" in page_text:
                print(f"[Scraper] ✅ Club page loaded successfully!")
                return True
            else:
                print(f"[Scraper] ⚠️ Club data not found on page")
                # Still return True, maybe data loads dynamically
                return True

        except Exception as e:
            print(f"[Scraper] Navigation error: {e}")
            return False

    # === TAB SCRAPERS ===

    async def scrape_overview(self) -> Dict[str, Any]:
        """Scrape Overview tab - club stats, division, skill rating"""
        print("[Scraper] Scraping Overview...")
        await self._click_tab("Overview")

        overview = {
            "club_id": self.club_id,
            "platform": self.platform,
            "scraped_at": datetime.now().isoformat(),
        }

        # Extract stat cards
        cards = await self._extract_cards()
        overview.update(cards)

        # Extract tables
        tables = await self._extract_table()
        if tables:
            overview["players_summary"] = tables

        # Extract from page text using regex
        page_text = await self.page.inner_text("body")

        division_match = re.search(r'Division\s+(\d+)', page_text, re.IGNORECASE)
        if division_match:
            overview["division"] = division_match.group(1)

        skill_match = re.search(r'Skill Rating[:\s]+(\d+)', page_text, re.IGNORECASE)
        if skill_match:
            overview["skill_rating"] = int(skill_match.group(1))

        wins_match = re.search(r'(\d+)\s*Wins?', page_text, re.IGNORECASE)
        if wins_match and "wins" not in overview:
            overview["wins"] = int(wins_match.group(1))

        losses_match = re.search(r'(\d+)\s*Loss(?:es)?', page_text, re.IGNORECASE)
        if losses_match and "losses" not in overview:
            overview["losses"] = int(losses_match.group(1))

        draws_match = re.search(r'(\d+)\s*Draws?', page_text, re.IGNORECASE)
        if draws_match and "draws" not in overview:
            overview["draws"] = int(draws_match.group(1))

        return overview

    async def scrape_players(self) -> List[Dict[str, str]]:
        """Scrape Players tab - detailed individual stats"""
        print("[Scraper] Scraping Players...")
        await self._click_tab("Players")

        players = await self._extract_table()

        cards = await self._extract_cards()
        if cards and not players:
            players = [cards]

        return players

    async def scrape_matches(self) -> List[Dict[str, str]]:
        """Scrape Matches tab - full match history"""
        print("[Scraper] Scraping Matches...")
        await self._click_tab("Matches")

        matches = await self._extract_table()

        # If no table, try match cards
        if not matches:
            match_containers = await self.page.query_selector_all('.match, .match-card, [data-testid*="match"]')
            for container in match_containers:
                try:
                    match_data = {}
                    opp = await container.query_selector('.opponent, .team-name, h3, h4')
                    if opp:
                        match_data["Opponent"] = (await opp.inner_text()).strip()

                    score = await container.query_selector('.score, .result')
                    if score:
                        match_data["Score"] = (await score.inner_text()).strip()

                    result = await container.query_selector('.win, .loss, .draw, .result-badge')
                    if result:
                        match_data["Result"] = (await result.inner_text()).strip()

                    date = await container.query_selector('.date, time, .timestamp')
                    if date:
                        match_data["Date"] = (await date.inner_text()).strip()

                    if match_data:
                        matches.append(match_data)
                except:
                    continue

        return matches

    async def scrape_form(self) -> Dict[str, Any]:
        """Scrape Form tab"""
        print("[Scraper] Scraping Form...")
        await self._click_tab("Form")

        form_data = {
            "recent_form": [],
            "streaks": {},
            "graphs": []
        }

        form_text = await self._extract_text('.form-string, .form-display, .recent-form')
        if form_text:
            form_data["recent_form_string"] = form_text

        streak_text = await self._extract_text('.streak, .current-streak')
        if streak_text:
            form_data["streaks"]["current"] = streak_text

        form_table = await self._extract_table()
        if form_table:
            form_data["match_form"] = form_table

        cards = await self._extract_cards()
        if cards:
            form_data["stats"] = cards

        return form_data

    async def scrape_chemistry(self) -> Dict[str, Any]:
        """Scrape Chemistry tab"""
        print("[Scraper] Scraping Chemistry...")
        await self._click_tab("Chemistry")

        chemistry = {
            "combos": [],
            "partnerships": [],
            "stats": {}
        }

        tables = await self._extract_table()
        if tables:
            chemistry["combos"] = tables

        cards = await self._extract_cards()
        if cards:
            chemistry["stats"] = cards

        return chemistry

    async def scrape_head_to_head(self) -> Dict[str, Any]:
        """Scrape Head to Head tab"""
        print("[Scraper] Scraping Head to Head...")
        await self._click_tab("Head")

        h2h = {
            "comparisons": [],
            "stats": {}
        }

        tables = await self._extract_table()
        if tables:
            h2h["comparisons"] = tables

        cards = await self._extract_cards()
        if cards:
            h2h["stats"] = cards

        return h2h

    async def scrape_roasts_memes(self) -> List[str]:
        """Scrape any roast/meme content"""
        print("[Scraper] Scraping roasts/memes...")

        roasts = []

        # Try clicking roast tabs
        for tab_name in ["Roasts", "Memes", "Banter", "Trash Talk", "Awards"]:
            if await self._click_tab(tab_name):
                tab_roasts = await self._extract_roasts()
                roasts.extend(tab_roasts)

        return roasts

    async def _extract_roasts(self) -> List[str]:
        """Extract roast text from current page"""
        roasts = []
        try:
            roast_selectors = [
                '.roast',
                '.banter',
                '.meme',
                '.trash-talk',
                '.commentary',
                '[data-testid="roast"]',
                '.funny',
                '.joke',
            ]

            for selector in roast_selectors:
                elements = await self.page.query_selector_all(selector)
                for el in elements:
                    text = (await el.inner_text()).strip()
                    if text and len(text) > 10:
                        roasts.append(text)

            paragraphs = await self.page.query_selector_all('p')
            for p in paragraphs:
                text = (await p.inner_text()).strip()
                if any(word in text.lower() for word in ['roast', 'banter', 'trash', 'garbage', 'clown', 'fraud', 'sold']):
                    if text not in roasts and len(text) > 10:
                        roasts.append(text)
        except:
            pass
        return roasts

    # === MAIN SCRAPE ===

    async def scrape_all(self) -> Dict[str, Any]:
        """Scrape ALL tabs and return complete data"""
        if not self.playwright_available:
            print("[Scraper] Playwright not available!")
            return {}

        await self._init_browser()

        try:
            if not await self.navigate_to_club():
                await self._close_browser()
                return {}

            all_data = {
                "club_id": self.club_id,
                "platform": self.platform,
                "scraped_at": datetime.now().isoformat(),
                "url": self.club_url,
            }

            all_data["overview"] = await self.scrape_overview()
            all_data["players"] = await self.scrape_players()
            all_data["matches"] = await self.scrape_matches()
            all_data["form"] = await self.scrape_form()
            all_data["chemistry"] = await self.scrape_chemistry()
            all_data["head_to_head"] = await self.scrape_head_to_head()
            all_data["roasts_memes"] = await self.scrape_roasts_memes()

            print(f"[Scraper] Complete!")
            print(f"  - Overview: {len(all_data['overview'])} stats")
            print(f"  - Players: {len(all_data['players'])} players")
            print(f"  - Matches: {len(all_data['matches'])} matches")
            print(f"  - Form: {len(all_data['form'].get('recent_form', []))} entries")
            print(f"  - Chemistry: {len(all_data['chemistry'].get('combos', []))} combos")
            print(f"  - H2H: {len(all_data['head_to_head'].get('comparisons', []))} comparisons")
            print(f"  - Roasts: {len(all_data['roasts_memes'])} roasts/memes")

            return all_data

        except Exception as e:
            print(f"[Scraper] Fatal error: {e}")
            import traceback
            traceback.print_exc()
            return {}

        finally:
            await self._close_browser()

    # === CONVERSION ===

    def _parse_score(self, score_str: str) -> Tuple[int, int]:
        """Parse score string like '3-1'"""
        try:
            score_clean = score_str.replace(" ", "")
            if "-" in score_clean:
                parts = score_clean.split("-")
                return int(parts[0]), int(parts[1])
            elif ":" in score_clean:
                parts = score_clean.split(":")
                return int(parts[0]), int(parts[1])
        except:
            pass
        return 0, 0

    def _convert_match(self, raw_match: Dict, players_data: List[Dict]) -> Optional[Dict]:
        """Convert proclubstracker match to bot format"""
        try:
            opponent = raw_match.get("Opponent", raw_match.get("opponent", raw_match.get("Team", "Unknown")))

            score_str = raw_match.get("Score", raw_match.get("score", raw_match.get("Result", "0-0")))
            team_goals, opponent_goals = self._parse_score(score_str)

            result_str = raw_match.get("Result", raw_match.get("result", "")).lower()
            if "w" in result_str or "win" in result_str:
                result = "win"
            elif "l" in result_str or "loss" in result_str:
                result = "loss"
            else:
                result = "win" if team_goals > opponent_goals else "loss" if team_goals < opponent_goals else "draw"

            date_str = raw_match.get("Date", raw_match.get("date", raw_match.get("Time", datetime.now().isoformat())))

            # Build player stats from players_data
            player_stats = {}
            for player in players_data:
                player_name = player.get("Player", player.get("Name", player.get("player", ""))).lower().strip()
                if not player_name:
                    continue

                def parse_num(val, default=0):
                    if val is None:
                        return default
                    val_str = str(val).replace("%", "").replace(",", "").strip()
                    try:
                        return float(val_str) if "." in val_str else int(val_str)
                    except:
                        return default

                passes_attempted = parse_num(player.get("Passes", player.get("Pass Attempts", 0)))
                passes_made = parse_num(player.get("Passes Made", player.get("Pass Completion", 0)))

                player_stats[player_name] = {
                    "goals": parse_num(player.get("Goals", 0)),
                    "assists": parse_num(player.get("Assists", 0)),
                    "shots": parse_num(player.get("Shots", 0)),
                    "passes_attempted": passes_attempted,
                    "passes_made": passes_made,
                    "pass_accuracy": round((passes_made / max(passes_attempted, 1)) * 100, 1),
                    "key_passes": parse_num(player.get("Key Passes", 0)),
                    "tackles": parse_num(player.get("Tackles", 0)),
                    "interceptions": parse_num(player.get("Interceptions", 0)),
                    "possession_losses": parse_num(player.get("Possession Losses", passes_attempted - passes_made)),
                    "dribbles_attempted": parse_num(player.get("Dribbles", 0)),
                    "dribbles_completed": parse_num(player.get("Dribbles Completed", 0)),
                    "fouls": parse_num(player.get("Fouls", 0)),
                    "yellow_cards": parse_num(player.get("Yellow Cards", 0)),
                    "red_cards": parse_num(player.get("Red Cards", 0)),
                    "rating": parse_num(player.get("Rating", player.get("Match Rating", 6.0)), 6.0),
                    "motm": str(player.get("MOTM", player.get("Man of the Match", ""))).lower() in ["yes", "1", "true", "✓", "⭐"],
                    "position": player.get("Position", "unknown"),
                    "minutes_played": parse_num(player.get("Minutes", 90)),
                }

            return {
                "match_id": raw_match.get("Match ID", raw_match.get("match_id", f"pct_{datetime.now().timestamp()}")),
                "timestamp": int(datetime.now().timestamp()),
                "match_time": date_str if isinstance(date_str, str) else datetime.now().isoformat(),
                "opponent": opponent,
                "team_goals": team_goals,
                "opponent_goals": opponent_goals,
                "result": result,
                "match_type": "gameType9",
                "player_stats": player_stats,
            }

        except Exception as e:
            print(f"[Convert Match] Error: {e}")
            return None

    async def sync_to_stats_engine(self, stats_engine, count: int = 10) -> int:
        """Sync scraped matches to stats engine"""
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
                    print(f"[Sync] Added: {parsed['match_time']} vs {parsed['opponent']} ({parsed['result']})")

        if added == 0:
            print(f"[Sync] No new matches (checked {len(matches)} from proclubstracker)")

        return added

    async def check_new_match(self) -> Optional[Dict]:
        """Check for most recent match"""
        all_data = await self.scrape_all()
        matches = all_data.get("matches", [])
        players = all_data.get("players", [])

        if matches:
            return self._convert_match(matches[0], players)
        return None


def get_scraper(club_id: str, platform: str = "common-gen5", division: str = "6") -> ProClubsTrackerScraper:
    return ProClubsTrackerScraper(club_id, platform, division)
