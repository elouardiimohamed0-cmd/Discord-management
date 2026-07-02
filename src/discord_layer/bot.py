"""Discord bot factory with all services wired."""
from __future__ import annotations

import asyncio
import os
from typing import Optional

import discord
from discord.ext import commands, tasks

from src.core.config import Settings
from src.core.logging import get_logger
from src.data.repositories import ClubRepository
from src.discord_layer.commands import register_commands
from src.engine.card_engine import CardEngine
from src.engine.roast_engine import RoastEngine
from src.engine.video_engine import VideoEngine
from src.services.auto_service import AutoContentService
from src.services.match_service import MatchService
from src.services.records_service import RecordsService
from src.squad.registry import SquadRegistry

logger = get_logger(__name__)


class ClubBot(commands.Bot):
    """Main Discord bot with all services attached."""

    def __init__(self, settings: Settings, **kwargs):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix="!",
            intents=intents,
            **kwargs,
        )
        self.settings = settings
        self.matches: Optional[MatchService] = None
        self.roast: Optional[RoastEngine] = None
        self.cards: Optional[CardEngine] = None
        self.video: Optional[VideoEngine] = None
        self.records: Optional[RecordsService] = None
        self.auto: Optional[AutoContentService] = None
        self.squad: Optional[SquadRegistry] = None

    async def setup_hook(self) -> None:
        """Called before the bot logs in."""
        logger.info("[Bot] Setup hook running...")

        # Register all slash commands
        register_commands(self)

        # Sync commands with Discord
        if self.settings.guild_id:
            guild = discord.Object(id=self.settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info("[Bot] Synced %d commands to guild %s", len(synced), self.settings.guild_id)
        else:
            synced = await self.tree.sync()
            logger.info("[Bot] Synced %d global commands", len(synced))

    async def on_ready(self) -> None:
        """Called when the bot is ready."""
        logger.info("[Bot] Logged in as %s (ID: %s)", self.user.name, self.user.id)
        logger.info("[Bot] Guild ID: %s", self.settings.guild_id)

        # Start background tasks
        if self.auto:
            self.auto_post_loop.start()
            logger.info("[Bot] Auto-post loop started")

    @tasks.loop(hours=1)
    async def auto_post_loop(self) -> None:
        """Background task for auto-posting content."""
        if not self.auto:
            return
        try:
            await self.auto.run_cycle()
        except Exception as e:
            logger.error("[Bot] Auto-post loop error: %s", e)

    @auto_post_loop.before_loop
    async def before_auto_post(self) -> None:
        await self.wait_until_ready()

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Handle command errors."""
        logger.error("[Bot] Command error: %s", error)

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ) -> None:
        """Handle slash command errors."""
        logger.error("[Bot] App command error: %s", error)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    f"❌ Command error: {str(error)[:500]}", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ Command error: {str(error)[:500]}", ephemeral=True
                )
        except Exception:
            pass


def build_bot(
    settings: Settings,
    squad: SquadRegistry,
    match_service: MatchService,
    roast: RoastEngine,
    cards: CardEngine,
    video: VideoEngine,
    records: RecordsService,
    auto: AutoContentService,
) -> ClubBot:
    """Build and configure the Discord bot with all services."""
    bot = ClubBot(settings=settings)

    # Wire all services
    bot.squad = squad
    bot.matches = match_service
    bot.roast = roast
    bot.cards = cards
    bot.video = video
    bot.records = records
    bot.auto = auto

    return bot
