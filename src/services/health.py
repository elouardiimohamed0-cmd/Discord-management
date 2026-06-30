from __future__ import annotations

import asyncio
from datetime import datetime

from aiohttp import web

_start_time = datetime.now()


async def health_handler(request: web.Request) -> web.Response:
    uptime = (datetime.now() - _start_time).total_seconds()
    return web.json_response(
        {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "service": "proclubs_bot",
            "uptime_seconds": uptime,
        }
    )


async def start_health_server(port: int = 8000) -> None:
    """Start a minimal health server immediately. Never crashes."""
    app = web.Application()
    app.router.add_get("/health", health_handler)
    app.router.add_get("/", health_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    # Keep the server alive forever
    while True:
        await asyncio.sleep(3600)
