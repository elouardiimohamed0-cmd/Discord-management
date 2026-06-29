from __future__ import annotations

import asyncio

from src.core.app import create_app
from src.core.logging import configure_logging, get_logger
from src.services.health import start_health_server

logger = get_logger(__name__)


async def main() -> None:
    app = create_app()
    configure_logging(app.settings.log_level)

    # Start health server for Render
    health_task = asyncio.create_task(start_health_server(port=8000))

    # Start bot
    logger.info("Starting bot...")
    async with app.bot:
        await app.bot.start(app.settings.discord_token)


if __name__ == "__main__":
    asyncio.run(main())
