"""Application configuration from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    discord_token: str
    guild_id: int | None
    log_level: str = "INFO"
    database_path: Path = Path("data/club.db")
    squad_file: Path = Path("data/squad.json")
    cache_dir: Path = Path("data/cache")
    pct_club_url: str = "https://proclubstracker.com/api/clubs/1427607?platform=common-gen5"
    auto_channel_id: int | None = None
    roast_channel_id: int | None = None
    video_channel_id: int | None = None
    awards_channel_id: int | None = None
    roast_cooldown_hours: int = 6
    auto_post_interval_hours: int = 1
    awards_interval_hours: int = 24
    browser_headless: bool = True
    browser_retries: int = 3


def load_settings() -> Settings:
    """Load settings from environment variables."""
    token = os.environ.get("DISCORD_TOKEN", "")
    if not token:
        raise ValueError("DISCORD_TOKEN environment variable is required")

    guild_id = os.environ.get("GUILD_ID")
    guild_id = int(guild_id) if guild_id else None

    auto_channel = os.environ.get("AUTO_CHANNEL_ID")
    roast_channel = os.environ.get("ROAST_CHANNEL_ID")
    video_channel = os.environ.get("VIDEO_CHANNEL_ID")
    awards_channel = os.environ.get("AWARDS_CHANNEL_ID")

    return Settings(
        discord_token=token,
        guild_id=guild_id,
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        database_path=Path(os.environ.get("DATABASE_PATH", "data/club.db")),
        squad_file=Path(os.environ.get("SQUAD_FILE", "data/squad.json")),
        cache_dir=Path(os.environ.get("CACHE_DIR", "data/cache")),
        pct_club_url=os.environ.get(
            "PCT_CLUB_URL",
            "https://proclubstracker.com/api/clubs/1427607?platform=common-gen5",
        ),
        auto_channel_id=int(auto_channel) if auto_channel else None,
        roast_channel_id=int(roast_channel) if roast_channel else None,
        video_channel_id=int(video_channel) if video_channel else None,
        awards_channel_id=int(awards_channel) if awards_channel else None,
        roast_cooldown_hours=int(os.environ.get("ROAST_COOLDOWN_HOURS", "6")),
        auto_post_interval_hours=int(os.environ.get("AUTO_POST_INTERVAL_HOURS", "1")),
        awards_interval_hours=int(os.environ.get("AWARDS_INTERVAL_HOURS", "24")),
        browser_headless=os.environ.get("BROWSER_HEADLESS", "true").lower() == "true",
        browser_retries=int(os.environ.get("BROWSER_RETRIES", "3")),
    )
