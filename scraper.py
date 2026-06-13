"""
Rachad L3ERGONI Bot - ProClubsTracker.com DEBUG Scraper v8
Saves screenshots and HTML for debugging
"""

import os
import json
import asyncio
import re
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple


class ProClubsTrackerScraper:
    """
    DEBUG scraper for proclubstracker.com
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
            print("[Scraper] Playwright not installed!")

    async def _init_browser(self):
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
            ]
        )

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
        """Scrape with DEBUG output"""
        if not self.playwright_available:
            print("[Scraper] Playwright not available!")
            return {}

        await self._init_browser()

        try:
            print(f"[Scraper] Navigating to: {self.club_url}")
            await self.page.goto(self.club_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(5)  # Extra wait for JS

            # DEBUG: Save screenshot
            screenshot_path = "/mnt/agents/output/debug_screenshot.png"
            await self.page.screenshot(path=screenshot_path, full_page=True)
            print(f"[Scraper] Screenshot saved to {screenshot_path}")

            # DEBUG: Save HTML
            html_content = await self.page.content()
            with open("/mnt/agents/output/debug_page.html", "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"[Scraper] HTML saved to debug_page.html")

            # DEBUG: Get page title
            title = await self.page.title()
            print(f"[Scraper] Page title: {title}")

            # DEBUG: Get all text
            body_text = await self.page.inner_text("body")
            print(f"[Scraper] Body text length: {len(body_text)}")
            print(f"[Scraper] Body text preview: {body_text[:500]}")

            # DEBUG: List all buttons and links
            buttons = await self.page.query_selector_all('button')
            print(f"[Scraper] Found {len(buttons)} buttons")
            for i, btn in enumerate(buttons[:10]):
                text = await btn.inner_text()
                print(f"  Button {i}: {text}")

            links = await self.page.query_selector_all('a')
            print(f"[Scraper] Found {len(links)} links")
            for i, link in enumerate(links[:10]):
                text = await link.inner_text()
                href = await link.get_attribute('href')
                print(f"  Link {i}: {text} -> {href}")

            # DEBUG: List all tables
            tables = await self.page.query_selector_all('table')
            print(f"[Scraper] Found {len(tables)} tables")

            # DEBUG: List all elements with 'match' in class or id
            match_elements = await self.page.query_selector_all('[class*="match"], [id*="match"], [data-testid*="match"]')
            print(f"[Scraper] Found {len(match_elements)} match elements")

            # Try to find ANY data
            all_data = {
                "club_id": self.club_id,
                "platform": self.platform,
                "scraped_at": datetime.now().isoformat(),
                "url": self.club_url,
                "page_title": title,
                "body_text_preview": body_text[:1000],
            }

            # Try to extract tables as raw data
            raw_tables = []
            for i, table in enumerate(tables):
                try:
                    rows = await table.query_selector_all('tr')
                    table_data = []
                    for row in rows:
                        cells = await row.query_selector_all('td, th')
                        row_text = [await cell.inner_text() for cell in cells]
                        table_data.append(row_text)
                    if table_data:
                        raw_tables.append(table_data)
                except:
                    pass

            all_data["raw_tables"] = raw_tables

            return all_data

        except Exception as e:
            print(f"[Scraper] Fatal error: {e}")
            import traceback
            traceback.print_exc()
            return {}

        finally:
            await self._close_browser()

    async def sync_to_stats_engine(self, stats_engine, count: int = 10) -> int:
        """For compatibility - returns 0 since we debug"""
        data = await self.scrape_all()
        return 0

    async def check_new_match(self) -> Optional[Dict]:
        """For compatibility"""
        return None


def get_scraper(club_id: str, platform: str = "common-gen5", division: str = "6") -> ProClubsTrackerScraper:
    return ProClubsTrackerScraper(club_id, platform, division)
