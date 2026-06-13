"""
Rachad L3ERGONI Bot - DIAGNOSTIC VERSION
Logs every step to find where it breaks
"""

import os
import sys
import asyncio
import traceback

print("[STARTUP] Step 1: Imports starting...")

try:
    import discord
    print("[STARTUP] ✅ discord.py imported")
except Exception as e:
    print(f"[STARTUP] ❌ discord.py import failed: {e}")
    sys.exit(1)

try:
    from discord.ext import commands
    print("[STARTUP] ✅ commands imported")
except Exception as e:
    print(f"[STARTUP] ❌ commands import failed: {e}")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
    print("[STARTUP] ✅ dotenv loaded")
except Exception as e:
    print(f"[STARTUP] ❌ dotenv failed: {e}")

print("[STARTUP] Step 2: Loading env vars...")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
MATCH_CHANNEL_ID = int(os.getenv("MATCH_CHANNEL_ID", "0"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID", "0"))
GENERAL_CHANNEL_ID = int(os.getenv("GENERAL_CHANNEL_ID", "0"))
CLUB_ID = os.getenv("CLUB_ID", "1427607")
PLATFORM = os.getenv("PLATFORM", "common-gen5")
PORT = int(os.getenv("PORT", "10000"))

print(f"[STARTUP] ✅ Env vars loaded: CLUB_ID={CLUB_ID}, PLATFORM={PLATFORM}")

print("[STARTUP] Step 3: Loading custom modules...")

try:
    from darija_engine import get_engine, PERSONALITIES
    print("[STARTUP] ✅ darija_engine loaded")
except Exception as e:
    print(f"[STARTUP] ❌ darija_engine failed: {e}")
    traceback.print_exc()
    darija = None
    PERSONALITIES = {}

try:
    from stats_engine import get_stats_engine
    print("[STARTUP] ✅ stats_engine loaded")
except Exception as e:
    print(f"[STARTUP] ❌ stats_engine failed: {e}")
    traceback.print_exc()
    stats_engine = None

try:
    from image_gen import get_image_generator
    print("[STARTUP] ✅ image_gen loaded")
except Exception as e:
    print(f"[STARTUP] ❌ image_gen failed: {e}")
    traceback.print_exc()
    image_gen = None

try:
    from scraper import get_scraper
    print("[STARTUP] ✅ scraper loaded")
except Exception as e:
    print(f"[STARTUP] ❌ scraper failed: {e}")
    traceback.print_exc()
    scraper = None

print("[STARTUP] Step 4: Initializing modules...")

try:
    if darija is not None:
        darija = get_engine("squad.json")
        print("[STARTUP] ✅ darija initialized")
except Exception as e:
    print(f"[STARTUP] ❌ darija init failed: {e}")
    darija = None

try:
    if stats_engine is not None:
        stats_engine = get_stats_engine("match_data.json")
        print("[STARTUP] ✅ stats_engine initialized")
except Exception as e:
    print(f"[STARTUP] ❌ stats_engine init failed: {e}")
    stats_engine = None

try:
    if image_gen is not None:
        image_gen = get_image_generator("assets")
        print("[STARTUP] ✅ image_gen initialized")
except Exception as e:
    print(f"[STARTUP] ❌ image_gen init failed: {e}")
    image_gen = None

try:
    if scraper is not None:
        scraper = get_scraper(CLUB_ID, PLATFORM)
        print("[STARTUP] ✅ scraper initialized")
except Exception as e:
    print(f"[STARTUP] ❌ scraper init failed: {e}")
    traceback.print_exc()
    scraper = None

print("[STARTUP] Step 5: Setting up Discord bot...")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

print("[STARTUP] ✅ Intents configured")

class L3ERGONIBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        print("[STARTUP] ✅ Bot class created")
        
    async def setup_hook(self):
        print("[SETUP] setup_hook called")
        try:
            if darija is not None:
                self.darija = darija
            if stats_engine is not None:
                self.stats = stats_engine
            if image_gen is not None:
                self.images = image_gen
            if scraper is not None:
                self.scraper = scraper
            
            self.squad = self._load_squad()
            self.session_active = False
            print("[SETUP] ✅ Bot attributes set")
        except Exception as e:
            print(f"[SETUP] ❌ Error: {e}")
            traceback.print_exc()

    def _load_squad(self) -> dict:
        try:
            import json
            with open("squad.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[SQUAD] ❌ Load failed: {e}")
            return {}

    async def on_ready(self):
        print(f"[READY] ✅ Bot logged in as {self.user}")
        print(f"[READY] ✅ Connected to {len(self.guilds)} guilds")
        print(f"[READY] ✅ Commands: {len(self.commands)} registered")
        for cmd in self.commands:
            print(f"  - {cmd.name}")
        
    async def on_command_error(self, ctx, error):
        print(f"[ERROR] Command error: {error}")
        if isinstance(error, commands.CommandNotFound):
            print(f"[ERROR] Command not found: {ctx.message.content}")
        else:
            traceback.print_exc()

    async def on_message(self, message):
        print(f"[MESSAGE] Received: '{message.content}' from {message.author}")
        if message.author.bot:
            return
        await self.process_commands(message)

bot = L3ERGONIBot()
print("[STARTUP] ✅ Bot instance created")

bot.remove_command('help')
print("[STARTUP] ✅ Default help removed")

@bot.command(name="ping")
async def ping_cmd(ctx):
    print(f"[COMMAND] !ping from {ctx.author}")
    await ctx.send("🏓 Pong!")

@bot.command(name="test")
async def test_cmd(ctx):
    print(f"[COMMAND] !test from {ctx.author}")
    await ctx.send("✅ Bot is working!")

@bot.command(name="sync")
async def sync_cmd(ctx):
    print(f"[COMMAND] !sync from {ctx.author}")
    if scraper is None:
        await ctx.send("❌ Scraper not available")
        return
    await ctx.send("Syncing...")
    try:
        added = await scraper.sync_to_stats_engine(bot.stats, count=10)
        await ctx.send(f"Synced {added} matches")
    except Exception as e:
        print(f"[SYNC] Error: {e}")
        traceback.print_exc()
        await ctx.send(f"Error: {e}")

@bot.command(name="help")
async def help_cmd(ctx):
    print(f"[COMMAND] !help from {ctx.author}")
    await ctx.send("Commands: !ping, !test, !sync, !help")

print(f"[STARTUP] ✅ Commands registered: {len(bot.commands)}")
for cmd in bot.commands:
    print(f"  - {cmd.name}")

# Health server
async def start_health_server():
    from aiohttp import web
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Bot OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"[HEALTH] Server on port {PORT}")

async def main():
    print("[STARTUP] Step 6: Starting services...")
    await start_health_server()
    print("[STARTUP] ✅ Health server started")
    await asyncio.sleep(1)
    print("[STARTUP] Step 7: Starting bot...")
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    print("[STARTUP] Starting main loop...")
    asyncio.run(main())
