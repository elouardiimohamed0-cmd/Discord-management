import os
import json
from dotenv import load_dotenv

load_dotenv()

class Config:
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    DISCORD_GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", 0))
    DISCORD_STATS_CHANNEL_ID = int(os.getenv("DISCORD_STATS_CHANNEL_ID", 0))
    DISCORD_ROAST_CHANNEL_ID = int(os.getenv("DISCORD_ROAST_CHANNEL_ID", 0))
    
    PCT_CLUB_URL = os.getenv("PCT_CLUB_URL", "https://proclubstracker.com/club/1427607?platform=common-gen5&div=6")
    PCT_PLATFORM = os.getenv("PCT_PLATFORM", "common-gen5")
    
    SCRAPE_INTERVAL = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "5"))
    HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
    STEALTH = os.getenv("PLAYWRIGHT_STEALTH", "true").lower() == "true"
    
    DEFAULT_PERSONALITY = os.getenv("DEFAULT_PERSONALITY", "casablanca")
    ROAST_FREQUENCY = float(os.getenv("ROAST_FREQUENCY", "0.95"))
    
    SQUAD_FILE = os.getenv("SQUAD_FILE", "squad.json")
    MATCH_DB = os.getenv("MATCH_DB", "matches.db")
    MEMORY_DB = os.getenv("MEMORY_DB", "memory.db")
    ASSETS_DIR = os.getenv("ASSETS_DIR", "assets")
    
    @classmethod
    def load_squad(cls):
        with open(cls.SQUAD_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Support both dict format (your current squad.json) and proper list format
        if isinstance(data, dict) and "players" not in data:
            players = []
            for key, player in data.items():
                player["_key"] = key
                players.append(player)
            return {"players": players}
        return data

def load_squad():
    return Config.load_squad()
