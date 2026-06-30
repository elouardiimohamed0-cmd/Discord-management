from __future__ import annotations

import asyncio
from typing import Optional

from src.core.config import Settings
from src.core.logging import get_logger
from src.data.repositories import ClubRepository
from src.domain.models import ClubSnapshot
from src.scraper.browser import BrowserManager
from src.scraper.cache import FileCache
from src.scraper.parser import ProClubsTrackerParser
from src.squad.registry import SquadRegistry

logger = get_logger(__name__)


class ProClubsTrackerClient:
    def __init__(
        self,
        settings: Settings,
        squad: SquadRegistry,
        repository: ClubRepository,
        headless: bool = True,
    ):
        self.settings = settings
        self.squad = squad
        self.repo = repository
        self.cache = FileCache(settings.cache_dir, ttl_seconds=120)
        self.parser = ProClubsTrackerParser()
        self.browser = BrowserManager(headless=headless)
        self._initialized = False

    async def ensure_browser(self) -> None:
        if not self._initialized:
            await self.browser.start()
            self._initialized = True

    async def prewarm(self) -> None:
        """Start browser early so it's ready when needed."""
        await self.ensure_browser()
        logger.info("Browser pre-warmed and ready")

    async def refresh(self, force: bool = False, source: str = "scheduled") -> ClubSnapshot:
        url = self.settings.pct_club_url
        if not force:
            cached = self.cache.get(url)
            if cached:
                logger.info("Using cached snapshot")
                return self.parser.parse_club_page("", url, cached)

        await self.ensure_browser()
        snapshot = await self._scrape_with_retry(url)
        self.cache.set(url, snapshot.model_dump())
        self.repo.save_snapshot(snapshot)
        self.repo.log_scrape(source=source, success=True, request_count=1)
        return snapshot

    async def _scrape_with_retry(self, url: str, max_retries: int = 3) -> ClubSnapshot:
        last_error = ""
        for attempt in range(max_retries):
            try:
                page = await self.browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_selector("table, .match-row, .club-header", timeout=15000)
                html = await page.content()
                raw_json = await page.evaluate("""() => {
                    if (window.__INITIAL_STATE__) return window.__INITIAL_STATE__;
                    if (window.__DATA__) return window.__DATA__;
                    return null;
                }""")
                await page.close()
                snapshot = self.parser.parse_club_page(html, url, raw_json)
                logger.info("Scraped %d matches", len(snapshot.matches))
                return snapshot
            except Exception as e:
                last_error = str(e)
                logger.warning("Scrape attempt %d failed: %s", attempt + 1, e)
                await asyncio.sleep(2 ** attempt)

        self.repo.log_scrape(source="proclubs_tracker", success=False, error=last_error, request_count=max_retries)
        raise Exception(f"Failed to scrape after {max_retries} attempts: {last_error}")

    async def close(self) -> None:
        await self.browser.close()
        self._initialized = False
