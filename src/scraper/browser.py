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

    async def start(self) -> None:
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
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser closed")

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.close()
