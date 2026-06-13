"""
Rachad L3ERGONI Bot - EA FC Pro Clubs API Scraper
Fetches real match data from EA's Pro Clubs API
"""

import os
import json
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
import httpx
from dataclasses import asdict

from stats_engine import MatchResult, PlayerMatchStats, StatsEngine


class ProClubsScraper:
    """Scraper for EA FC Pro Clubs API"""

    def __init__(self, club_id: str = None, platform: str = "ps5"):
        self.club_id = club_id or os.getenv("CLUB_ID", "")
        self.platform = platform or os.getenv("PLATFORM", "ps5")
        self.base_url = os.getenv("EA_API_BASE", "https://proclubs.ea.com/api/fifa")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def fetch_club_stats(self) -> dict:
        """Fetch club overall stats"""
        url = f"{self.base_url}/clubs/stats?platform={self.platform}&clubId={self.club_id}"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching club stats: {e}")
            return {}

    async def fetch_match_history(self, match_type: str = "gameType9", count: int = 20) -> List[dict]:
        """Fetch recent match history"""
        url = f"{self.base_url}/clubs/matches?matchType={match_type}&platform={self.platform}&clubIds={self.club_id}"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()
            return data[:count] if isinstance(data, list) else []
        except Exception as e:
            print(f"Error fetching match history: {e}")
            return []

    async def fetch_match_details(self, match_id: str) -> dict:
        """Fetch detailed match data"""
        url = f"{self.base_url}/match?matchId={match_id}&platform={self.platform}"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching match details: {e}")
            return {}

    async def fetch_player_stats(self, player_name: str) -> dict:
        """Fetch individual player stats"""
        url = f"{self.base_url}/members/stats?platform={self.platform}&clubId={self.club_id}"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()
            for member in data.get("members", []):
                if member.get("name", "").lower() == player_name.lower():
                    return member
            return {}
        except Exception as e:
            print(f"Error fetching player stats: {e}")
            return {}

    def parse_match_data(self, match_data: dict) -> MatchResult:
        """Parse raw API data into MatchResult"""
        match_id = match_data.get("matchId", "")

        # Determine teams
        clubs = match_data.get("clubs", {})
        our_club = None
        opponent_club = None

        for club_id, club_info in clubs.items():
            if str(club_id) == str(self.club_id):
                our_club = club_info
            else:
                opponent_club = club_info

        if not our_club or not opponent_club:
            # Fallback: assume first is us
            club_ids = list(clubs.keys())
            our_club = clubs.get(club_ids[0], {}) if club_ids else {}
            opponent_club = clubs.get(club_ids[1], {}) if len(club_ids) > 1 else {}

        # Parse player stats
        players_data = match_data.get("players", {})
        player_stats = {}

        for club_id, players in players_data.items():
            if str(club_id) == str(self.club_id):
                for player in players:
                    name = player.get("playername", "Unknown")
                    stats = player.get("stats", {})

                    player_stats[name] = PlayerMatchStats(
                        name=name,
                        position=player.get("position", "ST"),
                        goals=int(stats.get("goals", 0)),
                        assists=int(stats.get("assists", 0)),
                        shots=int(stats.get("shots", 0)),
                        shots_on_target=int(stats.get("shotattempts", 0)),
                        passes_attempted=int(stats.get("passattempts", 0)),
                        passes_completed=int(stats.get("passesmade", 0)),
                        key_passes=int(stats.get("keypasses", 0)),
                        tackles=int(stats.get("tacklesmade", 0)),
                        interceptions=int(stats.get("interceptions", 0)),
                        possession_losses=int(stats.get("possessionlost", 0)),
                        dribbles_attempted=int(stats.get("dribbles", 0)),
                        dribbles_completed=int(stats.get("dribbleSuccess", 0)),
                        fouls=int(stats.get("fouls", 0)),
                        yellow_cards=int(stats.get("yellowcards", 0)),
                        red_cards=int(stats.get("redcards", 0)),
                        rating=float(stats.get("rating", 6.0)),
                        motm=stats.get("motm", "0") == "1",
                        minutes_played=int(stats.get("minutesPlayed", 90)),
                        distance_covered=float(stats.get("distance", 0)),
                        sprint_speed=float(stats.get("sprintSpeed", 0))
                    )

        # Parse team stats
        team_stats = our_club.get("gameStats", {}) if our_club else {}
        opp_stats = opponent_club.get("gameStats", {}) if opponent_club else {}

        match_result = MatchResult(
            match_id=match_id,
            date=match_data.get("timestamp", datetime.now().isoformat()),
            opponent=opponent_club.get("details", {}).get("name", "Unknown") if opponent_club else "Unknown",
            team_goals=int(team_stats.get("goals", 0)),
            opponent_goals=int(opp_stats.get("goals", 0)),
            team_possession=float(team_stats.get("possession", 50)),
            opponent_possession=float(opp_stats.get("possession", 50)),
            team_shots=int(team_stats.get("shots", 0)),
            opponent_shots=int(opp_stats.get("shots", 0)),
            team_shots_on_target=int(team_stats.get("shotattempts", 0)),
            opponent_shots_on_target=int(opp_stats.get("shotattempts", 0)),
            team_passes=int(team_stats.get("passesmade", 0)),
            opponent_passes=int(opp_stats.get("passesmade", 0)),
            team_tackles=int(team_stats.get("tacklesmade", 0)),
            opponent_tackles=int(opp_stats.get("tacklesmade", 0)),
            team_corners=int(team_stats.get("corners", 0)),
            opponent_corners=int(opp_stats.get("corners", 0)),
            team_fouls=int(team_stats.get("fouls", 0)),
            opponent_fouls=int(opp_stats.get("fouls", 0)),
            player_stats=player_stats
        )

        return match_result

    async def sync_recent_matches(self, stats_engine: StatsEngine, count: int = 10) -> int:
        """Sync recent matches to stats engine"""
        matches = await self.fetch_match_history(count=count)
        added = 0

        for match_summary in matches:
            match_id = match_summary.get("matchId", "")
            if not any(m.match_id == match_id for m in stats_engine.matches):
                match_data = await self.fetch_match_details(match_id)
                if match_data:
                    match_result = self.parse_match_data(match_data)
                    stats_engine.add_match(match_result)
                    added += 1

        return added

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Singleton instance
_scraper = None

def get_scraper(club_id: str = None, platform: str = "ps5") -> ProClubsScraper:
    global _scraper
    if _scraper is None:
        _scraper = ProClubsScraper(club_id, platform)
    return _scraper
