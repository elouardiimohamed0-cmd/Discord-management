"""
Rachad L3ERGONI Bot — Memory System
Tracks legends, disasters, rivalries, weekly frauds.
"""

import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class SquadMemory:
    def __init__(self, path: str = "squad_memory.json"):
        self.path = Path(path)
        self.data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "historic_disasters": [],
            "weekly_frauds": [],
            "mvp_history": [],
            "rivalries": {},
            "legends": {},
            "funny_moments": [],
            "last_updated": datetime.now().isoformat(),
        }

    def save(self):
        self.data["last_updated"] = datetime.now().isoformat()
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def record_match(self, match_result: dict, player_stats: dict):
        """Analyze a match and record notable events."""
        # Disaster: loss by 3+ goals
        if match_result.get("team_goals", 0) < match_result.get("opponent_goals", 0) - 2:
            self.data["historic_disasters"].append({
                "date": datetime.now().isoformat(),
                "opponent": match_result.get("opponent", "Unknown"),
                "score": f"{match_result['team_goals']}-{match_result['opponent_goals']}",
                "note": "Historic disaster",
            })
            # Keep last 20
            self.data["historic_disasters"] = self.data["historic_disasters"][-20:]

        # Weekly fraud: worst rating with 0 G/A
        for name, stats in player_stats.items():
            if stats.get("rating", 10) < 5.5 and stats.get("goals", 0) == 0 and stats.get("assists", 0) == 0:
                self.data["weekly_frauds"].append({
                    "date": datetime.now().isoformat(),
                    "player": name,
                    "rating": stats.get("rating", 0),
                    "note": "Weekly fraud candidate",
                })
                self.data["weekly_frauds"] = self.data["weekly_frauds"][-50:]

        self.save()

    def get_fraud_streak(self, name: str) -> int:
        """How many recent weeks this player appeared as fraud."""
        count = 0
        for f in reversed(self.data.get("weekly_frauds", [])):
            if f["player"] == name:
                count += 1
            else:
                break
        return count

    def get_disaster_count(self) -> int:
        return len(self.data.get("historic_disasters", []))

    def get_last_disaster(self) -> Optional[dict]:
        disasters = self.data.get("historic_disasters", [])
        return disasters[-1] if disasters else None

    def add_funny_moment(self, text: str):
        self.data["funny_moments"].append({
            "date": datetime.now().isoformat(),
            "text": text,
        })
        self.data["funny_moments"] = self.data["funny_moments"][-100:]
        self.save()

    def get_random_moment(self) -> Optional[str]:
        moments = self.data.get("funny_moments", [])
        return random.choice(moments)["text"] if moments else None


import random

_memory = None

def get_memory(path: str = "squad_memory.json") -> SquadMemory:
    global _memory
    if _memory is None:
        _memory = SquadMemory(path)
    return _memory
