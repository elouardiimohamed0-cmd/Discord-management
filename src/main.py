from__future__ import annotations
import asyncio
import os
from src.core.app import create_app
from src.core.logging import configure_logging, get_logger
from src.services.health import start_health_server
logger = get_logger(__name__)
async def async_main() -> None:
        app = create_app()
        configure_logging(app.settings.log_level)
        port = int(os.getenv("PORT", "8000"))
        start_health_server(port)
        logger.info("Starting %s", app.settings.app_name)
        await app.bot.start(app.settings.discord_token)
def main() -> None:
        asyncio.run(async_main())
if __name__ == "__main__":
        main()
