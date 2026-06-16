"""config.py — bridges environment variables to bot constants."""
import os
from pathlib import Path

# Discord
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
DISCORD_GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0"))
GENERAL_CHANNEL_ID = int(os.getenv("GENERAL_CHANNEL_ID", "0"))

# Data
ASSETS_DIR = Path(os.getenv("ASSETS_DIR", "assets"))
MATCH_DB = os.getenv("MATCH_DB", "matches.db")
SQUAD_FILE = ASSETS_DIR / os.getenv("SQUAD_FILE", "squad.json")

# Daily post time (9:00 AM default)
DAILY_POST_HOUR = int(os.getenv("DAILY_POST_HOUR", "9"))
DAILY_POST_MINUTE = int(os.getenv("DAILY_POST_MINUTE", "0"))

# Roast intensity
ROAST_INTENSITY = float(os.getenv("ROAST_INTENSITY", "0.99"))

# Club
CLUB_ID = os.getenv("CLUB_ID", "1427607")
