import os
import json
from dotenv import load_dotenv

load_dotenv()

class Config:
    DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
    DISCORD_GUILD_ID = int(os.environ.get("DISCORD_GUILD_ID", "0"))
    GENERAL_CHANNEL_ID = int(os.environ.get("GENERAL_CHANNEL_ID", "0"))
    MATCH_CHANNEL_ID = int(os.environ.get("MATCH_CHANNEL_ID", "0"))
    LEADERBORD_CHANNEL_ID = int(os.environ.get("LEADERBORD_CHANNEL_ID", "0"))
    DAILY_CHANNEL_ID = int(os.environ.get("DAILY_CHANNEL_ID", "0"))
    CLUB_ID = os.environ.get("CLUB_ID", "1427607")
    PCT_CLUB_URL = os.environ.get("PCT_CLUB_URL", "https://proclubstracker.com/club/1427607?platform=common-gen5&div=6")
    PCT_PLATFORM = os.environ.get("PCT_PLATFORM", "common-gen5")
    SCRAPE_INTERVAL_MINUTES = int(os.environ.get("SCRAPE_INTERVAL_MINUTES", "10"))
    DEFAULT_PERSONALITY = os.environ.get("DEFAULT_PERSONALITY", "casablanca")
    ROAST_FREQUENCY = float(os.environ.get("ROAST_FREQUENCY", "0.95"))
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    SQUAD_FILE = os.environ.get("SQUAD_FILE", "squad.json")
    MATCH_DB = os.environ.get("MATCH_DB", "/tmp/matches.db")
    MEMORY_DB = os.environ.get("MEMORY_DB", "/tmp/memory.db")
    ASSETS_DIR = os.environ.get("ASSETS_DIR", "assets")
    PORT = int(os.environ.get("PORT", "8000"))
    # NEW: PostgreSQL support (Render auto-sets DATABASE_URL if addon enabled)
    DATABASE_URL = os.environ.get("DATABASE_URL", "")
    SQLITE_PATH = os.environ.get("SQLITE_PATH", "/tmp/rachad_data.db")


def load_squad():
    path = Config.SQUAD_FILE
    if not os.path.exists(path):
        return {"players": []}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        return {"players": data}
    return {"players": []}
