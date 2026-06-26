from __future__ import annotations

from typing import Any, Optional

from src.data.repositories import ClubRepository
from src.domain.models import ClubSnapshot, Match
from src.scraper.proclubs_tracker import ProClubsTrackerClient


class MatchService:
    def __init__(self, client: ProClubsTrackerClient, repository: ClubRepository):
        self.client = client
        self.repository = repository
        self.current_snapshot: Optional[ClubSnapshot] = None

    async def refresh(self, force: bool = False, source: str = "manual") -> ClubSnapshot:
        self.current_snapshot = await self.client.refresh(force=force, source=source)
        return self.current_snapshot

    def latest_match(self) -> Optional[Match]:
        if self.current_snapshot and self.current_snapshot.latest_match:
            return self.current_snapshot.latest_match
        return self.repository.latest_match()

    def status(self) -> dict[str, Any]:
        latest = self.latest_match()
        return {
            "has_latest_match": latest is not None,
            "latest_match_id": latest.match_id if latest else None,
            "latest_players": len(latest.players) if latest else 0,
            "latest_score": f"{latest.score_for}-{latest.score_against}" if latest else None,
            "opponent": latest.opponent if latest else None,
        }
