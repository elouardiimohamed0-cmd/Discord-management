"""Playwright browser manager for fallback scraping."""
from __future__ import annotations

from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from src.core.logging import get_logger

logger = get_logger(__name__)


class BrowserManager:
    """Manages a Playwright browser instance."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    async def start(self) -> None:
        """Start the browser if not already running."""
        if self._browser and not self._browser.is_connected():
            await self.close()

        if not self._browser:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--disable-gpu",
                    "--window-size=1920,1080",
                ],
            )
            self._context = await self._browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            )
            logger.info("[Browser] Started (headless=%s)", self.headless)

    async def new_page(self) -> Page:
        """Create a new page in the browser context."""
        if not self._context:
            await self.start()
        return await self._context.new_page()

    async def close(self) -> None:
        """Close the browser and cleanup."""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("[Browser] Closed")
