"""
EA API + ProClubsTracker Fallback
Uses direct EA endpoints with PCT as backup
"""
import os
import logging
from typing import List, Dict, Optional
import httpx

logger = logging.getLogger("ea_api")

CLUB_ID = os.getenv("CLUB_ID", "1427607")
PLATFORM = os.getenv("PLATFORM", "common-gen5")

# ProClubsTracker API (your current working source)
PCT_API = "https://proclubstracker.com/api"

# EA API (backup)
EA_BASE = "https://proclubs.ea.com/api/fc/clubs"

class APIClient:
    """Client that tries EA first, falls back to PCT."""

    def __init__(self, club_id: str = CLUB_ID, platform: str = PLATFORM):
        self.club_id = club_id
        self.platform = platform
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            }
        )

    # ─── MATCHES ───
    async def get_matches(self, count: int = 5) -> List[Dict]:
        """Get matches from PCT API (proven to work)."""
        try:
            url = f"{PCT_API}/matches/{self.club_id}"
            params = {"platform": self.platform, "limit": count}
            resp = await self.client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                matches = data.get("matches", [])
                if matches:
                    logger.info(f"✅ PCT matches: {len(matches)}")
                    return matches
        except Exception as e:
            logger.warning(f"PCT matches failed: {e}")

        # Try EA fallback
        try:
            url = f"{EA_BASE}/matches"
            params = {
                "platform": self.platform,
                "clubIds": self.club_id,
                "matchType": "gameType9",
                "count": count
            }
            resp = await self.client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data
                return data.get("matches", [])
        except Exception as e:
            logger.error(f"EA fallback also failed: {e}")

        return []

    # ─── CLUB INFO ───
    async def get_club_info(self) -> Dict:
        """Get club info from PCT API."""
        try:
            url = f"{PCT_API}/club/{self.club_id}"
            params = {"platform": self.platform}
            resp = await self.client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"✅ PCT club info loaded")
                return data
        except Exception as e:
            logger.warning(f"PCT club info failed: {e}")

        # Try EA fallback
        try:
            url = f"{EA_BASE}/club/info"
            params = {"platform": self.platform, "clubId": self.club_id}
            resp = await self.client.get(url, params=params)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"EA club info fallback failed: {e}")

        return {}

    # ─── MEMBERS ───
    async def get_members(self) -> List[Dict]:
        """Get members from PCT API."""
        try:
            # PCT includes members in club info
            info = await self.get_club_info()
            members = info.get("members", [])
            if members:
                return members
        except Exception as e:
            logger.warning(f"PCT members failed: {e}")

        return []

    async def close(self):
        await self.client.aclose()

# Global instance
_client: Optional[APIClient] = None

def get_client() -> APIClient:
    global _client
    if _client is None:
        _client = APIClient()
    return _client

# ─── PARSERS (Handle both PCT and EA formats) ───

def parse_match(raw: Dict) -> Dict:
    """Parse match data — handles both PCT and EA formats."""
    try:
        # PCT format
        if "match_id" in raw or "our_goals" in raw:
            return _parse_pct_format(raw)

        # EA format
        return _parse_ea_format(raw)
    except Exception as e:
        logger.error(f"Parse error: {e}")
        return {}

def _parse_pct_format(raw: Dict) -> Dict:
    """Parse ProClubsTracker format."""
    return {
        "match_id": str(raw.get("match_id", raw.get("id", ""))),
        "our_name": raw.get("our_name", "Rachad L3ERGONI"),
        "opp_name": raw.get("opp_name", "Unknown"),
        "our_goals": int(raw.get("our_goals", 0)),
        "opp_goals": int(raw.get("opp_goals", 0)),
        "result": raw.get("result", "?"),
        "date": raw.get("date", ""),
        "players": raw.get("players", []),
    }

def _parse_ea_format(raw: Dict) -> Dict:
    """Parse EA API format."""
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
        players.append({
            "name": p.get("playername", "Unknown"),
            "position": p.get("pos", ""),
            "rating": float(p.get("rating", 0)) / 10.0 if float(p.get("rating", 0)) > 10 else float(p.get("rating", 0)),
            "goals": int(p.get("goals", 0)),
            "assists": int(p.get("assists", 0)),
            "shots": int(p.get("shots", 0)),
            "tackles": int(p.get("tacklesmade", 0)),
            "passes_attempted": int(p.get("passattempts", 0)),
            "passes_completed": int(p.get("passesmade", 0)),
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
    }

def get_match_id(raw: Dict) -> str:
    """Get unique match ID from any format."""
    return str(raw.get("match_id", raw.get("matchId", raw.get("id", raw.get("timestamp", "")))))

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
                    "shots": 0, "tackles": 0,
                    "ratings": [], "avg_rating": 0.0,
                }
            agg[name]["games"] += 1
            agg[name]["goals"] += p.get("goals", 0)
            agg[name]["assists"] += p.get("assists", 0)
            agg[name]["shots"] += p.get("shots", 0)
            agg[name]["tackles"] += p.get("tackles", 0)
            agg[name]["ratings"].append(p.get("rating", 0))

    for name in agg:
        ratings = agg[name]["ratings"]
        agg[name]["avg_rating"] = sum(ratings) / len(ratings) if ratings else 0

    return agg
