from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    log_level: str
    timezone: str

    discord_token: str
    discord_guild_id: Optional[int]
    command_prefix: str

    general_channel_id: Optional[int]
    match_channel_id: Optional[int]
    leaderboard_channel_id: Optional[int]
    daily_channel_id: Optional[int]

    club_id: str
    pct_platform: str
    pct_club_url: str
    scrape_interval_minutes: int

    squad_file: Path
    assets_dir: Path
    templates_dir: Path
    cache_dir: Path
    database_path: Path


def _int_or_none(value: str | None) -> Optional[int]:
    if value is None or value == "" or value == "0":
        return None
    return int(value)


def load_settings() -> Settings:
    load_dotenv()
    club_id = os.getenv("CLUB_ID", "1427607")
    platform = os.getenv("PCT_PLATFORM", "common-gen5")
    default_pct_url = f"https://proclubstracker.com/club/{club_id}?platform={platform}&div=6"

    return Settings(
        app_name=os.getenv("APP_NAME", "Rachad Pro Clubs Bot"),
        environment=os.getenv("ENVIRONMENT", "development"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        timezone=os.getenv("TIMEZONE", "Europe/Paris"),
        discord_token=os.getenv("DISCORD_TOKEN", ""),
        discord_guild_id=_int_or_none(os.getenv("DISCORD_GUILD_ID")),
        command_prefix=os.getenv("COMMAND_PREFIX", "!"),
        general_channel_id=_int_or_none(os.getenv("GENERAL_CHANNEL_ID")),
        match_channel_id=_int_or_none(os.getenv("MATCH_CHANNEL_ID")),
        leaderboard_channel_id=_int_or_none(
            os.getenv("LEADERBOARD_CHANNEL_ID") or os.getenv("LEADERBORD_CHANNEL_ID")
        ),
        daily_channel_id=_int_or_none(os.getenv("DAILY_CHANNEL_ID")),
        club_id=club_id,
        pct_platform=platform,
        pct_club_url=os.getenv("PCT_CLUB_URL", default_pct_url),
        scrape_interval_minutes=int(os.getenv("SCRAPE_INTERVAL_MINUTES", "10")),
        squad_file=Path(os.getenv("SQUAD_FILE", "squad.json")),
        assets_dir=Path(os.getenv("ASSETS_DIR", "assets")),
        templates_dir=Path(os.getenv("TEMPLATES_DIR", "assets/templates")),
        cache_dir=Path(os.getenv("CACHE_DIR", ".cache")),
        database_path=Path(os.getenv("DATABASE_PATH", "data/proclubs.db")),
    )
