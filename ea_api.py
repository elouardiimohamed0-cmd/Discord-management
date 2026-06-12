"""
EA API — Uses scraper.py as primary source (already returns parsed format).
This module provides aggregate_stats and helper functions for gemini.py.
"""
import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger("ea_api")

CLUB_ID = os.getenv("CLUB_ID", "1427607")
PLATFORM = os.getenv("PLATFORM", "common-gen5")

# ─── PARSERS ─────────────────────────────────────────────────────────────────

def aggregate_stats(matches: List[Dict]) -> Dict[str, Dict]:
    """Aggregate player stats across matches."""
    agg = {}
    for m in matches:
        for p in m.get("players", []):
            name = p["name"]
            if name not in agg:
                agg[name] = {
                    "name": name,
                    "games": 0, "goals": 0, "assists": 0,
                    "shots": 0, "tackles": 0, "tackles_attempted": 0,
                    "interceptions": 0, "passes_attempted": 0, "passes_completed": 0,
                    "ratings": [], "avg_rating": 0.0,
                }
            agg[name]["games"] += 1
            agg[name]["goals"] += p.get("goals", 0)
            agg[name]["assists"] += p.get("assists", 0)
            agg[name]["shots"] += p.get("shots", 0)
            agg[name]["tackles"] += p.get("tackles", 0)
            agg[name]["tackles_attempted"] += p.get("tackles_attempted", 0)
            agg[name]["interceptions"] += p.get("interceptions", 0)
            agg[name]["passes_attempted"] += p.get("passes_attempted", 0)
            agg[name]["passes_completed"] += p.get("passes_completed", 0)
            agg[name]["ratings"].append(p.get("rating", 0))

    for name in agg:
        ratings = agg[name]["ratings"]
        agg[name]["avg_rating"] = sum(ratings) / len(ratings) if ratings else 0

    return agg


def aggregate_from_members(members: List[Dict]) -> Dict[str, Dict]:
    """Fallback: aggregate from member list (season stats)."""
    agg = {}
    for m in members:
        name = m.get("proName") or m.get("name", "Unknown")
        agg[name] = {
            "name": name,
            "games": m.get("gamesPlayed", 0),
            "goals": m.get("goals", 0),
            "assists": m.get("assists", 0),
            "shots": m.get("shots", 0),
            "tackles": 0,
            "tackles_attempted": 0,
            "interceptions": 0,
            "passes_attempted": 0,
            "passes_completed": 0,
            "ratings": [m.get("ratingAve", 0)],
            "avg_rating": m.get("ratingAve", 0) or 0,
        }
    return agg
