from __future__ import annotations

import discord
from discord.ext import commands

from src.core.config import Settings
from src.core.logging import get_logger
from src.discord_layer.commands import register_commands
from src.services.match_service import MatchService
from src.squad.registry import SquadRegistry

logger = get_logger(__name__)


def build_bot(settings: Settings, squad: SquadRegistry, match_service: MatchService) -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix=settings.command_prefix, intents=intents, help_command=None)

    bot.settings = settings  # type: ignore[attr-defined]
    bot.squad = squad  # type: ignore[attr-defined]
    bot.matches = match_service  # type: ignore[attr-defined]

    @bot.event
    async def on_ready() -> None:
        logger.info("Logged in as %s", bot.user)
        if settings.discord_guild_id:
            guild = discord.Object(id=settings.discord_guild_id)
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            logger.info("Synced commands to guild %s", settings.discord_guild_id)
        else:
            await bot.tree.sync()
            logger.info("Synced global commands")

    register_commands(bot)
    return bot
