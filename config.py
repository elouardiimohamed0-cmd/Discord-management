"""Configuration - compatible with existing Config class."""
import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent
ASSETS_DIR = Path(os.getenv("ASSETS_DIR", "assets"))
SQUAD_FILE = Path(os.getenv("SQUAD_FILE", "squad.json"))
MATCH_DB = os.getenv("MATCH_DB", "matches.db")
MEMORY_DB = os.getenv("MEMORY_DB", "memory.db")

# Discord
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0"))
GENERAL_CHANNEL_ID = int(os.getenv("GENERAL_CHANNEL_ID", "0"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID", "0"))
MATCH_CHANNEL_ID = int(os.getenv("MATCH_CHANNEL_ID", "0"))

# External APIs
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ProClubsTracker
PCT_CLUB_URL = os.getenv("PCT_CLUB_URL", "https://proclubstracker.com/club/1427607?platform=common-gen5&div=6")
PCT_PLATFORM = os.getenv("PCT_PLATFORM", "common-gen5")
CLUB_ID = int(os.getenv("CLUB_ID", "1427607"))

# Bot behavior
ROAST_FREQUENCY = float(os.getenv("ROAST_FREQUENCY", "0.95"))
DEFAULT_PERSONALITY = os.getenv("DEFAULT_PERSONALITY", "casablanca")
SCRAPE_INTERVAL_MINUTES = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "5"))
PORT = int(os.getenv("PORT", "8000"))

# Card generation
CARD_WIDTH = 1440
CARD_HEIGHT = 2160

# Aura thresholds
AURA_S_TIER_MIN = 90
AURA_A_TIER_MIN = 80
AURA_B_TIER_MIN = 70
AURA_FRAUD_MAX = 50
AURA_GHOST_GAMES_THRESHOLD = 3

# Daily content
STAT_OF_DAY_ROAST_PROB = 0.80
STAT_OF_DAY_MVP_PROB = 0.20
DAILY_POST_HOUR = 20
DAILY_POST_MINUTE = 0

# Fonts
FONT_PRIMARY = "Arial Bold"
FONT_SECONDARY = "Arial"
FONT_ARABIC = "Arial"

# Darija dataset reference
DARIJA_DATASET_URL = "https://github.com/darija-open-dataset/dataset"
