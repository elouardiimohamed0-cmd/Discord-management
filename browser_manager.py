import os
import asyncio
import logging
from typing import Optional

logger = logging.getLogger("rachad_bot.browser")

class BrowserManager:
    """
    Singleton Playwright browser manager.
    Launches browser ONCE and reuses it across all scrapes.
    Handles graceful cleanup and cookie persistence.
    """
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._available = False
        self._cookie_file = "/tmp/rachad_cache/pct_cookies.json"
        self._user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        self._initialized = True

    async def _ensure_playwright(self):
        if self._playwright is not None:
            return True
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            logger.info("Playwright started")
            return True
        except ImportError:
            logger.error("Playwright not installed. Browser fallback unavailable.")
            return False

    async def _load_cookies(self):
        import json
        if not os.path.exists(self._cookie_file):
            return []
        try:
            with open(self._cookie_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    async def _save_cookies(self):
        import json
        if not self._context:
            return
        try:
            os.makedirs(os.path.dirname(self._cookie_file), exist_ok=True)
            cookies = await self._context.cookies()
            with open(self._cookie_file, "w", encoding="utf-8") as f:
                json.dump(cookies, f, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning("Cookie save failed: %s", e)

    async def get_page(self) -> Optional:
        """Get a reusable Playwright page. Initializes browser if needed."""
        async with self._lock:
            if self._page and not self._page.is_closed():
                return self._page

            if not await self._ensure_playwright():
                return None

            # Close old browser if exists (stale)
            if self._browser:
                try:
                    await self._browser.close()
                except Exception:
                    pass
                self._browser = None
                self._context = None

            try:
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-web-security",
                        "--disable-features=IsolateOrigins,site-per-process",
                    ]
                )

                cookies = await self._load_cookies()
                self._context = await self._browser.new_context(
                    user_agent=self._user_agent,
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US",
                    timezone_id="America/New_York",
                )

                if cookies:
                    await self._context.add_cookies(cookies)

                self._page = await self._context.new_page()

                # Stealth script
                await self._page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                    window.chrome = { runtime: {} };
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' 
                            ? Promise.resolve({ state: Notification.permission })
                            : originalQuery(parameters)
                    );
                """)

                self._available = True
                logger.info("Browser initialized and page ready")
                return self._page

            except Exception as e:
                logger.error("Browser launch failed: %s", e)
                self._available = False
                return None

    async def save_session(self):
        """Save cookies after a successful scrape."""
        await self._save_cookies()

    async def close(self):
        """Gracefully close browser and playwright."""
        async with self._lock:
            if self._page:
                try:
                    await self._page.close()
                except Exception:
                    pass
                self._page = None
            if self._context:
                try:
                    await self._context.close()
                except Exception:
                    pass
                self._context = None
            if self._browser:
                try:
                    await self._browser.close()
                except Exception:
                    pass
                self._browser = None
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None
            self._available = False
            logger.info("Browser manager closed")

    @property
    def is_available(self) -> bool:
        return self._available and self._page is not None and not self._page.is_closed()
