from typing import List, Dict
from models import PlayerStats, ClubStats, MatchResult
​
class StatsEngine:
"""
Stable stats engine for Pro Clubs data.
Important rule:
PCT memberStats is the truth for season totals:
games, goals, assists, rating, passes, pass accuracy, win rate.
Recent match data is limited by PCT, often only last few matches.
So advanced ranking must NOT depend heavily on recent-only fields.
This file avoids relying on missing/unstable fields like:
shots_on_target
key_passes
fouls
interceptions
That makes MVP / Worst / Fraud / Carry / Ghost more stable.
"""
POSITION_WEIGHTS = {
"GK": {"off": 0.35, "def": 1.50, "pass": 0.90, "rating": 1.25},
"CB": {"off": 0.45, "def": 1.40, "pass": 1.00, "rating": 1.20},
"LB": {"off": 0.65, "def": 1.20, "pass": 1.05, "rating": 1.15},
"RB": {"off": 0.65, "def": 1.20, "pass": 1.05, "rating": 1.15},
"CDM": {"off": 0.75, "def": 1.20, "pass": 1.25, "rating": 1.15},
"CM": {"off": 0.95, "def": 1.00, "pass": 1.35, "rating": 1.10},
"CAM": {"off": 1.25, "def": 0.65, "pass": 1.35, "rating": 1.10},
"LW": {"off": 1.40, "def": 0.55, "pass": 1.05, "rating": 1.05},
"RW": {"off": 1.40, "def": 0.55, "pass": 1.05, "rating": 1.05},
"ST": {"off": 1.55, "def": 0.35, "pass": 0.85, "rating": 1.05},
"CF": {"off": 1.40, "def": 0.50, "pass": 1.00, "rating": 1.05},
}
────────────────────────────────────────────
SAFE HELPERS
────────────────────────────────────────────
@staticmethod
def _num(value, default=0.0) -> float:
try:
if value is None:
return float(default)
return float(value)
except (TypeError, ValueError):
return float(default)
@staticmethod
def _int(value, default=0) -> int:
try:
if value is None:
return int(default)
return int(value)
except (TypeError, ValueError):
return int(default)
@classmethod
def _get(cls, player: PlayerStats, field: str, default=0.0) -> float:
return cls._num(getattr(player, field, default), default)
@classmethod
def _games(cls, player: PlayerStats) -> int:
return max(cls._int(getattr(player, "games", 0), 0), 1)
@classmethod
def _eligible(cls, players: List[PlayerStats], min_games: int = 1) -> List[PlayerStats]:
"""
Avoid selecting empty/new rows for rankings.
Still returns all players if nobody meets min_games.
"""
if not players:
return []
eligible = [
p for p in players
if getattr(p, "name", None)
and isinstance(getattr(p, "name", ""), str)
and getattr(p, "name", "").strip()
and cls._int(getattr(p, "games", 0), 0) >= min_games
]
return eligible or players
@staticmethod
def _clamp(value: float, low: float, high: float) -> float:
return max(low, min(high, value))
────────────────────────────────────────────
BASIC PER-GAME STATS
────────────────────────────────────────────
@classmethod
def compute_per_game(cls, player: PlayerStats) -> PlayerStats:
g = cls._games(player)
goals = cls._get(player, "goals", 0)
assists = cls._get(player, "assists", 0)
rating = cls._get(player, "rating", 0)
wins = cls._get(player, "wins", 0)
losses = cls._get(player, "losses", 0)
draws = cls._get(player, "draws", 0)
player.goals_pg = round(goals / g, 2)
player.assists_pg = round(assists / g, 2)
PCT ratingAve is usually already average 1-10.
Some APIs can return 70 instead of 7.0, so normalize safely.
if rating > 100:
player.rating_pg = round(rating / max(g, 1), 2)
elif rating > 10:
player.rating_pg = round(rating / 10.0, 2)
else:
player.rating_pg = round(rating, 2)
Preserve scraper win_rate if W/L/D are empty.
This was your critical Phase 1 fix.
wld_total = wins + losses + draws
if wld_total > 0:
player.win_rate = round(wins / wld_total * 100, 1)
else:
player.win_rate = round(cls._get(player, "win_rate", 0), 1)
return player
────────────────────────────────────────────
STABLE ADVANCED STATS
────────────────────────────────────────────
@classmethod
def compute_advanced(cls, player: PlayerStats, position: str = "CM") -> PlayerStats:
"""
Stable advanced calculation.
Uses reliable season fields:
rating_pg
goals / assists
pass_accuracy / passes_made
tackles
clean_sheets / saves / goals_conceded
possession_losses
cards
win_rate
Avoids fragile fields:
shots_on_target
key_passes
fouls
interceptions
"""
position = (position or "CM").upper()
weights = cls.POSITION_WEIGHTS.get(position, cls.POSITION_WEIGHTS["CM"])
g = cls._games(player)
goals = cls._get(player, "goals", 0)
assists = cls._get(player, "assists", 0)
tackles = cls._get(player, "tackles", 0)
clean_sheets = cls._get(player, "clean_sheets", 0)
saves = cls._get(player, "saves", 0)
goals_conceded = cls._get(player, "goals_conceded", 0)
passes_made = cls._get(player, "passes_made", 0)
pass_accuracy = cls._get(player, "pass_accuracy", 0)
possession_losses = cls._get(player, "possession_losses", 0)
cards = cls._get(player, "cards", 0)
win_rate = cls._get(player, "win_rate", 0)
rating_pg = cls._get(player, "rating_pg", cls._get(player, "rating", 0))
goals_pg = goals / g
assists_pg = assists / g
tackles_pg = tackles / g
passes_pg = passes_made / g
losses_pg = possession_losses / g
cards_pg = cards / g
saves_pg = saves / g
conceded_pg = goals_conceded / g
clean_sheet_rate = clean_sheets / g
Offensive contribution: stable season totals.
offensive = (
goals_pg * 22.0 +
assists_pg * 16.0 +
rating_pg * 2.0
) * weights["off"]
Defensive contribution: stable for defenders/GK, still harmless for attackers.
defensive = (
tackles_pg * 3.0 +
clean_sheet_rate * 10.0 +
saves_pg * 2.0 -
conceded_pg * 1.2
) * weights["def"]
Passing influence: do not overrate huge pass volume alone.
passing = (
cls._clamp(pass_accuracy, 0, 100) * 0.18 +
cls._clamp(passes_pg, 0, 80) * 0.18
) * weights["pass"]
Rating anchor: PCT ratingAve is one of the most reliable fields.
rating_anchor = rating_pg  7.5  weights["rating"]
Win contribution: small bonus only, not dominant.
win_bonus = cls._clamp(win_rate, 0, 100) * 0.12
Penalties: possession losses/cards hurt impact but do not destroy it.
error_penalty = (
losses_pg * 1.4 +
cards_pg * 8.0
)
player.offensive_contribution = round(max(0.0, offensive), 2)
player.defensive_contribution = round(max(0.0, defensive), 2)
player.passing_influence = round(max(0.0, passing), 2)
player.impact_score = round(
max(
0.0,
rating_anchor +
player.offensive_contribution +
player.defensive_contribution +
player.passing_influence +
win_bonus -
error_penalty
),
2,
)
Carry score = good rating + goal contribution + win impact.
player.clutch_score = round(
max(
0.0,
rating_pg * 8.0 +
goals_pg * 18.0 +
assists_pg * 12.0 +
cls._clamp(win_rate, 0, 100) * 0.18
),
2,
)
Error score/fraud score:
Use low rating, possession losses, cards, bad pass accuracy.
low_rating_penalty = max(0.0, 6.5 - rating_pg) * 6.0
bad_pass_penalty = max(0.0, 75.0 - pass_accuracy) * 0.18 if pass_accuracy > 0 else 2.0
loss_penalty = losses_pg * 2.2
card_penalty = cards_pg * 10.0
player.error_score = round(
max(0.0, low_rating_penalty + bad_pass_penalty + loss_penalty + card_penalty),
2,
)
player.throwing_score = round(
max(
0.0,
player.error_score +
max(0.0, 6.0 - rating_pg) * 2.0
),
2,
)
Form is rating centered around 6.5 instead of 5.0.
6.5 is a more realistic "okay" rating in FC clubs.
player.form_index = round(rating_pg - 6.5, 2)
Extra helper scores for commands.
player.ghost_score = round(
max(
0.0,
(7.0 - rating_pg) * 5.0 +
max(0.0, 0.20 - goals_pg) * 8.0 +
max(0.0, 0.20 - assists_pg) * 6.0 +
max(0.0, 12.0 - passes_pg) * 0.25
),
2,
)
player.ball_loss_score = round(
max(
0.0,
losses_pg * 3.0 +
bad_pass_penalty +
max(0.0, 6.0 - rating_pg) * 2.0
),
2,
)
return player
@classmethod
def compute_all(cls, players: List[PlayerStats], squad_map: Dict) -> List[PlayerStats]:
result = []
for p in players:
pos = squad_map.get(getattr(p, "name", ""), {}).get("position", "CM")
p = cls.compute_per_game(p)
p = cls.compute_advanced(p, pos)
result.append(p)
return result
────────────────────────────────────────────
RANKING SELECTORS
────────────────────────────────────────────
@classmethod
def get_mvp(cls, players: List[PlayerStats]) -> PlayerStats:
eligible = cls._eligible(players, min_games=1)
return max(
eligible,
key=lambda p: (
cls._get(p, "impact_score", 0),
cls._get(p, "rating_pg", 0),
cls._get(p, "goals", 0) + cls._get(p, "assists", 0),
),
)
@classmethod
def get_worst(cls, players: List[PlayerStats]) -> PlayerStats:
eligible = cls._eligible(players, min_games=1)
return min(
eligible,
key=lambda p: (
cls._get(p, "impact_score", 0),
cls._get(p, "rating_pg", 0),
),
)
@classmethod
def get_fraud(cls, players: List[PlayerStats]) -> PlayerStats:
eligible = cls._eligible(players, min_games=1)
return max(
eligible,
key=lambda p: (
cls._get(p, "throwing_score", 0),
cls._get(p, "error_score", 0),
-cls._get(p, "rating_pg", 0),
),
)
@classmethod
def get_carry(cls, players: List[PlayerStats]) -> PlayerStats:
eligible = cls._eligible(players, min_games=1)
return max(
eligible,
key=lambda p: (
cls._get(p, "clutch_score", 0),
cls._get(p, "impact_score", 0),
cls._get(p, "rating_pg", 0),
),
)
@classmethod
def get_ghost(cls, players: List[PlayerStats]) -> PlayerStats:
eligible = cls._eligible(players, min_games=1)
return max(
eligible,
key=lambda p: (
cls._get(p, "ghost_score", 0),
-cls._get(p, "rating_pg", 0),
),
)
@classmethod
def get_ball_hog(cls, players: List[PlayerStats]) -> PlayerStats:
eligible = cls._eligible(players, min_games=1)
return max(
eligible,
key=lambda p: (
cls._get(p, "ball_loss_score", 0),
cls._get(p, "possession_losses", 0) / max(cls._get(p, "games", 1), 1),
),
)
────────────────────────────────────────────
INTERPRETATION TEXT
────────────────────────────────────────────
@classmethod
def interpret_stat(cls, stat_name: str, value: float, position: str = "") -> str:
interpretations = {
"pass_accuracy": {
(0, 60): "Pass accuracy {val}% — كتباصي الكرة بحال إلا كتدير raffle.",
(60, 75): "Pass accuracy {val}% — 3ndak 25% ديال التخربيق فكل باصة.",
(75, 85): "Pass accuracy {val}% — مزيان، ولكن داك 15% الباقي خاصو تحقيق.",
(85, 92): "Pass accuracy {val}% — صاحي، كتباصي بحال Modrić.",
(92, 100): "Pass accuracy {val}% — هادي ماشي pass accuracy، هادي precision surgical.",
},
"rating": {
(0, 5): "Rating {val} — هادي ماشي note، هادي warning.",
(5, 6): "Rating {val} — كنتي NPC رسمي اليوم.",
(6, 7): "Rating {val} — ماشي مزيان ماشي خايب، average.",
(7, 8): "Rating {val} — صاحي، كتبان لي كتعرف شنو كتدير.",
(8, 10): "Rating {val} — هادا rating ديال Ballon d'Or، ولا غير lucky game؟",
},
"goals_pg": {
(0, 0.3): "Goals per game {val} — الحارس دار save أكثر منك.",
(0.3, 0.7): "Goals per game {val} — كتسجل من فترة لفترة، بحال taxes.",
(0.7, 1.2): "Goals per game {val} — كتسجل بانتظام، مزيان.",
(1.2, 2): "Goals per game {val} — هادا striker حقيقي، كتضرب بحال Haaland.",
(2, 10): "Goals per game {val} — واش كتباغي تدخل التاريخ ولا شنو؟",
},
"impact_score": {
(0, 30): "Impact {val} — واش كتجي تشوف المباراة ولا تلعب؟",
(30, 55): "Impact {val} — خاصك تزيد تخدم.",
(55, 75): "Impact {val} — مزيان، contribution واضح.",
(75, 95): "Impact {val} — صاحي، كتجبد الفريق.",
(95, 999): "Impact {val} — هادا carry رسمي، Ballon d'Or material.",
},
}
ranges = interpretations.get(stat_name, {})
for (low, high), text in ranges.items():
if low <= value < high:
return text.replace("{val}", str(round(value, 2)))
return f"{stat_name}: {round(value, 2) if isinstance(value, (int, float)) else value}"
