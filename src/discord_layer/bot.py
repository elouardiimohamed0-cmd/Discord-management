from __future__ import annotations

import discord
from discord.ext import commands

from src.core.config import Settings
from src.core.logging import get_logger
from src.discord_layer.commands import register_commands
from src.engine.card_engine import CardEngine
from src.engine.roast_engine import RoastEngine
from src.engine.video_engine import VideoEngine
from src.services.auto_service import AutoContentService
from src.services.match_service import MatchService
from src.squad.registry import SquadRegistry

logger = get_logger(__name__)


def build_bot(
    settings: Settings,
    squad: SquadRegistry,
    match_service: MatchService,
    roast: RoastEngine,
    cards: CardEngine,
    video: VideoEngine,
    auto: AutoContentService,
) -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix=settings.command_prefix, intents=intents, help_command=None)

    bot.settings = settings  # type: ignore[attr-defined]
    bot.squad = squad  # type: ignore[attr-defined]
    bot.matches = match_service  # type: ignore[attr-defined]
    bot.roast = roast  # type: ignore[attr-defined]
    bot.cards = cards  # type: ignore[attr-defined]
    bot.video = video  # type: ignore[attr-defined]
    bot.auto = auto  # type: ignore[attr-defined]

    @bot.event
    async def on_ready() -> None:
        logger.info("Logged in as %s", bot.user)
        auto.attach_bot(bot)
        await auto.start()

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
