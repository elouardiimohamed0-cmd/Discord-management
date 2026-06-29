from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.core.logging import get_logger
from src.data.repositories import ClubRepository
from src.domain.models import ClubSnapshot, Match, PlayerForm, PlayerMatchStats
from src.scraper.proclubs_tracker import ProClubsTrackerClient
from src.squad.registry import SquadRegistry

logger = get_logger(__name__)


class MatchService:
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
        snapshot = await self.client.refresh(force=force, source=source)
        # Compute advanced metrics for each match
        for match in snapshot.matches:
            self._compute_and_save_form(match)
        return snapshot

    def _compute_and_save_form(self, match: Match) -> None:
        for player in match.players:
            identity = self.squad.find_by_ea_id(player.ea_id)
            if not identity:
                continue

            # Impact Score: weighted offensive + defensive
            impact = (
                player.goals * 3.0 +
                player.assists * 2.5 +
                player.key_passes * 2.0 +
                player.tackles * 1.5 +
                player.interceptions * 1.5 +
                player.saves * 2.0 -
                player.possession_losses * 1.0 -
                player.yellow_cards * 1.5 -
                player.red_cards * 3.0
            )
            # Normalize to 0-10
            impact_score = max(0.0, min(10.0, impact / 10.0))

            # Clutch Score: performance in close matches
            clutch = 0.0
            if match.result == "W" and abs(match.score_for - match.score_against) <= 1:
                clutch = player.rating * 0.8 + player.goals * 2.0
            elif match.result == "W":
                clutch = player.rating * 0.5
            clutch_score = max(0.0, min(10.0, clutch / 5.0))

            # Error Score
            error = player.possession_losses + player.yellow_cards * 2 + player.red_cards * 4 + (10 - player.pass_accuracy) / 10
            error_score = max(0.0, min(10.0, error))

            # Throwing Score: error / rating ratio
            throwing = error / max(player.rating, 1.0) * 5.0
            throwing_score = max(0.0, min(10.0, throwing))

            # Form Score: composite
            form = (impact_score * 0.4 + clutch_score * 0.2 + (10 - error_score) * 0.3 + player.rating * 0.1)

            pf = PlayerForm(
                ea_id=player.ea_id,
                match_id=match.match_id,
                form_score=round(form, 2),
                impact_score=round(impact_score, 2),
                clutch_score=round(clutch_score, 2),
                error_score=round(error_score, 2),
                throwing_score=round(throwing_score, 2),
            )
            self.repo.save_form(pf)

    def status(self) -> Dict[str, Any]:
        latest = self.repo.latest_match()
        if not latest:
            return {"latest_match_id": None, "latest_score": None, "opponent": None, "latest_players": 0}
        return {
            "latest_match_id": latest.match_id,
            "latest_score": f"{latest.score_for}-{latest.score_against}",
            "opponent": latest.opponent,
            "latest_players": len(latest.players),
        }

    def latest_match(self) -> Optional[Match]:
        return self.repo.latest_match()

    def last_matches(self, limit: int = 10) -> List[Match]:
        return self.repo.last_matches(limit)

    def player_history(self, ea_id: str, limit: int = 20) -> List[PlayerMatchStats]:
        return self.repo.player_matches(ea_id, limit)
