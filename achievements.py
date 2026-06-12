"""
Achievements & Curses System
From AllCalculatedRoast project - adds fun gamification to match reports
"""
from typing import Dict, List, Any

Player = Dict[str, Any]

# ─── Conditions ───

def _holy_trifecta(p: Player) -> bool:
    """Goal + 2+ assists + 100% passing (min 10 passes)."""
    return (p.get("goals", 0) >= 1 and p.get("assists", 0) >= 2 and 
            p.get("passes_attempted", 0) >= 10 and 
            p.get("passes_completed", 0) == p.get("passes_attempted", 0))

def _sniper(p: Player) -> bool:
    """2+ long-range goals."""
    return p.get("long_goals", 0) >= 2

def _hat_trick(p: Player) -> bool:
    """5+ goals in one match."""
    return p.get("goals", 0) >= 5

def _playmaker(p: Player) -> bool:
    """3+ assists."""
    return p.get("assists", 0) >= 3

def _brickfoot(p: Player) -> bool:
    """Miss 3+ big chances."""
    return p.get("big_chances_missed", 0) >= 3

def _ghost(p: Player) -> bool:
    """0 goals, 0 assists, 0 tackles, 0 interceptions but played."""
    return (p.get("goals", 0) == 0 and p.get("assists", 0) == 0 and 
            p.get("tackles", 0) == 0 and p.get("interceptions", 0) == 0 and
            p.get("passes_attempted", 0) >= 5)

def _iron_wall(p: Player) -> bool:
    """12+ combined tackles + interceptions."""
    return (p.get("tackles", 0) + p.get("interceptions", 0)) >= 12

# ─── Achievements List ───

ACHIEVEMENTS = [
    {"key": "holy_trifecta", "label": "👑 Holy Trifecta", "condition": _holy_trifecta, "desc": "Goal + 2 assists + 100% passing"},
    {"key": "sniper", "label": "🎯 Sniper", "condition": _sniper, "desc": "2+ long-range goals"},
    {"key": "hat_trick", "label": "🎩 Hat-Trick", "condition": _hat_trick, "desc": "5+ goals"},
    {"key": "playmaker", "label": "🎪 Playmaker", "condition": _playmaker, "desc": "3+ assists"},
    {"key": "iron_wall", "label": "🛡️ Iron Wall", "condition": _iron_wall, "desc": "12+ tackles + interceptions"},
]

CURSES = [
    {"key": "brickfoot", "label": "🧱 Brickfoot", "condition": _brickfoot, "desc": "Missed 3+ big chances"},
    {"key": "ghost", "label": "👻 Ghost", "condition": _ghost, "desc": "0 contributions entire match"},
]

def evaluate_player(p: Player) -> Dict:
    """Check achievements and curses for a player."""
    earned = [a for a in ACHIEVEMENTS if a["condition"](p)]
    curses = [c for c in CURSES if c["condition"](p)]
    return {"achievements": earned, "curses": curses}

def format_badges(results: Dict) -> str:
    """Format achievements/curses as emoji string."""
    badges = []
    for a in results["achievements"]:
        badges.append(a["label"])
    for c in results["curses"]:
        badges.append(c["label"])
    return " ".join(badges) if badges else ""
