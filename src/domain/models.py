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
    shots_on_target: int = 0
    passes_attempted: int = 0
    passes_completed: int = 0
    key_passes: int = 0
    tackles: int = 0
    interceptions: int = 0
    saves: int = 0
    possession_losses: int = 0
    red_cards: int = 0
    yellow_cards: int = 0
    clean_sheets: int = 0
    distance_covered: float = 0.0
    sprint_speed: float = 0.0
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
        filtered = [p for p in players if p.played]
        return filtered

    def get_player(self, ea_id: str) -> PlayerMatchStats:
        for p in self.players:
            if p.ea_id == ea_id:
                return p
        raise PlayerNotInMatch(f"Player {ea_id} not in match.players")

    @property
    def mvp(self) -> Optional[PlayerMatchStats]:
        if not self.players:
            return None
        return max(self.players, key=lambda p: (p.rating, p.goals, p.assists, -p.possession_losses))

    @property
    def fraud(self) -> Optional[PlayerMatchStats]:
        if not self.players:
            return None
        return min(self.players, key=lambda p: (p.rating, -p.possession_losses, p.minutes))

    @property
    def ghost(self) -> Optional[PlayerMatchStats]:
        if not self.players:
            return None
        ghosts = [p for p in self.players if p.minutes < 20 and p.rating < 5.0]
        if not ghosts:
            return min(self.players, key=lambda p: (p.minutes, p.rating))
        return min(ghosts, key=lambda p: (p.minutes, p.rating))

    @property
    def carry(self) -> Optional[PlayerMatchStats]:
        if not self.players:
            return None
        return max(self.players, key=lambda p: (p.goals + p.assists, p.rating, p.key_passes))

    @property
    def ball_loser(self) -> Optional[PlayerMatchStats]:
        if not self.players:
            return None
        return max(self.players, key=lambda p: (p.possession_losses, -p.passes_completed))

    @property
    def playmaker(self) -> Optional[PlayerMatchStats]:
        if not self.players:
            return None
        return max(self.players, key=lambda p: (p.assists + p.key_passes, p.pass_accuracy, p.passes_completed))

    @property
    def sniper(self) -> Optional[PlayerMatchStats]:
        if not self.players:
            return None
        eligible = [p for p in self.players if p.shots > 0]
        if not eligible:
            return None
        return max(eligible, key=lambda p: (p.goals / max(p.shots, 1), p.shots_on_target / max(p.shots, 1)))


class ClubSnapshot(BaseModel):
    club_name: str
    division: int = 0
    skill_rating: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_scored: int = 0
    goals_conceded: int = 0
    matches: List[Match] = Field(default_factory=list)
    scraped_at: datetime = Field(default_factory=datetime.now)

    @property
    def latest_match(self) -> Optional[Match]:
        if not self.matches:
            return None
        return max(self.matches, key=lambda m: m.date)


class PlayerForm(BaseModel):
    ea_id: str
    match_id: str
    form_score: float = 0.0
    impact_score: float = 0.0
    clutch_score: float = 0.0
    error_score: float = 0.0
    throwing_score: float = 0.0
    created_at: datetime = Field(default_factory=datetime.now)
