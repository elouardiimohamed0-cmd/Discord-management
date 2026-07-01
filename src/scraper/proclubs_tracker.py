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
        self._initializing = False
        self._init_error: Optional[str] = None

    async def ensure_browser(self) -> None:
        if self._initialized:
            return
        if self._init_error:
            raise RuntimeError(f"Browser previously failed to initialize: {self._init_error}")
        if self._initializing:
            # Wait for another task to finish initializing (with timeout)
            for _ in range(300):  # 30 seconds max wait
                if not self._initializing:
                    break
                await asyncio.sleep(0.1)
            if self._initialized:
                return
            if self._init_error:
                raise RuntimeError(f"Browser initialization failed: {self._init_error}")
            raise RuntimeError("Browser initialization timed out")

        self._initializing = True
        try:
            await asyncio.wait_for(self.browser.start(), timeout=60.0)
            self._initialized = True
            logger.info("Browser initialized")
        except Exception as e:
            self._init_error = str(e)
            logger.error("Browser initialization failed: %s", e)
            raise RuntimeError(f"Browser failed to start: {e}")
        finally:
            self._initializing = False

    async def prewarm(self) -> None:
        """Start browser early so it's ready when needed."""
        try:
            await self.ensure_browser()
            logger.info("Browser pre-warmed and ready")
        except Exception as e:
            logger.warning("Browser prewarm failed (will retry on first use): %s", e)

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
            page = None
            try:
                page = await self.browser.new_page()
                logger.info("Scraping %s (attempt %d/%d)", url, attempt + 1, max_retries)

                # Set a shorter timeout for navigation, with better error handling
                response = await page.goto(url, wait_until="domcontentloaded", timeout=20000)

                if response:
                    logger.info("Page loaded: HTTP %s", response.status)
                    if response.status >= 400:
                        raise Exception(f"HTTP {response.status}")
                else:
                    logger.warning("Page goto returned no response")

                # Wait a bit for JS to execute, then check for content
                await asyncio.sleep(2)

                # Try to extract JSON from page
                raw_json = await page.evaluate("""() => {
                    if (window.__INITIAL_STATE__) return window.__INITIAL_STATE__;
                    if (window.__DATA__) return window.__DATA__;
                    return null;
                }""")

                if raw_json:
                    logger.info("Found window data, parsing JSON...")
                    html = await page.content()
                    snapshot = self.parser.parse_club_page(html, url, raw_json)
                    logger.info("Scraped %d matches from JSON", len(snapshot.matches))
                    return snapshot

                # Fallback: get HTML and try to parse
                logger.info("No window data found, falling back to HTML parsing...")
                html = await page.content()

                # Log page title for debugging
                title = await page.title()
                logger.info("Page title: %s", title)

                # Check if we got blocked
                if "cloudflare" in html.lower() or "cf-browser-verification" in html.lower():
                    raise Exception("Cloudflare blocked the request")
                if "access denied" in html.lower():
                    raise Exception("Access denied by server")

                snapshot = self.parser.parse_club_page(html, url, None)
                logger.info("Scraped %d matches from HTML", len(snapshot.matches))
                return snapshot

            except Exception as e:
                last_error = str(e)
                logger.warning("Scrape attempt %d failed: %s", attempt + 1, e)

                # Take screenshot on failure for debugging
                if page:
                    try:
                        screenshot_path = f"/tmp/scrape_fail_{attempt}.png"
                        await page.screenshot(path=screenshot_path, full_page=True)
                        logger.info("Screenshot saved to %s", screenshot_path)
                    except Exception:
                        pass

                await asyncio.sleep(2 ** attempt)
            finally:
                if page:
                    try:
                        await page.close()
                    except Exception:
                        pass

        self.repo.log_scrape(source="proclubs_tracker", success=False, error=last_error, request_count=max_retries)
        raise Exception(f"Failed to scrape after {max_retries} attempts: {last_error}")

    async def close(self) -> None:
        await self.browser.close()
        self._initialized = False
        self._init_error = None
