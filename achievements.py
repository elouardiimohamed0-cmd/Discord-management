"""
Achievements & Curses System
Based on AllCalculatedRoast — adds fun gamification to match reports
"""
from typing import Dict, List, Callable, Any

Player = Dict[str, Any]

# ─── Conditions ───

def _holy_trifecta(p: Player) -> bool:
    """Goal + 2+ assists + 100% passing (min 10 passes)."""
    return (p["goals"] >= 1 and p["assists"] >= 2 and 
            p["passes_attempted"] >= 10 and p["passes_completed"] == p["passes_attempted"])

def _sniper(p: Player) -> bool:
    """2+ long-range goals."""
    return p.get("long_goals", 0) >= 2

def _hat_trick(p: Player) -> bool:
    """5+ goals in one match."""
    return p["goals"] >= 5

def _playmaker(p: Player) -> bool:
    """3+ assists."""
    return p["assists"] >= 3

def _brickfoot(p: Player) -> bool:
    """Miss 3+ big chances."""
    return p.get("big_chances_missed", 0) >= 3

def _ghost(p: Player) -> bool:
    """0 goals, 0 assists, 0 tackles, 0 interceptions but played."""
    return (p["goals"] == 0 and p["assists"] == 0 and 
            p["tackles"] == 0 and p["interceptions"] == 0 and
            p.get("passes_attempted", 0) >= 5)

def _iron_wall(p: Player) -> bool:
    """12+ combined tackles + interceptions."""
    return (p["tackles"] + p["interceptions"]) >= 12

# ─── Achievements List ───

ACHIEVEMENTS = [
    {"key": "holy_trifecta", "label": "👑 Holy Trifecta", "condition": _holy_trifecta, "desc": "Goal + 2 assists + 100% passing"},
    {"key": "sniper", "label": "🎯 Sniper", "condition": _sniper, "desc": "2+ long-range goals"},
    {"key": "hat_trick", "label": "🎩 Hat-Trick Tyrant", "condition": _hat_trick, "desc": "5+ goals"},
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
