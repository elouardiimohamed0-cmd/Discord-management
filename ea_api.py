"""
EA API — Uses working scraper.py as primary source
Falls back to direct API calls if scraper fails
"""
import os
import logging
from typing import List, Dict, Optional

import httpx

logger = logging.getLogger("ea_api")

CLUB_ID = os.getenv("CLUB_ID", "1427607")
PLATFORM = os.getenv("PLATFORM", "common-gen5")

# ─── IMPORT WORKING SCRAPER ───
try:
    import scraper as _scraper
    HAS_SCRAPER = True
except ImportError:
    HAS_SCRAPER = False
    logger.warning("scraper.py not found — using direct API only")

class APIClient:
    """Client that uses scraper.py first, then direct API."""

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
        """Get matches using scraper.py (proven to work)."""
        if HAS_SCRAPER:
            try:
                data = await _scraper.fetch_all(max_matches=count, force=False)
                matches = data.get("matches", [])
                if matches:
                    logger.info(f"✅ Scraper matches: {len(matches)}")
                    return matches
            except Exception as e:
                logger.warning(f"Scraper failed: {e}")

        # Direct API fallback
        try:
            url = f"https://proclubstracker.com/api/clubs/{self.club_id}"
            params = {"platform": self.platform}
            resp = await self.client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                raw_matches = data.get("matches", {})
                if isinstance(raw_matches, dict):
                    league = raw_matches.get("league", [])
                    playoff = raw_matches.get("playoff", [])
                    friendly = raw_matches.get("friendly", [])
                    all_matches = (league + playoff + friendly)[:count]
                else:
                    all_matches = raw_matches[:count] if isinstance(raw_matches, list) else []
                if all_matches:
                    logger.info(f"✅ Direct API matches: {len(all_matches)}")
                    return all_matches
        except Exception as e:
            logger.error(f"Direct API also failed: {e}")

        return []

    # ─── CLUB INFO ───
    async def get_club_info(self) -> Dict:
        """Get club info using scraper.py."""
        if HAS_SCRAPER:
            try:
                data = await _scraper.fetch_all(max_matches=1, force=False)
                if data.get("club_stats") or data.get("members"):
                    logger.info("✅ Scraper club info loaded")
                    return data
            except Exception as e:
                logger.warning(f"Scraper club info failed: {e}")

        # Direct API fallback
        try:
            url = f"https://proclubstracker.com/api/clubs/{self.club_id}"
            params = {"platform": self.platform}
            resp = await self.client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                # Extract data in scraper format
                member_stats = data.get("memberStats", {})
                members = member_stats.get("members", [])
                overall = data.get("overallStats", {})
                club_stats = {
                    "wins": overall.get("wins", "?"),
                    "losses": overall.get("losses", "?"),
                    "ties": overall.get("ties", "?"),
                    "goals": overall.get("goals", "?"),
                    "goalsAgainst": overall.get("goalsAgainst", "?"),
                    "skillRating": overall.get("skillRating", "?"),
                    "gamesPlayed": overall.get("gamesPlayed", "?"),
                    "bestDivision": overall.get("bestDivision", "?"),
                    "wstreak": overall.get("wstreak", "?"),
                    "unbeatenstreak": overall.get("unbeatenstreak", "?"),
                }
                return {
                    "members": members,
                    "club_stats": club_stats,
                    "club_info": data.get("clubInfoData", {}),
                }
        except Exception as e:
            logger.error(f"Direct API club info failed: {e}")

        return {}

    # ─── MEMBERS ───
    async def get_members(self) -> List[Dict]:
        """Get members from club info."""
        info = await self.get_club_info()
        members = info.get("members", [])
        if members:
            return members
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

# ─── PARSERS ───

def parse_match(raw: Dict) -> Dict:
    """Parse match data — handles both scraper and API formats."""
    try:
        # Scraper format (already parsed)
        if "our_goals" in raw and "players" in raw:
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

        # Raw PCT API format (needs parsing)
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
            # Try alternative format
            return _parse_simple_format(raw)

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
    except Exception as e:
        logger.error(f"Parse error: {e}")
        return _parse_simple_format(raw)

def _parse_simple_format(raw: Dict) -> Dict:
    """Parse simple format from scraper."""
    try:
        return {
            "match_id": str(raw.get("match_id", raw.get("id", "unknown"))),
            "our_name": raw.get("our_name", "Rachad L3ERGONI"),
            "opp_name": raw.get("opp_name", "Unknown"),
            "our_goals": int(raw.get("our_goals", 0)),
            "opp_goals": int(raw.get("opp_goals", 0)),
            "result": raw.get("result", "?"),
            "date": raw.get("date", ""),
            "players": raw.get("players", []),
        }
    except:
        return {
            "match_id": "unknown",
            "our_name": "Rachad L3ERGONI",
            "opp_name": "Unknown",
            "our_goals": 0,
            "opp_goals": 0,
            "result": "?",
            "date": "",
            "players": [],
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
