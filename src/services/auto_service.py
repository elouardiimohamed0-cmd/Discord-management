from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord.ext import tasks

from src.core.config import Settings
from src.core.logging import get_logger
from src.data.repositories import ClubRepository
from src.domain.models import Match
from src.engine.card_engine import CardEngine
from src.engine.roast_engine import RoastEngine
from src.engine.video_engine import VideoEngine
from src.squad.registry import SquadRegistry

logger = get_logger(__name__)


class AutoContentService:
    def __init__(
        self,
        settings: Settings,
        repository: ClubRepository,
        squad: SquadRegistry,
        roast: RoastEngine,
        cards: CardEngine,
        video: VideoEngine,
    ):
        self.settings = settings
        self.repo = repository
        self.squad = squad
        self.roast = roast
        self.cards = cards
        self.video = video
        self._bot: Optional[discord.Client] = None
        self._last_match_id: Optional[str] = None

    def attach_bot(self, bot: discord.Client) -> None:
        self._bot = bot

    async def start(self) -> None:
        if self.settings.match_channel_id:
            self.check_matches.start()
        if self.settings.daily_channel_id:
            self.daily_content.start()
        logger.info("Auto content services started")

    def _get_channel(self, channel_id: Optional[int]) -> Optional[discord.TextChannel]:
        if not self._bot or not channel_id:
            return None
        channel = self._bot.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        return None

    @tasks.loop(minutes=5.0)
    async def check_matches(self) -> None:
        try:
            latest = self.repo.latest_match()
            if not latest or latest.match_id == self._last_match_id:
                return
            self._last_match_id = latest.match_id
            channel = self._get_channel(self.settings.match_channel_id)
            if not channel:
                return

            # Auto post match report
            embed = await self._build_match_embed(latest)
            await channel.send(embed=embed)

            # MVP card
            if latest.mvp:
                mvp = latest.mvp
                identity = self.squad.find_by_ea_id(mvp.ea_id)
                if identity and self.cards and self.roast:
                    try:
                        card_path = self.cards.generate_mvp_card(mvp, identity)
                        roast_text = self.roast.mvp_roast(mvp, identity)
                        await channel.send(content=roast_text, file=discord.File(card_path))
                    except Exception as e:
                        logger.error("Auto MVP post failed: %s", e)

            # Fraud of match
            if latest.fraud:
                fraud = latest.fraud
                identity = self.squad.find_by_ea_id(fraud.ea_id)
                if identity and self.cards and self.roast:
                    try:
                        card_path = self.cards.generate_fraud_card(fraud, identity)
                        roast_text = self.roast.fraud_roast(fraud, identity)
                        await channel.send(content=roast_text, file=discord.File(card_path))
                    except Exception as e:
                        logger.error("Auto fraud post failed: %s", e)

        except Exception as e:
            logger.error("Auto match check failed: %s", e)

    @tasks.loop(hours=24.0)
    async def daily_content(self) -> None:
        try:
            channel = self._get_channel(self.settings.daily_channel_id)
            if not channel:
                return

            # Weekly fraud
            await self._post_weekly_fraud(channel)
            # Weekly ghost
            await self._post_weekly_ghost(channel)
            # Weekly MVP
            await self._post_weekly_mvp(channel)

        except Exception as e:
            logger.error("Daily content failed: %s", e)

    async def _build_match_embed(self, match: Match) -> discord.Embed:
        embed = discord.Embed(
            title=f"{'✅' if match.result == 'W' else '❌' if match.result == 'L' else '➖'} {match.score_for}-{match.score_against} vs {match.opponent}",
            timestamp=match.date,
            color=0x00FF00 if match.result == "W" else 0xFF0000 if match.result == "L" else 0xFFFF00,
        )
        if match.mvp:
            mvp_id = match.mvp.ea_id
            identity = self.squad.find_by_ea_id(mvp_id)
            name = identity.nickname if identity else match.mvp.display_name
            embed.add_field(name="MVP", value=f"{name} (Rating: {match.mvp.rating})", inline=False)
        return embed

    async def _post_weekly_fraud(self, channel: discord.TextChannel) -> None:
        try:
            since = (datetime.now() - timedelta(days=7)).isoformat()
            with self.repo.db.connect() as conn:
                rows = conn.execute(
                    """SELECT ea_id, AVG(rating) as avg_rating, SUM(possession_losses) as total_losses
                    FROM player_match_stats
                    WHERE created_at > ?
                    GROUP BY ea_id
                    ORDER BY avg_rating ASC, total_losses DESC
                    LIMIT 1""",
                    (since,),
                ).fetchall()
            if not rows:
                return
            row = rows[0]
            identity = self.squad.find_by_ea_id(row["ea_id"])
            if identity:
                text = f"🚨 **Fraud of the Week**: {identity.nickname}\nAvg Rating: {row['avg_rating']:.1f} | Possession Losses: {row['total_losses']}"
                await channel.send(text)
        except Exception as e:
            logger.error("Weekly fraud post failed: %s", e)

    async def _post_weekly_ghost(self, channel: discord.TextChannel) -> None:
        try:
            since = (datetime.now() - timedelta(days=7)).isoformat()
            with self.repo.db.connect() as conn:
                rows = conn.execute(
                    """SELECT ea_id, AVG(minutes) as avg_minutes, COUNT(*) as matches
                    FROM player_match_stats
                    WHERE created_at > ?
                    GROUP BY ea_id
                    ORDER BY avg_minutes ASC
                    LIMIT 1""",
                    (since,),
                ).fetchall()
            if not rows:
                return
            row = rows[0]
            identity = self.squad.find_by_ea_id(row["ea_id"])
            if identity:
                text = f"👻 **Ghost of the Week**: {identity.nickname}\nAvg Minutes: {row['avg_minutes']:.0f} over {row['matches']} matches"
                await channel.send(text)
        except Exception as e:
            logger.error("Weekly ghost post failed: %s", e)

    async def _post_weekly_mvp(self, channel: discord.TextChannel) -> None:
        try:
            since = (datetime.now() - timedelta(days=7)).isoformat()
            with self.repo.db.connect() as conn:
                rows = conn.execute(
                    """SELECT ea_id, AVG(rating) as avg_rating, SUM(goals) as total_goals, SUM(assists) as total_assists
                    FROM player_match_stats
                    WHERE created_at > ?
                    GROUP BY ea_id
                    ORDER BY avg_rating DESC, total_goals DESC
                    LIMIT 1""",
                    (since,),
                ).fetchall()
            if not rows:
                return
            row = rows[0]
            identity = self.squad.find_by_ea_id(row["ea_id"])
            if identity:
                text = f"🔥 **MVP of the Week**: {identity.nickname}\nAvg Rating: {row['avg_rating']:.1f} | G+A: {row['total_goals']}+{row['total_assists']}"
                await channel.send(text)
        except Exception as e:
            logger.error("Weekly MVP post failed: %s", e)
