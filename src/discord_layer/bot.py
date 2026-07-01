from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from src.core.config import Settings
from src.core.logging import get_logger
from src.discord_layer.commands import register_commands
from src.engine.card_engine import CardEngine
from src.engine.roast_engine import RoastEngine
from src.engine.video_engine import VideoEngine
from src.services.auto_service import AutoContentService
from src.services.match_service import MatchService
from src.services.records_service import RecordsService
from src.squad.registry import SquadRegistry

logger = get_logger(__name__)


def build_bot(
    settings: Settings,
    squad: SquadRegistry,
    match_service: MatchService,
    roast: RoastEngine,
    cards: CardEngine,
    video: VideoEngine,
    records: RecordsService,
    auto: AutoContentService,
) -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix=settings.command_prefix, intents=intents, help_command=None)

    bot.settings = settings
    bot.squad = squad
    bot.matches = match_service
    bot.roast = roast
    bot.cards = cards
    bot.video = video
    bot.records = records
    bot.auto = auto

    @bot.event
    async def on_ready() -> None:
        logger.info("Logged in as %s", bot.user)
        auto.attach_bot(bot)
        await auto.start()

        # CRITICAL: Pre-warm browser in background so first /sync is fast
        # Without this, /sync blocks for 20-30s while Chromium launches
        asyncio.create_task(match_service.client.prewarm())

        if settings.discord_guild_id:
            guild = discord.Object(id=settings.discord_guild_id)
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            logger.info("Synced commands to guild %s", settings.discord_guild_id)
        else:
            await bot.tree.sync()
            logger.info("Synced global commands")

    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        """Global error handler for slash commands."""
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"\u23f3 Command on cooldown. Try again in {error.retry_after:.1f}s.",
                ephemeral=True
            )
        elif isinstance(error, app_commands.CommandInvokeError):
            cause = error.original
            logger.error("Command %s failed: %s", interaction.command.name if interaction.command else "unknown", cause, exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(f"\u274c Command failed: {str(cause)[:500]}", ephemeral=True)
            else:
                try:
                    await interaction.followup.send(f"\u274c Command failed: {str(cause)[:500]}")
                except Exception:
                    pass
        else:
            logger.error("Unhandled app command error: %s", error, exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message("\u274c An unexpected error occurred.", ephemeral=True)

    register_commands(bot)
    return bot
