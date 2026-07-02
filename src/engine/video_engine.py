"""Video engine for generating highlight videos."""
from __future__ import annotations

from src.core.config import Settings
from src.core.logging import get_logger
from src.squad.registry import SquadRegistry

logger = get_logger(__name__)


class VideoEngine:
    """Generate highlight videos."""

    def __init__(self, settings: Settings, squad: SquadRegistry):
        self.settings = settings
        self.squad = squad
