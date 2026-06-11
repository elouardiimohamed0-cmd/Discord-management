"""
Persistent state to track which matches have already been reported.
Uses a simple JSON file so restarts don't repost old matches.
"""
import json
import os
import logging

logger = logging.getLogger(__name__)

STATE_FILE = os.path.join(os.path.dirname(__file__), "seen_matches.json")


def load_seen() -> set[str]:
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE) as f:
                data = json.load(f)
                return set(data.get("seen", []))
    except Exception as e:
        logger.warning("Could not load state: %s", e)
    return set()


def save_seen(seen: set[str]) -> None:
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({"seen": list(seen)}, f)
    except Exception as e:
        logger.warning("Could not save state: %s", e)


def get_match_id(match: dict) -> str | None:
    return match.get("matchId") or match.get("timestamp") or None
