import os
import json
from dotenv import load_dotenv

load_dotenv()

def _env(key, default=""):
    val = os.getenv(key, default)
    if isinstance(val, str):
        val = val.strip().strip('"').strip("'")
    return val

class Config:
    DISCORD_TOKEN = _env("DISCORD_TOKEN")
    DISCORD_GUILD_ID = int(_env("DISCORD_GUILD_ID", "0") or "0")
    
    # Channel IDs (optional — bot replies in the same channel by default)
    GENERAL_CHANNEL_ID = int(_env("GENERAL_CHANNEL_ID", "0") or "0")
    MATCH_CHANNEL_ID = int(_env("MATCH_CHANNEL_ID", "0") or "0")
    LEADERBORD_CHANNEL_ID = int(_env("LEADERBORD_CHANNEL_ID", "0") or "0")
    DISCORD_STATS_CHANNEL_ID = int(_env("DISCORD_STATS_CHANNEL_ID", "0") or "0")
    DISCORD_ROAST_CHANNEL_ID = int(_env("DISCORD_ROAST_CHANNEL_ID", "0") or "0")
    
    # EA API / Club settings
    CLUB_ID = _env("CLUB_ID", "1427607")
    PCT_CLUB_URL = _env("PCT_CLUB_URL", "https://proclubstracker.com/club/1427607?platform=common-gen5&div=6")
    PCT_PLATFORM = _env("PCT_PLATFORM", "common-gen5")
    
    # Scraper
    SCRAPE_INTERVAL = int(_env("SCRAPE_INTERVAL_MINUTES", "5") or "5")
    
    # Bot Personality
    DEFAULT_PERSONALITY = _env("DEFAULT_PERSONALITY", "casablanca")
    ROAST_FREQUENCY = float(_env("ROAST_FREQUENCY", "0.95") or "0.95")
    
    # External APIs
    GROQ_API_KEY = _env("GROQ_API_KEY", "")
    
    # Paths
    SQUAD_FILE = _env("SQUAD_FILE", "squad.json")
    MATCH_DB = _env("MATCH_DB", "matches.db")
    MEMORY_DB = _env("MEMORY_DB", "memory.db")
    ASSETS_DIR = _env("ASSETS_DIR", "assets")
    PORT = int(_env("PORT", "8000") or "8000")

    @classmethod
    def load_squad(cls):
        with open(cls.SQUAD_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "players" not in data:
            players = []
            for key, player in data.items():
                player["_key"] = key
                players.append(player)
            return {"players": players}
        return data

def load_squad():
    return Config.load_squad()
