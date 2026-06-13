"""
Rachad L3ERGONI Bot - ProClubsTracker.com Scraper v3
Scrapes EA FC26 data from proclubstracker.com using Playwright
Clicks all tabs, extracts every stat, converts to bot format
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any


class ProClubsTrackerScraper:
    """Scraper for proclubstracker.com - extracts all club stats via Playwright"""

    BASE_URL = "https://proclubstracker.com"

    def __init__(self, club_name: str, platform: str = "ps5"):
        self.club_name = club_name
        self.platform = platform  # ps5, ps4, xbox, switch
        self.playwright_available = False
        try:
            from playwright.async_api import async_playwright
            self.playwright_available = True
        except ImportError:
            print("[Scraper] Playwright not installed - install with: pip install playwright && playwright install chromium")

    async def _init_browser(self):
        """Initialize Playwright browser"""
        from playwright.async_api import async_playwright
        self.playwright = await async_playwright().start()

        # Launch with args to bypass some detection
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
                '--window-size=1920,1080',
            ]
        )

        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='Europe/London',
        )

        self.page = await self.context.new_page()

        # Block unnecessary resources to speed up loading
        await self.page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}", lambda route: route.abort())

    async def _close_browser(self):
        """Close browser"""
        if hasattr(self, 'context'):
            await self.context.close()
        if hasattr(self, 'browser'):
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

    async def search_club(self) -> Optional[str]:
        """Search for club and return the club page URL"""
        try:
            print(f"[Scraper] Searching for club: {self.club_name}")
            await self.page.goto(f"{self.BASE_URL}/search", wait_until="networkidle", timeout=30000)

            # Wait for search input
            await self.page.wait_for_selector('input[placeholder*="Search"], input[type="search"], [data-testid="search-input"]', timeout=10000)

            # Type club name
            search_input = await self.page.query_selector('input[placeholder*="Search"], input[type="search"], [data-testid="search-input"]')
            if not search_input:
                # Try alternative selectors
                search_input = await self.page.query_selector('input')

            if search_input:
                await search_input.fill(self.club_name)
                await search_input.press("Enter")

                # Wait for results
                await asyncio.sleep(3)

                # Click first result or the club link
                club_link = await self.page.query_selector(f'a:has-text("{self.club_name}"), [data-testid="club-result"], .club-card, .search-result')
                if club_link:
                    await club_link.click()
                    await self.page.wait_for_load_state("networkidle")
                    await asyncio.sleep(2)

                    # Return current URL
                    return self.page.url
                else:
                    # Try clicking any link that contains our club name
                    links = await self.page.query_selector_all('a')
                    for link in links:
                        text = await link.inner_text()
                        if self.club_name.lower() in text.lower():
                            await link.click()
                            await self.page.wait_for_load_state("networkidle")
                            await asyncio.sleep(2)
                            return self.page.url

            print(f"[Scraper] Could not find club: {self.club_name}")
            return None

        except Exception as e:
            print(f"[Scraper] Search error: {e}")
            return None

    async def _click_tab(self, tab_name: str) -> bool:
        """Click a tab by name and wait for content"""
        try:
            # Try multiple selectors for tabs
            selectors = [
                f'button:has-text("{tab_name}")',
                f'a:has-text("{tab_name}")',
                f'[role="tab"]:has-text("{tab_name}")',
                f'.tab:has-text("{tab_name}")',
                f'[data-testid="{tab_name.lower()}-tab"]',
            ]

            for selector in selectors:
                tab = await self.page.query_selector(selector)
                if tab:
                    await tab.click()
                    await asyncio.sleep(2)  # Wait for content to load
                    return True

            print(f"[Scraper] Tab not found: {tab_name}")
            return False

        except Exception as e:
            print(f"[Scraper] Tab click error: {e}")
            return False

    async def _extract_table_data(self) -> List[Dict]:
        """Extract data from tables on current page"""
        data = []
        try:
            tables = await self.page.query_selector_all('table')
            for table in tables:
                rows = await table.query_selector_all('tr')
                headers = []

                # Extract headers
                header_row = await table.query_selector('thead tr, tr:first-child')
                if header_row:
                    header_cells = await header_row.query_selector_all('th, td')
                    headers = [await cell.inner_text() for cell in header_cells]

                # Extract data rows
                data_rows = await table.query_selector_all('tbody tr, tr:not(:first-child)')
                for row in data_rows:
                    cells = await row.query_selector_all('td, th')
                    row_data = {}
                    for i, cell in enumerate(cells):
                        if i < len(headers):
                            row_data[headers[i].strip()] = (await cell.inner_text()).strip()
                    if row_data:
                        data.append(row_data)
        except Exception as e:
            print(f"[Scraper] Table extraction error: {e}")

        return data

    async def _extract_stats_cards(self) -> Dict[str, Any]:
        """Extract stats from card/grid layouts"""
        stats = {}
        try:
            # Look for stat cards
            cards = await self.page.query_selector_all('[data-testid="stat-card"], .stat-card, .stats-card, .card')
            for card in cards:
                label = await card.query_selector('.label, .title, .name, h3, h4')
                value = await card.query_selector('.value, .number, .stat, .data')
                if label and value:
                    label_text = (await label.inner_text()).strip()
                    value_text = (await value.inner_text()).strip()
                    stats[label_text] = value_text
        except Exception as e:
            print(f"[Scraper] Card extraction error: {e}")

        return stats

    async def scrape_overview(self) -> Dict[str, Any]:
        """Scrape Overview tab - club stats, wins, losses, etc."""
        print("[Scraper] Scraping Overview tab...")
        await self._click_tab("Overview")

        overview = {
            "club_name": self.club_name,
            "platform": self.platform,
            "scraped_at": datetime.now().isoformat(),
        }

        # Extract club stats cards
        cards = await self._extract_stats_cards()
        overview.update(cards)

        # Extract any tables
        tables = await self._extract_table_data()
        if tables:
            overview["players_summary"] = tables

        return overview

    async def scrape_players(self) -> List[Dict[str, Any]]:
        """Scrape Players tab - detailed player stats"""
        print("[Scraper] Scraping Players tab...")
        await self._click_tab("Players")

        players = await self._extract_table_data()
        return players

    async def scrape_matches(self) -> List[Dict[str, Any]]:
        """Scrape Matches tab - match history"""
        print("[Scraper] Scraping Matches tab...")
        await self._click_tab("Matches")

        matches = await self._extract_table_data()
        return matches

    async def scrape_chemistry(self) -> Dict[str, Any]:
        """Scrape Chemistry tab - player combos"""
        print("[Scraper] Scraping Chemistry tab...")
        await self._click_tab("Chemistry")

        chemistry = {
            "combos": await self._extract_table_data(),
            "stats": await self._extract_stats_cards(),
        }
        return chemistry

    async def scrape_form(self) -> Dict[str, Any]:
        """Scrape Form tab - recent form graphs"""
        print("[Scraper] Scraping Form tab...")
        await self._click_tab("Form")

        form = {
            "data": await self._extract_table_data(),
            "stats": await self._extract_stats_cards(),
        }
        return form

    async def scrape_head_to_head(self) -> Dict[str, Any]:
        """Scrape Head to Head tab - player comparisons"""
        print("[Scraper] Scraping Head to Head tab...")
        await self._click_tab("Head")

        h2h = {
            "comparisons": await self._extract_table_data(),
        }
        return h2h

    async def scrape_all(self) -> Dict[str, Any]:
        """Scrape ALL tabs and return complete data"""
        if not self.playwright_available:
            print("[Scraper] Playwright not available. Install: pip install playwright && playwright install chromium")
            return {}

        await self._init_browser()

        try:
            # Search and navigate to club page
            club_url = await self.search_club()
            if not club_url:
                print("[Scraper] Failed to find club page")
                await self._close_browser()
                return {}

            print(f"[Scraper] Club page: {club_url}")

            # Scrape all tabs
            all_data = {
                "club_name": self.club_name,
                "platform": self.platform,
                "scraped_at": datetime.now().isoformat(),
                "url": club_url,
            }

            # Overview (should already be loaded)
            all_data["overview"] = await self.scrape_overview()

            # Players
            all_data["players"] = await self.scrape_players()

            # Matches
            all_data["matches"] = await self.scrape_matches()

            # Chemistry (if available)
            chemistry = await self.scrape_chemistry()
            if chemistry.get("combos") or chemistry.get("stats"):
                all_data["chemistry"] = chemistry

            # Form (if available)
            form = await self.scrape_form()
            if form.get("data") or form.get("stats"):
                all_data["form"] = form

            # Head to Head (if available)
            h2h = await self.scrape_head_to_head()
            if h2h.get("comparisons"):
                all_data["head_to_head"] = h2h

            print(f"[Scraper] Scraped {len(all_data)} sections")
            return all_data

        except Exception as e:
            print(f"[Scraper] Scraping error: {e}")
            import traceback
            traceback.print_exc()
            return {}

        finally:
            await self._close_browser()

    def _convert_match_to_bot_format(self, match_data: Dict, players_data: List[Dict]) -> Optional[Dict]:
        """Convert proclubstracker match data to bot's match_data.json format"""
        try:
            # Extract match info from match_data dict
            opponent = match_data.get("Opponent", match_data.get("opponent", "Unknown"))
            result_str = match_data.get("Result", match_data.get("result", ""))

            # Parse score
            score = match_data.get("Score", match_data.get("score", "0-0"))
            if "-" in score:
                parts = score.split("-")
                team_goals = int(parts[0].strip())
                opponent_goals = int(parts[1].strip())
            else:
                team_goals = int(match_data.get("Goals For", 0))
                opponent_goals = int(match_data.get("Goals Against", 0))

            result = "win" if "W" in result_str or team_goals > opponent_goals else \
                     "loss" if "L" in result_str or team_goals < opponent_goals else "draw"

            # Build player stats from players_data
            player_stats = {}
            for player in players_data:
                player_name = player.get("Player", player.get("Name", player.get("player", ""))).lower().strip()
                if not player_name:
                    continue

                # Parse numeric values, handling percentages
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
                    "motm": str(player.get("MOTM", player.get("Man of the Match", ""))).lower() in ["yes", "1", "true", "✓"],
                    "position": player.get("Position", "unknown"),
                    "minutes_played": parse_num(player.get("Minutes", 90)),
                }

            return {
                "match_id": match_data.get("Match ID", match_data.get("match_id", f"pct_{datetime.now().timestamp()}")),
                "timestamp": int(datetime.now().timestamp()),
                "match_time": match_data.get("Date", match_data.get("date", datetime.now().isoformat())),
                "opponent": opponent,
                "team_goals": team_goals,
                "opponent_goals": opponent_goals,
                "result": result,
                "match_type": "gameType9",  # Default to league
                "player_stats": player_stats,
            }

        except Exception as e:
            print(f"[Scraper] Match conversion error: {e}")
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
            parsed = self._convert_match_to_bot_format(match, players)
            if parsed:
                if not stats_engine.match_exists(parsed["match_id"]):
                    stats_engine.add_match(parsed)
                    added += 1
                    print(f"[Sync] Added match: {parsed['match_time']} vs {parsed['opponent']} ({parsed['result']})")

        if added == 0:
            print(f"[Sync] No new matches found (checked {len(matches)} recent)")

        return added

    async def check_new_match(self) -> Optional[Dict]:
        """Check for most recent match"""
        all_data = await self.scrape_all()
        matches = all_data.get("matches", [])
        players = all_data.get("players", [])

        if matches:
            return self._convert_match_to_bot_format(matches[0], players)
        return None


def get_scraper(club_name: str, platform: str = "ps5") -> ProClubsTrackerScraper:
    """Factory function - note: club_name is the club NAME, not ID"""
    return ProClubsTrackerScraper(club_name, platform)


# --- Test / Debug ---
if __name__ == "__main__":
    async def test():
        # Replace with your actual club name as shown on proclubstracker.com
        scraper = ProClubsTrackerScraper(club_name="Rachad L3ERGONI", platform="ps5")

        print("Testing scrape...")
        data = await scraper.scrape_all()

        if data:
            print(f"\nScraped sections: {list(data.keys())}")
            print(f"Matches found: {len(data.get('matches', []))}")
            print(f"Players found: {len(data.get('players', []))}")

            # Save raw data for inspection
            with open("proclubstracker_raw.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print("\nRaw data saved to proclubstracker_raw.json")
        else:
            print("No data scraped - check club name and platform")

    asyncio.run(test())
