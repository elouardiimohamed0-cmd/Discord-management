from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.logging import get_logger
from src.domain.models import ClubSnapshot, Match, PlayerMatchStats

logger = get_logger(__name__)


class ProClubsTrackerParser:
    """Parse ProClubsTracker HTML/JSON into domain models."""

    def parse_club_page(self, html: str, url: str, raw_json: Optional[dict] = None) -> ClubSnapshot:
        # Try structured JSON first
        if raw_json and "matches" in raw_json:
            return self._parse_json_snapshot(raw_json)

        # Fallback: extract from embedded JSON in script tags
        return self._parse_html_snapshot(html, url)

    def _parse_json_snapshot(self, data: dict) -> ClubSnapshot:
        club = data.get("club", {})
        matches_data = data.get("matches", [])
        matches = [self._parse_match(m) for m in matches_data if self._is_valid_match(m)]
        return ClubSnapshot(
            club_name=club.get("name", "Unknown"),
            division=club.get("division", 0),
            skill_rating=club.get("skillRating", 0),
            wins=club.get("wins", 0),
            draws=club.get("draws", 0),
            losses=club.get("losses", 0),
            goals_scored=club.get("goalsFor", 0),
            goals_conceded=club.get("goalsAgainst", 0),
            matches=matches,
            scraped_at=datetime.now(),
        )

    def _parse_html_snapshot(self, html: str, url: str) -> ClubSnapshot:
        # Extract match rows from HTML tables
        # ProClubsTracker uses data-match-id attributes
        matches: List[Match] = []
        match_blocks = re.findall(r'data-match-id="(\d+)"[^>]*>(.*?)</tr>', html, re.DOTALL)
        for match_id, block in match_blocks:
            match = self._parse_match_block(match_id, block)
            if match:
                matches.append(match)

        # Extract club info
        club_name = self._extract_meta(html, r'<h1[^>]*class="club-name"[^>]*>(.*?)</h1>', "Rachad FC")
        return ClubSnapshot(
            club_name=club_name,
            matches=matches,
            scraped_at=datetime.now(),
        )

    def _parse_match_block(self, match_id: str, html: str) -> Optional[Match]:
        try:
            opponent = self._extract_meta(html, r'class="opponent-name"[^>]*>(.*?)</', "Unknown")
            score_text = self._extract_meta(html, r'class="score"[^>]*>(.*?)</', "0-0")
            score_for, score_against = self._parse_score(score_text)
            date_str = self._extract_meta(html, r'data-date="([^"]*)"', datetime.now().isoformat())
            result = "W" if score_for > score_against else "L" if score_for < score_against else "D"

            players = self._extract_players_from_match(html, match_id)
            return Match(
                match_id=match_id,
                date=datetime.fromisoformat(date_str.replace("Z", "+00:00")),
                opponent=opponent,
                score_for=score_for,
                score_against=score_against,
                result=result,
                players=players,
            )
        except Exception as e:
            logger.warning("Failed to parse match block %s: %s", match_id, e)
            return None

    def _extract_players_from_match(self, html: str, match_id: str) -> List[PlayerMatchStats]:
        players = []
        # Look for player rows within match detail
        player_rows = re.findall(r'<tr[^>]*class="player-row"[^>]*>(.*?)</tr>', html, re.DOTALL)
        for row in player_rows:
            p = self._parse_player_row(row)
            if p and p.played:
                players.append(p)
        return players

    def _parse_player_row(self, html: str) -> Optional[PlayerMatchStats]:
        try:
            ea_id = self._extract_meta(html, r'data-player-id="([^"]*)"', "")
            name = self._extract_meta(html, r'class="player-name"[^>]*>(.*?)</', "Unknown")
            rating = float(self._extract_meta(html, r'class="rating"[^>]*>(.*?)</', "0"))
            minutes = int(self._extract_meta(html, r'class="minutes"[^>]*>(.*?)</', "0"))
            goals = int(self._extract_meta(html, r'class="goals"[^>]*>(.*?)</', "0"))
            assists = int(self._extract_meta(html, r'class="assists"[^>]*>(.*?)</', "0"))

            return PlayerMatchStats(
                ea_id=ea_id or name,
                display_name=name,
                rating=rating,
                minutes=minutes,
                goals=goals,
                assists=assists,
            )
        except Exception as e:
            logger.warning("Failed to parse player row: %s", e)
            return None

    def _parse_match(self, data: dict) -> Match:
        players = []
        for p in data.get("players", []):
            stats = PlayerMatchStats(
                ea_id=str(p.get("playerId", p.get("name", "unknown"))),
                display_name=p.get("name", "Unknown"),
                position=p.get("position"),
                rating=float(p.get("rating", 0)),
                minutes=int(p.get("minutes", 0)),
                goals=int(p.get("goals", 0)),
                assists=int(p.get("assists", 0)),
                shots=int(p.get("shots", 0)),
                shots_on_target=int(p.get("shotsOnTarget", 0)),
                passes_attempted=int(p.get("passesAttempted", 0)),
                passes_completed=int(p.get("passesCompleted", 0)),
                key_passes=int(p.get("keyPasses", 0)),
                tackles=int(p.get("tackles", 0)),
                interceptions=int(p.get("interceptions", 0)),
                saves=int(p.get("saves", 0)),
                possession_losses=int(p.get("possessionLosses", 0)),
                red_cards=int(p.get("redCards", 0)),
                yellow_cards=int(p.get("yellowCards", 0)),
                clean_sheets=int(p.get("cleanSheet", 0)),
                distance_covered=float(p.get("distance", 0)),
                sprint_speed=float(p.get("sprintSpeed", 0)),
                raw=p,
            )
            if stats.played:
                players.append(stats)

        return Match(
            match_id=str(data.get("matchId", data.get("id", "unknown"))),
            date=datetime.fromisoformat(str(data.get("date", datetime.now().isoformat())).replace("Z", "+00:00")),
            opponent=str(data.get("opponent", "Unknown")),
            score_for=int(data.get("scoreFor", 0)),
            score_against=int(data.get("scoreAgainst", 0)),
            result=data.get("result", "D"),
            players=players,
            raw=data,
        )

    def _is_valid_match(self, data: dict) -> bool:
        return bool(data.get("matchId") or data.get("id"))

    def _parse_score(self, text: str) -> tuple[int, int]:
        parts = text.replace(" ", "").split("-")
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
        return 0, 0

    def _extract_meta(self, html: str, pattern: str, default: str) -> str:
        m = re.search(pattern, html)
        if m:
            return m.group(1).strip()
        return default
