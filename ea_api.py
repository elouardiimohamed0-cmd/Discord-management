"""
EA Sports Pro Clubs data layer.
Uses scraper.py to fetch real data (PCT JSON API → Playwright DOM fallback).
Provides parse_match(), aggregate_stats(), and helper utilities.
"""
import asyncio
import logging
import datetime

import scraper as _scraper

logger = logging.getLogger(__name__)

CLUB_ID  = _scraper.CLUB_ID
PLATFORM = _scraper.PLATFORM


# ─── Public fetch functions ───────────────────────────────────────────────────

async def get_all_data(max_matches: int = 5) -> dict:
    return await _scraper.fetch_all(max_matches=max_matches)


async def get_recent_matches(max_count: int = 5) -> list:
    data = await _scraper.fetch_all(max_matches=max_count)
    return data.get("matches", [])


async def get_member_stats() -> list:
    data = await _scraper.fetch_all(max_matches=1)
    return data.get("members", [])


# ─── Data Parsing ─────────────────────────────────────────────────────────────

def parse_match(match: dict, club_id: str = CLUB_ID) -> dict:
    """
    Normalise a raw PCT/EA match object into a clean dict.

    Handles two player data layouts:
      • EA / PCT API:   match["players"][club_id][player_id]   (nested by club)
      • Legacy / old:   match["players"][player_id]             (flat)

    Also handles matches already parsed by Playwright DOM (_from_dom=True),
    which arrive pre-normalised and are returned as-is.
    """
    # ── Already normalised (from Playwright DOM extraction) ───────────────────
    if match.get("_from_dom"):
        return match

    clubs  = match.get("clubs", {})
    our_id  = str(club_id)
    opp_id  = next((k for k in clubs if k != our_id), None)
    our     = clubs.get(our_id, {})
    opp     = clubs.get(opp_id, {}) if opp_id else {}

    our_goals = int(our.get("goals", 0) or 0)
    opp_goals = int(opp.get("goals", 0) or 0)
    opp_name  = opp.get("details", {}).get("name", "Adversaire")
    our_name  = our.get("details", {}).get("name", "Rachad L3ERGONI")

    ts = match.get("timestamp", 0)
    try:
        date_str = datetime.datetime.fromtimestamp(int(ts)).strftime("%d/%m/%Y")
    except Exception:
        date_str = "—"

    # ── Players ───────────────────────────────────────────────────────────────
    players_raw = match.get("players", {})

    # Detect layout: nested-by-club vs flat
    # Nested: {"clubId": {"playerId": {...}}, ...}
    # Flat:   {"playerId": {...}, ...}
    our_players_dict: dict = {}

    if isinstance(players_raw, dict):
        # Check if any top-level key looks like a club ID (all-digit string or int)
        # and its value is a dict-of-dicts (player map)
        def _is_club_bucket(v) -> bool:
            return (
                isinstance(v, dict)
                and v                  # non-empty
                and all(isinstance(inner, dict) for inner in v.values())
            )

        nested_keys = [k for k, v in players_raw.items() if _is_club_bucket(v)]
        if nested_keys:
            # Nested layout — pull our club's players
            our_players_dict = players_raw.get(our_id, {})
        else:
            # Flat layout — all entries are our club's players
            our_players_dict = players_raw

    players: list[dict] = []
    for pid, p in our_players_dict.items():
        if not isinstance(p, dict):
            continue
        name = p.get("playername") or p.get("name", "")
        if not name:
            continue
        players.append({
            "id":       pid,
            "name":     name,
            "rating":   float(p.get("rating", 0) or 0),
            "goals":    int(p.get("goals", 0) or 0),
            "assists":  int(p.get("assists", 0) or 0),
            "shots":    int(p.get("shots", 0) or 0),
            "tackles":  int(p.get("tackleattempts", 0) or p.get("tackleAttempts", 0) or 0),
            "passes":   int(p.get("passattempts", 0) or p.get("passAttempts", 0) or 0),
            "saves":    int(p.get("saves", 0) or 0),
            "motm":     bool(p.get("mom") or p.get("motm", False)),
            "position": p.get("pos", "MID"),
        })

    players.sort(key=lambda x: x["rating"], reverse=True)

    result = "W" if our_goals > opp_goals else ("D" if our_goals == opp_goals else "L")

    return {
        "match_id":  match.get("matchId", ""),
        "timestamp": ts,
        "date":      date_str,
        "our_name":  our_name,
        "opp_name":  opp_name,
        "our_goals": our_goals,
        "opp_goals": opp_goals,
        "result":    result,
        "players":   players,
        "raw":       match,
    }


def get_match_id(match: dict) -> str | None:
    return match.get("matchId") or str(match.get("timestamp") or "") or None


# ─── Aggregate helpers ────────────────────────────────────────────────────────

def aggregate_stats(matches: list[dict]) -> dict[str, dict]:
    """
    Aggregate per-player stats across multiple parsed matches.
    Handles both EA-format (player stats in match) and PCT member stats (flat list).
    """
    stats: dict[str, dict] = {}

    for m in matches:
        for p in m.get("players", []):
            n = p.get("name", "")
            if not n:
                continue
            if n not in stats:
                stats[n] = {
                    "name": n,
                    "goals": 0, "assists": 0, "shots": 0,
                    "tackles": 0, "saves": 0, "ratings": [], "games": 0,
                }
            stats[n]["goals"]   += p.get("goals", 0) or 0
            stats[n]["assists"] += p.get("assists", 0) or 0
            stats[n]["shots"]   += p.get("shots", 0) or 0
            stats[n]["tackles"] += p.get("tackles", 0) or 0
            stats[n]["saves"]   += p.get("saves", 0) or 0
            if p.get("rating"):
                stats[n]["ratings"].append(float(p["rating"]))
            stats[n]["games"] += 1

    for s in stats.values():
        s["avg_rating"] = (
            round(sum(s["ratings"]) / len(s["ratings"]), 2)
            if s["ratings"] else 0.0
        )

    return stats


def aggregate_from_members(members: list[dict]) -> dict[str, dict]:
    """
    Build an aggregate stats dict from PCT member stats objects
    (used when EA match-level player data is unavailable).
    member keys: name, proName, goals, assists, gamesPlayed, ratingAve,
                 tacklesMade, passesMade, cleanSheetsDef, cleanSheetsGK
    """
    stats: dict[str, dict] = {}
    for m in members:
        if not isinstance(m, dict):
            continue
        name = m.get("proName") or m.get("name", "")
        if not name:
            continue
        games = int(m.get("gamesPlayed", 0) or 0)
        stats[name] = {
            "name":       name,
            "goals":      int(m.get("goals", 0) or 0),
            "assists":    int(m.get("assists", 0) or 0),
            "shots":      0,
            "tackles":    int(m.get("tacklesMade", 0) or 0),
            "saves":      0,
            "ratings":    [],
            "games":      games,
            "avg_rating": float(m.get("ratingAve", 0) or 0),
        }
    return stats
