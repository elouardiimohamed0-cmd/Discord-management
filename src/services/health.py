"""Lightweight HTTP health server to keep Fly.io happy."""
from __future__ import annotations

from aiohttp import web

from src.core.logging import get_logger

logger = get_logger(__name__)


async def health_handler(request: web.Request) -> web.Response:
    """Simple health check endpoint."""
    return web.json_response({"status": "ok", "service": "discord-bot"})


async def start_health_server(port: int = 8000) -> None:
    """Start a lightweight HTTP server for Fly health checks."""
    app = web.Application()
    app.router.add_get("/health", health_handler)
    app.router.add_get("/", health_handler)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info("[Health] Server running on 0.0.0.0:%d", port)
