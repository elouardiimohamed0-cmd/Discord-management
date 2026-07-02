"""Entry point for the Discord bot."""
from __future__ import annotations

import asyncio
import signal
import sys

from src.core.app import create_app
from src.core.logging import get_logger

logger = get_logger(__name__)


async def main() -> None:
    """Main async entry point."""
    app = create_app()
    bot = app.bot

    # Start health server for Fly.io
    try:
        from health_server import start_health_server
        asyncio.create_task(start_health_server(port=8000))
    except ImportError:
        logger.warning("[Main] Health server not available, skipping")

    # Handle graceful shutdown
    def shutdown_handler(signum, frame):
        logger.info("[Main] Shutdown signal received")
        asyncio.create_task(bot.close())

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        # Pre-warm browser in background
        asyncio.create_task(app.pct.prewarm())

        # Start the bot
        logger.info("[Main] Starting bot...")
        await bot.start(app.settings.discord_token)
    except KeyboardInterrupt:
        logger.info("[Main] Keyboard interrupt")
    finally:
        await app.pct.close()
        logger.info("[Main] Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
