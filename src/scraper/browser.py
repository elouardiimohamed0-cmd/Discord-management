from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from src.core.logging import get_logger

logger = get_logger(__name__)


class BrowserFetcher:
    def __init__(self, cache_dir: Path, headless: bool = True):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cookie_path = self.cache_dir / "pct_cookies.json"
        self.headless = headless

    async def fetch_json_from_page(self, page_url: str, api_url: str) -> Optional[dict[str, Any]]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("Playwright is not installed; browser fallback disabled")
            return None

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
            )
            await self._load_cookies(context)
            page = await context.new_page()
            try:
                await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
                await page.goto(page_url, wait_until="networkidle", timeout=30000)
                data = await page.evaluate("() => window.__INITIAL_STATE__ || window.__DATA__ || window.clubData || null")
                if not data:
                    data = await page.evaluate(
                        """async (url) => {
                            const response = await fetch(url, {headers: {Accept: 'application/json'}});
                            return await response.json();
                        }""",
                        api_url,
                    )
                await self._save_cookies(context)
                return data if isinstance(data, dict) else None
            except Exception as exc:
                logger.warning("Browser fetch failed: %s", exc)
                return None
            finally:
                await browser.close()

    async def _load_cookies(self, context: Any) -> None:
        if not self.cookie_path.exists():
            return
        try:
            cookies = json.loads(self.cookie_path.read_text(encoding="utf-8"))
            if cookies:
                await context.add_cookies(cookies)
        except Exception:
            return

    async def _save_cookies(self, context: Any) -> None:
        try:
            cookies = await context.cookies()
            self.cookie_path.write_text(json.dumps(cookies, ensure_ascii=False), encoding="utf-8")
        except Exception:
            return
