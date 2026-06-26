from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from src.core.errors import PlayerNotInMatch


Result = Literal["W", "D", "L"]


class PlayerIdentity(BaseModel):
    ea_id: str
    nickname: str
    image: Optional[str] = None
    personality: Optional[str] = None
    meme_tags: List[str] = Field(default_factory=list)
    position: Optional[str] = None
    number: Optional[int] = None
    raw: Dict[str, Any] = Field(default_factory=dict)


class PlayerMatchStats(BaseModel):
    ea_id: str
    display_name: str
    position: Optional[str] = None
    rating: float = 0.0
    minutes: int = 0
    goals: int = 0
    assists: int = 0
    shots: int = 0
    passes_attempted: int = 0
    passes_completed: int = 0
    tackles: int = 0
    interceptions: int = 0
    saves: int = 0
    possession_losses: int = 0
    red_cards: int = 0
    yellow_cards: int = 0
    clean_sheets: int = 0
    raw: Dict[str, Any] = Field(default_factory=dict)

    @property
    def pass_accuracy(self) -> float:
        if self.passes_attempted <= 0:
            return 0.0
        return round((self.passes_completed / self.passes_attempted) * 100, 1)

    @property
    def played(self) -> bool:
        return self.minutes > 0 or self.rating > 0 or bool(self.raw)


class Match(BaseModel):
    match_id: str
    date: datetime
    opponent: str
    score_for: int
    score_against: int
    result: Result
    players: List[PlayerMatchStats] = Field(default_factory=list)
    raw: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("players")
    @classmethod
    def only_real_played_players(cls, players: List[PlayerMatchStats]) -> List[PlayerMatchStats]:
        # This is the global hard rule: if a player is not in match.players,
        # they do not exist for match-level commands.
        return [player for player in players if player.played]

    @property
    def player_ids(self) -> set[str]:
        return {player.ea_id.lower() for player in self.players}

    def require_player(self, ea_id_or_name: str) -> PlayerMatchStats:
        key = ea_id_or_name.lower().strip()
        for player in self.players:
            if player.ea_id.lower() == key or player.display_name.lower() == key:
                return player
        raise PlayerNotInMatch(f"{ea_id_or_name} did not play this match")


class ClubSnapshot(BaseModel):
    club_name: str
    division: int = 0
    skill_rating: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_scored: int = 0
    goals_conceded: int = 0
    scraped_at: datetime = Field(default_factory=datetime.now)
    matches: List[Match] = Field(default_factory=list)

    @property
    def latest_match(self) -> Optional[Match]:
        return self.matches[0] if self.matches else None


def enforce_match_players_only(match: Match, candidates: List[PlayerIdentity]) -> List[PlayerIdentity]:
    """Return identities only for people who are present in match.players."""
    allowed = match.player_ids
    return [candidate for candidate in candidates if candidate.ea_id.lower() in allowed]
