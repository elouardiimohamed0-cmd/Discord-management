"""
EA FC Pro Clubs Direct API
Uses official EA endpoints — no web scraping needed
Based on: https://github.com/carlos-menezes/fc-clubs-api
"""
import os
import json
import asyncio
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

import httpx

logger = logging.getLogger("ea_api")

# EA API Configuration
CLUB_ID = os.getenv("CLUB_ID", "1427607")
PLATFORM = os.getenv("PLATFORM", "common-gen5")

# EA API Base URLs
EA_BASE = "https://proclubs.ea.com/fc/api/fc24/clubs"
PCT_BASE = "https://proclubstracker.com/api"  # Fallback

class EAClient:
    """Direct EA API client — no scraping."""
    
    def __init__(self, club_id: str = CLUB_ID, platform: str = PLATFORM):
        self.club_id = club_id
        self.platform = platform
        self.client = httpx.AsyncClient(timeout=30.0, limits=httpx.Limits(max_connections=20))
    
    async def get_matches(self, count: int = 5) -> List[Dict]:
        """Get last N matches directly from EA."""
        try:
            url = f"{EA_BASE}/matchHistory"
            params = {
                "platform": self.platform,
                "clubIds": self.club_id,
                "matchType": "gameType9",  # Pro Clubs 11v11
                "count": count
            }
            resp = await self.client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else data.get("matches", [])
        except Exception as e:
            logger.warning(f"EA API failed: {e}, trying fallback...")
        
        # Fallback to ProClubsTracker API
        try:
            url = f"{PCT_BASE}/matches/{self.club_id}"
            params = {"platform": self.platform, "limit": count}
            resp = await self.client.get(url, params=params)
            if resp.status_code == 200:
                return resp.json().get("matches", [])
        except Exception as e:
            logger.error(f"Fallback also failed: {e}")
        
        return []
    
    async def get_club_info(self) -> Dict:
        """Get club info: name, stats, division, skill rating."""
        try:
            url = f"{EA_BASE}/club/info"
            params = {"platform": self.platform, "clubId": self.club_id}
            resp = await self.client.get(url, params=params)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"Club info error: {e}")
        
        # Fallback
        try:
            url = f"{PCT_BASE}/club/{self.club_id}"
            resp = await self.client.get(url, params={"platform": self.platform})
            if resp.status_code == 200:
                return resp.json()
        except:
            pass
        
        return {}
    
    async def get_members(self) -> List[Dict]:
        """Get all club members with career stats."""
        try:
            url = f"{EA_BASE}/members/career/stats"
            params = {"platform": self.platform, "clubId": self.club_id}
            resp = await self.client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else data.get("members", [])
        except Exception as e:
            logger.error(f"Members error: {e}")
        return []
    
    async def get_member_stats(self, member_id: str) -> Dict:
        """Get specific member stats."""
        try:
            url = f"{EA_BASE}/members/stats"
            params = {
                "platform": self.platform,
                "clubId": self.club_id,
                "memberId": member_id
            }
            resp = await self.client.get(url, params=params)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"Member stats error: {e}")
        return {}
    
    async def close(self):
        await self.client.aclose()

# Global client
_client: Optional[EAClient] = None

def get_client() -> EAClient:
    global _client
    if _client is None:
        _client = EAClient()
    return _client

# ─── Data Parsers ───

def parse_match(raw: Dict) -> Dict:
    """Parse EA match data into clean format."""
    try:
        # EA format
        our_id = str(CLUB_ID)
        clubs = raw.get("clubs", {})
        
        # Find our club and opponent
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
        opp_goals = int(opp_club.get("goals", 0)) if opp_club else 0
        
        # Determine result
        if our_goals > opp_goals:
            result = "W"
        elif our_goals < opp_goals:
            result = "L"
        else:
            result = "D"
        
        # Parse players
        players = []
        our_players = raw.get("players", {}).get(str(list(clubs.keys())[0]), [])
        if not our_players and str(list(clubs.keys())[0]) != our_id:
            our_players = raw.get("players", {}).get(our_id, [])
        
        for p in our_players:
            players.append({
                "name": p.get("playername", "Unknown"),
                "rating": float(p.get("rating", 0)) / 10.0 if float(p.get("rating", 0)) > 10 else float(p.get("rating", 0)),
                "goals": int(p.get("goals", 0)),
                "assists": int(p.get("assists", 0)),
                "shots": int(p.get("shots", 0)),
                "tackles": int(p.get("tackles", 0)),
                "passes": int(p.get("passattempts", 0)),
                "pass_success": int(p.get("passsuccesses", 0)),
            })
        
        # Sort by rating desc
        players.sort(key=lambda x: x["rating"], reverse=True)
        
        return {
            "match_id": raw.get("matchId", raw.get("timestamp", "")),
            "our_name": our_club.get("name", "Rachad L3ERGONI"),
            "opp_name": opp_club.get("name", "Unknown") if opp_club else "Unknown",
            "our_goals": our_goals,
            "opp_goals": opp_goals,
            "result": result,
            "date": raw.get("timestamp", "Unknown"),
            "players": players,
            "possession": our_club.get("possession", 0),
            "shots": our_club.get("shots", 0),
            "tackles": our_club.get("tackles", 0),
            "passes": our_club.get("passes", 0),
        }
    except Exception as e:
        logger.error(f"Parse error: {e}")
        return {}

def get_match_id(raw: Dict) -> str:
    """Get unique match ID."""
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
                    "games": 0,
                    "goals": 0,
                    "assists": 0,
                    "shots": 0,
                    "tackles": 0,
                    "passes": 0,
                    "ratings": [],
                    "avg_rating": 0.0,
                }
            agg[name]["games"] += 1
            agg[name]["goals"] += p.get("goals", 0)
            agg[name]["assists"] += p.get("assists", 0)
            agg[name]["shots"] += p.get("shots", 0)
            agg[name]["tackles"] += p.get("tackles", 0)
            agg[name]["passes"] += p.get("passes", 0)
            agg[name]["ratings"].append(p.get("rating", 0))
    
    for name in agg:
        ratings = agg[name]["ratings"]
        agg[name]["avg_rating"] = sum(ratings) / len(ratings) if ratings else 0
    
    return agg
