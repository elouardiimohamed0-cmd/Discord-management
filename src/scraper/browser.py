from __future__ import annotations

import asyncio
from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from src.core.logging import get_logger

logger = get_logger(__name__)


class BrowserManager:
    def __init__(self, headless: bool = True, stealth: bool = True):
        self.headless = headless
        self.stealth = stealth
        self._playwright: Optional[Any] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        async with self._lock:
            if self._browser and not self._browser.is_connected():
                logger.warning("Browser disconnected, restarting...")
                await self._cleanup()
            if self._browser and self._browser.is_connected():
                return  # Already started

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            self._context = await self._browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0",
            )
            if self.stealth:
                await self._context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                """)
            logger.info("Browser started")

    async def new_page(self) -> Page:
        if not self._context:
            raise RuntimeError("Browser not started")
        return await self._context.new_page()

    async def close(self) -> None:
        async with self._lock:
            await self._cleanup()

    async def _cleanup(self) -> None:
        if self._context:
            try:
                await self._context.close()
            except Exception as e:
                logger.debug("Context close error: %s", e)
            self._context = None
        if self._browser:
            try:
                await self._browser.close()
            except Exception as e:
                logger.debug("Browser close error: %s", e)
            self._browser = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.debug("Playwright stop error: %s", e)
            self._playwright = None
        logger.info("Browser closed")

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.close()
