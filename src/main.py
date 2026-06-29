from __future__ import annotations

import asyncio
import os

from src.core.app import create_app
from src.core.logging import configure_logging, get_logger
from src.services.health import start_health_server

logger = get_logger(__name__)
