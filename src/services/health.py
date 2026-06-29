from __future__ import annotations

import asyncio
from datetime import datetime

from aiohttp import web


async def health_handler(request: web.Request) -> web.Response:
    return web.json_response(
        {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "service": "proclubs_bot",
        }
    )


async def start_health_server(port: int = 8000) -> None:
    app = web.Application()
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
