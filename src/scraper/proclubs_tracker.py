from __future__ import annotations

import gzip
from typing import Any, Optional

import httpx

from src.core.config import Settings
from src.core.logging import get_logger
from src.data.repositories import ClubRepository
from src.domain.models import ClubSnapshot
from src.scraper.browser import BrowserFetcher
from src.scraper.cache import JsonCache
from src.scraper.parser import ProClubsTrackerParser
from src.squad.registry import SquadRegistry

logger = get_logger(__name__)


class ProClubsTrackerClient:
    def __init__(self, settings: Settings, squad: SquadRegistry, repository: ClubRepository):
        self.settings = settings
        self.squad = squad
        self.repository = repository
        self.parser = ProClubsTrackerParser(settings.club_id, squad)
        self.cache = JsonCache(settings.cache_dir / "pct")
        self.browser = BrowserFetcher(settings.cache_dir / "browser")
        self.api_url = f"https://proclubstracker.com/api/clubs/{settings.club_id}?platform={settings.pct_platform}"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
            "Accept": "application/json, text/html,*/*",
            "Referer": "https://proclubstracker.com/",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def refresh(self, force: bool = False, source: str = "manual") -> ClubSnapshot:
        raw: Optional[dict[str, Any]] = None
        request_count = 0

        if not force:
            raw = self.cache.get("club", ttl_seconds=max(60, self.settings.scrape_interval_minutes * 60))
            if raw:
                logger.info("Using cached Pro Clubs Tracker payload")

        try:
            if raw is None:
                request_count += 1
                raw = await self._fetch_api()

            if raw is None:
                request_count += 1
                raw = await self.browser.fetch_json_from_page(self.settings.pct_club_url, self.api_url)

            if raw is None:
                raise RuntimeError("Pro Clubs Tracker returned no usable data")

            self.cache.set("club", raw)
            snapshot = self.parser.parse(raw)
            self.repository.save_snapshot(snapshot, raw=raw)
            self.repository.log_scrape(source=source, success=True, request_count=request_count)
            logger.info("Saved snapshot: %s matches", len(snapshot.matches))
            return snapshot
        except Exception as exc:
            self.repository.log_scrape(source=source, success=False, error=str(exc), request_count=request_count)
            logger.exception("Refresh failed")
            raise

    async def _fetch_api(self) -> Optional[dict[str, Any]]:
        async with httpx.AsyncClient(headers=self.headers, follow_redirects=True, timeout=20) as client:
            response = await client.get(self.api_url)
            if response.status_code in {403, 429}:
                logger.warning("PCT API blocked/limited: %s", response.status_code)
                return None
            if response.status_code != 200:
                logger.warning("PCT API status %s", response.status_code)
                return None

            raw = response.content
            if raw[:2] == b"\x1f\x8b" or "gzip" in response.headers.get("content-encoding", "").lower():
                raw = gzip.decompress(raw)
            if raw[:100].strip().startswith(b"<"):
                logger.warning("PCT API returned HTML instead of JSON")
                return None

            data = response.json()
            return data if isinstance(data, dict) else None
