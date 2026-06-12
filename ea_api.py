"""
EA FC Pro Clubs Direct API
Uses official EA endpoints — no web scraping
Based on AllCalculatedRoast match_fetcher.py
"""
import os
import json
import logging
from typing import List, Dict, Optional
import httpx

logger = logging.getLogger("ea_api")

CLUB_ID = os.getenv("CLUB_ID", "1427607")
PLATFORM = os.getenv("PLATFORM", "common-gen5")

# EA API endpoints
EA_BASE = "https://proclubs.ea.com/api/fc/clubs"
EA_MATCHES = f"{EA_BASE}/matches"

class EAClient:
    """Direct EA API client."""
    
    def __init__(self, club_id: str = CLUB_ID, platform: str = PLATFORM):
        self.club_id = club_id
        self.platform = platform
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
    
    async def get_matches(self, count: int = 5, match_type: str = "gameType9") -> List[Dict]:
        """Get last N matches from EA API."""
        try:
            params = {
                "platform": self.platform,
                "clubIds": self.club_id,
                "matchType": match_type,
                "count": count
            }
            resp = await self.client.get(EA_MATCHES, params=params)
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"EA API error: {e}")
        return []
    
    async def get_club_info(self) -> Dict:
        """Get club info."""
        try:
            url = f"{EA_BASE}/club/info"
            params = {"platform": self.platform, "clubId": self.club_id}
            resp = await self.client.get(url, params=params)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"Club info error: {e}")
        return {}
    
    async def close(self):
        await self.client.aclose()

# Global instance
_client: Optional[EAClient] = None

def get_client() -> EAClient:
    global _client
    if _client is None:
        _client = EAClient()
    return _client

# ─── Parsers ───

def parse_match(raw: Dict) -> Dict:
    """Parse EA match data into clean format."""
    try:
        our_id = str(CLUB_ID)
        clubs = raw.get("clubs", {})
        
        our_club = None
        opp_club = None
        for cid, club in clubs.items():
            if str(cid) == our_id:
                our_club = club
            else:
                opp_club = club
        
        if not our_club:
            return {}
        
        our_goals = int(our_club.get("goals", 0))
        opp_goals = int(our_club.get("goalsAgainst", 0))
        
        result = "W" if our_goals > opp_goals else "L" if our_goals < opp_goals else "D"
        
        # Parse players
        players = []
        our_players_raw = raw.get("players", {}).get(our_id, {})
        
        for pid, p in our_players_raw.items():
            # Parse events
            events = {}
            for agg_key in ("match_event_aggregate_0", "match_event_aggregate_1"):
                raw_agg = p.get(agg_key, "")
                for part in raw_agg.split(","):
                    if ":" in part:
                        try:
                            eid, val = part.split(":", 1)
                            events[int(eid)] = int(val)
                        except:
                            pass
            
            def _ev(eid, default=0):
                return events.get(eid, default)
            
            pas_att = int(p.get("passattempts", 0))
            pas_comp = int(p.get("passesmade", 0))
            
            players.append({
                "name": p.get("playername", "Unknown"),
                "position": p.get("pos", ""),
                "rating": float(p.get("rating", 0)),
                "goals": int(p.get("goals", 0)),
                "assists": int(p.get("assists", 0)),
                "shots": int(p.get("shots", 0)) or _ev(8),
                "shots_on_target": int(p.get("shotsongoal", 0)) or _ev(6),
                "passes_attempted": pas_att,
                "passes_completed": pas_comp,
                "tackles": int(p.get("tacklesmade", 0)) or _ev(13),
                "tackles_attempted": int(p.get("tackleattempts", 0)) or _ev(32),
                "interceptions": int(p.get("interceptions", 0)) or _ev(29),
                "dribbles": int(p.get("dribbles", 0)) or _ev(174),
                "big_chances_missed": _ev(152),
                "own_goals": _ev(177),
                "red_cards": _ev(178),
                "long_goals": _ev(157),
            })
        
        players.sort(key=lambda x: x["rating"], reverse=True)
        
        return {
            "match_id": str(raw.get("matchId", raw.get("timestamp", ""))),
            "our_name": our_club.get("details", {}).get("name", "Rachad L3ERGONI"),
            "opp_name": opp_club.get("details", {}).get("name", "Unknown") if opp_club else "Unknown",
            "our_goals": our_goals,
            "opp_goals": opp_goals,
            "result": result,
            "date": raw.get("timestamp", ""),
            "players": players,
            "match_type": our_club.get("matchType", "1"),
        }
    except Exception as e:
        logger.error(f"Parse error: {e}")
        return {}

def get_match_id(raw: Dict) -> str:
    return str(raw.get("matchId", raw.get("timestamp", "")))

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
                    "shots": 0, "tackles": 0, "interceptions": 0,
                    "passes_attempted": 0, "passes_completed": 0,
                    "ratings": [], "avg_rating": 0.0,
                }
            agg[name]["games"] += 1
            agg[name]["goals"] += p.get("goals", 0)
            agg[name]["assists"] += p.get("assists", 0)
            agg[name]["shots"] += p.get("shots", 0)
            agg[name]["tackles"] += p.get("tackles", 0)
            agg[name]["interceptions"] += p.get("interceptions", 0)
            agg[name]["passes_attempted"] += p.get("passes_attempted", 0)
            agg[name]["passes_completed"] += p.get("passes_completed", 0)
            agg[name]["ratings"].append(p.get("rating", 0))
    
    for name in agg:
        ratings = agg[name]["ratings"]
        agg[name]["avg_rating"] = sum(ratings) / len(ratings) if ratings else 0
    
    return agg
