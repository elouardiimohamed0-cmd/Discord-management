from __future__ import annotations

import asyncio
import signal

from src.core.app import create_app
from src.core.logging import configure_logging, get_logger
from src.services.health import start_health_server

logger = get_logger(__name__)


async def main() -> None:
    app = create_app()
    configure_logging(app.settings.log_level)

    health_task = asyncio.create_task(start_health_server(port=8000))

    # Graceful shutdown handler
    shutdown_event = asyncio.Event()

    def _signal_handler(sig):
        logger.info("Received signal %s, shutting down...", sig)
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig: _signal_handler(s))
        except NotImplementedError:
            pass  # Windows doesn't support add_signal_handler

    logger.info("Starting bot...")
    bot_task = asyncio.create_task(app.bot.start(app.settings.discord_token))

    # Wait for either bot to finish or shutdown signal
    done, pending = await asyncio.wait(
        [bot_task, asyncio.create_task(shutdown_event.wait())],
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Cancel remaining tasks
    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # Close bot cleanly
    try:
        await app.bot.close()
    except Exception as e:
        logger.debug("Bot close error: %s", e)

    # Close browser
    try:
        await app.pct.close()
    except Exception as e:
        logger.debug("Browser close error: %s", e)

    # Cancel health server
    health_task.cancel()
    try:
        await health_task
    except asyncio.CancelledError:
        pass

    logger.info("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
