"""Parser for ProClubsTracker HTML and JSON responses."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from src.core.logging import get_logger
from src.domain.models import ClubSnapshot, Match, PlayerMatchStats

logger = get_logger(__name__)


class ProClubsTrackerParser:
    """Parse ProClubsTracker club page data."""

    def parse_club_page(
        self, html: str, url: str, raw_json: Optional[dict] = None
    ) -> ClubSnapshot:
        """Parse club page HTML or JSON data."""
        if raw_json:
            return self._parse_json(raw_json)

        # Fallback: try to extract JSON from HTML
        return self._parse_html(html, url)

    def _parse_json(self, data: dict) -> ClubSnapshot:
        """Parse raw JSON API response."""
        info = data.get("clubInfoData", {})
        club_info = next(iter(info.values()), {}) if info else {}
        overall = data.get("overallStats", {})

        raw_matches = data.get("matches", {})
        all_matches = (
            (raw_matches.get("league", []) or [])
            + (raw_matches.get("playoff", []) or [])
            + (raw_matches.get("friendly", []) or [])
        )

        matches = []
        for rm in all_matches[:30]:
            match = self._parse_match(rm)
            if match:
                matches.append(match)

        return ClubSnapshot(
            club_name=club_info.get("name") or club_info.get("clubName") or "Unknown",
            division=self._int(overall.get("bestDivision") or club_info.get("divisionId"), 6),
            skill_rating=self._int(overall.get("skillRating") or club_info.get("skillRating"), 0),
            wins=self._int(overall.get("wins"), 0),
            draws=self._int(overall.get("ties"), 0),
            losses=self._int(overall.get("losses"), 0),
            goals_scored=self._int(overall.get("goals"), 0),
            goals_conceded=self._int(overall.get("goalsAgainst"), 0),
            matches=matches,
            scraped_at=datetime.now(),
        )

    def _parse_html(self, html: str, url: str) -> ClubSnapshot:
        """Parse HTML page as fallback."""
        logger.warning("[Parser] HTML parsing not fully implemented, returning empty snapshot")
        return ClubSnapshot(
            club_name="Unknown",
            matches=[],
            scraped_at=datetime.now(),
        )

    def _parse_match(self, raw: dict) -> Optional[Match]:
        """Parse a single match from raw data."""
        try:
            our_id = str(raw.get("clubId", ""))
            clubs = raw.get("clubs", {})
            ours, opp = None, None
            for cid, c in clubs.items():
                if str(cid) == our_id:
                    ours = c
                else:
                    opp = c
            if not ours:
                return None

            gf = self._int(ours.get("goals"), 0)
            ga = self._int(ours.get("goalsAgainst"), 0)
            result = "W" if gf > ga else "L" if gf < ga else "D"

            ts = raw.get("timestamp")
            date = datetime.now()
            if ts:
                try:
                    date = datetime.fromtimestamp(int(ts))
                except Exception:
                    pass

            players = []
            our_players = raw.get("players", {}).get(our_id, {})
            match_id = str(raw.get("matchId", ""))
            for pid, p in our_players.items():
                seconds = self._int(p.get("secondsPlayed"), 0)
                passes_att = self._int(p.get("passattempts"), 0)
                passes_comp = self._int(p.get("passesmade"), 0)

                stats = PlayerMatchStats(
                    ea_id=str(pid),
                    display_name=p.get("playername", "Unknown"),
                    match_id=match_id,
                    position=p.get("pos", ""),
                    rating=self._float(p.get("rating"), 0.0),
                    minutes=seconds // 60,
                    goals=self._int(p.get("goals"), 0),
                    assists=self._int(p.get("assists"), 0),
                    shots=self._int(p.get("shots"), 0),
                    passes_attempted=passes_att,
                    passes_completed=passes_comp,
                    tackles=self._int(p.get("tacklesmade"), 0),
                    saves=self._int(p.get("saves"), 0),
                    possession_losses=max(0, passes_att - passes_comp),
                    red_cards=self._int(p.get("redcards"), 0),
                    clean_sheets=self._int(p.get("cleansheetsany"), 0),
                    raw=p,
                )
                players.append(stats)

            return Match(
                match_id=match_id,
                date=date,
                opponent=opp.get("details", {}).get("name", "Unknown") if opp else "Unknown",
                score_for=gf,
                score_against=ga,
                result=result,
                players=players,
                raw=raw,
            )
        except Exception as e:
            logger.warning("[Parser] Match parse error: %s", e)
            return None

    def _int(self, v, d=0):
        try:
            return int(float(str(v))) if v is not None else d
        except Exception:
            return d

    def _float(self, v, d=0.0):
        try:
            return float(str(v)) if v is not None else d
        except Exception:
            return d
