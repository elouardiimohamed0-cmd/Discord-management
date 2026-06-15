import os
import asyncio
import time
from datetime import datetime
from typing import Optional
import httpx
from models import ClubStats, PlayerStats, MatchResult

CLUB_ID = os.environ.get("CLUB_ID", "1427607")
PLATFORM = os.environ.get("PCT_PLATFORM", "common-gen5")
PCT_API = f"https://proclubstracker.com/api/clubs/{CLUB_ID}?platform={PLATFORM}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html,*/*",
    "Referer": "https://proclubstracker.com/",
    "Accept-Language": "en-US,en;q=0.9",
}

class ProClubsTrackerScraper:
    def __init__(self, club_url: str, headless: bool = True, use_stealth: bool = True):
        # headless/use_stealth kept for backward compatibility
        self.club_url = club_url
        self.club_id = CLUB_ID
        self.platform = PLATFORM
        self._last_error = None

    def _to_int(self, val, default=0) -> int:
        try:
            return int(float(str(val))) if val is not None else default
        except (ValueError, TypeError):
            return default

    def _to_float(self, val, default=0.0) -> float:
        try:
            return float(str(val)) if val is not None else default
        except (ValueError, TypeError):
            return default

    def _parse_rating(self, val) -> float:
        r = self._to_float(val, 0.0)
        if r > 10:
            return round(r / 10.0, 2)
        return r

    async def _fetch_pct_api(self) -> Optional[dict]:
        try:
            print(f"📡 Fetching PCT API: {PCT_API}")
            async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20) as client:
                resp = await client.get(PCT_API)
            print(f"📡 Status: {resp.status_code}")
            if resp.status_code != 200:
                print(f"⚠️ PCT API HTTP {resp.status_code}: {resp.text[:200]}")
                return None
            data = resp.json()
            print(f"✅ PCT API OK (keys: {list(data.keys())})")
            return data
        except Exception as e:
            print(f"❌ PCT API error: {e}")
            self._last_error = str(e)
            return None

    def _extract_match_players(self, raw: dict) -> list:
        our_id = str(self.club_id)
        clubs = raw.get("clubs", {})
        our_players_raw = raw.get("players", {}).get(our_id, {})
        players = []
        for pid, p in our_players_raw.items():
            if not isinstance(p, dict):
                continue
            passes_att = self._to_int(p.get("passattempts"), 0)
            passes_comp = self._to_int(p.get("passesmade"), 0)
            seconds = self._to_int(p.get("secondsPlayed"), 0)
            rating = self._to_float(p.get("rating"), 0.0)
            if rating > 10:
                rating = round(rating / 10.0, 2)
            players.append({
                "name": p.get("playername", "Unknown"),
                "position": p.get("pos", ""),
                "goals": self._to_int(p.get("goals"), 0),
                "assists": self._to_int(p.get("assists"), 0),
                "shots": self._to_int(p.get("shots"), 0),
                "tackles": self._to_int(p.get("tacklesmade"), 0),
                "interceptions": self._to_int(p.get("interceptions"), 0),
                "passes_attempted": passes_att,
                "passes_completed": passes_comp,
                "minutes": seconds // 60,
                "motm": str(p.get("man_of_the_match", "0")) == "1",
                "rating": rating,
            })
        return players

    def _parse_pct_match(self, raw: dict) -> Optional[MatchResult]:
        try:
            our_id = str(self.club_id)
            clubs = raw.get("clubs", {})
            our_club, opp_club = None, None
            for cid, cdata in clubs.items():
                if str(cid) == our_id:
                    our_club = cdata
                else:
                    opp_club = cdata
            if not our_club:
                return None

            our_goals = self._to_int(our_club.get("goals"), 0)
            opp_goals = self._to_int(our_club.get("goalsAgainst"), 0)
            result = "W" if our_goals > opp_goals else "L" if our_goals < opp_goals else "D"

            ts = raw.get("timestamp")
            date = datetime.now()
            if ts:
                try:
                    date = datetime.fromtimestamp(int(ts))
                except Exception:
                    pass

            match_id = str(raw.get("matchId", raw.get("timestamp", "")))
            opp_name = opp_club.get("details", {}).get("name", "Unknown") if opp_club else "Unknown"

            return MatchResult(
                match_id=match_id,
                date=date,
                opponent=opp_name,
                score_for=our_goals,
                score_against=opp_goals,
                result=result,
            )
        except Exception as e:
            print(f"⚠️ Parse match error: {e}")
            return None

    async def scrape_club(self) -> Optional[ClubStats]:
        print(f"🔍 PCT API scrape for club {self.club_id}")
        data = await self._fetch_pct_api()
        if not data:
            print(f"❌ PCT API returned nothing. Error: {self._last_error}")
            return None

        club = ClubStats(club_name="Rachad L3ERGONI", last_updated=datetime.now())

        # ── Club Info & Stats ──
        club_info_raw = data.get("clubInfoData") or {}
        club_info = club_info_raw.get(str(self.club_id)) or next(iter(club_info_raw.values()), {})
        overall = data.get("overallStats") or {}

        club.club_name = club_info.get("name") or club_info.get("clubName") or "Rachad L3ERGONI"
        club.division = self._to_int(overall.get("bestDivision") or club_info.get("divisionId"), 6)
        club.skill_rating = self._to_int(overall.get("skillRating") or club_info.get("skillRating"), 0)
        club.wins = self._to_int(overall.get("wins"), 0)
        club.losses = self._to_int(overall.get("losses"), 0)
        club.draws = self._to_int(overall.get("ties"), 0)
        club.goals_scored = self._to_int(overall.get("goals"), 0)
        club.goals_conceded = self._to_int(overall.get("goalsAgainst"), 0)

        games_played = self._to_int(overall.get("gamesPlayed"), 0)
        if games_played > 0:
            club.win_rate = round((club.wins / games_played) * 100, 1)

        print(f"✅ Club: {club.club_name} | Div {club.division} | SR {club.skill_rating} | {club.wins}W {club.losses}L {club.draws}D")

        # ── Players ──
        member_stats = data.get("memberStats") or {}
        members = member_stats.get("members") or []

        raw_matches_dict = data.get("matches") or {}
        all_matches_raw = (raw_matches_dict.get("league", []) or []) + \
                          (raw_matches_dict.get("playoff", []) or []) + \
                          (raw_matches_dict.get("friendly", []) or [])

        # Build from memberStats (season totals)
        player_map = {}
        for m in members:
            name = m.get("proName") or m.get("name") or "Unknown"
            p = PlayerStats(name=str(name))
            p.games = self._to_int(m.get("gamesPlayed"), 0)
            p.goals = self._to_int(m.get("goals"), 0)
            p.assists = self._to_int(m.get("assists"), 0)
            p.shots = self._to_int(m.get("shots"), 0)
            p.rating = self._parse_rating(m.get("ratingAve"))
            p.tackles = self._to_int(m.get("tacklesmade"), 0)
            p.interceptions = self._to_int(m.get("interceptions"), 0)
            p.minutes_played = self._to_int(m.get("secondsPlayed"), 0) // 60
            p.motm = self._to_int(m.get("manOfTheMatch"), 0)
            p.pass_accuracy = self._to_float(m.get("passAccuracy"), 0.0)
            p.possession_losses = self._to_int(m.get("possessionLost"), 0)
            p.distance_covered = self._to_float(m.get("distanceCovered"), 0.0)
            player_map[p.name] = p

        # Supplement from match aggregation
        match_agg = {}
        for raw_match in all_matches_raw[:30]:
            for mp in self._extract_match_players(raw_match):
                name = mp["name"]
                if name not in match_agg:
                    match_agg[name] = {
                        "games": 0, "goals": 0, "assists": 0, "shots": 0,
                        "tackles": 0, "interceptions": 0, "passes_attempted": 0,
                        "passes_completed": 0, "minutes": 0, "motm": 0,
                        "possession_losses": 0, "ratings": [],
                    }
                a = match_agg[name]
                a["games"] += 1
                a["goals"] += mp["goals"]
                a["assists"] += mp["assists"]
                a["shots"] += mp["shots"]
                a["tackles"] += mp["tackles"]
                a["interceptions"] += mp["interceptions"]
                a["passes_attempted"] += mp["passes_attempted"]
                a["passes_completed"] += mp["passes_completed"]
                a["minutes"] += mp["minutes"]
                a["motm"] += 1 if mp["motm"] else 0
                a["possession_losses"] += mp["passes_attempted"] - mp["passes_completed"]
                a["ratings"].append(mp["rating"])

        for name, agg in match_agg.items():
            if name in player_map:
                p = player_map[name]
                if p.games == 0 and agg["games"] > 0:
                    p.games = agg["games"]
                    p.goals = agg["goals"]
                    p.assists = agg["assists"]
                    p.shots = agg["shots"]
                    p.tackles = agg["tackles"]
                    p.interceptions = agg["interceptions"]
                    p.minutes_played = agg["minutes"]
                    p.motm = agg["motm"]
                    if agg["ratings"]:
                        p.rating = round(sum(agg["ratings"]) / len(agg["ratings"]), 2)
                    if agg["passes_attempted"] > 0:
                        p.pass_accuracy = round((agg["passes_completed"] / agg["passes_attempted"]) * 100, 1)
                    p.possession_losses = agg["possession_losses"]
            else:
                p = PlayerStats(name=name)
                p.games = agg["games"]
                p.goals = agg["goals"]
                p.assists = agg["assists"]
                p.shots = agg["shots"]
                p.tackles = agg["tackles"]
                p.interceptions = agg["interceptions"]
                p.minutes_played = agg["minutes"]
                p.motm = agg["motm"]
                if agg["ratings"]:
                    p.rating = round(sum(agg["ratings"]) / len(agg["ratings"]), 2)
                if agg["passes_attempted"] > 0:
                    p.pass_accuracy = round((agg["passes_completed"] / agg["passes_attempted"]) * 100, 1)
                p.possession_losses = agg["possession_losses"]
                player_map[name] = p

        club.players = list(player_map.values())
        print(f"✅ Parsed {len(club.players)} players")

        # ── Matches ──
        for raw_match in all_matches_raw[:30]:
            parsed = self._parse_pct_match(raw_match)
            if parsed:
                club.matches.append(parsed)

        print(f"✅ Parsed {len(club.matches)} matches")

        if club.players or club.matches:
            return club

        print("⚠️ No players or matches found")
        return None

    async def close(self):
        pass
