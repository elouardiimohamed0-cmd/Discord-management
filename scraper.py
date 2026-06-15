import os
import asyncio
import re
from datetime import datetime
from typing import Optional
import httpx
from models import ClubStats, PlayerStats, MatchResult

# EA Pro Clubs API base (FC25/FC26 use /api/fc/)
EA_API_BASE = "https://proclubs.ea.com/api/fc"
# Fallback API versions if the primary fails
EA_API_FALLBACKS = [
    "https://proclubs.ea.com/api/fc",
    "https://proclubs.ea.com/api/fc26",
    "https://proclubs.ea.com/api/fc25",
]

class ProClubsTrackerScraper:
    def __init__(self, club_url: str, headless: bool = True, use_stealth: bool = True):
        # club_url kept for backward compatibility; we prefer CLUB_ID env
        self.club_url = club_url
        self.club_id = self._extract_club_id(club_url)
        self.platform = os.environ.get("PCT_PLATFORM", "common-gen5").strip().lower()
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://www.ea.com",
            "Referer": "https://www.ea.com/",
        }
        self._last_error = None
        self._base_url = EA_API_BASE

    def _extract_club_id(self, url: str) -> str:
        # Try env first
        env_id = os.environ.get("CLUB_ID", "").strip()
        if env_id:
            return env_id
        # Extract from URL like .../club/1427607?...
        m = re.search(r"/club/(\d+)", url)
        if m:
            return m.group(1)
        return "1427607"

    async def _fetch_json(self, endpoint: str, params: dict) -> Optional[dict | list]:
        """Fetch JSON from EA API with retries and fallback base URLs."""
        last_err = None
        for base in [self._base_url] + [b for b in EA_API_FALLBACKS if b != self._base_url]:
            url = f"{base}/{endpoint}"
            for attempt in range(3):
                try:
                    print(f"🌐 [{base}] {endpoint} (attempt {attempt + 1})...")
                    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                        resp = await client.get(url, headers=self.headers, params=params)
                    print(f"🌐 Status: {resp.status_code}")
                    if resp.status_code == 200:
                        data = resp.json()
                        print(f"✅ {endpoint} OK")
                        return data
                    elif resp.status_code in (429, 502, 503, 504):
                        # Rate limit / server error → retry
                        wait = 2 * (attempt + 1)
                        print(f"⏳ Rate limit / server error, waiting {wait}s...")
                        await asyncio.sleep(wait)
                    else:
                        print(f"⚠️ {endpoint} HTTP {resp.status_code}: {resp.text[:200]}")
                        return None
                except Exception as e:
                    last_err = e
                    print(f"⚠️ {endpoint} attempt {attempt + 1} error: {e}")
                    if attempt < 2:
                        await asyncio.sleep(2)
            # If all attempts failed for this base, try next base
        self._last_error = str(last_err)
        return None

    async def _get_club_info(self) -> Optional[dict]:
        data = await self._fetch_json(
            "clubs/info",
            {"platform": self.platform, "clubIds": self.club_id},
        )
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        if isinstance(data, dict):
            return data
        return None

    async def _get_member_stats(self) -> Optional[list]:
        data = await self._fetch_json(
            "members/stats",
            {"platform": self.platform, "clubId": self.club_id},
        )
        if isinstance(data, list):
            return data
        return None

    async def _get_matches(self, match_type: str = "gameType13") -> Optional[list]:
        """Fetch matches. gameType13 = friendlies, gameType9 = league, gameType5 = playoff."""
        data = await self._fetch_json(
            "clubs/matches",
            {"platform": self.platform, "clubIds": self.club_id, "matchType": match_type},
        )
        if isinstance(data, list):
            return data
        return None

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

    async def scrape_club(self) -> Optional[ClubStats]:
        print(f"🔍 EA API scrape started for club {self.club_id} (platform: {self.platform})")

        # Fetch everything concurrently
        info_task = self._get_club_info()
        members_task = self._get_member_stats()
        matches_friendly_task = self._get_matches("gameType13")
        matches_league_task = self._get_matches("gameType9")

        info, members, matches_friendly, matches_league = await asyncio.gather(
            info_task, members_task, matches_friendly_task, matches_league_task
        )

        # Merge match lists (friendlies first, then league)
        all_matches = []
        if matches_friendly:
            all_matches.extend(matches_friendly)
        if matches_league:
            all_matches.extend(matches_league)

        # If no data at all, fail
        if not info and not members and not all_matches:
            print(f"❌ EA API returned no data. Last error: {self._last_error}")
            return None

        club = ClubStats(club_name="Rachad L3ERGONI", last_updated=datetime.now())

        # ── Club Info ──
        if info and isinstance(info, dict):
            club.club_name = info.get("name") or info.get("clubName") or club.club_name
            club.division = self._to_int(info.get("divisionId") or info.get("division"), 6)
            club.skill_rating = self._to_int(info.get("skillRating") or info.get("skillrating"), 0)
            club.wins = self._to_int(info.get("wins"), 0)
            club.losses = self._to_int(info.get("losses"), 0)
            club.draws = self._to_int(info.get("ties") or info.get("draws"), 0)
            print(
                f"✅ Club: {club.club_name} | Div {club.division} | "
                f"SR {club.skill_rating} | {club.wins}W {club.losses}L {club.draws}D"
            )

        # ── Players ──
        if members and isinstance(members, list):
            for m in members:
                name = m.get("name") or m.get("playername") or "Unknown"
                p = PlayerStats(name=str(name))

                p.games = self._to_int(m.get("games") or m.get("matchPlayed"), 0)
                p.goals = self._to_int(m.get("goals"), 0)
                p.assists = self._to_int(m.get("assists"), 0)
                p.rating = self._to_float(m.get("averageRating") or m.get("rating"), 0.0)

                # Pass accuracy
                pa = self._to_int(m.get("passattempts"), 0)
                pm = self._to_int(m.get("passesmade"), 0)
                p.pass_accuracy = round((pm / pa * 100), 1) if pa > 0 else 0.0

                p.tackles = self._to_int(m.get("tacklesmade") or m.get("tackles"), 0)
                p.interceptions = self._to_int(m.get("interceptions"), 0)
                p.possession_losses = self._to_int(
                    m.get("possessionLost") or m.get("possession_losses"), 0
                )
                p.motm = self._to_int(m.get("man_of_the_match") or m.get("manOfTheMatch"), 0)
                p.minutes_played = self._to_int(m.get("secondsPlayed"), 0) // 60
                p.shots = self._to_int(m.get("shots"), 0)
                p.distance_covered = self._to_float(m.get("distanceCovered"), 0.0)

                club.players.append(p)

            print(f"✅ Parsed {len(club.players)} players from EA API")

        # ── Matches ──
        if all_matches and isinstance(all_matches, list):
            for i, m in enumerate(all_matches[:30]):
                try:
                    match_id = str(m.get("matchId") or m.get("match_id") or f"m{i}")
                    ts = m.get("timestamp") or m.get("match_timestamp")
                    date = datetime.now()
                    if ts:
                        try:
                            date = datetime.fromtimestamp(int(ts))
                        except Exception:
                            pass

                    # The match object has a "clubs" dict: {clubId: {goals, goalsAgainst, name, ...}}
                    teams = m.get("clubs") or m.get("teams") or {}
                    if not teams or not isinstance(teams, dict):
                        continue

                    our_team = None
                    opp_team = None
                    for tid, tdata in teams.items():
                        if str(tid) == str(self.club_id):
                            our_team = tdata
                        else:
                            opp_team = tdata

                    if not our_team or not opp_team:
                        # Sometimes EA only returns one club in the dict for the opponent
                        # Try to infer from top-level fields
                        continue

                    sf = self._to_int(our_team.get("goals"), 0)
                    sa = self._to_int(opp_team.get("goals") or opp_team.get("goalsAgainst"), 0)
                    res = "W" if sf > sa else "L" if sf < sa else "D"
                    opp_name = str(opp_team.get("name") or "Unknown")

                    match = MatchResult(
                        match_id=match_id,
                        date=date,
                        opponent=opp_name,
                        score_for=sf,
                        score_against=sa,
                        result=res,
                    )
                    club.matches.append(match)
                except Exception as e:
                    print(f"⚠️ Match parse error: {e}")
                    continue

            print(f"✅ Parsed {len(club.matches)} matches from EA API")

        if club.players or club.matches:
            return club

        print("⚠️ No players or matches found in EA API response")
        return None

    async def close(self):
        """No-op: httpx client is created per-request."""
        pass
