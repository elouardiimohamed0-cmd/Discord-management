from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime

class PlayerStats(BaseModel):
    name: str
    position: Optional[str] = None
    games: int = 0
    rating: float = 0.0
    goals: int = 0
    assists: int = 0
    shots: int = 0
    shots_on_target: int = 0
    pass_accuracy: float = 0.0
    passes_made: int = 0
    key_passes: int = 0
    tackles: int = 0
    interceptions: int = 0
    possession_losses: int = 0
    dribbles: int = 0
    fouls: int = 0
    cards: int = 0
    distance_covered: float = 0.0
    minutes_played: int = 0
    motm: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    saves: int = 0
    clean_sheets: int = 0
    goals_conceded: int = 0
    
    # Per-game averages (computed)
    goals_pg: float = 0.0
    assists_pg: float = 0.0
    rating_pg: float = 0.0
    win_rate: float = 0.0
    
    # Advanced metrics (computed)
    impact_score: float = 0.0
    clutch_score: float = 0.0
    error_score: float = 0.0
    throwing_score: float = 0.0
    form_index: float = 0.0
    passing_influence: float = 0.0
    defensive_contribution: float = 0.0
    offensive_contribution: float = 0.0

class MatchResult(BaseModel):
    match_id: str
    date: datetime
    opponent: str
    score_for: int
    score_against: int
    result: str  # W, L, D
    player_stats: Dict[str, dict] = {}
    motm: Optional[str] = None

class ClubStats(BaseModel):
    club_name: str
    division: int = 6
    skill_rating: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    goals_scored: int = 0
    goals_conceded: int = 0
    win_rate: float = 0.0
    current_streak: int = 0
    best_streak: int = 0
    players: List[PlayerStats] = []
    matches: List[MatchResult] = []
    last_updated: datetime = Field(default_factory=datetime.now)
