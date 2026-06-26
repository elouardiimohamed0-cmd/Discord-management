from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from src.domain.models import ClubSnapshot, Match, PlayerMatchStats
from src.squad.registry import SquadRegistry


class ProClubsTrackerParser:
    def __init__(self, club_id: str, squad: SquadRegistry):
        self.club_id = str(club_id)
        self.squad = squad

    def parse(self, raw: dict[str, Any]) -> ClubSnapshot:
        club_info = raw.get("clubInfoData") or {}
        club_row = club_info.get(self.club_id) or (next(iter(club_info.values()), {}) if club_info else {})
        overall = raw.get("overallStats") or {}
        matches = self._parse_matches(raw)
        return ClubSnapshot(
            club_name=club_row.get("name") or club_row.get("clubName") or "Unknown Club",
            division=self._int(overall.get("bestDivision") or club_row.get("divisionId"), 0),
            skill_rating=self._int(overall.get("skillRating") or club_row.get("skillRating"), 0),
            wins=self._int(overall.get("wins"), 0),
            draws=self._int(overall.get("ties"), 0),
            losses=self._int(overall.get("losses"), 0),
            goals_scored=self._int(overall.get("goals"), 0),
            goals_conceded=self._int(overall.get("goalsAgainst"), 0),
            scraped_at=datetime.now(),
            matches=matches,
        )

    def _parse_matches(self, raw: dict[str, Any]) -> list[Match]:
        raw_matches = raw.get("matches") or {}
        all_matches: list[dict[str, Any]] = []
        if isinstance(raw_matches, dict):
            for key in ("league", "playoff", "friendly"):
                rows = raw_matches.get(key) or []
                if isinstance(rows, list):
                    all_matches.extend(rows)
        elif isinstance(raw_matches, list):
            all_matches = raw_matches

        parsed: list[Match] = []
        for row in all_matches:
            if not isinstance(row, dict):
                continue
            match = self._parse_match(row)
            if match and match.players:
                parsed.append(match)
        parsed.sort(key=lambda m: m.date, reverse=True)
        return parsed

    def _parse_match(self, row: dict[str, Any]) -> Optional[Match]:
        clubs = row.get("clubs") or {}
        if not isinstance(clubs, dict):
            return None
        ours = clubs.get(self.club_id)
        opponent = None
        for club_key, club_value in clubs.items():
            if str(club_key) != self.club_id:
                opponent = club_value
                break
        if not isinstance(ours, dict):
            return None

        score_for = self._int(ours.get("goals"), 0)
        score_against = self._int(ours.get("goalsAgainst"), 0)
        result = "W" if score_for > score_against else "L" if score_for < score_against else "D"
        timestamp = row.get("timestamp") or row.get("time")
        date = datetime.now()
        if timestamp:
            try:
                date = datetime.fromtimestamp(int(timestamp))
            except Exception:
                pass
        match_id = str(row.get("matchId") or row.get("matchid") or timestamp or f"{date.isoformat()}-{score_for}-{score_against}")
        players = self._parse_match_players(row)
        return Match(
            match_id=match_id,
            date=date,
            opponent=self._opponent_name(opponent),
            score_for=score_for,
            score_against=score_against,
            result=result,  # type: ignore[arg-type]
            players=players,
            raw=row,
        )

    def _parse_match_players(self, row: dict[str, Any]) -> list[PlayerMatchStats]:
        raw_players = ((row.get("players") or {}).get(self.club_id) or {})
        players: list[PlayerMatchStats] = []
        if not isinstance(raw_players, dict):
            return players
        for _pid, raw_player in raw_players.items():
            if not isinstance(raw_player, dict):
                continue
            ea_id = str(
                raw_player.get("playername")
                or raw_player.get("name")
                or raw_player.get("personaName")
                or "Unknown"
            ).strip()
            identity = self.squad.find(ea_id)
            display = identity.nickname if identity else ea_id
            passes_attempted = self._int(raw_player.get("passattempts"), 0)
            passes_completed = self._int(raw_player.get("passesmade"), 0)
            rating = self._rating(raw_player.get("rating"))
            minutes = self._int(raw_player.get("secondsPlayed"), 0) // 60
            players.append(
                PlayerMatchStats(
                    ea_id=ea_id,
                    display_name=display,
                    position=(identity.position if identity else (raw_player.get("pos") or None)),
                    rating=rating,
                    minutes=minutes,
                    goals=self._int(raw_player.get("goals"), 0),
                    assists=self._int(raw_player.get("assists"), 0),
                    shots=self._int(raw_player.get("shots"), 0),
                    passes_attempted=passes_attempted,
                    passes_completed=passes_completed,
                    tackles=self._int(raw_player.get("tacklesmade"), 0),
                    interceptions=self._int(raw_player.get("interceptions"), 0),
                    saves=self._int(raw_player.get("saves"), 0),
                    possession_losses=max(0, passes_attempted - passes_completed),
                    red_cards=self._int(raw_player.get("redcards"), 0),
                    yellow_cards=self._int(raw_player.get("yellowcards"), 0),
                    clean_sheets=self._int(raw_player.get("cleansheetsany"), 0),
                    raw=raw_player,
                )
            )
        return players

    @staticmethod
    def _opponent_name(opponent: Any) -> str:
        if not isinstance(opponent, dict):
            return "Unknown"
        details = opponent.get("details") if isinstance(opponent.get("details"), dict) else {}
        return details.get("name") or opponent.get("name") or opponent.get("clubName") or "Unknown"

    @staticmethod
    def _int(value: Any, default: int = 0) -> int:
        try:
            return int(float(str(value))) if value is not None else default
        except Exception:
            return default

    @staticmethod
    def _float(value: Any, default: float = 0.0) -> float:
        try:
            return float(str(value)) if value is not None else default
        except Exception:
            return default

    def _rating(self, value: Any) -> float:
        rating = self._float(value, 0.0)
        return round(rating / 10.0, 2) if rating > 10 else round(rating, 2)
