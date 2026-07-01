from __future__ import annotations

import asyncio
import signal
import sys
import traceback

from src.services.health import start_health_server


async def _main() -> None:
    # 1. Start health server immediately so Fly.io smoke checks pass
    health_task = asyncio.create_task(start_health_server(port=8000))

    # 2. Now import and initialize the app (this may take time)
    try:
        from src.core.app import create_app
        from src.core.logging import configure_logging, get_logger

        app = create_app()
        configure_logging(app.settings.log_level)
        logger = get_logger(__name__)
    except Exception as e:
        print(f"FATAL: Failed to initialize app: {e}", file=sys.stderr)
        traceback.print_exc()
        await health_task
        return

    logger.info("App initialized, starting bot...")

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
            pass

    bot_task = asyncio.create_task(app.bot.start(app.settings.discord_token))

    done, pending = await asyncio.wait(
        [bot_task, asyncio.create_task(shutdown_event.wait())],
        return_when=asyncio.FIRST_COMPLETED,
    )

    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    try:
        await app.bot.close()
    except Exception as e:
        logger.debug("Bot close error: %s", e)

    try:
        await app.pct.close()
    except Exception as e:
        logger.debug("Browser close error: %s", e)

    health_task.cancel()
    try:
        await health_task
    except asyncio.CancelledError:
        pass

    logger.info("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(_main())
