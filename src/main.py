from __future__ import annotations

import asyncio

from src.core.app import create_app
from src.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


async def async_main() -> None:
    app = create_app()
    configure_logging(app.settings.log_level)
    logger.info("Starting %s", app.settings.app_name)
    await app.bot.start(app.settings.discord_token)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
