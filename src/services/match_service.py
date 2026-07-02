from __future__ import annotations

from typing import Optional

from src.core.logging import get_logger
from src.data.repositories import ClubRepository
from src.domain.models import ClubSnapshot, Match
from src.scraper.proclubs_tracker import ProClubsTrackerClient
from src.squad.registry import SquadRegistry

logger = get_logger(__name__)


class MatchService:
    """Orchestrates match data fetching and caching."""

    def __init__(
        self,
        client: ProClubsTrackerClient,
        repository: ClubRepository,
        squad: SquadRegistry,
    ):
        self.client = client
        self.repo = repository
        self.squad = squad

    async def refresh(self, force: bool = False, source: str = "scheduled") -> ClubSnapshot:
        """Fetch fresh data from ProClubsTracker."""
        logger.info("[MatchService] Refreshing data (force=%s, source=%s)", force, source)
        snapshot = await self.client.refresh(force=force, source=source)
        return snapshot

    def latest_match(self) -> Optional[Match]:
        """Get the most recent match from the database."""
        return self.repo.latest_match()

    def last_matches(self, limit: int = 10) -> list[Match]:
        """Get the last N matches from the database."""
        return self.repo.last_matches(limit=limit)
