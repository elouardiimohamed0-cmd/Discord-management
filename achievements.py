"""
Achievements & Curses System v3.0
Inspired by AllCalculatedRoast — gamification with crowns, powers, and curses.

Achievements (Crowns) = good performance rewards with POWERS
Curses = bad performance punishments with CURSES
"""
from typing import Dict, List, Any

Player = Dict[str, Any]

# ── Conditions ────────────────────────────────────────────────────────────────

def _perfect_passing(p: Player) -> bool:
    """100% pass accuracy with at least 10 passes attempted."""
    return p.get("passes_attempted", 0) >= 10 and p.get("passes_completed", 0) == p.get("passes_attempted", 0)

def _holy_trifecta(p: Player) -> bool:
    """Goal + 2 assists + 100% passing (min 10 passes) in one match."""
    return p.get("goals", 0) >= 1 and p.get("assists", 0) >= 2 and _perfect_passing(p)

def _sniper(p: Player) -> bool:
    """2+ long-range goals."""
    return p.get("long_goals", 0) >= 2

def _hat_trick(p: Player) -> bool:
    """5+ goals in one match."""
    return p.get("goals", 0) >= 5

def _midfield_wizard(p: Player) -> bool:
    """3+ assists in one match — any position."""
    return p.get("assists", 0) >= 3

def _midfield_maestro(p: Player) -> bool:
    """Midfielder with 90%+ passing (min 15 attempts) AND 2+ interceptions."""
    pos = p.get("position", "").lower()
    is_mid = any(k in pos for k in ("midfield", "creator", "magician", "recycler", "maestro", "spark", "cam", "cm", "cdm", "box"))
    if not is_mid:
        return False
    pas_pct = (p.get("passes_completed", 0) / max(p.get("passes_attempted", 1), 1) * 100
               if p.get("passes_attempted", 0) >= 15 else 0)
    return pas_pct >= 90 and p.get("interceptions", 0) >= 2

def _defensive_titan(p: Player) -> bool:
    """Defender/CDM with 10+ combined tackles+interceptions."""
    pos = p.get("position", "").lower()
    is_def = any(k in pos for k in ("defend", "boss", "cdm", "sweeper", "centre back", "fullback", "wall", "recycler", "keeper"))
    if not is_def:
        return False
    return (p.get("tackles", 0) + p.get("interceptions", 0)) >= 10

def _iron_wall(p: Player) -> bool:
    """Any position — interceptions + tackles reach 12 or more."""
    return (p.get("interceptions", 0) + p.get("tackles", 0)) >= 12

def _own_goal_jester(p: Player) -> bool:
    """Score an own goal."""
    return p.get("own_goals", 0) >= 1

def _brickfoot(p: Player) -> bool:
    """Miss 3 or more big chances in one match."""
    return p.get("big_chances_missed", 0) >= 3

def _ice_cold(p: Player) -> bool:
    """Striker who took zero shots."""
    return any(k in p.get("position", "").upper() for k in ("ST", "CF", "LW", "RW")) and p.get("shots", 0) == 0

def _ghost(p: Player) -> bool:
    """Played the full match but 0 goals, 0 assists, 0 interceptions, 0 tackles."""
    return (
        p.get("goals", 0) == 0
        and p.get("assists", 0) == 0
        and p.get("interceptions", 0) == 0
        and p.get("tackles", 0) == 0
        and p.get("passes_attempted", 0) >= 5
    )

def _playmaker(p: Player) -> bool:
    """5 or more assists in one match."""
    return p.get("assists", 0) >= 5

def _clinical_finisher(p: Player) -> bool:
    """3+ goals with 80%+ conversion rate."""
    shots = p.get("shots", 0)
    goals = p.get("goals", 0)
    return goals >= 3 and shots >= 3 and (goals / shots * 100) >= 80

def _brick_wall_keeper(p: Player) -> bool:
    """Keeper with 5+ saves (implied by low goals against if keeper)."""
    pos = p.get("position", "").lower()
    return "keeper" in pos or "goalkeeper" in pos or "gk" in pos

# ── Achievement Catalogue (Crowns) ───────────────────────────────────────────

ACHIEVEMENTS = [
    {
        "key": "holy_trifecta",
        "label": "👑 Holy Trifecta Crown",
        "condition": _holy_trifecta,
        "power": "Controls lineup and positions for the next 3 matches",
        "emoji": "👑",
    },
    {
        "key": "sniper",
        "label": "🎯 Sniper",
        "condition": _sniper,
        "power": "Must attempt at least 5 long shots next match",
        "emoji": "🎯",
    },
    {
        "key": "hat_trick_tyrant",
        "label": "🎩 Hat-Trick Tyrant",
        "condition": _hat_trick,
        "power": "Team must feed this player exclusively for one half",
        "emoji": "🎩",
    },
    {
        "key": "midfield_wizard",
        "label": "🧙 Midfield Wizard",
        "condition": _midfield_wizard,
        "power": "Chooses the team formation next match",
        "emoji": "🧙",
    },
    {
        "key": "playmaker",
        "label": "🎪 Playmaker",
        "condition": _playmaker,
        "power": "Everyone must attempt at least one assist next match",
        "emoji": "🎪",
    },
    {
        "key": "midfield_maestro",
        "label": "🎼 Midfield Maestro",
        "condition": _midfield_maestro,
        "power": "Calls all set pieces next match",
        "emoji": "🎼",
    },
    {
        "key": "defensive_titan",
        "label": "🧱 Defensive Titan",
        "condition": _defensive_titan,
        "power": "Chooses who plays at the back next match",
        "emoji": "🧱",
    },
    {
        "key": "iron_wall",
        "label": "🛡️ Iron Wall",
        "condition": _iron_wall,
        "power": "Team must play ultra-defensive next match",
        "emoji": "🛡️",
    },
    {
        "key": "clinical_finisher",
        "label": "⚡ Clinical Finisher",
        "condition": _clinical_finisher,
        "power": "Gets penalty duty next match",
        "emoji": "⚡",
    },
]

# ── Curse Catalogue ──────────────────────────────────────────────────────────

CURSES = [
    {
        "key": "own_goal_jester",
        "label": "🤡 Own Goal Jester",
        "condition": _own_goal_jester,
        "curse": "Team votes your position next match",
        "emoji": "🤡",
    },
    {
        "key": "brickfoot",
        "label": "🧱 Brickfoot",
        "condition": _brickfoot,
        "curse": "Must play as a defender next match",
        "emoji": "🧱",
    },
    {
        "key": "ice_cold",
        "label": "🥶 Ice Cold",
        "condition": _ice_cold,
        "curse": "Cannot shoot next match — passes only",
        "emoji": "🥶",
    },
    {
        "key": "ghost",
        "label": "👻 Ghost",
        "condition": _ghost,
        "curse": "Must announce every touch in voice chat next match",
        "emoji": "👻",
    },
]

# ── Public Engine ────────────────────────────────────────────────────────────

def evaluate_players(players: List[Player]) -> List[Dict]:
    """Run every rule against every player and return structured results."""
    results = []
    for player in players:
        earned_achievements = [a for a in ACHIEVEMENTS if a["condition"](player)]
        earned_curses = [c for c in CURSES if c["condition"](player)]
        results.append({
            "player": player,
            "achievements": earned_achievements,
            "curses": earned_curses,
        })
    return results


def evaluate_player(p: Player) -> Dict:
    """Check achievements and curses for a single player."""
    earned = [a for a in ACHIEVEMENTS if a["condition"](p)]
    curses = [c for c in CURSES if c["condition"](p)]
    return {"achievements": earned, "curses": curses}


def format_badges(results: Dict) -> str:
    """Format achievements/curses as emoji string."""
    badges = []
    for a in results.get("achievements", []):
        badges.append(a["emoji"] + " " + a["label"])
    for c in results.get("curses", []):
        badges.append(c["emoji"] + " " + c["label"])
    return " ".join(badges) if badges else ""


def format_chaos_report(results: List[Dict]) -> str:
    """Format full chaos report with achievements and curses."""
    lines = []

    # Crowns section
    crown_players = [r for r in results if r["achievements"]]
    if crown_players:
        lines.append("🏆 **CROWNS**")
        for r in crown_players:
            p = r["player"]
            for a in r["achievements"]:
                lines.append(f"  {a['emoji']} **{p['name']}** — {a['label']}")
                lines.append(f"    ⚡ Power: *{a['power']}*")
        lines.append("")

    # Curses section
    cursed_players = [r for r in results if r["curses"]]
    if cursed_players:
        lines.append("💀 **CURSES**")
        for r in cursed_players:
            p = r["player"]
            for c in r["curses"]:
                lines.append(f"  {c['emoji']} **{p['name']}** — {c['label']}")
                lines.append(f"    😈 Curse: *{c['curse']}*")
        lines.append("")

    return "\n".join(lines) if lines else ""


def count_crowns(results: List[Dict]) -> Dict[str, int]:
    """Return {player_name: crown_count} for leaderboard."""
    return {
        r["player"]["name"]: len(r["achievements"])
        for r in results
        if r["achievements"]
    }


def count_curses(results: List[Dict]) -> Dict[str, int]:
    """Return {player_name: curse_count} for leaderboard."""
    return {
        r["player"]["name"]: len(r["curses"])
        for r in results
        if r["curses"]
    }
